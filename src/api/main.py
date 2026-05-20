"""FastAPI app: /api/* routes (JWT-gated) + SPA static mount."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.auth import (
    LoginRequest,
    LoginResponse,
    create_token,
    get_current_user,
    verify_password,
)
from src.api.characters import resume_pending_trainings
from src.api.characters import router as characters_router
from src.clients.higgsfield import HiggsfieldCLI, HiggsfieldError, get_higgsfield_cli
from src.config import PROVIDER_COST_CREDITS, VideoProvider, settings
from src.models import (
    CreativeBrief,
    Reference,
    ReferenceKind,
    RunResult,
    RunStatus,
    ScriptOutput,
    Shot,
    ShotPlan,
)
from src.pipeline import Pipeline
from src.utils.characters_db import get_characters_db
from src.utils.youtube import (
    fetch_audio_track,
    fetch_transcript,
    fetch_voice_sample,
    is_youtube_url,
)

_VALID_PROVIDERS: set[str] = {"seedance", "kling", "veo", "cinematic_studio_v2"}
_MAX_TOPIC_LEN = 4000
# Run IDs accepted from the client (frontend pre-allocates one so it can
# upload references against it before posting /api/run/draft). Strict format
# check — keeps this from being a path-traversal vector when we build
# settings.output_dir / run_id below.
_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")

# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------

_RUN_STATE: dict[str, RunResult] = {}
_LOCK = asyncio.Lock()


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Reattach Soul-ID training pollers on startup so the UI doesn't see
    a `training` character get stuck forever after a server restart.
    """
    try:
        await resume_pending_trainings()
    except Exception:
        logger.exception("[startup] failed to resume character pollers")
    yield


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="ai-reels-factory", version="0.2.0", lifespan=_lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.output_dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _load_runs_from_disk() -> list[RunResult]:
    runs: list[RunResult] = []
    if not settings.output_dir.exists():
        return runs
    for run_dir in sorted(settings.output_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        result_file = run_dir / "result.json"
        if not result_file.exists():
            continue
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            runs.append(RunResult(**data))
        except Exception:
            logger.warning(f"could not load {result_file}")
    return runs


def _all_runs() -> list[RunResult]:
    merged: dict[str, RunResult] = {r.run_id: r for r in _load_runs_from_disk()}
    for run_id, r in _RUN_STATE.items():
        merged[run_id] = r
    return sorted(merged.values(), key=lambda r: r.created_at, reverse=True)


def _run_summary(r: RunResult) -> dict[str, Any]:
    provider = r.provider
    credits = PROVIDER_COST_CREDITS.get(provider) if provider else None  # type: ignore[arg-type]
    return {
        "run_id": r.run_id,
        "topic": r.topic,
        "status": r.status.value,
        "created_at": r.created_at.isoformat(),
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "error": r.error,
        "provider": provider,
        "current_step": r.current_step,
        "cost_credits": credits,
        "soul_id": r.soul_id,
        "has_video": r.final_video_path is not None
        and Path(r.final_video_path).exists(),
    }


def _run_detail(r: RunResult) -> dict[str, Any]:
    summary = _run_summary(r)
    summary["script"] = r.script.model_dump() if r.script else None
    summary["shot_plan"] = r.shot_plan.model_dump() if r.shot_plan else None
    summary["brief"] = r.brief.model_dump() if r.brief else None
    summary["caption"] = None
    caption_file = settings.output_dir / r.run_id / "caption.txt"
    if caption_file.exists():
        summary["caption"] = caption_file.read_text(encoding="utf-8")
    return summary


async def _execute_run(
    topic: str,
    run_id: str,
    provider: VideoProvider | None = None,
    burn_subtitles: bool = False,
    references: list[Reference] | None = None,
    pause_after: str | None = None,
    soul_id: str | None = None,
    voiceless: bool = False,
    use_keyframes: bool = False,
    brief: CreativeBrief | None = None,
) -> None:
    pipeline = Pipeline()
    try:
        result = await pipeline.run(
            topic=topic,
            run_id=run_id,
            provider=provider,
            burn_subtitles=burn_subtitles,
            references=references,
            pause_after=pause_after,
            soul_id=soul_id,
            voiceless=voiceless,
            use_keyframes=use_keyframes,
            brief=brief,
        )
    except Exception as exc:
        logger.exception("pipeline crashed")
        async with _LOCK:
            r = _RUN_STATE.get(run_id)
            if r:
                r.status = RunStatus.FAILED
                r.error = str(exc)
                r.finished_at = datetime.now(UTC)
        return
    async with _LOCK:
        _RUN_STATE[run_id] = result


async def _resume_run(run_id: str, edited_script: ScriptOutput) -> None:
    pipeline = Pipeline()
    try:
        result = await pipeline.resume(run_id=run_id, edited_script=edited_script)
    except Exception as exc:
        logger.exception("pipeline resume crashed")
        async with _LOCK:
            r = _RUN_STATE.get(run_id)
            if r:
                r.status = RunStatus.FAILED
                r.error = str(exc)
                r.finished_at = datetime.now(UTC)
        return
    async with _LOCK:
        _RUN_STATE[run_id] = result


# ---------------------------------------------------------------------------
# routers
# ---------------------------------------------------------------------------

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
api_router = APIRouter(prefix="/api", tags=["api"], dependencies=[Depends(get_current_user)])


@auth_router.post("/login", response_model=LoginResponse)
@limiter.limit("5/15 minutes")
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    if not verify_password(body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid password",
        )
    token, expires_at = create_token()
    return LoginResponse(token=token, expires_at=expires_at)


@auth_router.get("/me")
async def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"sub": user.get("sub"), "exp": user.get("exp")}


