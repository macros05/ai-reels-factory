"""Final assembly via ffmpeg: concat clips + mux/keep audio + (optional) music bed + burn subtitles.

Three audio flows depending on what's in the context:

1. **Voice + music** (Kling/Seedance with ElevenLabs + music ref): voiceover at
   full gain ducks the music via amix with weighted inputs. Music is also
   loudnorm'd so its absolute level matches the voice.
2. **Voice, no music**: as before — single ElevenLabs track + loudnorm.
3. **No voice + music** (e.g. Veo with a music ref overriding native audio):
   the native Veo audio is muted; the music ref becomes the audio track.
4. **No voice, no music** (Veo): keep Veo native audio + loudnorm.

In every case subtitles are burned at the end and loudness lands at IG's
-14 LUFS target so the reel sits at competitive perceived volume in feed.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from src.config import settings
from src.models import AssembledOutput, Reference, ScriptOutput, SubtitleOutput, VoiceOutput


# Music gain (linear, not dB) when mixed UNDER an ElevenLabs voiceover.
# 0.28 = ~-11 dB attenuation — score is clearly audible but doesn't fight the
# voice. Tune via env if needed; this is a "feels right" default tested on
# the IG mobile feed playback level.
_MUSIC_GAIN_UNDER_VOICE = 0.28
# Music gain when there's no voice. Push closer to full to let the score breathe.
_MUSIC_GAIN_SOLO = 0.92


class AssemblerStep:
    """Builds the final reel: concat → audio → burn subtitles → write caption."""

    name = "assembler"

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        script: ScriptOutput = context["script"]
        subs: SubtitleOutput | None = context.get("subtitles")
        output_dir: Path = context["output_dir"]
        clip_paths: list[Path] = context["video_clips"]
        voice: VoiceOutput | None = context.get("voice")

        # Pull any `music` reference dropped by the user. The first one wins
        # — multiple music tracks would just step on each other.
        refs: list[Reference] = context.get("references", []) or []
        music_path: Path | None = next(
            (r.path for r in refs if r.kind == "music"), None
        )

        final_path = output_dir / "video.mp4"
        caption_path = output_dir / "caption.txt"
        script_path = output_dir / "script.json"

        logger.info("[assembler] writing caption.txt and script.json")
        caption_path.write_text(
            script.caption.strip()
            + "\n\n"
            + " ".join(f"#{tag.lstrip('#')}" for tag in script.hashtags),
            encoding="utf-8",
        )
        script_path.write_text(
            json.dumps(script.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(
            f"[assembler] assembling — provider={context.get('video_provider')} "
            f"voice={'yes' if voice else 'embedded'} "
            f"music={'yes' if music_path else 'no'} "
            f"subs={'yes' if subs else 'no'}"
        )
        await asyncio.to_thread(
            _assemble,
            clip_paths=clip_paths,
            audio_path=voice.audio_path if voice else None,
            music_path=music_path,
            srt_path=subs.srt_path if subs else None,
            final_path=final_path,
            output_dir=output_dir,
        )

        logger.info(f"[assembler] final video → {final_path}")
        context["assembled"] = AssembledOutput(final_video_path=final_path)
        context["caption_path"] = caption_path
        return context


def _assemble(
    *,
    clip_paths: list[Path],
    audio_path: Path | None,
    music_path: Path | None,
    srt_path: Path | None,
    final_path: Path,
    output_dir: Path,
) -> None:
    import ffmpeg

    concat_list = output_dir / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{Path(p).resolve()}'" for p in clip_paths),
        encoding="utf-8",
    )

    concat_video = output_dir / "concat.mp4"
    # Scale/crop to the target aspect ratio AND apply a light cinematic grade
    # (slight saturation + contrast lift) so the final reel pops on the IG feed.
    # The grade is intentionally subtle — anything stronger trips the "AI look".
    video_filter = (
        f"scale={settings.video_width}:{settings.video_height}:force_original_aspect_ratio=increase,"
        f"crop={settings.video_width}:{settings.video_height},"
        f"eq=saturation=1.08:contrast=1.05:gamma=1.02"
    )

    # When a music ref is present + no ElevenLabs voiceover (Veo case), we
    # explicitly want to DROP Veo's native audio so the score takes over —
    # otherwise the two would clash. In every other case we preserve native
    # audio so the loudnorm filter at the end has something to normalise.
    drop_native_audio = audio_path is None and music_path is not None

    concat_kwargs: dict[str, Any] = {
        "vf": video_filter,
        "c:v": "libx264",
        "crf": 18,
        "preset": "slow",
        "pix_fmt": "yuv420p",
        "r": 30,
    }
    if audio_path is not None or drop_native_audio:
        # No native audio in the concat — voice + music get added in the
        # final mux pass below.
        concat_kwargs["an"] = None
    else:
        concat_kwargs["c:a"] = "aac"
        concat_kwargs["b:a"] = "192k"

    (
        ffmpeg.input(str(concat_list), format="concat", safe=0)
        .output(str(concat_video), **concat_kwargs)
        .overwrite_output()
        .run(quiet=True)
    )

    video_in = ffmpeg.input(str(concat_video))
    if srt_path is None:
        burned_video = video_in.video
    else:
        subtitle_style = ",".join(
            [
                f"FontName={settings.subtitle_font}",
                f"FontSize={settings.subtitle_font_size}",
                f"PrimaryColour={settings.subtitle_primary_colour}",
                f"OutlineColour={settings.subtitle_outline_colour}",
                f"BackColour={settings.subtitle_back_colour}",
                "BorderStyle=1",
                f"Outline={settings.subtitle_outline}",
                f"Shadow={settings.subtitle_shadow}",
                "Alignment=2",
                f"MarginV={settings.subtitle_margin_v}",
                "MarginL=80",
                "MarginR=80",
                "Bold=0",
                "Spacing=0.5",
            ]
        )
        srt_abs = str(Path(srt_path).resolve())
        burned_video = video_in.video.filter("subtitles", srt_abs, force_style=subtitle_style)

    # Assemble final audio. Branch on (voice?, music?):
    final_audio = _build_audio_chain(
        ffmpeg=ffmpeg,
        video_in=video_in,
        voice_path=audio_path,
        music_path=music_path,
        drop_native_audio=drop_native_audio,
    )

    output_kwargs: dict[str, Any] = {
        "vcodec": "libx264",
        "crf": 18,
        "preset": "slow",
        "acodec": "aac",
        "audio_bitrate": "192k",
        "pix_fmt": "yuv420p",
        "movflags": "+faststart",
    }
    # Anchor duration to the video stream so a long music track gets trimmed
    # to clip length rather than the other way around.
    if audio_path is not None or music_path is not None:
        output_kwargs["shortest"] = None

    (
        ffmpeg.output(burned_video, final_audio, str(final_path), **output_kwargs)
        .overwrite_output()
        .run(quiet=True)
    )


def _build_audio_chain(
    *,
    ffmpeg: Any,
    video_in: Any,
    voice_path: Path | None,
    music_path: Path | None,
    drop_native_audio: bool,
) -> Any:
    """Return the ffmpeg audio node to mux into the final output.

    Three branches:
    1. voice + music → amix the two, voice at full, music attenuated.
    2. voice only   → loudnorm the voice (existing behaviour).
    3. music only   → loudnorm the music, anchored to video length.
    4. nothing      → loudnorm the native audio of the concat (Veo path).
    """
    # Branch 1: voice + music → ducked amix
    if voice_path is not None and music_path is not None:
        # NOTE: don't pre-loudnorm the voice stream. Stacking the per-stream
        # loudnorm in front of amix + duration=first + outer loudnorm chewed
        # ~3s off the tail of the mix because loudnorm's lookahead buffer
        # collides with amix's duration-clamping. One loudnorm at the end
        # is enough and predictable.
        voice = ffmpeg.input(str(voice_path)).audio
        # Music: fade-in/fade-out so the score doesn't pop in or cut abruptly,
        # then attenuate so the voice sits clearly on top.
        music = (
            ffmpeg.input(str(music_path))
            .audio.filter("afade", t="in", st=0, d=0.6)
            .filter("afade", t="out", st=27, d=2.5)  # fade-out tail near reel end
            .filter("volume", _MUSIC_GAIN_UNDER_VOICE)
        )
        # duration=longest so a voiceover shorter than the reel doesn't
        # truncate the final mix to the voice length — the music carries
        # the rest of the timeline until -shortest anchors to the video.
        mixed = ffmpeg.filter(
            [voice, music], "amix", inputs=2, duration="longest", normalize=0
        )
        return mixed.filter("loudnorm", I=-14, LRA=11, TP=-1.0)

    # Branch 2: voice only
    if voice_path is not None:
        return ffmpeg.input(str(voice_path)).audio.filter(
            "loudnorm", I=-14, LRA=11, TP=-1.0
        )

    # Branch 3: music only (replaces native — e.g. Veo + music ref)
    if music_path is not None:
        return (
            ffmpeg.input(str(music_path))
            .audio.filter("afade", t="in", st=0, d=0.6)
            .filter("afade", t="out", st=27, d=2.5)
            .filter("volume", _MUSIC_GAIN_SOLO)
            .filter("loudnorm", I=-14, LRA=11, TP=-1.0)
        )

    # Branch 4: native audio passthrough with normalisation (Veo, no music)
    _ = drop_native_audio  # unused in this branch; declared to keep linter happy
    return video_in.audio.filter("loudnorm", I=-14, LRA=11, TP=-1.0)
