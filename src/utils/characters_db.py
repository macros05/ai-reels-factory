"""SQLite store for trained Soul-ID characters.

The DB lives at `<data_dir>/characters.db` (default `./data/characters.db`,
bind-mounted from the host in prod). Each character points to a `soul_id`
managed by Higgsfield's cloud — losing the DB only loses metadata; the
trained Soul itself can still be queried via `higgsfield soul-id list`.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.models import Character

_SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
    soul_id      TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    status       TEXT NOT NULL,
    soul_model   TEXT NOT NULL,
    image_uuids  TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    ready_at     TEXT,
    error        TEXT,
    preview_path TEXT
);

CREATE INDEX IF NOT EXISTS characters_status_idx ON characters(status);
"""


class CharactersDB:
    """Thread-safe wrapper around the characters sqlite file.

    Connections are short-lived (open per call), which keeps thread safety
    trivial and survives the FastAPI background-task pool without worrying
    about cross-thread connection reuse.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._init_lock = threading.Lock()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._init_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.path) as con:
                con.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def upsert(self, character: Character) -> None:
        with self._conn() as con:
            con.execute(
                """
                INSERT INTO characters (
                    soul_id, name, status, soul_model, image_uuids,
                    created_at, ready_at, error, preview_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(soul_id) DO UPDATE SET
                    name=excluded.name,
                    status=excluded.status,
                    soul_model=excluded.soul_model,
                    image_uuids=excluded.image_uuids,
                    ready_at=excluded.ready_at,
                    error=excluded.error,
                    preview_path=excluded.preview_path
                """,
                (
                    character.soul_id,
                    character.name,
                    character.status,
                    character.soul_model,
                    json.dumps(character.image_uuids),
                    character.created_at.isoformat(),
                    character.ready_at.isoformat() if character.ready_at else None,
                    character.error,
                    str(character.preview_path) if character.preview_path else None,
                ),
            )

    def get(self, soul_id: str) -> Character | None:
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM characters WHERE soul_id = ?", (soul_id,)
            ).fetchone()
        return _row_to_character(row) if row else None

    def list(self) -> list[Character]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM characters ORDER BY created_at DESC"
            ).fetchall()
        return [c for c in (_row_to_character(r) for r in rows) if c is not None]

    def mark_ready(self, soul_id: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE characters SET status='ready', ready_at=? WHERE soul_id=?",
                (datetime.now(UTC).isoformat(), soul_id),
            )

    def mark_failed(self, soul_id: str, error: str) -> None:
        with self._conn() as con:
            con.execute(
                "UPDATE characters SET status='failed', error=? WHERE soul_id=?",
                (error[:1000], soul_id),
            )

    def delete(self, soul_id: str) -> bool:
        with self._conn() as con:
            cur = con.execute("DELETE FROM characters WHERE soul_id=?", (soul_id,))
            return cur.rowcount > 0


def _row_to_character(row: sqlite3.Row | None) -> Character | None:
    if row is None:
        return None
    data: dict[str, Any] = dict(row)
    data["image_uuids"] = json.loads(data.get("image_uuids") or "[]")
    if data.get("preview_path"):
        data["preview_path"] = Path(data["preview_path"])
    else:
        data["preview_path"] = None
    return Character(**data)


# Module-level singleton — initialised lazily so tests can monkey-patch
# `settings.data_dir` before the first import.
_CACHED: dict[str, CharactersDB] = {}


def get_characters_db() -> CharactersDB:
    from src.config import settings

    key = str(settings.data_dir.resolve())
    db = _CACHED.get(key)
    if db is None:
        db = CharactersDB(settings.data_dir / "characters.db")
        _CACHED[key] = db
    return db


def reset_cache() -> None:
    """Test helper: forces the next get_characters_db() to re-resolve the path."""
    _CACHED.clear()


def iter_pending(db: CharactersDB) -> Iterable[Character]:
    """All characters still training, oldest first — used by the resumer."""
    return [c for c in db.list() if c.status == "training"]
