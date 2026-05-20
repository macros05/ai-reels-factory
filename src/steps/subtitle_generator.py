"""Subtitle generation via whisper-timestamped.

Source audio resolution:
- If a previous step produced `context["voice"]` (ElevenLabs path), transcribe that file.
- Otherwise (Veo provider has native audio embedded per clip) concatenate the audio
  tracks of every clip in `context["video_clips"]` into a single mp3 with ffmpeg and
  transcribe that — this keeps the subtitle timeline aligned with the final assembled
  video.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from src.config import settings
from src.models import SubtitleOutput, SubtitleSegment, VoiceOutput


class SubtitleGeneratorStep:
    """Transcribes the source audio and produces an SRT with word-level timing."""

    name = "subtitle_generator"

    def __init__(self, transcribe_fn: Any | None = None) -> None:
        self._transcribe_fn = transcribe_fn

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        output_dir: Path = context["output_dir"]
        srt_path = output_dir / "subtitles.srt"

        audio_path = await self._resolve_audio(context, output_dir)
        # Feed the script as a transcription hint: Whisper uses it as a prior for
        # vocabulary (proper nouns, acronyms like RRHH, brand names) without forcing
        # the output. Massively improves accuracy on Spanish + brand-heavy scripts.
        script = context.get("script")
        hint = script.full_script if script is not None else None
        logger.info(f"[subtitle_generator] transcribing {audio_path}")

        segments = await asyncio.to_thread(self._transcribe, audio_path, hint)
        _write_srt(srt_path, segments)
        logger.info(f"[subtitle_generator] subtitles ok → {srt_path} ({len(segments)} segments)")

        context["subtitles"] = SubtitleOutput(srt_path=srt_path, segments=segments)
        return context

    async def _resolve_audio(self, context: dict[str, Any], output_dir: Path) -> Path:
        voice: VoiceOutput | None = context.get("voice")
        if voice is not None:
            return voice.audio_path

        clip_paths: list[Path] = context.get("video_clips", [])
        if not clip_paths:
            raise RuntimeError(
                "subtitle_generator: no audio source available — neither voice nor video clips"
            )
        extracted = output_dir / "audio_from_clips.mp3"
        await asyncio.to_thread(_extract_audio_from_clips, clip_paths, extracted)
        return extracted

    def _transcribe(
        self, audio_path: Path, hint: str | None = None
    ) -> list[SubtitleSegment]:
        if self._transcribe_fn is not None:
            return self._transcribe_fn(audio_path)

        import whisper_timestamped as wt

        model = wt.load_model(settings.whisper_model)
        kwargs: dict[str, Any] = {"language": settings.language}
        if hint:
            kwargs["initial_prompt"] = hint[:600]
        result = wt.transcribe(model, str(audio_path), **kwargs)

        words: list[tuple[float, float, str]] = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []) or []:
                text = str(w.get("text", "")).strip()
                if not text:
                    continue
                words.append((float(w["start"]), float(w["end"]), text))
            if not seg.get("words"):
                words.append(
                    (float(seg["start"]), float(seg["end"]), str(seg["text"]).strip())
                )
        return _chunk_words(words, settings.subtitle_max_words_per_chunk)


def _chunk_words(
    words: list[tuple[float, float, str]], max_per_chunk: int
) -> list[SubtitleSegment]:
    """Group word-level timestamps into short, naturally-phrased chunks (1-3 words).

    Breaks at strong punctuation so each chunk reads as a phrase fragment, not a
    blocky wall of text. Karaoke-style — the chunk that's on screen at any moment
    is short enough to read at a glance.
    """
    if not words:
        return []
    segments: list[SubtitleSegment] = []
    buf: list[tuple[float, float, str]] = []
    for w in words:
        buf.append(w)
        ends_phrase = w[2].rstrip().endswith((".", ",", "!", "?", ";", ":"))
        if len(buf) >= max_per_chunk or ends_phrase:
            segments.append(
                SubtitleSegment(
                    start=buf[0][0],
                    end=buf[-1][1],
                    text=" ".join(t for _, _, t in buf).strip(),
                )
            )
            buf = []
    if buf:
        segments.append(
            SubtitleSegment(
                start=buf[0][0],
                end=buf[-1][1],
                text=" ".join(t for _, _, t in buf).strip(),
            )
        )
    return segments


def _extract_audio_from_clips(clip_paths: list[Path], dest: Path) -> None:
    """Concatenate audio tracks of every clip into a single mp3.

    Uses ffmpeg's concat demuxer over an intermediate list file. Re-encodes to
    mp3 so whisper-timestamped can read it reliably regardless of the source
    codec the video provider used.
    """
    import ffmpeg

    list_file = dest.with_suffix(".concat.txt")
    list_file.write_text(
        "\n".join(f"file '{Path(p).resolve()}'" for p in clip_paths),
        encoding="utf-8",
    )
    (
        ffmpeg.input(str(list_file), format="concat", safe=0)
        .output(str(dest), vn=None, acodec="libmp3lame", ar=44100, ac=2)
        .overwrite_output()
        .run(quiet=True)
    )


def _write_srt(path: Path, segments: list[SubtitleSegment]) -> None:
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_fmt(seg.start)} --> {_fmt(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _fmt(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
