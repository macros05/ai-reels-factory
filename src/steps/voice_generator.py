"""Voice synthesis via ElevenLabs."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from loguru import logger

from src.config import settings
from src.models import ScriptOutput, VoiceOutput


class VoiceGeneratorStep:
    """Generates the voiceover audio file for the script."""

    name = "voice_generator"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from elevenlabs.client import ElevenLabs

            self._client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        return self._client

    def _clone_voice(self, sample_path: Path, run_id: str) -> str:
        """ElevenLabs Instant Voice Cloning: upload a short sample → voice_id.

        We name the clone after the run so it's easy to spot in the dashboard
        if cleanup ever fails. ElevenLabs IVC accepts 1-25 audio files; we send
        the single sample produced by `fetch_voice_sample` or uploaded by the
        user (60 s, mono mp3 — comfortably in the recommended 30-90 s band).
        """
        client = self._get_client()
        with open(sample_path, "rb") as fh:
            voice = client.voices.ivc.create(
                name=f"reel-{run_id}",
                description=f"per-run clone for {run_id}",
                files=[fh],
            )
        return voice.voice_id

    def _delete_voice(self, voice_id: str) -> None:
        try:
            self._get_client().voices.delete(voice_id=voice_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[voice_generator] failed to delete cloned voice {voice_id}: {exc}")

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        script: ScriptOutput = context["script"]
        output_dir: Path = context["output_dir"]
        run_id: str = context.get("run_id", output_dir.name)
        audio_path = output_dir / "audio.mp3"

        voice_refs = [r for r in context.get("references", []) if r.kind == "voice"]
        cloned_voice_id: str | None = None
        if voice_refs:
            cloned_voice_id = await asyncio.to_thread(
                self._clone_voice, voice_refs[0].path, run_id
            )
            voice_id = cloned_voice_id
            logger.info(
                f"[voice_generator] using cloned voice id={voice_id} "
                f"(source={voice_refs[0].path.name})"
            )
        else:
            voice_id = _pick_voice_id(script.persona_gender)
            logger.info(
                f"[voice_generator] synthesizing via ElevenLabs "
                f"model={settings.elevenlabs_model} gender={script.persona_gender} voice={voice_id}"
            )

        clean_text = _preprocess_text(script.full_script)

        def _synthesize() -> None:
            client = self._get_client()
            stream = client.text_to_speech.convert(
                voice_id=voice_id,
                model_id=settings.elevenlabs_model,
                text=clean_text,
                output_format=settings.elevenlabs_output_format,
                voice_settings={
                    "stability": settings.elevenlabs_stability,
                    "similarity_boost": settings.elevenlabs_similarity_boost,
                    "style": settings.elevenlabs_style,
                    "use_speaker_boost": settings.elevenlabs_use_speaker_boost,
                },
            )
            with audio_path.open("wb") as fh:
                for chunk in stream:
                    if chunk:
                        fh.write(chunk)

        try:
            await asyncio.to_thread(_synthesize)
        finally:
            if cloned_voice_id and not settings.voice_clone_keep:
                # Tidy up — the cloned voice was per-run; don't leave it in the
                # user's voice library forever.
                await asyncio.to_thread(self._delete_voice, cloned_voice_id)

        duration = await _probe_duration(audio_path)

        provider = context.get("provider", settings.video_provider)
        target = settings.clip_count_for(provider) * settings.clip_duration_for(provider)
        if duration > target + 0.2:
            speedup = min(duration / target, _MAX_ATEMPO)
            fitted = output_dir / "audio_fitted.mp3"
            await asyncio.to_thread(_atempo, audio_path, fitted, speedup)
            audio_path.unlink()
            fitted.rename(audio_path)
            new_duration = await _probe_duration(audio_path)
            logger.info(
                f"[voice_generator] audio fitted via atempo={speedup:.3f}x: "
                f"{duration:.2f}s → {new_duration:.2f}s (target {target}s)"
            )
            duration = new_duration
        else:
            logger.info(f"[voice_generator] audio ok — {duration:.2f}s — {audio_path}")

        context["voice"] = VoiceOutput(audio_path=audio_path, duration_seconds=duration)
        return context


_MARKDOWN_INLINE_RE = re.compile(r"(\*\*|__|\*|_|`|~~)")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+", flags=re.MULTILINE)
_ELLIPSIS_RE = re.compile(r"\.{3,}|…")
_DASH_RE = re.compile(r"\s*[—–]\s*")
_PUNCT_NO_SPACE_RE = re.compile(r"([,.!?;:])(?=[^\s\d])")
_MULTI_WS_RE = re.compile(r"[ \t]{2,}")


def _preprocess_text(text: str) -> str:
    """Normalize the script before sending it to ElevenLabs.

    eleven_v3 does not need SSML and sometimes reads it literally — keep it
    plain. We strip markdown noise, collapse ellipses to a final period (so
    the model lands the sentence instead of trailing off), ensure punctuation
    has a trailing space, and convert em/en-dashes to commas to keep the
    prosody flowing.
    """
    out = text
    out = _HEADING_RE.sub("", out)
    out = _MARKDOWN_INLINE_RE.sub("", out)
    out = _ELLIPSIS_RE.sub(".", out)
    out = _DASH_RE.sub(", ", out)
    out = _PUNCT_NO_SPACE_RE.sub(r"\1 ", out)
    out = _MULTI_WS_RE.sub(" ", out)
    return out.strip()


def _pick_voice_id(gender: str) -> str:
    """Choose the voice_id matching the persona's gender, with sensible fallbacks."""
    if gender == "male" and settings.elevenlabs_voice_id_male:
        return settings.elevenlabs_voice_id_male
    if gender == "female" and settings.elevenlabs_voice_id_female:
        return settings.elevenlabs_voice_id_female
    return (
        settings.elevenlabs_voice_id
        or settings.elevenlabs_voice_id_female
        or settings.elevenlabs_voice_id_male
    )


async def _probe_duration(path: Path) -> float:
    """Best-effort duration probe via ffprobe; returns 0.0 if unavailable."""

    def _probe() -> float:
        import ffmpeg

        try:
            info = ffmpeg.probe(str(path))
            return float(info["format"]["duration"])
        except Exception:
            return 0.0

    return await asyncio.to_thread(_probe)


_MAX_ATEMPO = 1.25


def _atempo(source: Path, dest: Path, ratio: float) -> None:
    """Speed up `source` by `ratio`× without changing pitch.

    Used when ElevenLabs overshoots the script's nominal word-rate budget and
    the audio would otherwise run past the video timeline (the assembler's
    `-shortest` would silently truncate the CTA). atempo preserves pitch up
    to ~1.25x; beyond that the voice starts sounding rushed, so the caller
    caps the ratio.
    """
    import ffmpeg

    (
        ffmpeg.input(str(source))
        .output(
            str(dest),
            af=f"atempo={ratio:.4f}",
            acodec="libmp3lame",
            ar=44100,
            ac=2,
            **{"q:a": 2},
        )
        .overwrite_output()
        .run(quiet=True)
    )
