"""Soul-ID character management endpoints.

Two-step UX:
  1. POST /api/characters/upload  — drop one photo; server uploads it to
     Higgsfield and returns the upload UUID. Repeat 5–20 times per
     character (the frontend collects the IDs).
  2. POST /api/characters  — name + soul_model + list of UUIDs.
     Server kicks off `higgsfield soul-id create` and immediately returns
     the character with status="training". A background task polls
     `soul-id get` until the status flips to ready/failed.

GET /api/characters lists everything in the local SQLite store.
DELETE /api/characters/{soul_id} removes the local record (the Soul itself
stays in Higgsfield's cloud).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from loguru import logger

from src.api.auth import get_current_user
from src.clients.higgsfield import HiggsfieldError, get_higgsfield_cli
from src.config import settings
from src.models import Character
from src.utils.characters_db import get_characters_db

router = APIRouter(
    prefix="/api/characters",
    tags=["characters"],
    dependencies=[Depends(get_current_user)],
)


# ----------------------------------------------------------------------
# tunables
# ----------------------------------------------------------------------

_MAX_PHOTO_BYTES = 15 * 1024 * 1024  # 15 MB per photo
_ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
_MIN_PHOTOS = 5
_MAX_PHOTOS = 20


# ----------------------------------------------------------------------
# upload helper — per-photo
# ----------------------------------------------------------------------


@router.post("/upload")
async def upload_character_photo(file: UploadFile = File(...)) -> dict[str, Any]:
    """Persist one photo locally + push it to Higgsfield. Returns its upload UUID."""
    mime = file.content_type or "application/octet-stream"
    if mime not in _ALLOWED_IMAGE_MIMES:
        raise HTTPException(
            status_code=400,
            detail=f"mime {mime!r} not allowed (jpg/png/webp only)",
        )
    raw = await file.read()
    if len(raw) > _MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"file too large ({len(raw)} bytes, max {_MAX_PHOTO_BYTES})",
        )

    photos_dir = settings.data_dir / "character_photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime, ".bin")
    safe_name = Path(file.filename or "photo").stem.replace("/", "_")[:40]
    # Local filename intentionally non-clobbering so a re-upload of the same
    # source filename doesn't overwrite the previous one mid-training.
    dest = photos_dir / f"{safe_name}-{abs(hash(raw)):x}{suffix}"
    dest.write_bytes(raw)

    cli = get_higgsfield_cli()
    try:
        uuid = await cli.upload(dest)
    except HiggsfieldError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "upload_id": uuid,
        "local_path": str(dest),
        "bytes": len(raw),
        "mime": mime,
    }


# ----------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------


@router.post("")
async def create_character(
    background: BackgroundTasks,
    body: dict[str, Any],
) -> dict[str, Any]:
    name = str(body.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if len(name) > 80:
        raise HTTPException(status_code=400, detail="name too long (max 80 chars)")

    soul_model = body.get("soul_model", "soul-2")
    if soul_model not in {"soul-2", "soul-cinematic"}:
        raise HTTPException(
            status_code=400,
            detail="soul_model must be 'soul-2' or 'soul-cinematic'",
        )

    image_uuids = body.get("image_uuids") or []
    if not isinstance(image_uuids, list) or not all(isinstance(x, str) for x in image_uuids):
        raise HTTPException(status_code=400, detail="image_uuids must be a list of strings")
    if not (_MIN_PHOTOS <= len(image_uuids) <= _MAX_PHOTOS):
        raise HTTPException(
            status_code=400,
            detail=f"need {_MIN_PHOTOS}–{_MAX_PHOTOS} images, got {len(image_uuids)}",
        )

    preview_path_raw = body.get("preview_path")
    preview_path: Path | None = None
    if preview_path_raw:
        candidate = Path(str(preview_path_raw)).resolve()
        photos_root = settings.data_dir.resolve() / "character_photos"
        if str(candidate).startswith(str(photos_root)) and candidate.exists():
            preview_path = candidate

    cli = get_higgsfield_cli()
    try:
        created = await cli.soul_id_create(
            name=name,
            image_uuids=image_uuids,
            soul_model=soul_model,
        )
    except HiggsfieldError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    soul_id = (
        created.get("id")
        or created.get("soul_id")
        or created.get("uuid")
    )
    if not soul_id:
        raise HTTPException(
            status_code=502,
            detail=f"higgsfield soul-id create returned no id: {created!r}",
        )

    character = Character(
        soul_id=str(soul_id),
        name=name,
        status="training",
        soul_model=soul_model,  # type: ignore[arg-type]
        image_uuids=image_uuids,
        preview_path=preview_path,
    )
    db = get_characters_db()
    db.upsert(character)
    logger.info(f"[characters] created soul_id={soul_id} name={name!r} — training")

    background.add_task(_wait_for_training, str(soul_id))
    return _character_payload(character)


@router.get("")
async def list_characters() -> dict[str, Any]:
    db = get_characters_db()
    return {"characters": [_character_payload(c) for c in db.list()]}


@router.get("/{soul_id}")
async def get_character(soul_id: str) -> dict[str, Any]:
    db = get_characters_db()
    c = db.get(soul_id)
    if c is None:
        raise HTTPException(status_code=404, detail="character not found")
    return _character_payload(c)


@router.delete("/{soul_id}")
async def delete_character(soul_id: str) -> dict[str, Any]:
    db = get_characters_db()
    ok = db.delete(soul_id)
    if not ok:
        raise HTTPException(status_code=404, detail="character not found")
    return {"deleted": soul_id}


@router.post("/{soul_id}/refresh")
async def refresh_character(soul_id: str) -> dict[str, Any]:
    """Manually poke the status (in case a background poll was lost on a restart)."""
    db = get_characters_db()
    c = db.get(soul_id)
    if c is None:
        raise HTTPException(status_code=404, detail="character not found")
    await _poll_once(soul_id)
    fresh = db.get(soul_id)
    return _character_payload(fresh) if fresh else {"deleted": soul_id}


# ----------------------------------------------------------------------
# background poller
# ----------------------------------------------------------------------


async def _wait_for_training(soul_id: str) -> None:
    """Block (in background) until Higgsfield reports the Soul training done.

    Uses `higgsfield soul-id wait <id>` which already polls server-side, so
    this is a single subprocess call that blocks ~3–5 min in the happy path.
    """
    cli = get_higgsfield_cli()
    db = get_characters_db()
    try:
        result = await cli.soul_id_wait(soul_id, timeout_seconds=20 * 60)
    except HiggsfieldError as exc:
        logger.exception(f"[characters] soul-id wait {soul_id} failed")
        db.mark_failed(soul_id, str(exc))
        return

    status = _extract_status(result)
    if status == "ready":
        db.mark_ready(soul_id)
        logger.info(f"[characters] soul_id={soul_id} READY")
    elif status == "failed":
        db.mark_failed(soul_id, _extract_error(result) or "training failed")
        logger.warning(f"[characters] soul_id={soul_id} FAILED")
    else:
        # Unknown terminal state — surface as failed so the UI doesn't hang
        # forever in "training".
        db.mark_failed(
            soul_id, f"unexpected terminal status: {status!r} (raw: {result!r})"
        )


async def _poll_once(soul_id: str) -> None:
    cli = get_higgsfield_cli()
    db = get_characters_db()
    try:
        result = await cli.soul_id_get(soul_id)
    except HiggsfieldError as exc:
        db.mark_failed(soul_id, str(exc))
        return
    status = _extract_status(result)
    if status == "ready":
        db.mark_ready(soul_id)
    elif status == "failed":
        db.mark_failed(soul_id, _extract_error(result) or "training failed")


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _extract_status(payload: dict[str, Any]) -> str:
    status = payload.get("status")
    if isinstance(status, str):
        return status.lower()
    return ""


def _extract_error(payload: dict[str, Any]) -> str | None:
    err = payload.get("error") or payload.get("error_message")
    return str(err) if err else None


def _character_payload(c: Character) -> dict[str, Any]:
    """JSON-serialisable payload for API responses (paths as strings)."""
    data = c.model_dump(mode="json")
    if c.preview_path is not None:
        data["preview_path"] = str(c.preview_path)
    return data


# Re-export the singleton getter so callers don't need a separate import.
__all__ = ["router", "get_characters_db"]


# Optional: run-on-import resume of pending trainings.
async def resume_pending_trainings() -> None:
    """Re-attach background pollers to any character left in 'training' after
    a server restart. Called from the FastAPI startup hook in `api/main.py`.
    """
    db = get_characters_db()
    pending = [c for c in db.list() if c.status == "training"]
    for c in pending:
        logger.info(f"[characters] resuming wait for soul_id={c.soul_id} ({c.name!r})")
        asyncio.create_task(_wait_for_training(c.soul_id))
