"""Targeted tests for the video_generator step: payload formatting per provider.

These tests focus on the *exact* arguments handed to the Higgsfield CLI —
especially Veo's `duration` literal ('4'|'6'|'8') and the inline-audio /
soul-id-still wiring for Kling and Seedance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import settings
from src.models import ScriptOutput
from tests.conftest import FakeHiggsfieldCLI


def _script(num_clips: int) -> ScriptOutput:
    return ScriptOutput(
        hook="h",
        body="b",
        cta="c",
        full_script="h b c",
        caption="cap",
        hashtags=["a"],
        persona_description="persona",
        persona_gender="female",
        visual_prompts=[f"prompt {i}" for i in range(num_clips)],
    )


@pytest.mark.asyncio
async def test_veo_payload_sends_duration_as_string_literal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_hf_cli: FakeHiggsfieldCLI
) -> None:
    """Regression: Higgsfield veo3_1 requires duration in {'4','6','8'} as string."""
    from src.steps.video_generator import VideoGeneratorStep

    monkeypatch.setattr(settings, "video_provider", "veo")

    step = VideoGeneratorStep(cli=fake_hf_cli)
    await step.run({"script": _script(3), "output_dir": tmp_path})

    assert len(fake_hf_cli.generate_calls) == 3
    for model, args in fake_hf_cli.generate_calls:
        assert model == settings.veo_model
        assert args["duration"] == "8", (
            f"veo duration must be the string '8', got {args['duration']!r}"
        )
        assert args["aspect_ratio"] == "9:16"


@pytest.mark.asyncio
async def test_kling_payload_always_silences_native_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_hf_cli: FakeHiggsfieldCLI
) -> None:
    """Kling v3.0 native audio is always off — the assembler controls audio
    (voiceover + music ref), so letting Kling invent ambient sound here
    would only clash with whatever we layer on top.
    """
    from src.steps.video_generator import VideoGeneratorStep

    monkeypatch.setattr(settings, "video_provider", "kling")
    step = VideoGeneratorStep(cli=fake_hf_cli)
    await step.run({"script": _script(5), "output_dir": tmp_path})

    assert len(fake_hf_cli.generate_calls) == 5
    for model, args in fake_hf_cli.generate_calls:
        assert model == settings.kling_model
        assert args["duration"] == 5
        assert args["mode"] == settings.kling_mode
        assert args["sound"] == "off"
        assert "audio" not in args


@pytest.mark.asyncio
async def test_seedance_payload_sends_resolution_and_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_hf_cli: FakeHiggsfieldCLI
) -> None:
    """Seedance 2.0 accepts integer duration + resolution + mode."""
    from src.steps.video_generator import VideoGeneratorStep

    monkeypatch.setattr(settings, "video_provider", "seedance")
    step = VideoGeneratorStep(cli=fake_hf_cli)
    await step.run({"script": _script(5), "output_dir": tmp_path})

    assert len(fake_hf_cli.generate_calls) == 5
    for _, args in fake_hf_cli.generate_calls:
        assert args["duration"] == 5
        assert args["resolution"] == settings.seedance_resolution
        assert args["mode"] == settings.seedance_mode


@pytest.mark.asyncio
async def test_kling_with_audio_flips_sound_off_and_passes_audio_uuid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_hf_cli: FakeHiggsfieldCLI
) -> None:
    """When ElevenLabs audio is present, Kling gets --audio and --sound off."""
    from src.models import VoiceOutput
    from src.steps.video_generator import VideoGeneratorStep

    monkeypatch.setattr(settings, "video_provider", "kling")
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"x" * 4096)

    step = VideoGeneratorStep(cli=fake_hf_cli)
    await step.run({
        "script": _script(5),
        "output_dir": tmp_path,
        "voice": VoiceOutput(audio_path=audio, duration_seconds=25.0),
    })

    # 5 audio segment uploads
    assert len(fake_hf_cli.uploads) == 5
    for _, args in fake_hf_cli.generate_calls:
        assert args["sound"] == "off"
        assert args["audio"].startswith("upload-")


def test_veo_build_request_rejects_out_of_range_duration() -> None:
    """Direct call with an invalid duration must raise — not silently send junk."""
    from src.steps.video_generator import _build_clip_flags

    for bad in (5, 7, 10, 0):
        with pytest.raises(ValueError, match="veo duration"):
            _build_clip_flags(
                provider="veo", duration=bad, start_image_uuid=None, audio_uuid=None
            )

    for ok in (4, 6, 8):
        flags = _build_clip_flags(
            provider="veo", duration=ok, start_image_uuid=None, audio_uuid=None
        )
        assert flags["duration"] == str(ok)


def test_higgsfield_subscribe_response_unwraps_single_job_list() -> None:
    """Regression: `higgsfield generate create --wait --json` returns a LIST.

    Single-clip generations come back as `[{...result_url: ...}]`, not a
    bare dict. Before the fix, `_as_dict` wrapped this as `{"items":[...]}`
    and `extract_video_url` couldn't find the URL, so tenacity retried and
    burned 3× credits per failed run. This test pins the list-unwrap so
    the bug can't silently regress.
    """
    from src.clients.higgsfield import _as_dict, extract_video_url

    cli_response = [
        {
            "id": "abc",
            "status": "completed",
            "result_url": "https://cdn.example.com/clip.mp4",
        }
    ]
    parsed = _as_dict(cli_response)
    assert parsed.get("result_url", "").startswith("http")
    assert extract_video_url(parsed) == "https://cdn.example.com/clip.mp4"


def test_settings_rejects_invalid_veo_clip_duration() -> None:
    """Pydantic must surface a misconfigured VEO duration at startup."""
    from pydantic import ValidationError

    from src.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, veo_clip_duration=7)  # type: ignore[call-arg]