@api_router.get("/providers")
async def providers() -> dict[str, Any]:
    return {
        "current": settings.video_provider,
        "available": [
            {
                "id": "seedance",
                "name": "Seedance 2.0",
                "tier": "Económico",
                "model_id": settings.seedance_model,
                "native_audio": False,
                "supports_persona": True,
                "supports_soul_id": True,
                "clips": settings.standard_num_clips,
                "clip_duration": settings.standard_clip_duration,
                "total_duration": settings.standard_num_clips * settings.standard_clip_duration,
                "cost_credits": PROVIDER_COST_CREDITS["seedance"],
            },
            {
                "id": "kling",
                "name": "Kling v3.0",
                "tier": "Equilibrado",
                "model_id": settings.kling_model,
                "native_audio": False,
                "supports_persona": True,
                "supports_soul_id": True,
                "clips": settings.standard_num_clips,
                "clip_duration": settings.standard_clip_duration,
                "total_duration": settings.standard_num_clips * settings.standard_clip_duration,
                "cost_credits": PROVIDER_COST_CREDITS["kling"],
            },
            {
                "id": "veo",
                "name": "Veo 3.1",
                "tier": "Premium",
                "model_id": settings.veo_model,
                "native_audio": True,
                "supports_persona": True,
                "supports_soul_id": False,
                "clips": settings.veo_num_clips,
                "clip_duration": settings.veo_clip_duration,
                "total_duration": settings.veo_num_clips * settings.veo_clip_duration,
                "cost_credits": PROVIDER_COST_CREDITS["veo"],
            },
            {
                "id": "cinematic_studio_v2",
                "name": "Cinematic Studio v2",
                "tier": "Cinematográfico",
                "model_id": settings.cinematic_studio_model,
                "native_audio": False,
                "supports_persona": True,
                "supports_soul_id": True,
                "clips": settings.standard_num_clips,
                "clip_duration": settings.standard_clip_duration,
                "total_duration": settings.standard_num_clips * settings.standard_clip_duration,
                "cost_credits": PROVIDER_COST_CREDITS["cinematic_studio_v2"],
            },
        ],
    }


