"""Tests for the references sprint: upload endpoints, pipeline branches, IVC."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.auth import create_token
from src.models import Reference, ScriptOutput
from src.steps.script_generator import REFERENCE_PROMPT_TEMPLATE


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    from src.config import settings

    monkeypatch.setattr(settings, "app_password", "test-password")
    monkeypatch.setattr(settings, "output_dir", tmp_path)
    monkeypatch.setattr(settings, "references_dir", tmp_path / "_uploads")

    import src.api.main as api_main

    monkeypatch.setattr(api_main, "_RUN_STATE", {})
    monkeypatch.setattr(api_main, "_PENDING_REFS", {})
    return TestClient(api_main.app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_upload_persona_reference_persists_file(auth_client: TestClient, tmp_path: Path) -> None:
    token, _ = create_token()
    img = b"\xff\xd8\xff\xe0" + b"\x00" * 2048  # tiny fake jpeg
    r = auth_client.post(
        "/api/references",
        data={"run_id": "20260518-test-aaa", "kind": "persona"},
        files={"file": ("face.jpg", img, "image/jpeg")},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "persona"
    assert body["mime"] == "image/jpeg"
    assert body["bytes"] == len(img)
    assert Path(body["path"]).exists()


def test_upload_rejects_wrong_mime_for_kind(auth_client: TestClient) -> None:
    token, _ = create_token()
    r = auth_client.post(
        "/api/references",
        data={"run_id": "20260518-test-bbb", "kind": "persona"},
        files={"file": ("foo.mp3", b"id3", "audio/mpeg")},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert "not allowed" in r.json()["detail"]


def test_upload_rejects_unknown_kind(auth_client: TestClient) -> None:
    token, _ = create_token()
    r = auth_client.post(
        "/api/references",
        data={"run_id": "20260518-test-ccc", "kind": "bogus"},
        files={"file": ("x.jpg", b"\xff\xd8\xff", "image/jpeg")},
        headers=_auth(token),
    )
    assert r.status_code == 400


def test_list_references_returns_pending_refs(auth_client: TestClient) -> None:
    token, _ = create_token()
    auth_client.post(
        "/api/references",
        data={"run_id": "20260518-test-list", "kind": "persona"},
        files={"file": ("p.jpg", b"\xff\xd8\xff" + b"\x00" * 1024, "image/jpeg")},
        headers=_auth(token),
    )
    r = auth_client.get("/api/references/20260518-test-list", headers=_auth(token))
    assert r.status_code == 200
    refs = r.json()["references"]
    assert len(refs) == 1 and refs[0]["kind"] == "persona"


def test_create_run_drains_pending_references(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ref uploaded before /api/run is reachable should land on the RunResult."""
    token, _ = create_token()

    captured: dict[str, Any] = {}

    async def fake_execute(
        topic: str,
        run_id: str,
        provider: str | None = None,
        burn_subtitles: bool = True,
        references: list[Reference] | None = None,
        pause_after: str | None = None,
        soul_id: str | None = None,
        voiceless: bool = False,
        use_keyframes: bool = False,
    ) -> None:
        captured["topic"] = topic
        captured["run_id"] = run_id
        captured["references"] = list(references or [])
        captured["pause_after"] = pause_after

    import src.api.main as api_main

    monkeypatch.setattr(api_main, "_execute_run", fake_execute)

    # Upload first, with a client-supplied run_id.
    rid = "20260518-test-drain"
    auth_client.post(
        "/api/references",
        data={"run_id": rid, "kind": "persona"},
        files={"file": ("p.jpg", b"\xff\xd8\xff" + b"\x00" * 1024, "image/jpeg")},
        headers=_auth(token),
    )
    r = auth_client.post(
        "/api/run",
        json={"topic": "test", "run_id": rid},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["run_id"] == rid
    assert len(captured["references"]) == 1
    assert captured["references"][0].kind == "persona"


def test_draft_run_sets_pause_after_script_generator(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, _ = create_token()
    captured: dict[str, Any] = {}

    async def fake_execute(
        topic: str,
        run_id: str,
        provider: str | None = None,
        burn_subtitles: bool = True,
        references: list[Reference] | None = None,
        pause_after: str | None = None,
        soul_id: str | None = None,
        voiceless: bool = False,
        use_keyframes: bool = False,
    ) -> None:
        captured["pause_after"] = pause_after

    import src.api.main as api_main

    monkeypatch.setattr(api_main, "_execute_run", fake_execute)

    r = auth_client.post("/api/run/draft", json={"topic": "test"}, headers=_auth(token))
    assert r.status_code == 200
    assert captured["pause_after"] == "script_generator"


def test_confirm_run_requires_script_ready_status(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Confirming a run that isn't paused must 409, not silently restart."""
    token, _ = create_token()

    async def fake_execute(*args: Any, **kwargs: Any) -> None: pass

    import src.api.main as api_main

    monkeypatch.setattr(api_main, "_execute_run", fake_execute)

    r = auth_client.post("/api/run", json={"topic": "test"}, headers=_auth(token))
    rid = r.json()["run_id"]
    # status is still pending — confirming should 409.
    r2 = auth_client.post(
        f"/api/run/{rid}/confirm",
        json={"script": {"hook": "h", "body": "b", "cta": "c", "full_script": "h b c", "caption": "x", "persona_gender": "female"}},
        headers=_auth(token),
    )
    assert r2.status_code == 409


def test_script_generator_injects_transcript_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When a script reference is present, its content must reach Claude's prompt."""
    from src.steps.script_generator import ScriptGeneratorStep

    transcript_path = tmp_path / "ref.txt"
    transcript_path.write_text("THE_QUOTED_TRANSCRIPT_TOKEN", encoding="utf-8")
    ref = Reference(
        kind="script",
        path=transcript_path,
        source_url="https://youtu.be/abc",
        mime="text/plain",
        bytes=transcript_path.stat().st_size,
    )

    captured: dict[str, Any] = {}

    class FakeContent:
        def __init__(self, text: str) -> None:
            self.text = text
            self.type = "text"

    class FakeMessage:
        content = [
            FakeContent(
                '{"hook":"x","body":"y","cta":"z","full_script":"x y z",'
                '"caption":"c","hashtags":[],"visual_prompts":[],'
                '"persona_description":"","persona_gender":"female"}'
            )
        ]

    class FakeMessages:
        async def create(self, **kwargs: Any) -> FakeMessage:
            captured["messages"] = kwargs["messages"]
            return FakeMessage()

    class FakeClient:
        messages = FakeMessages()

    step = ScriptGeneratorStep(client=FakeClient())  # type: ignore[arg-type]
    import asyncio

    ctx: dict[str, Any] = {
        "topic": "x",
        "provider": "kling",
        "references": [ref],
    }
    asyncio.run(step.run(ctx))

    user_content = captured["messages"][0]["content"]
    assert "THE_QUOTED_TRANSCRIPT_TOKEN" in user_content
    assert "REFERENCIAS DE GUION" in user_content
    # Verify template is the reference-aware variant.
    assert "toma el ÁNGULO" in REFERENCE_PROMPT_TEMPLATE


@pytest.mark.asyncio
async def test_video_generator_uses_start_image_when_persona_ref_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_hf_cli: Any
) -> None:
    """A persona ref is uploaded once and reused as --start-image for every clip."""
    from src.config import settings
    from src.steps.video_generator import VideoGeneratorStep

    monkeypatch.setattr(settings, "video_provider", "kling")

    persona = tmp_path / "face.jpg"
    persona.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 2048)
    refs = [Reference(kind="persona", path=persona, mime="image/jpeg", bytes=persona.stat().st_size)]

    step = VideoGeneratorStep(cli=fake_hf_cli)

    script = ScriptOutput(
        hook="h",
        body="b",
        cta="c",
        full_script="h b c",
        caption="x",
        visual_prompts=["clip 1", "clip 2", "clip 3", "clip 4", "clip 5"],
        persona_description="woman",
        persona_gender="female",
    )

    ctx: dict[str, Any] = {
        "script": script,
        "output_dir": tmp_path,
        "provider": "kling",
        "references": refs,
        "style_brief": "",
    }
    out = await step.run(ctx)

    # Persona uploaded once and reused.
    assert len(fake_hf_cli.uploads) == 1
    assert len(fake_hf_cli.generate_calls) == 5
    # Every call goes to the same kling t2v/i2v model and carries start_image.
    for model, args in fake_hf_cli.generate_calls:
        assert model == settings.kling_model
        assert args["start_image"] == "upload-1"
    assert len(out["video_clips"]) == 5


@pytest.mark.asyncio
async def test_video_generator_veo_with_persona_passes_image_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_hf_cli: Any
) -> None:
    """Veo3.1 takes a single --image; persona ref flows there instead of switching providers."""
    from src.config import settings
    from src.steps.video_generator import VideoGeneratorStep

    persona = tmp_path / "face.jpg"
    persona.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 2048)
    refs = [Reference(kind="persona", path=persona, mime="image/jpeg", bytes=persona.stat().st_size)]

    step = VideoGeneratorStep(cli=fake_hf_cli)
    script = ScriptOutput(
        hook="h",
        body="b",
        cta="c",
        full_script="h",
        caption="x",
        visual_prompts=["a", "b", "c"],
        persona_description="p",
        persona_gender="female",
    )

    ctx: dict[str, Any] = {
        "script": script,
        "output_dir": tmp_path,
        "provider": "veo",
        "references": refs,
        "style_brief": "",
    }
    out = await step.run(ctx)
    assert out["video_provider"] == "veo"
    for model, args in fake_hf_cli.generate_calls:
        assert model == settings.veo_model
        assert args["image"] == "upload-1"


