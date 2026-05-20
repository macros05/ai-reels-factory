"""Style extraction step: turns one or more reference images/videos into a
short visual brief that gets appended to every clip prompt.

We send up to 3 references to Claude's vision endpoint and ask for a 60-word
prose description of palette, lighting, lens, composition, and mood. For
video references we extract two still frames (1/3 and 2/3 of the way through)
with ffmpeg first — Claude only accepts images.

The brief is stored in `context["style_brief"]`; the video_generator picks it
up and appends it to each visual_prompt before submitting to fal.ai.
"""

from __future__ import annotations

import asyncio
import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from loguru import logger

from src.config import settings
from src.models import Reference

_MAX_REFS = 3
_STYLE_PROMPT = (
    "Eres un director de fotografía. Mira las imágenes y describe el ESTILO "
    "visual que comparten en un párrafo de máximo 60 palabras, en INGLÉS, "
    "listo para añadirlo al final de un prompt de generación de vídeo. "
    "Cubre: paleta de color, tipo de iluminación, óptica (lens / focal / dof), "
    "composición y mood. No describas el contenido (qué hay en la imagen), "
    "solo el estilo. Responde SOLO con el párrafo, sin preámbulos."
)


class StyleExtractorStep:
    """Builds `context['style_brief']` from style references, if any."""

    name = "style_extractor"

    def __init__(self, client: AsyncAnthropic | None = None) -> None:
        self._client = client

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        style_refs: list[Reference] = [
            r for r in context.get("references", []) if r.kind == "style"
        ][:_MAX_REFS]
        if not style_refs:
            logger.info("[style_extractor] no style refs — skipping")
            context["style_brief"] = ""
            return context

        images: list[tuple[str, bytes]] = []
        for ref in style_refs:
            if ref.mime.startswith("image/"):
                images.append((ref.mime, ref.path.read_bytes()))
            elif ref.mime.startswith("video/"):
                images.extend(await asyncio.to_thread(_extract_frames, ref.path))
            else:
                logger.warning(f"[style_extractor] unsupported mime {ref.mime} — skipping")

        if not images:
            context["style_brief"] = ""
            return context

        # Trim to 3 images max even after video frame extraction.
        images = images[:_MAX_REFS]

        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": base64.b64encode(data).decode("ascii"),
                },
            }
            for mime, data in images
        ]
        content.append({"type": "text", "text": _STYLE_PROMPT})

        client = self._get_client()
        message = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=400,
            messages=[{"role": "user", "content": content}],
        )
        brief = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        ).strip()
        logger.info(f"[style_extractor] brief ({len(brief.split())} words): {brief[:120]}…")
        context["style_brief"] = brief
        return context


def _extract_frames(video_path: Path) -> list[tuple[str, bytes]]:
    """Pull 2 still frames (1/3 and 2/3 in) from a reference video."""
    with tempfile.TemporaryDirectory(prefix="style-frames-") as tmp:
        tmp_dir = Path(tmp)
        dur = _probe_duration(video_path)
        offsets = [dur / 3, 2 * dur / 3] if dur > 0 else [0.5, 1.5]
        out: list[tuple[str, bytes]] = []
        for i, t in enumerate(offsets):
            frame = tmp_dir / f"frame_{i}.jpg"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{t:.2f}",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    str(frame),
                ],
                capture_output=True,
                check=False,
            )
            if frame.exists() and frame.stat().st_size > 0:
                out.append(("image/jpeg", frame.read_bytes()))
        return out


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0