@api_router.get("/higgsfield/status")
async def higgsfield_status() -> dict[str, Any]:
    """Surface CLI auth + balance to the frontend so the UI can warn when
    the operator hasn't run `higgsfield auth login` on the host yet.
    """
    cli: HiggsfieldCLI = get_higgsfield_cli()
    try:
        data = await cli.account_status()
        return {"authenticated": True, "account": data}
    except HiggsfieldError as exc:
        return {"authenticated": False, "error": str(exc)}


@api_router.post("/run")
async def create_run(
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict[str, Any],
) -> dict[str, Any]:
    topic = str(body.get("topic", "")).strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")
    if len(topic) > _MAX_TOPIC_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"topic too long (max {_MAX_TOPIC_LEN} chars, got {len(topic)})",
        )

    provider_raw = body.get("provider")
    provider: VideoProvider | None
    if provider_raw is None or provider_raw == "":
        provider = None  # fall back to settings.video_provider
    else:
        if provider_raw not in _VALID_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"invalid provider {provider_raw!r}; must be one of {sorted(_VALID_PROVIDERS)}",
            )
        provider = provider_raw  # type: ignore[assignment]

    chosen_provider: VideoProvider = provider or settings.video_provider

    # Optional voiceless mode — for cinematic music-only reels where the user
    # wants the score to carry, not an ElevenLabs narrator.
    voiceless = bool(body.get("voiceless", False))
    # Optional keyframe-via-Nano-Banana-Pro mode — generates one image per
    # clip with the unlimited NBP tier and feeds it to Kling/Seedance as
    # --start-image for production-grade composition control.
    use_keyframes = bool(body.get("use_keyframes", False))

    # Optional structured creative brief. Validated by pydantic so a
    # malformed payload becomes a clean 400 instead of crashing the pipeline.
    brief_payload = body.get("brief")
    brief: CreativeBrief | None = None
    if isinstance(brief_payload, dict):
        # Topic in brief mirrors the top-level topic — keep them in sync so
        # downstream consumers only have to read one.
        brief_payload = {**brief_payload, "topic": topic}
        try:
            brief = CreativeBrief.model_validate(brief_payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid brief: {exc}") from exc

    # Optional character (Soul-ID). If supplied we validate that it exists
    # locally and is `ready` — otherwise the run would fail mid-pipeline.
    soul_id_raw = body.get("soul_id")
    soul_id: str | None = None
    if soul_id_raw:
        if not isinstance(soul_id_raw, str):
            raise HTTPException(status_code=400, detail="soul_id must be a string")
        character = get_characters_db().get(soul_id_raw)
        if character is None:
            raise HTTPException(status_code=400, detail=f"unknown soul_id {soul_id_raw!r}")
        if character.status != "ready":
            raise HTTPException(
                status_code=409,
                detail=f"character {character.name!r} is still {character.status}; "
                f"wait for it to finish training",
            )
        soul_id = soul_id_raw

    burn_subtitles = False

    client_run_id = str(body.get("run_id", "")).strip()
    if client_run_id:
        # Accept a client-supplied id so the frontend can upload refs against
        # the same id before kicking off the pipeline. Strict format check
        # (alphanum + dash + underscore) keeps this from being a path-traversal
        # vector when we use it to build output_dir.
        if not _SAFE_RUN_ID_RE.match(client_run_id):
            raise HTTPException(status_code=400, detail="invalid run_id format")
        run_id = client_run_id
    else:
        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    output_dir = settings.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    result = RunResult(
        run_id=run_id,
        topic=topic,
        status=RunStatus.PENDING,
        output_dir=output_dir,
        provider=chosen_provider,
        references=_drain_pending_refs(run_id),
        soul_id=soul_id,
        voiceless=voiceless,
        use_keyframes=use_keyframes,
        brief=brief,
    )
    async with _LOCK:
        _RUN_STATE[run_id] = result

    references = _drain_pending_refs(run_id) or list(result.references)
    result.references = list(references)
    skip_editor = bool(body.get("skip_editor", True))
    pause_after = None if skip_editor else "script_generator"
    background_tasks.add_task(
        _execute_run,
        topic,
        run_id,
        provider,
        burn_subtitles,
        references,
        pause_after,
        soul_id,
        voiceless,
        use_keyframes,
        brief,
    )
    return {
        "run_id": run_id,
        "status": result.status.value,
        "provider": chosen_provider,
        "soul_id": soul_id,
        "subtitles": burn_subtitles,
        "brief": brief.model_dump() if brief else None,
    }


@api_router.post("/run/draft")
async def create_draft_run(
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Same as POST /run but pauses after script_generator so the user can edit."""
    body = {**body, "skip_editor": False}
    return await create_run(request, background_tasks, body)  # type: ignore[arg-type]


@api_router.post("/run/{run_id}/confirm")
async def confirm_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Resume a paused run with the (possibly edited) script."""
    runs = {r.run_id: r for r in _all_runs()}
    r = runs.get(run_id)
    if r is None:
        raise HTTPException(status_code=404, detail="run not found")
    if r.status != RunStatus.SCRIPT_READY:
        raise HTTPException(
            status_code=409,
            detail=f"run not paused: status is {r.status.value}, expected script_ready",
        )

    script_payload = body.get("script")
    if not isinstance(script_payload, dict):
        raise HTTPException(status_code=400, detail="body.script (object) is required")
    try:
        edited = ScriptOutput.model_validate(script_payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid script: {exc}") from exc

    background_tasks.add_task(_resume_run, run_id, edited)
    return {
        "run_id": run_id,
        "status": RunStatus.RUNNING.value,
    }


@api_router.get("/runs")
async def list_runs() -> dict[str, Any]:
    return {"runs": [_run_summary(r) for r in _all_runs()]}


@api_router.put("/runs/{run_id}/shot-plan")
async def update_shot_plan(run_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Overwrite the persisted ShotPlan for a run.

    Used by the detail view to let an operator hand-tune individual shots
    before resuming a paused run, and by the MCP server tools to
    programmatically refine the plan from outside.
    """
    runs = {r.run_id: r for r in _all_runs()}
    r = runs.get(run_id)
    if r is None:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        plan = ShotPlan.model_validate(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid shot_plan: {exc}") from exc
    r.shot_plan = plan
    output_dir = settings.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.json").write_text(
        r.model_dump_json(indent=2), encoding="utf-8"
    )
    async with _LOCK:
        _RUN_STATE[run_id] = r
    return {"run_id": run_id, "shot_plan": plan.model_dump()}


@api_router.post("/runs/{run_id}/shot-plan/refine")
async def refine_shot(run_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Refine a single shot via Claude using a natural-language instruction.

    Body: {"shot_index": int, "instruction": str}
    Returns the updated shot. Persisted alongside the rest of the plan.
    """
    from anthropic import AsyncAnthropic

    shot_index = body.get("shot_index")
    instruction = str(body.get("instruction") or "").strip()
    if not isinstance(shot_index, int):
        raise HTTPException(status_code=400, detail="shot_index (int) is required")
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction is required")

    runs = {r.run_id: r for r in _all_runs()}
    r = runs.get(run_id)
    if r is None:
        raise HTTPException(status_code=404, detail="run not found")
    if r.shot_plan is None or not r.shot_plan.shots:
        raise HTTPException(status_code=409, detail="run has no shot_plan yet")
    if not (0 <= shot_index < len(r.shot_plan.shots)):
        raise HTTPException(
            status_code=400,
            detail=f"shot_index {shot_index} out of range (0..{len(r.shot_plan.shots) - 1})",
        )

    shot = r.shot_plan.shots[shot_index]
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    system = (
        "Eres un director de cine. Recibes un shot existente en JSON y una "
        "instrucción del operador. Devuelves SIEMPRE un único objeto JSON con "
        "EL MISMO esquema del shot, ajustado según la instrucción. Mantén el "
        "index y duration_seconds. No incluyas markdown, sólo JSON."
    )
    user = (
        f"SHOT ACTUAL:\n{shot.model_dump_json(indent=2)}\n\n"
        f"PERSONA LOCK (mantener):\n{r.shot_plan.persona_lock}\n\n"
        f"STYLE BRIEF (mantener):\n{r.shot_plan.style_brief}\n\n"
        f"INSTRUCCIÓN DEL OPERADOR:\n{instruction}\n\n"
        "Devuelve el shot ajustado completo, en JSON."
    )
    try:
        message = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        raw = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        ).strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
        new_shot = Shot.model_validate(json.loads(raw))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"director refine failed: {exc}") from exc

    new_shot.index = shot.index
    new_shot.duration_seconds = shot.duration_seconds
    r.shot_plan.shots[shot_index] = new_shot
    output_dir = settings.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.json").write_text(
        r.model_dump_json(indent=2), encoding="utf-8"
    )
    async with _LOCK:
        _RUN_STATE[run_id] = r
    return {"run_id": run_id, "shot_index": shot_index, "shot": new_shot.model_dump()}


@api_router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    runs = {r.run_id: r for r in _all_runs()}
    r = runs.get(run_id)
    if r is None:
        raise HTTPException(status_code=404, detail="run not found")
    return _run_detail(r)


_VALID_REFERENCE_KINDS: set[str] = {"persona", "style", "script", "voice", "music"}
_MAX_UPLOAD_BYTES = 30 * 1024 * 1024  # 30 MB hard cap per upload
_ALLOWED_REF_MIME: dict[ReferenceKind, set[str]] = {
    "persona": {"image/jpeg", "image/png", "image/webp"},
    "style": {"image/jpeg", "image/png", "image/webp", "video/mp4", "video/quicktime"},
    "script": {"text/plain", "application/json"},
    "voice": {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac"},
    "music": {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac", "audio/flac"},
}


def _run_uploads_dir(run_id: str) -> Path:
    d = (settings.references_dir / run_id).resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


@api_router.post("/references")
async def upload_reference(
    run_id: str = Form(...),
    kind: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Accept a multipart upload, persist it under output/_uploads/{run_id}/."""
    if kind not in _VALID_REFERENCE_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"invalid kind {kind!r}; must be one of {sorted(_VALID_REFERENCE_KINDS)}",
        )
    mime = file.content_type or "application/octet-stream"
    allowed = _ALLOWED_REF_MIME[kind]  # type: ignore[index]
    if mime not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"mime {mime!r} not allowed for kind={kind}; allowed: {sorted(allowed)}",
        )

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"file too large ({len(raw)} bytes, max {_MAX_UPLOAD_BYTES})",
        )

    suffix = Path(file.filename or "ref.bin").suffix or _suffix_for_mime(mime)
    dest_dir = _run_uploads_dir(run_id)
    seq = len(list(dest_dir.glob(f"{kind}_*")))
    dest = dest_dir / f"{kind}_{seq:02d}{suffix}"
    dest.write_bytes(raw)

    ref = Reference(kind=kind, path=dest, mime=mime, bytes=len(raw))  # type: ignore[arg-type]
    _attach_reference(run_id, ref)
    return ref.model_dump(mode="json")


@api_router.post("/references/youtube")
async def add_youtube_reference(body: dict[str, Any]) -> dict[str, Any]:
    """Pull a YouTube URL as either a transcript (script ref) or a voice sample."""
    run_id = str(body.get("run_id", "")).strip()
    kind = str(body.get("kind", "")).strip()
    url = str(body.get("url", "")).strip()
    if not run_id or kind not in {"script", "voice", "music"} or not url:
        raise HTTPException(
            status_code=400,
            detail="run_id, kind (script|voice|music), and url are required",
        )
    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="not a YouTube URL")

    dest_dir = _run_uploads_dir(run_id)
    seq = len(list(dest_dir.glob(f"{kind}_*")))
    try:
        if kind == "script":
            dest = dest_dir / f"script_{seq:02d}.txt"
            await asyncio.to_thread(
                fetch_transcript,
                url,
                dest,
                max_chars=settings.youtube_transcript_max_chars,
            )
            mime = "text/plain"
        elif kind == "voice":
            dest = dest_dir / f"voice_{seq:02d}.mp3"
            await asyncio.to_thread(
                fetch_voice_sample,
                url,
                dest,
                max_seconds=settings.youtube_voice_sample_seconds,
            )
            mime = "audio/mpeg"
        else:  # music — stereo, longer window (up to 120s, trimmed in assembler).
            dest = dest_dir / f"music_{seq:02d}.mp3"
            await asyncio.to_thread(
                fetch_audio_track,
                url,
                dest,
                max_seconds=120,
            )
            mime = "audio/mpeg"
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    ref = Reference(
        kind=kind,  # type: ignore[arg-type]
        path=dest,
        source_url=url,
        mime=mime,
        bytes=dest.stat().st_size,
    )
    _attach_reference(run_id, ref)
    return ref.model_dump(mode="json")


@api_router.get("/references/{run_id}")
async def list_references(run_id: str) -> dict[str, Any]:
    refs = [r.model_dump(mode="json") for r in _references_for(run_id)]
    return {"run_id": run_id, "references": refs}


def _suffix_for_mime(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "text/plain": ".txt",
        "application/json": ".json",
        "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
    }.get(mime, ".bin")


_PENDING_REFS: dict[str, list[Reference]] = {}


def _attach_reference(run_id: str, ref: Reference) -> None:
    """Stash refs until the run is created (or attach to existing run)."""
    r = _RUN_STATE.get(run_id)
    if r is not None:
        r.references.append(ref)
        return
    _PENDING_REFS.setdefault(run_id, []).append(ref)


def _references_for(run_id: str) -> list[Reference]:
    r = _RUN_STATE.get(run_id)
    if r is not None:
        return list(r.references)
    return list(_PENDING_REFS.get(run_id, []))


def _drain_pending_refs(run_id: str) -> list[Reference]:
    return _PENDING_REFS.pop(run_id, [])


_ALLOWED_FILES = {"video.mp4", "caption.txt", "script.json", "audio.mp3", "subtitles.srt"}


@api_router.get("/output/{run_id}/{filename}")
async def get_output_file(run_id: str, filename: str) -> Any:
    if filename not in _ALLOWED_FILES:
        raise HTTPException(status_code=404, detail="file not allowed")
    base = settings.output_dir.resolve()
    target = (base / run_id / filename).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="invalid path")
    if not target.exists():
        raise HTTPException(status_code=404, detail="file not found")
    media_types = {
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".txt": "text/plain; charset=utf-8",
        ".json": "application/json",
        ".srt": "text/plain; charset=utf-8",
    }
    media = media_types.get(target.suffix, "application/octet-stream")
    return FileResponse(target, media_type=media)


app.include_router(auth_router)
app.include_router(api_router)
app.include_router(characters_router)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def api_not_found(rest: str) -> Any:
    """Catch-all for unmatched /api/* paths so they 404 as JSON instead of
    falling through to the SPA static mount and returning index.html."""
    raise HTTPException(status_code=404, detail=f"unknown api route: /api/{rest}")


# ---------------------------------------------------------------------------
# SPA static mount (production)
# ---------------------------------------------------------------------------


class SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html for unknown paths (React Router)."""

    async def get_response(self, path: str, scope: Any) -> Any:  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except Exception:
            return await super().get_response("index.html", scope)


_dist = settings.frontend_dist
if _dist.exists() and (_dist / "index.html").exists():
    app.mount("/", SPAStaticFiles(directory=str(_dist), html=True), name="spa")
else:
    @app.get("/")
    async def spa_placeholder() -> Any:
        return JSONResponse(
            {
                "message": (
                    f"Frontend not built. Run `cd frontend && npm install && npm run build` "
                    f"to produce {_dist}/index.html. API is available at /api/*."
                )
            }
        )
