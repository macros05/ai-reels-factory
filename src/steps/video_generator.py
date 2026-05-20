"""Video clip generation via the Higgsfield CLI.

Supported providers (selected via VIDEO_PROVIDER env var):

- veo       → Google Veo 3.1 (`veo3_1`) — 8s clips with NATIVE audio, 3 clips.
              Skips ElevenLabs voice generation downstream.
- kling     → Kling v3.0 (`kling3_0`) — 5s clips, 5 clips, lip-sync inline via --audio.
- seedance  → ByteDance Seedance 2.0 (`seedance_2_0`) — 5s clips, 5 clips,
              lip-sync inline via --audio. Cheapest, default.

For kling / seedance we *fuse* what used to be the separate lipsync step into
this one call: the ElevenLabs voiceover is sliced per clip, each segment is
uploaded to Higgsfield, and the audio UUID is passed alongside the persona
start-image, so the model generates a lip-synced clip in a single shot
instead of (a) generating then (b) calling a separate lipsync model.

If a `soul_id` is present in the context, we first materialise one persona
still per clip with `text2image_soul_v2 --soul-id <id> --prompt <visual_prompt>`
and feed that still as `--start-image`. This is how we get the same face
across all clips — what Kling text-to-video alone could never deliver.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from src.clients.higgsfield import (
    HiggsfieldCLI,
    download_to_path,
    extract_video_url,
    get_higgsfield_cli,
)
from src.config import VideoProvider, settings
from src.models import ScriptOutput, ShotPlan, VoiceOutput


class VideoGeneratorStep:
    """Generates vertical clips via the Higgsfield CLI for the chosen provider."""

    name = "video_generator"

    def __init__(self, cli: HiggsfieldCLI | None = None) -> None:
        self._cli = cli

    def _get_cli(self) -> HiggsfieldCLI:
        if self._cli is None:
            self._cli = get_higgsfield_cli()
        return self._cli

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        script: ScriptOutput = context["script"]
        output_dir: Path = context["output_dir"]
        clips_dir = output_dir / "clips"
        segments_dir = output_dir / "audio_segments"
        stills_dir = output_dir / "stills"
        clips_dir.mkdir(parents=True, exist_ok=True)

        provider: VideoProvider = context.get("provider", settings.video_provider)
        persona_refs = [r for r in context.get("references", []) if r.kind == "persona"]
        soul_id: str | None = context.get("soul_id")

        # Veo only takes a single input_image (i2v) — no Soul-ID per-clip
        # workflow makes sense, and a persona ref also funnels through a
        # single still. If the user picked Veo + Soul ID, swap to kling so
        # they actually get per-clip Soul stills (the whole point of Soul).
        if soul_id and provider == "veo":
            logger.warning(
                "[video_generator] veo doesn't drive Soul-ID per-clip; "
                "switching provider to kling"
            )
            provider = "kling"
        # Veo doesn't accept arbitrary audio input; if a persona ref forced
        # the audio path to matter, we'd still skip kling-style lipsync for
        # Veo. Both cases are below.

        num_clips = settings.clip_count_for(provider)
        clip_duration = settings.clip_duration_for(provider)

        style_brief = context.get("style_brief", "").strip()
        plan: ShotPlan | None = context.get("shot_plan")
        # Prefer the director's final_prompt per shot when available; fall
        # back to the script's visual_prompts so older runs still work.
        # The director already folds style_brief into each final_prompt (see
        # DirectorStep.docstring), so when we're using the plan we must NOT
        # append style_brief again — doing so duplicates the entire style
        # paragraph in the prompt and blows past Kling's ~512-token limit
        # (the resulting HTTP 500 was the symptom).
        used_director_prompts = False
        if plan and plan.shots:
            prompts = [
                (s.final_prompt or "").strip() for s in plan.shots[:num_clips]
            ]
            used_director_prompts = True
            # Backfill any empty director prompt from the script (defensive
            # for runs where the director soft-failed on a single shot).
            for i, p in enumerate(prompts):
                if not p:
                    backup = (
                        script.visual_prompts[i]
                        if i < len(script.visual_prompts)
                        else script.persona_description
                    )
                    prompts[i] = backup
                    used_director_prompts = False  # backfilled prompt lacks style
        else:
            prompts = list(script.visual_prompts[:num_clips])
        if len(prompts) < num_clips:
            fallback = prompts[-1] if prompts else script.persona_description
            prompts.extend([fallback] * (num_clips - len(prompts)))
        if style_brief and not used_director_prompts:
            prompts = [f"{p.rstrip('. ')}. {style_brief}" for p in prompts]
        # Belt-and-braces: clamp any prompt that somehow grew past Kling's
        # safe size so a stray long prompt can't 500 the whole pipeline.
        MAX_PROMPT_CHARS = 2000
        prompts = [
            (p if len(p) <= MAX_PROMPT_CHARS else p[:MAX_PROMPT_CHARS])
            for p in prompts
        ]

        cli = self._get_cli()

        # ----- audio segments (drives in-call lip-sync for kling/seedance) -----
        voice: VoiceOutput | None = context.get("voice")
        audio_uuids: list[str | None] = [None] * num_clips
        if voice and provider != "veo":
            segments_dir.mkdir(parents=True, exist_ok=True)
            logger.info(
                f"[video_generator] slicing voiceover into {num_clips}×{clip_duration}s "
                f"for inline lip-sync"
            )
            segment_paths: list[Path] = []
            for idx in range(num_clips):
                segment_path = segments_dir / f"segment_{idx:02d}.mp3"
                await asyncio.to_thread(
                    _slice_audio,
                    source=voice.audio_path,
                    dest=segment_path,
                    start_seconds=idx * clip_duration,
                    duration_seconds=clip_duration,
                )
                segment_paths.append(segment_path)
            audio_uuids = list(
                await asyncio.gather(*(cli.upload(p) for p in segment_paths))
            )

        # ----- per-clip start image (persona ref, Soul-ID still, or NBP keyframe) -----
        # `start_image_uuids[i]` is the UUID to pass as --start-image for clip i,
        # or None for pure t2v. Resolution order:
        #   1. soul_id present  → text2image_soul_v2 per-clip still (per-scene face lock)
        #   2. context['use_keyframes'] = True  → Nano Banana Pro per-clip keyframe
        #      (unlimited tier on Ultra plan, so this controls composition for free
        #      and dramatically improves Kling i2v output quality vs pure t2v)
        #   3. persona_refs present  → upload + reuse single image for every clip
        #   4. fallback  → pure text-to-video, no start-image
        start_image_uuids: list[str | None] = [None] * num_clips
        use_keyframes: bool = bool(context.get("use_keyframes", False))
        if soul_id:
            stills_dir.mkdir(parents=True, exist_ok=True)
            start_image_uuids = await self._generate_soul_stills(
                cli=cli,
                soul_id=soul_id,
                prompts=prompts,
                persona_desc=script.persona_description,
                stills_dir=stills_dir,
            )
        elif use_keyframes:
            stills_dir.mkdir(parents=True, exist_ok=True)
            start_image_uuids = await self._generate_nbp_keyframes(
                cli=cli,
                prompts=prompts,
                stills_dir=stills_dir,
            )
        elif persona_refs:
            # Single persona photo, reused as start-image for every clip.
            shared_uuid = await cli.upload(persona_refs[0].path)
            logger.info(
                f"[video_generator] reusing persona ref {persona_refs[0].path.name} "
                f"as start-image for all {num_clips} clips"
            )
            start_image_uuids = [shared_uuid] * num_clips

        logger.info(
            f"[video_generator] provider={provider} model={settings.cli_model_for(provider)} "
            f"clips={num_clips} duration={clip_duration}s "
            f"start_image={'yes' if any(start_image_uuids) else 'no'} "
            f"keyframes={'NBP' if use_keyframes else ('soul' if soul_id else ('persona' if persona_refs else 'none'))} "
            f"audio={'yes' if any(audio_uuids) else 'no'} style_brief={'yes' if style_brief else 'no'}"
        )

        tasks = [
            self._generate_clip(
                provider=provider,
                prompt=prompt,
                index=idx,
                clips_dir=clips_dir,
                duration=clip_duration,
                start_image_uuid=start_image_uuids[idx],
                audio_uuid=audio_uuids[idx],
                cli=cli,
            )
            for idx, prompt in enumerate(prompts)
        ]
        clip_paths: list[Path] = await asyncio.gather(*tasks)

        context["video_clips"] = clip_paths
        context["video_provider"] = provider
        context["video_clip_duration"] = clip_duration

        if provider == "veo":
            context["skip_voice_generation"] = True
            logger.info("[video_generator] Veo includes native audio — ElevenLabs skipped")
        # Lip-sync is fused into the video generation call for kling/seedance,
        # native for Veo. The legacy lipsync step is always a no-op now.
        context["skip_lipsync"] = True

        return context

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    async def _generate_nbp_keyframes(
        self,
        *,
        cli: HiggsfieldCLI,
        prompts: list[str],
        stills_dir: Path,
    ) -> list[str | None]:
        """One Nano-Banana-Pro keyframe per clip, uploaded back as UUID.

        NBP is on the unlimited tier of Ultra plan, so every still is free.
        Generating the keyframe ourselves gives us total control over the
        first frame composition — wider shots, naturalistic framing, exact
        product placements — instead of letting Kling text-to-video guess.
        Kling then animates from this exact keyframe via image-to-video,
        which is the architecture the Higgsfield docs themselves recommend
        for production-grade ads.
        """
        async def _one(idx: int, scene_prompt: str) -> str:
            logger.info(
                f"[video_generator] NBP keyframe {idx} ← {scene_prompt[:80]}…"
            )
            result = await cli.generate(
                "nano_banana_2",
                prompt=scene_prompt,
                aspect_ratio="9:16",
                resolution="2k",
                wait=True,
                wait_timeout="5m",
            )
            url = _extract_image_url(result)
            local = stills_dir / f"keyframe_{idx:02d}.png"
            await download_to_path(url, local)
            return await cli.upload(local)

        return list(await asyncio.gather(
            *(_one(idx, p) for idx, p in enumerate(prompts))
        ))

    async def _generate_soul_stills(
        self,
        *,
        cli: HiggsfieldCLI,
        soul_id: str,
        prompts: list[str],
        persona_desc: str,
        stills_dir: Path,
    ) -> list[str | None]:
        """One persona still per clip via text2image_soul_v2 + soul_id.

        We prepend the persona description from the script so the Soul-ID
        face is placed in a scene that matches the clip's visual prompt
        (e.g. "wearing a blue suit in an office" vs "running on a beach").
        Returns a list of upload UUIDs ready to use as --start-image.
        """
        async def _one(idx: int, scene_prompt: str) -> str:
            still_prompt = f"{persona_desc}. {scene_prompt}".strip(". ").rstrip(".")
            logger.info(
                f"[video_generator] soul-id still {idx} ← {still_prompt[:80]}…"
            )
            result = await cli.generate(
                settings.soul_image_model,
                prompt=still_prompt,
                soul_id=soul_id,
                aspect_ratio="9:16",
                wait=True,
                wait_timeout="10m",
            )
            url = _extract_image_url(result)
            local = stills_dir / f"still_{idx:02d}.jpg"
            await download_to_path(url, local)
            return await cli.upload(local)

        return list(await asyncio.gather(
            *(_one(idx, p) for idx, p in enumerate(prompts))
        ))

    async def _generate_clip(
        self,
        *,
        provider: VideoProvider,
        prompt: str,
        index: int,
        clips_dir: Path,
        duration: int,
        start_image_uuid: str | None,
        audio_uuid: str | None,
        cli: HiggsfieldCLI,
    ) -> Path:
        flags = _build_clip_flags(
            provider=provider,
            duration=duration,
            start_image_uuid=start_image_uuid,
            audio_uuid=audio_uuid,
        )
        motion_prompt = f"{prompt.rstrip('. ')}. {settings.motion_prompt_suffix}"
        logger.info(
            f"[video_generator] {provider} clip {index} "
            f"{'(i2v)' if start_image_uuid else '(t2v)'} "
            f"{'+ audio' if audio_uuid else ''} → {prompt[:80]}…"
        )

        result = await cli.generate(
            settings.cli_model_for(provider),
            prompt=motion_prompt,
            wait=True,
            wait_timeout="20m",
            **flags,
        )

        video_url = extract_video_url(result)
        clip_path = clips_dir / f"clip_{index:02d}.mp4"
        await download_to_path(video_url, clip_path)
        logger.info(f"[video_generator] {provider} clip {index} saved → {clip_path}")
        return clip_path


VEO_ALLOWED_DURATIONS: frozenset[int] = frozenset({4, 6, 8})


def _build_clip_flags(
    *,
    provider: VideoProvider,
    duration: int,
    start_image_uuid: str | None,
    audio_uuid: str | None,
) -> dict[str, Any]:
    """Return the **kwargs dict passed to `HiggsfieldCLI.generate`.

    Keep this separate from the request runner so we can unit-test the exact
    flag mapping per provider — that's where the bugs hide.
    """
    flags: dict[str, Any] = {"aspect_ratio": "9:16"}

    if provider == "veo":
        if duration not in VEO_ALLOWED_DURATIONS:
            raise ValueError(
                f"veo duration must be one of {sorted(VEO_ALLOWED_DURATIONS)}, got {duration}"
            )
        flags["duration"] = str(duration)
        flags["model"] = settings.veo_variant
        flags["quality"] = settings.veo_quality
        if start_image_uuid:
            # Veo's input_image slot — we feed it as --image (single).
            flags["image"] = start_image_uuid
        # Veo doesn't accept arbitrary audio injection in this version.
        return flags

    if provider == "kling":
        flags["duration"] = duration
        flags["mode"] = settings.kling_mode
        # Always silence Kling's native audio. We control the final audio
        # track in the assembler (voiceover + music). Letting Kling generate
        # ambient noise it invents from the prompt clashes with whatever we
        # layer on top.
        flags["sound"] = "off"
        if start_image_uuid:
            flags["start_image"] = start_image_uuid
            # NOTE (2026-05-19): kling3_0 returns an instant HTTP 500 when
            # --audio and --start-image are passed together. Skip --audio in
            # i2v mode and let the assembler layer voice+music after the fact
            # (same path cinematic_studio_v2 uses). Pure t2v mode (no
            # start_image) still accepts --audio for inline lip-sync.
        elif audio_uuid:
            flags["audio"] = audio_uuid
        return flags

    if provider == "seedance":
        flags["duration"] = duration
        flags["mode"] = settings.seedance_mode
        flags["resolution"] = settings.seedance_resolution
        if start_image_uuid:
            flags["start_image"] = start_image_uuid
        if audio_uuid:
            flags["audio"] = audio_uuid
        return flags

    if provider == "cinematic_studio_v2":
        # cinematic_studio_video_v2 is a pure t2v/i2v model — it does NOT
        # accept --audio. The assembler layers ElevenLabs voice + music ref
        # over the silent clips post-hoc, which is exactly what we want for
        # an intimate-monologue reel where the narrator can't be lip-synced
        # to anything anyway.
        flags["duration"] = duration
        flags["mode"] = settings.cinematic_studio_mode
        flags["genre"] = settings.cinematic_studio_genre
        if start_image_uuid:
            flags["start_image"] = start_image_uuid
        return flags

    raise ValueError(f"unknown video provider: {provider}")


def _extract_image_url(result: dict[str, Any]) -> str:
    """Pull an image URL out of an image-gen `--wait` result.

    The Higgsfield CLI returns image jobs with `result_url` at the top
    level (PNG / JPG URL). We accept several shapes for robustness in
    case the CLI evolves: top-level `result_url`/`url`/`image_url`,
    `images[0].url`, `items[0].result_url` (the list-unwrapped form),
    and the nested `jobs[0].result.url` shape used by older endpoints.
    """
    images = result.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict) and isinstance(first.get("url"), str):
            return str(first["url"])
        if isinstance(first, str) and first.startswith("http"):
            return first
    for key in ("image_url", "result_url", "url"):
        val = result.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    items = result.get("items")
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            for key in ("result_url", "url"):
                v = first.get(key)
                if isinstance(v, str) and v.startswith("http"):
                    return v
    jobs = result.get("jobs")
    if isinstance(jobs, list) and jobs:
        first = jobs[0]
        if isinstance(first, dict):
            for key in ("result_url", "url"):
                if isinstance(first.get(key), str):
                    return str(first[key])
            res = first.get("result")
            if isinstance(res, dict):
                if isinstance(res.get("url"), str):
                    return str(res["url"])
                imgs = res.get("images")
                if isinstance(imgs, list) and imgs:
                    head = imgs[0]
                    if isinstance(head, dict) and isinstance(head.get("url"), str):
                        return str(head["url"])
    raise RuntimeError(f"could not find image URL in image-gen result: {result!r}")


def _slice_audio(
    *, source: Path, dest: Path, start_seconds: int, duration_seconds: int
) -> None:
    """Cut [start, start+duration) from `source` into `dest`, padding with silence.

    ElevenLabs frequently emits audio shorter than `num_clips * clip_duration`
    (e.g. 19.8s when the pipeline expects 25s). A naive `-ss 20 -t 5` on a
    19.8s source produces a near-empty mp3, which Higgsfield would reject
    just like fal.ai did. The `apad,atrim` chain pads with trailing silence
    to at least `start+duration` seconds then trims to exactly `duration`
    seconds, so every segment is a valid mp3 of the expected length
    regardless of how short the upstream voiceover came out.
    """
    import ffmpeg

    total_seconds = start_seconds + duration_seconds
    filter_chain = (
        f"apad=whole_dur={total_seconds},"
        f"atrim=start={start_seconds}:duration={duration_seconds},"
        f"asetpts=PTS-STARTPTS"
    )
    (
        ffmpeg.input(str(source))
        .output(
            str(dest),
            af=filter_chain,
            acodec="libmp3lame",
            ar=44100,
            ac=2,
            **{"q:a": 2},
        )
        .overwrite_output()
        .run(quiet=True)
    )

    _validate_segment(dest, expected_duration=duration_seconds)


def _validate_segment(path: Path, *, expected_duration: int) -> None:
    """Reject segments Higgsfield will refuse before we waste an upload.

    Catches the failure mode that used to trigger fal.ai's "Failed to read
    audio metadata": a near-empty mp3 whose duration is unreadable. Same
    sanity check still applies to Higgsfield uploads.
    """
    import subprocess

    if not path.exists() or path.stat().st_size < 1024:
        size = path.stat().st_size if path.exists() else 0
        raise RuntimeError(
            f"audio segment {path.name} is invalid ({size} bytes) — "
            f"ffmpeg slice produced no decodable audio"
        )
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
    raw = result.stdout.strip()
    if result.returncode != 0 or not raw:
        raise RuntimeError(
            f"audio segment {path.name} has unreadable metadata (ffprobe rc="
            f"{result.returncode}, stderr={result.stderr.strip()!r})"
        )
    actual = float(raw)
    if actual < expected_duration - 0.5:
        raise RuntimeError(
            f"audio segment {path.name} too short: {actual:.2f}s "
            f"(expected ~{expected_duration}s)"
        )
