"""YouTube ingestion via yt-dlp + ffmpeg.

Two consumers:
- `script` references → `fetch_transcript`: pulls the human OR auto-generated
  caption track, falling back from `es` to `en` if Spanish isn't available.
- `voice` references → `fetch_voice_sample`: downloads the bestaudio stream,
  trims to `max_seconds` (default 60s — ElevenLabs IVC's quality sweet spot
  is 30-90s), re-encodes to 44.1 kHz mono MP3.

Both helpers return the local Path to the written file. They raise
`RuntimeError` on failure so the caller can surface a clean error to the API.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_YT_URL_RE = re.compile(
    r"^(https?://)?(www\.|m\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[A-Za-z0-9_-]{6,}",
    flags=re.IGNORECASE,
)


def is_youtube_url(url: str) -> bool:
    return bool(_YT_URL_RE.match(url.strip()))


def fetch_transcript(url: str, dest: Path, *, max_chars: int = 20000) -> Path:
    """Download the caption track and write it as plain text to `dest`."""
    with tempfile.TemporaryDirectory(prefix="yt-transcript-") as tmp:
        tmp_dir = Path(tmp)
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang",
            "es,en",
            "--sub-format",
            "vtt",
            "--convert-subs",
            "vtt",
            "--write-info-json",
            "-o",
            str(tmp_dir / "%(id)s.%(ext)s"),
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"yt-dlp failed to fetch transcript for {url}: {result.stderr.strip()[:500]}"
            )

        vtt_files = sorted(tmp_dir.glob("*.vtt"))
        if not vtt_files:
            raise RuntimeError(
                f"no captions found for {url} — the video may not have subtitles"
            )

        # Prefer es over en, prefer human-written over auto.
        vtt = _pick_best_vtt(vtt_files)
        text = _vtt_to_plain_text(vtt.read_text(encoding="utf-8"))

        info_files = list(tmp_dir.glob("*.info.json"))
        title = ""
        description = ""
        if info_files:
            try:
                info: dict[str, Any] = json.loads(info_files[0].read_text(encoding="utf-8"))
                title = str(info.get("title", "")).strip()
                description = str(info.get("description", "")).strip()
            except (json.JSONDecodeError, OSError):
                pass

        header_parts: list[str] = []
        if title:
            header_parts.append(f"TÍTULO: {title}")
        if description:
            header_parts.append(f"DESCRIPCIÓN: {description[:1000]}")
        if header_parts:
            text = "\n\n".join(header_parts) + "\n\n---\n\n" + text

        text = text[:max_chars]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        return dest


def fetch_voice_sample(url: str, dest: Path, *, max_seconds: int = 60) -> Path:
    """Download the audio track of `url`, trim, re-encode to mp3 at `dest`."""
    with tempfile.TemporaryDirectory(prefix="yt-voice-") as tmp:
        tmp_dir = Path(tmp)
        raw_template = str(tmp_dir / "raw.%(ext)s")
        cmd = [
            "yt-dlp",
            "-f",
            "bestaudio",
            "-o",
            raw_template,
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"yt-dlp failed to fetch audio for {url}: {result.stderr.strip()[:500]}"
            )

        raw_files = [p for p in tmp_dir.iterdir() if p.is_file() and p.name.startswith("raw.")]
        if not raw_files:
            raise RuntimeError(f"yt-dlp returned no audio file for {url}")
        raw = raw_files[0]

        dest.parent.mkdir(parents=True, exist_ok=True)
        ff = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw),
                "-t",
                str(max_seconds),
                "-vn",
                "-acodec",
                "libmp3lame",
                "-ar",
                "44100",
                "-ac",
                "1",
                "-q:a",
                "2",
                str(dest),
            ],
            capture_output=True,
            text=True,
        )
        if ff.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed to encode voice sample: {ff.stderr.strip()[:500]}"
            )
        return dest


def fetch_audio_track(url: str, dest: Path, *, max_seconds: int = 120) -> Path:
    """Download the audio of `url` as stereo MP3 at `dest`.

    Used for the `music` reference kind. Unlike `fetch_voice_sample` (mono,
    60s, tuned for ElevenLabs IVC), here we keep stereo + 192 kbps and allow
    a longer window so the soundtrack can carry a 25-30s reel without
    looping awkwardly.
    """
    with tempfile.TemporaryDirectory(prefix="yt-music-") as tmp:
        tmp_dir = Path(tmp)
        raw_template = str(tmp_dir / "raw.%(ext)s")
        cmd = ["yt-dlp", "-f", "bestaudio", "-o", raw_template, url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"yt-dlp failed to fetch audio for {url}: {result.stderr.strip()[:500]}"
            )

        raw_files = [p for p in tmp_dir.iterdir() if p.is_file() and p.name.startswith("raw.")]
        if not raw_files:
            raise RuntimeError(f"yt-dlp returned no audio file for {url}")
        raw = raw_files[0]

        dest.parent.mkdir(parents=True, exist_ok=True)
        ff = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(raw),
                "-t", str(max_seconds),
                "-vn",
                "-acodec", "libmp3lame",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "192k",
                str(dest),
            ],
            capture_output=True,
            text=True,
        )
        if ff.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed to encode music track: {ff.stderr.strip()[:500]}"
            )
        return dest


def _pick_best_vtt(files: list[Path]) -> Path:
    """Prefer es over en, human-written over auto-generated."""

    def rank(p: Path) -> tuple[int, int]:
        name = p.name.lower()
        lang_rank = 0 if ".es." in name else 1
        auto_rank = 1 if "auto" in name else 0
        return (lang_rank, auto_rank)

    return min(files, key=rank)


def _vtt_to_plain_text(raw: str) -> str:
    """Strip WEBVTT timestamps + tags, leaving just the spoken text."""
    out_lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if "-->" in line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        out_lines.append(line)
    text = " ".join(out_lines)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text