def test_youtube_url_detector() -> None:
    from src.utils.youtube import is_youtube_url

    assert is_youtube_url("https://youtu.be/abc1234")
    assert is_youtube_url("https://www.youtube.com/watch?v=ZTXcZQGtZdM")
    assert is_youtube_url("https://youtube.com/shorts/abc1234")
    assert not is_youtube_url("https://vimeo.com/123456")
    assert not is_youtube_url("not a url")


@pytest.mark.asyncio
async def test_voice_generator_clones_and_deletes_voice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A voice ref must trigger ElevenLabs IVC + cleanup via voices.delete."""
    from src.config import settings as cfg
    from src.steps.voice_generator import VoiceGeneratorStep

    monkeypatch.setattr(cfg, "voice_clone_keep", False)
    monkeypatch.setattr(cfg, "elevenlabs_voice_id_female", "preset-female")

    sample = tmp_path / "sample.mp3"
    sample.write_bytes(b"\xff\xfb" + b"\x00" * 4096)  # tiny fake mp3
    ref = Reference(kind="voice", path=sample, mime="audio/mpeg", bytes=sample.stat().st_size)

    calls: dict[str, Any] = {"ivc_args": None, "tts_voice_id": None, "deleted": None}

    class FakeVoice:
        voice_id = "cloned-123"

    class FakeIvc:
        def create(self, **kwargs: Any) -> FakeVoice:
            calls["ivc_args"] = kwargs
            return FakeVoice()

    class FakeVoices:
        ivc = FakeIvc()

        def delete(self, voice_id: str) -> None:
            calls["deleted"] = voice_id

    class FakeTts:
        def convert(self, **kwargs: Any):  # noqa: ANN201
            calls["tts_voice_id"] = kwargs["voice_id"]
            return iter([b"\xff\xfb" + b"\x00" * 2048])

    class FakeClient:
        voices = FakeVoices()
        text_to_speech = FakeTts()

    script = ScriptOutput(
        hook="h", body="b", cta="c", full_script="h b c", caption="x",
        visual_prompts=["v"], persona_description="p", persona_gender="female",
    )

    step = VoiceGeneratorStep(client=FakeClient())
    ctx: dict[str, Any] = {
        "script": script,
        "output_dir": tmp_path,
        "run_id": "test-run",
        "provider": "kling",
        "references": [ref],
    }
    out = await step.run(ctx)

    # IVC was called with the uploaded sample and a per-run name.
    assert calls["ivc_args"] is not None
    assert calls["ivc_args"]["name"] == "reel-test-run"
    # TTS used the cloned voice id, not the gender preset.
    assert calls["tts_voice_id"] == "cloned-123"
    # Cleanup ran with the same id.
    assert calls["deleted"] == "cloned-123"
    assert out["voice"].audio_path.exists()


@pytest.mark.asyncio
async def test_voice_generator_keeps_clone_when_flag_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """voice_clone_keep=True must skip the DELETE call (used for debugging)."""
    from src.config import settings as cfg
    from src.steps.voice_generator import VoiceGeneratorStep

    monkeypatch.setattr(cfg, "voice_clone_keep", True)

    sample = tmp_path / "s.mp3"
    sample.write_bytes(b"\xff\xfb" + b"\x00" * 2048)
    ref = Reference(kind="voice", path=sample, mime="audio/mpeg", bytes=sample.stat().st_size)

    deleted: list[str] = []

    class FakeVoice:
        voice_id = "keepme-456"

    class FakeIvc:
        def create(self, **_: Any) -> FakeVoice:
            return FakeVoice()

    class FakeVoices:
        ivc = FakeIvc()

        def delete(self, voice_id: str) -> None:
            deleted.append(voice_id)

    class FakeTts:
        def convert(self, **_: Any):  # noqa: ANN201
            return iter([b"x"])

    class FakeClient:
        voices = FakeVoices()
        text_to_speech = FakeTts()

    script = ScriptOutput(
        hook="h", body="b", cta="c", full_script="h b c", caption="x",
        visual_prompts=["v"], persona_description="p", persona_gender="female",
    )

    step = VoiceGeneratorStep(client=FakeClient())
    await step.run({
        "script": script, "output_dir": tmp_path, "run_id": "keep",
        "provider": "kling", "references": [ref],
    })
    assert deleted == []


@pytest.mark.asyncio
async def test_style_extractor_writes_brief_from_image_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A style image ref must produce a non-empty style_brief via Claude vision."""
    from src.steps.style_extractor import StyleExtractorStep

    style_img = tmp_path / "look.jpg"
    style_img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 1024)
    ref = Reference(kind="style", path=style_img, mime="image/jpeg", bytes=style_img.stat().st_size)

    captured: dict[str, Any] = {}

    class FakeBlock:
        def __init__(self, text: str) -> None:
            self.text = text
            self.type = "text"

    class FakeMsg:
        content = [FakeBlock("muted teal palette, soft directional window light, 50mm shallow DOF")]

    class FakeMessages:
        async def create(self, **kwargs: Any) -> FakeMsg:
            captured["messages"] = kwargs["messages"]
            return FakeMsg()

    class FakeClient:
        messages = FakeMessages()

    step = StyleExtractorStep(client=FakeClient())  # type: ignore[arg-type]
    ctx: dict[str, Any] = {"references": [ref]}
    out = await step.run(ctx)

    assert "muted teal" in out["style_brief"]
    # The image payload travelled to Claude as a base64 image block.
    content = captured["messages"][0]["content"]
    assert any(b.get("type") == "image" for b in content)


@pytest.mark.asyncio
async def test_video_generator_appends_style_brief_to_each_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_hf_cli: Any
) -> None:
    """The style_brief in context must be appended to every visual_prompt."""
    from src.config import settings as cfg
    from src.steps.video_generator import VideoGeneratorStep

    monkeypatch.setattr(cfg, "video_provider", "kling")

    step = VideoGeneratorStep(cli=fake_hf_cli)
    script = ScriptOutput(
        hook="h", body="b", cta="c", full_script="h",
        caption="x", visual_prompts=["clip A", "clip B", "clip C", "clip D", "clip E"],
        persona_description="p", persona_gender="female",
    )
    await step.run({
        "script": script,
        "output_dir": tmp_path,
        "provider": "kling",
        "references": [],
        "style_brief": "muted teal palette, soft window light",
    })

    assert len(fake_hf_cli.generate_calls) == 5
    for _, args in fake_hf_cli.generate_calls:
        assert "muted teal palette, soft window light" in args["prompt"]
