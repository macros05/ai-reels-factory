"""Shared test fixtures + Higgsfield CLI mocks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.config import settings


@pytest.fixture(autouse=True)
def _tmp_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect output_dir + data_dir to tmp_path for every test.

    Also pin standard_num_clips/standard_clip_duration to their original
    defaults so tests stay deterministic regardless of what the host .env
    overrides (a 30 s production reel uses STANDARD_NUM_CLIPS=6 in .env;
    that would otherwise leak into unit tests and change the expected
    clip count assertions).
    """
    monkeypatch.setattr(settings, "output_dir", tmp_path)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "_data")
    monkeypatch.setattr(settings, "standard_num_clips", 5)
    monkeypatch.setattr(settings, "standard_clip_duration", 5)
    monkeypatch.setattr(settings, "veo_num_clips", 3)
    monkeypatch.setattr(settings, "veo_clip_duration", 8)
    # Force the characters DB to re-resolve under the new data_dir for the test.
    from src.utils import characters_db
    characters_db.reset_cache()
    return tmp_path


class FakeHiggsfieldCLI:
    """Drop-in replacement for `HiggsfieldCLI` used in tests.

    Records every call (`generate`, `upload`, `soul_id_*`) so tests can assert
    on what flags were sent to which model. Returns deterministic stubs that
    look like real Higgsfield --json payloads.
    """

    def __init__(self) -> None:
        self.generate_calls: list[tuple[str, dict[str, Any]]] = []
        self.uploads: list[Path] = []
        self.soul_creates: list[dict[str, Any]] = []
        self.soul_waits: list[str] = []
        # Override per test to simulate failure scenarios.
        self.generate_return: dict[str, Any] | None = None
        self.image_return: dict[str, Any] | None = None
        self.video_url: str = "https://fake.hf/clip.mp4"
        self.image_url: str = "https://fake.hf/still.jpg"

    async def upload(self, path: Path | str) -> str:
        self.uploads.append(Path(str(path)))
        return f"upload-{len(self.uploads)}"

    async def generate(
        self, job_set_type: str, *, prompt: str, wait: bool = True, **flags: Any
    ) -> dict[str, Any]:
        self.generate_calls.append((job_set_type, {"prompt": prompt, **flags}))
        if "text2image" in job_set_type or "soul" in job_set_type:
            return self.image_return or {"images": [{"url": self.image_url}]}
        return self.generate_return or {"video": {"url": self.video_url}}

    async def soul_id_create(
        self, *, name: str, image_uuids: list[str], soul_model: str = "soul-2"
    ) -> dict[str, Any]:
        self.soul_creates.append(
            {"name": name, "image_uuids": list(image_uuids), "soul_model": soul_model}
        )
        return {"id": f"soul-{len(self.soul_creates)}", "name": name, "status": "training"}

    async def soul_id_wait(self, soul_id: str, *, timeout_seconds: int = 900) -> dict[str, Any]:
        self.soul_waits.append(soul_id)
        return {"id": soul_id, "status": "ready"}

    async def soul_id_get(self, soul_id: str) -> dict[str, Any]:
        return {"id": soul_id, "status": "ready"}

    async def soul_id_list(self) -> list[dict[str, Any]]:
        return [
            {"id": s["name"], "name": s["name"], "status": "ready"}
            for s in self.soul_creates
        ]

    async def account_status(self) -> dict[str, Any]:
        return {"email": "test@example.com", "plan": "ultra", "credits": 999}

    async def is_authenticated(self) -> bool:
        return True


@pytest.fixture
def fake_hf_cli(monkeypatch: pytest.MonkeyPatch) -> FakeHiggsfieldCLI:
    """Provide a FakeHiggsfieldCLI and patch download_to_path so steps don't
    actually try to fetch the stub URLs over the network.
    """
    fake = FakeHiggsfieldCLI()

    async def fake_download(url: str, dest: Path, *, timeout: float = 300.0) -> None:
        dest.write_bytes(f"fake:{url}".encode())

    import src.clients.higgsfield as hf
    import src.steps.video_generator as vg
    monkeypatch.setattr(hf, "download_to_path", fake_download)
    monkeypatch.setattr(vg, "download_to_path", fake_download)
    # Also patch the slicer so we don't need real ffmpeg for unit tests.
    def fake_slice(*, source: Path, dest: Path, start_seconds: int, duration_seconds: int) -> None:
        dest.write_bytes(
            f"slice:{Path(source).name}:{start_seconds}-{start_seconds + duration_seconds}".encode()
        )
    monkeypatch.setattr(vg, "_slice_audio", fake_slice)
    return fake
