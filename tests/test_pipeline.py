"""End-to-end pipeline tests with all external APIs mocked."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.config import settings
from src.models import (
    AssembledOutput,
    RunStatus,
    ScriptOutput,
    SubtitleOutput,
    SubtitleSegment,
    VoiceOutput,
)
from src.pipeline import Pipeline


def _make_script(num_clips: int) -> ScriptOutput:
    return ScriptOutput(
        hook="Hook potente.",
        body="Cuerpo del reel.",
        cta="Sígueme para más.",
        full_script="Hook potente. Cuerpo del reel. Sígueme para más.",
        caption="Caption del reel",
        hashtags=["reels", "ia", "viral"],
        persona_description="Mujer 30 años, pelo castaño",
        visual_prompts=[f"Prompt {i}" for i in range(num_clips)],
    )


class FakeScriptStep:
    name = "script_generator"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        context["script"] = _make_script(settings.clip_count())
        return context


class FakeVoiceStep:
    name = "voice_generator"

    def __init__(self) -> None:
        self.called = False

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        self.called = True
        output_dir: Path = context["output_dir"]
        audio_path = output_dir / "audio.mp3"
        audio_path.write_bytes(b"fake-mp3")
        context["voice"] = VoiceOutput(audio_path=audio_path, duration_seconds=25.0)
        return context


class FakeVideoStep:
    """Mirrors the provider-aware behaviour of the real VideoGeneratorStep."""

    name = "video_generator"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        output_dir: Path = context["output_dir"]
        clips_dir = output_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        clip_paths: list[Path] = []
        for i in range(settings.clip_count()):
            p = clips_dir / f"clip_{i:02d}.mp4"
            p.write_bytes(b"fake-mp4")
            clip_paths.append(p)
        context["video_clips"] = clip_paths
        context["video_provider"] = settings.video_provider
        context["video_clip_duration"] = settings.clip_duration()
        if settings.video_provider == "veo":
            context["skip_voice_generation"] = True
        return context


class FakeSubtitleStep:
    name = "subtitle_generator"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        output_dir: Path = context["output_dir"]
        srt_path = output_dir / "subtitles.srt"
        srt_path.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nHook potente.\n", encoding="utf-8"
        )
        context["subtitles"] = SubtitleOutput(
            srt_path=srt_path,
            segments=[SubtitleSegment(start=0.0, end=2.0, text="Hook potente.")],
        )
        return context


class FakeAssemblerStep:
    name = "assembler"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        script: ScriptOutput = context["script"]
        output_dir: Path = context["output_dir"]
        final_path = output_dir / "video.mp4"
        final_path.write_bytes(b"fake-final-mp4")
        caption_path = output_dir / "caption.txt"
        caption_path.write_text(
            script.caption + "\n\n" + " ".join(f"#{h}" for h in script.hashtags),
            encoding="utf-8",
        )
        (output_dir / "script.json").write_text(
            json.dumps(script.model_dump(), ensure_ascii=False), encoding="utf-8"
        )
        context["assembled"] = AssembledOutput(final_video_path=final_path)
        context["caption_path"] = caption_path
        return context


def _build_pipeline() -> tuple[Pipeline, FakeVoiceStep]:
    voice = FakeVoiceStep()
    pipeline = Pipeline(
        steps=[
            FakeScriptStep(),
            voice,
            FakeVideoStep(),
            FakeSubtitleStep(),
            FakeAssemblerStep(),
        ]
    )
    return pipeline, voice


@pytest.mark.parametrize("provider", ["seedance", "kling", "veo"])
@pytest.mark.asyncio
async def test_pipeline_end_to_end(provider: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "video_provider", provider)
    pipeline, voice = _build_pipeline()
    result = await pipeline.run(topic="café especialidad")

    assert result.status == RunStatus.DONE
    assert result.error is None
    assert result.final_video_path is not None and result.final_video_path.exists()
    assert result.caption_path is not None and result.caption_path.exists()
    assert "#reels" in result.caption_path.read_text(encoding="utf-8")
    assert (result.output_dir / "script.json").exists()
    assert (result.output_dir / "result.json").exists()

    if provider == "veo":
        assert voice.called is False
        assert len(list((result.output_dir / "clips").glob("clip_*.mp4"))) == 3
    else:
        assert voice.called is True
        assert len(list((result.output_dir / "clips").glob("clip_*.mp4"))) == 5


@pytest.mark.asyncio
async def test_pipeline_retries_then_succeeds() -> None:
    calls = {"n": 0}

    class FlakyScript(FakeScriptStep):
        async def run(self, context: dict[str, Any]) -> dict[str, Any]:
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("transient")
            return await super().run(context)

    pipeline = Pipeline(
        steps=[
            FlakyScript(),
            FakeVoiceStep(),
            FakeVideoStep(),
            FakeSubtitleStep(),
            FakeAssemblerStep(),
        ]
    )
    result = await pipeline.run(topic="tema")
    assert result.status == RunStatus.DONE
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_pipeline_fails_after_max_retries() -> None:
    class AlwaysFails:
        name = "script_generator"

        async def run(self, context: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("nope")

    pipeline = Pipeline(steps=[AlwaysFails()])
    result = await pipeline.run(topic="tema")
    assert result.status == RunStatus.FAILED
    assert result.error is not None
    assert "nope" in result.error


@pytest.mark.asyncio
async def test_script_generator_parses_json() -> None:
    from src.steps.script_generator import ScriptGeneratorStep

    class FakeBlock:
        type = "text"
        text = json.dumps(
            {
                "hook": "h",
                "body": "b",
                "cta": "c",
                "full_script": "h b c",
                "caption": "cap",
                "hashtags": ["a", "b"],
                "persona_description": "persona",
                "visual_prompts": ["p1", "p2", "p3", "p4", "p5"],
            }
        )

    class FakeMessage:
        content = [FakeBlock()]

    class FakeMessages:
        async def create(self, **kwargs: Any) -> Any:
            return FakeMessage()

    class FakeClient:
        messages = FakeMessages()

    step = ScriptGeneratorStep(client=FakeClient())
    context = await step.run({"topic": "demo"})
    script: ScriptOutput = context["script"]
    assert script.hook == "h"
    assert script.hashtags == ["a", "b"]
    assert len(script.visual_prompts) == 5


@pytest.mark.asyncio
async def test_subtitle_generator_uses_voice_when_available(tmp_path: Path) -> None:
    from src.steps.subtitle_generator import SubtitleGeneratorStep

    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"fake")

    def fake_transcribe(_path: Path) -> list[SubtitleSegment]:
        assert _path == audio_path
        return [SubtitleSegment(start=0.0, end=1.5, text="hola")]

    step = SubtitleGeneratorStep(transcribe_fn=fake_transcribe)
    context = await step.run(
        {
            "voice": VoiceOutput(audio_path=audio_path, duration_seconds=3.0),
            "output_dir": tmp_path,
        }
    )
    subs: SubtitleOutput = context["subtitles"]
    assert "hola" in subs.srt_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_subtitle_generator_extracts_audio_from_clips_for_veo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.steps import subtitle_generator as sg

    clip = tmp_path / "clip_00.mp4"
    clip.write_bytes(b"fake-video")

    extracted_paths: list[Path] = []

    def fake_extract(clip_paths: list[Path], dest: Path) -> None:
        extracted_paths.append(dest)
        dest.write_bytes(b"extracted-mp3")

    monkeypatch.setattr(sg, "_extract_audio_from_clips", fake_extract)

    def fake_transcribe(path: Path) -> list[SubtitleSegment]:
        assert path == extracted_paths[0]
        return [SubtitleSegment(start=0.0, end=8.0, text="from clip")]

    step = sg.SubtitleGeneratorStep(transcribe_fn=fake_transcribe)
    context = await step.run(
        {
            "video_clips": [clip],
            "output_dir": tmp_path,
        }
    )
    subs: SubtitleOutput = context["subtitles"]
    assert "from clip" in subs.srt_path.read_text(encoding="utf-8")
    assert extracted_paths[0].name == "audio_from_clips.mp3"


@pytest.mark.parametrize(
    "provider,expected_model_attr,expected_clips,expected_duration",
    [
        ("seedance", "seedance_model", 5, 5),
        ("kling", "kling_model", 5, 5),
        ("veo", "veo_model", 3, "8"),
    ],
)
@pytest.mark.asyncio
async def test_video_generator_dispatches_per_provider(
    provider: str,
    expected_model_attr: str,
    expected_clips: int,
    expected_duration: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_hf_cli: Any,
) -> None:
    from src.steps.video_generator import VideoGeneratorStep

    monkeypatch.setattr(settings, "video_provider", provider)

    step = VideoGeneratorStep(cli=fake_hf_cli)
    context = await step.run(
        {
            "script": _make_script(expected_clips),
            "output_dir": tmp_path,
        }
    )

    expected_model = getattr(settings, expected_model_attr)
    calls = fake_hf_cli.generate_calls
    assert len(calls) == expected_clips
    assert all(model == expected_model for model, _ in calls)
    assert len(context["video_clips"]) == expected_clips
    if provider == "veo":
        assert context["skip_voice_generation"] is True
        assert all(args["duration"] == "8" for _, args in calls)
    else:
        assert all(args["duration"] == 5 for _, args in calls)
    # The video step always declares lipsync as fused/skip.
    assert context["skip_lipsync"] is True


@pytest.mark.asyncio
async def test_pipeline_skips_voice_for_veo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "video_provider", "veo")
    pipeline, voice = _build_pipeline()
    result = await pipeline.run(topic="tema")
    assert result.status == RunStatus.DONE
    assert voice.called is False


@pytest.mark.asyncio
async def test_pipeline_runs_voice_for_non_veo_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for provider in ("seedance", "kling"):
        monkeypatch.setattr(settings, "video_provider", provider)
        pipeline, voice = _build_pipeline()
        result = await pipeline.run(topic="tema", run_id=f"r-{provider}")
        assert result.status == RunStatus.DONE, f"failed for {provider}"
        assert voice.called is True, f"voice must run for {provider}"


def test_api_run_creates_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/run with a valid JWT enqueues a run."""
    from fastapi.testclient import TestClient

    import src.api.main as api_main
    from src.api.auth import create_token

    async def fake_execute(
        topic: str,
        run_id: str,
        provider: str | None = None,
        burn_subtitles: bool = True,
        references: list | None = None,
        pause_after: str | None = None,
        soul_id: str | None = None,
        voiceless: bool = False,
        use_keyframes: bool = False,
    ) -> None:
        return None

    monkeypatch.setattr(api_main, "_execute_run", fake_execute)

    token, _ = create_token()
    client = TestClient(api_main.app)
    r = client.post(
        "/api/run",
        json={"topic": "café"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "run_id" in body
    assert body["status"] in {"pending", "running"}


def test_voice_generator_preprocess_text_cleans_input() -> None:
    """Markdown stripped, ellipses → period, em-dashes → comma, spacing fixed."""
    from src.steps.voice_generator import _preprocess_text

    raw = "# Título\n**Hola** mundo... esto es _genial_ — sí,muy bien.Próximo punto"
    out = _preprocess_text(raw)
    assert "*" not in out
    assert "_" not in out
    assert "..." not in out
    assert "—" not in out
    assert "#" not in out
    assert "sí, muy bien" in out
    assert "bien. Próximo" in out


def test_invalid_video_provider_raises() -> None:
    """settings should refuse an unknown VIDEO_PROVIDER value."""
    from pydantic import ValidationError

    from src.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, VIDEO_PROVIDER="invalid")  # type: ignore[call-arg]


def test_api_run_accepts_provider_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/run forwards a valid `provider` field to the executor."""
    from fastapi.testclient import TestClient

    import src.api.main as api_main
    from src.api.auth import create_token

    captured: dict[str, str | None] = {}

    async def fake_execute(
        topic: str,
        run_id: str,
        provider: str | None = None,
        burn_subtitles: bool = True,
        references: list | None = None,
        pause_after: str | None = None,
        soul_id: str | None = None,
        voiceless: bool = False,
        use_keyframes: bool = False,
    ) -> None:
        captured["topic"] = topic
        captured["provider"] = provider

    monkeypatch.setattr(api_main, "_execute_run", fake_execute)

    token, _ = create_token()
    client = TestClient(api_main.app)
    r = client.post(
        "/api/run",
        json={"topic": "café", "provider": "kling"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["provider"] == "kling"
    assert captured["provider"] == "kling"


def test_api_run_rejects_invalid_provider() -> None:
    """POST /api/run with an unknown provider returns 400."""
    from fastapi.testclient import TestClient

    import src.api.main as api_main
    from src.api.auth import create_token

    token, _ = create_token()
    client = TestClient(api_main.app)
    r = client.post(
        "/api/run",
        json={"topic": "café", "provider": "midjourney"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert "invalid provider" in r.json()["detail"]


def test_api_run_rejects_topic_too_long() -> None:
    """POST /api/run with a topic longer than 4000 chars returns 400."""
    from fastapi.testclient import TestClient

    import src.api.main as api_main
    from src.api.auth import create_token

    token, _ = create_token()
    client = TestClient(api_main.app)
    r = client.post(
        "/api/run",
        json={"topic": "x" * 4001},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert "too long" in r.json()["detail"]


# ---------------------------------------------------------------------------
# draft/confirm flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_draft_mode_stops_after_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """pause_after='script_generator' must SCRIPT_READY without running voice/video."""
    monkeypatch.setattr(settings, "video_provider", "kling")
    pipeline, voice = _build_pipeline()

    result = await pipeline.run(topic="rutinas", pause_after="script_generator")

    assert result.status == RunStatus.SCRIPT_READY
    assert result.script is not None
    assert voice.called is False
    # No final video, no caption — those steps did not run.
    assert result.final_video_path is None
    persisted_path = result.output_dir / "result.json"
    persisted = json.loads(persisted_path.read_text(encoding="utf-8"))
    assert persisted["status"] == RunStatus.SCRIPT_READY.value


@pytest.mark.asyncio
async def test_pipeline_resume_uses_edited_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """After SCRIPT_READY, resume() must inject the edited script into voice + assembler."""
    monkeypatch.setattr(settings, "video_provider", "kling")
    pipeline, voice = _build_pipeline()

    draft = await pipeline.run(topic="x", pause_after="script_generator")
    assert draft.status == RunStatus.SCRIPT_READY

    edited = ScriptOutput(
        hook="HOOK_EDITADO",
        body="BODY_EDITADO",
        cta="CTA_EDITADO",
        full_script="HOOK_EDITADO BODY_EDITADO CTA_EDITADO",
        caption="CAPTION_EDITADO",
        hashtags=["edited"],
        persona_description="p",
        persona_gender="female",
        visual_prompts=[f"prompt {i} edited" for i in range(settings.clip_count())],
    )
    final = await pipeline.resume(draft.run_id, edited)

    assert final.status == RunStatus.DONE
    assert voice.called is True
    # The assembler wrote the EDITED caption to disk.
    assert final.caption_path is not None
    assert "CAPTION_EDITADO" in final.caption_path.read_text(encoding="utf-8")
    assert final.script is not None
    assert final.script.hook == "HOOK_EDITADO"
