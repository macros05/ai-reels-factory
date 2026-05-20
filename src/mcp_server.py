"""MCP server exposing the reels pipeline as tools.

Lets Claude (Claude Desktop, Claude Code, any MCP client) orchestrate the
whole pipeline directly — kick off reels, inspect runs, read scripts, refine
the director's shot plan frame-by-frame.

Add this to your Claude Desktop config (`claude_desktop_config.json`):

    {
      "mcpServers": {
        "ai-reels-factory": {
          "command": "uv",
          "args": ["run", "reels-mcp"],
          "cwd": "/absolute/path/to/ai-reels-factory"
        }
      }
    }

Then ask Claude: "Crea un reel sobre cómo dormir mejor sin pastillas, con
mood intimista y paleta cálida; cuando esté el shot plan revísamelo y
afina el shot 2 para que sea un wide shot al amanecer."

Why this layer (and not just curl the FastAPI)? Because:
- Tools are typed, with JSON schemas — Claude won't guess endpoint shapes.
- Each tool wraps the auth + persistence dance so the LLM works at the
  business-domain level (a "reel", a "shot"), not HTTP.
- The same logic remains testable from Python and the same Pipeline class
  that the web frontend uses.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic
from loguru import logger

from src.config import VideoProvider, settings
from src.models import (
    CreativeBrief,
    Reference,
    RunResult,
    RunStatus,
    Shot,
    ShotPlan,
)
from src.pipeline import Pipeline

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - guarded
    raise SystemExit(
        "The `mcp` package is missing. Install with `uv sync` or "
        "`pip install mcp>=1.2.0`."
    ) from exc


mcp = FastMCP("ai-reels-factory")


def _persist(result: RunResult) -> None:
    out = result.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")


def _load_run(run_id: str) -> RunResult | None:
    p = settings.output_dir / run_id / "result.json"
    if not p.exists():
        return None
    try:
        return RunResult.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:
        return None


@mcp.tool()
async def list_runs() -> dict[str, Any]:
    """List every reel run on disk (newest first).

    Returns the same summary the web frontend shows: run_id, topic, status,
    provider, current step, and whether the final video file exists.
    """
    out_dir = settings.output_dir
    if not out_dir.exists():
        return {"runs": []}
    items: list[dict[str, Any]] = []
    for run_dir in sorted(out_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        f = run_dir / "result.json"
        if not f.exists():
            continue
        try:
            r = RunResult.model_validate_json(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        items.append(
            {
                "run_id": r.run_id,
                "topic": r.topic,
                "status": r.status.value,
                "provider": r.provider,
                "created_at": r.created_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "has_video": r.final_video_path is not None
                and Path(r.final_video_path).exists(),
                "has_shot_plan": r.shot_plan is not None,
            }
        )
    return {"runs": items}


@mcp.tool()
async def get_run(run_id: str) -> dict[str, Any]:
    """Fetch the full details of a run, including script, shot_plan and brief."""
    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    return r.model_dump(mode="json")


@mcp.tool()
async def create_reel(
    topic: str,
    provider: str = "seedance",
    audience: str | None = None,
    tone: list[str] | None = None,
    mood: list[str] | None = None,
    visual_vibe: list[str] | None = None,
    palette: str | None = None,
    cta_goal: str | None = None,
    extra_notes: str | None = None,
    soul_id: str | None = None,
    voiceless: bool = False,
    use_keyframes: bool = False,
) -> dict[str, Any]:
    """Create a new reel end-to-end.

    Runs the pipeline in the background and returns the new `run_id` along
    with a polling URL. Use `get_run` to inspect progress, `get_shot_plan`
    to read the director's plan once the `director` step completes.

    `provider` must be one of: seedance | kling | veo | cinematic_studio_v2.
    `tone`, `mood` and `visual_vibe` accept short tag lists (e.g. tone =
    ["calm", "confident"], mood = ["intimate"], visual_vibe = ["warm",
    "filmic", "shallow dof"]).
    """
    if not topic.strip():
        return {"error": "topic is required"}
    valid_providers: set[str] = {"seedance", "kling", "veo", "cinematic_studio_v2"}
    if provider not in valid_providers:
        return {
            "error": f"provider {provider!r} not in {sorted(valid_providers)}",
        }

    brief = CreativeBrief(
        topic=topic,
        audience=audience,
        tone=list(tone or []),
        mood=list(mood or []),
        visual_vibe=list(visual_vibe or []),
        palette=palette,
        cta_goal=cta_goal,
        extra_notes=extra_notes,
    )

    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    pipeline = Pipeline()

    async def _go() -> None:
        try:
            await pipeline.run(
                topic=topic,
                run_id=run_id,
                provider=provider,  # type: ignore[arg-type]
                burn_subtitles=False,
                references=None,
                soul_id=soul_id,
                voiceless=voiceless,
                use_keyframes=use_keyframes,
                brief=brief,
            )
        except Exception:
            logger.exception(f"[mcp] reel {run_id} crashed")

    asyncio.create_task(_go())
    return {
        "run_id": run_id,
        "status": "pending",
        "provider": provider,
        "brief": brief.model_dump(),
        "hint": f"Use get_run('{run_id}') to poll progress.",
    }


@mcp.tool()
async def get_shot_plan(run_id: str) -> dict[str, Any]:
    """Return the director's frame-by-frame shot plan for a run."""
    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    if r.shot_plan is None:
        return {
            "error": "no shot_plan yet — the director step has not run",
            "status": r.status.value,
            "current_step": r.current_step,
        }
    return {"run_id": run_id, "shot_plan": r.shot_plan.model_dump()}


@mcp.tool()
async def update_shot(
    run_id: str,
    shot_index: int,
    **fields: Any,
) -> dict[str, Any]:
    """Patch a single shot in the persisted plan with hand-supplied fields.

    Pass any subset of Shot fields as kwargs: `camera_move`, `lens_mm`,
    `shot_size`, `lighting`, `location`, `wardrobe`, `props`,
    `action_beats`, `dialogue_excerpt`, `emotion`, `color_palette`,
    `transition_in`, `transition_out`, `final_prompt`. `index` and
    `duration_seconds` are preserved.

    Use `refine_shot` instead when you want Claude to compose the changes
    from a natural-language instruction.
    """
    r = _load_run(run_id)
    if r is None or r.shot_plan is None:
        return {"error": f"run {run_id!r} has no shot_plan"}
    if not (0 <= shot_index < len(r.shot_plan.shots)):
        return {"error": f"shot_index {shot_index} out of range"}
    current = r.shot_plan.shots[shot_index]
    fields.pop("index", None)
    fields.pop("duration_seconds", None)
    try:
        new_shot = current.model_copy(update=fields)
        Shot.model_validate(new_shot.model_dump())  # round-trip validation
    except Exception as exc:
        return {"error": f"invalid shot update: {exc}"}
    r.shot_plan.shots[shot_index] = new_shot
    _persist(r)
    return {"run_id": run_id, "shot_index": shot_index, "shot": new_shot.model_dump()}


@mcp.tool()
async def refine_shot(
    run_id: str,
    shot_index: int,
    instruction: str,
) -> dict[str, Any]:
    """Refine a shot by asking Claude to apply a free-text instruction.

    Example instructions:
      - "Make this a wide shot at sunrise with the protagonist seen from
         behind"
      - "Switch lighting to neon city at night with cyan rim light"
      - "Tighten on the hands — extreme close-up of the espresso pour"
    """
    r = _load_run(run_id)
    if r is None or r.shot_plan is None:
        return {"error": f"run {run_id!r} has no shot_plan"}
    if not (0 <= shot_index < len(r.shot_plan.shots)):
        return {"error": f"shot_index {shot_index} out of range"}

    shot = r.shot_plan.shots[shot_index]
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    system = (
        "Eres un director de cine. Recibes un shot existente en JSON y una "
        "instrucción del operador. Devuelves SIEMPRE un único objeto JSON con "
        "EL MISMO esquema del shot, ajustado según la instrucción. Mantén el "
        "index y duration_seconds. No incluyas markdown, sólo JSON."
    )
    user = (
        f"SHOT ACTUAL:\n{shot.model_dump_json(indent=2)}\n\n"
        f"PERSONA LOCK (mantener):\n{r.shot_plan.persona_lock}\n\n"
        f"STYLE BRIEF (mantener):\n{r.shot_plan.style_brief}\n\n"
        f"INSTRUCCIÓN DEL OPERADOR:\n{instruction}\n\n"
        "Devuelve el shot ajustado completo, en JSON."
    )
    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = "".join(
        b.text for b in message.content if getattr(b, "type", None) == "text"
    ).strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        new_shot = Shot.model_validate(json.loads(raw))
    except Exception as exc:
        return {"error": f"director returned invalid JSON: {exc}", "raw": raw[:500]}
    new_shot.index = shot.index
    new_shot.duration_seconds = shot.duration_seconds
    r.shot_plan.shots[shot_index] = new_shot
    _persist(r)
    return {"run_id": run_id, "shot_index": shot_index, "shot": new_shot.model_dump()}


@mcp.tool()
async def replace_shot_plan(run_id: str, shot_plan: dict[str, Any]) -> dict[str, Any]:
    """Overwrite the entire ShotPlan with a hand-crafted version.

    The JSON must match the ShotPlan schema (top-level: title, logline,
    style_brief, persona_lock, shots[]). Useful when you want to
    programmatically replan from scratch.
    """
    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    try:
        plan = ShotPlan.model_validate(shot_plan)
    except Exception as exc:
        return {"error": f"invalid shot_plan: {exc}"}
    r.shot_plan = plan
    _persist(r)
    return {"run_id": run_id, "shot_plan": plan.model_dump()}


@mcp.tool()
async def get_script(run_id: str) -> dict[str, Any]:
    """Read the generated script (hook, body, cta, caption, hashtags)."""
    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    if r.script is None:
        return {"error": "no script yet", "status": r.status.value}
    return {"run_id": run_id, "script": r.script.model_dump()}


@mcp.tool()
async def get_final_video_path(run_id: str) -> dict[str, Any]:
    """Return the absolute path of the final mp4 (or null if not done yet)."""
    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    if r.final_video_path is None:
        return {"status": r.status.value, "current_step": r.current_step, "path": None}
    path = Path(r.final_video_path).resolve()
    return {
        "status": r.status.value,
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
    }


@mcp.tool()
async def wait_until_status(
    run_id: str,
    target_status: str = "done",
    timeout_seconds: int = 1800,
    poll_seconds: float = 4.0,
) -> dict[str, Any]:
    """Block until a run reaches `target_status` (or fails or times out).

    target_status: "script_ready" | "done" | "failed".
    """
    valid = {RunStatus.SCRIPT_READY.value, RunStatus.DONE.value, RunStatus.FAILED.value}
    if target_status not in valid:
        return {"error": f"target_status must be one of {sorted(valid)}"}
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while True:
        r = _load_run(run_id)
        if r is None:
            return {"error": f"run {run_id!r} not found"}
        if r.status.value in {RunStatus.FAILED.value, RunStatus.DONE.value}:
            return {"run_id": run_id, "status": r.status.value, "error": r.error}
        if r.status.value == target_status:
            return {"run_id": run_id, "status": r.status.value}
        if asyncio.get_event_loop().time() > deadline:
            return {
                "run_id": run_id,
                "status": r.status.value,
                "current_step": r.current_step,
                "timed_out": True,
            }
        await asyncio.sleep(poll_seconds)


@mcp.tool()
async def update_script(
    run_id: str,
    hook: str | None = None,
    body: str | None = None,
    cta: str | None = None,
    caption: str | None = None,
    hashtags: list[str] | None = None,
    persona_description: str | None = None,
    visual_prompts: list[str] | None = None,
    persona_gender: str | None = None,
) -> dict[str, Any]:
    """Patch the persisted script fields. Recomputes full_script when hook,
    body or cta change. Useful from MCP when you want to tweak copy without
    going through the UI.
    """
    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    if r.script is None:
        return {"error": "run has no script yet"}
    update: dict[str, Any] = {}
    if hook is not None:
        update["hook"] = hook
    if body is not None:
        update["body"] = body
    if cta is not None:
        update["cta"] = cta
    if caption is not None:
        update["caption"] = caption
    if hashtags is not None:
        update["hashtags"] = [h.lstrip("#") for h in hashtags]
    if persona_description is not None:
        update["persona_description"] = persona_description
    if visual_prompts is not None:
        update["visual_prompts"] = list(visual_prompts)
    if persona_gender is not None:
        if persona_gender not in {"female", "male"}:
            return {"error": "persona_gender must be 'female' or 'male'"}
        update["persona_gender"] = persona_gender
    new_script = r.script.model_copy(update=update)
    new_script.full_script = " ".join(
        s for s in (new_script.hook, new_script.body, new_script.cta) if s.strip()
    )
    r.script = new_script
    _persist(r)
    return {"run_id": run_id, "script": new_script.model_dump()}


@mcp.tool()
async def confirm_run(run_id: str) -> dict[str, Any]:
    """Resume a paused (script_ready) run with the currently persisted script.

    Fires the rest of the pipeline (director → voice → video → assemble) in
    the background. Use `wait_until_status` to block until it finishes.
    """
    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    if r.status != RunStatus.SCRIPT_READY:
        return {
            "error": f"cannot confirm — status is {r.status.value}, expected script_ready"
        }
    if r.script is None:
        return {"error": "run has no script to confirm"}

    edited = r.script
    pipeline = Pipeline()

    async def _go() -> None:
        try:
            await pipeline.resume(run_id=run_id, edited_script=edited)
        except Exception:
            logger.exception(f"[mcp] resume {run_id} crashed")

    asyncio.create_task(_go())
    return {"run_id": run_id, "status": "running"}


@mcp.tool()
async def regenerate_clip(
    run_id: str,
    clip_index: int,
    extra_instruction: str | None = None,
) -> dict[str, Any]:
    """Re-render one clip without re-running the whole reel.

    Reads the persisted ShotPlan, optionally appends `extra_instruction` to
    the active shot's final_prompt, then calls Higgsfield only for that clip
    and overwrites `clips/clip_XX.mp4`. The next call to `wait_until_status`
    will see the run go back to RUNNING while the regen lasts.

    Cheap path: skips voice, subtitle, director and assembler — only the
    video step touches the network.
    """
    from src.clients.higgsfield import (
        HiggsfieldCLI,
        download_to_path,
        extract_video_url,
        get_higgsfield_cli,
    )
    from src.steps.video_generator import _build_clip_flags

    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    if r.shot_plan is None or not r.shot_plan.shots:
        return {"error": "run has no shot_plan; regenerate from scratch with create_reel"}
    if not (0 <= clip_index < len(r.shot_plan.shots)):
        return {"error": f"clip_index {clip_index} out of range"}

    provider: VideoProvider = (r.provider or settings.video_provider)  # type: ignore[assignment]
    duration = settings.clip_duration_for(provider)
    shot = r.shot_plan.shots[clip_index]
    prompt = shot.final_prompt or ""
    if extra_instruction:
        prompt = f"{prompt.rstrip('. ')}. {extra_instruction.strip().rstrip('. ')}"
    if r.shot_plan.style_brief:
        prompt = f"{prompt.rstrip('. ')}. {r.shot_plan.style_brief}"
    prompt = f"{prompt.rstrip('. ')}. {settings.motion_prompt_suffix}"

    cli: HiggsfieldCLI = get_higgsfield_cli()
    flags = _build_clip_flags(
        provider=provider,
        duration=duration,
        start_image_uuid=None,
        audio_uuid=None,
    )
    logger.info(f"[mcp] regenerate clip {clip_index} for {run_id} via {provider}")
    result = await cli.generate(
        settings.cli_model_for(provider),
        prompt=prompt,
        wait=True,
        wait_timeout="20m",
        **flags,
    )
    url = extract_video_url(result)
    clips_dir = (settings.output_dir / run_id / "clips")
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_path = clips_dir / f"clip_{clip_index:02d}.mp4"
    await download_to_path(url, clip_path)
    return {
        "run_id": run_id,
        "clip_index": clip_index,
        "path": str(clip_path.resolve()),
        "bytes": clip_path.stat().st_size if clip_path.exists() else None,
    }


@mcp.tool()
async def get_brief(run_id: str) -> dict[str, Any]:
    """Read the structured creative brief that was attached to the run."""
    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    return {"run_id": run_id, "brief": r.brief.model_dump() if r.brief else None}


@mcp.tool()
async def set_brief(
    run_id: str,
    audience: str | None = None,
    tone: list[str] | None = None,
    mood: list[str] | None = None,
    visual_vibe: list[str] | None = None,
    palette: str | None = None,
    cta_goal: str | None = None,
    extra_notes: str | None = None,
) -> dict[str, Any]:
    """Patch the persisted brief. Only the fields you pass are overwritten.

    Doesn't re-run anything — but the next director call (e.g. after
    `regenerate_clip` or a fresh resume) will read the updated brief.
    """
    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    current = (
        r.brief.model_dump()
        if r.brief
        else {
            "topic": r.topic,
            "tone": [],
            "mood": [],
            "visual_vibe": [],
        }
    )
    if audience is not None:
        current["audience"] = audience
    if tone is not None:
        current["tone"] = list(tone)
    if mood is not None:
        current["mood"] = list(mood)
    if visual_vibe is not None:
        current["visual_vibe"] = list(visual_vibe)
    if palette is not None:
        current["palette"] = palette
    if cta_goal is not None:
        current["cta_goal"] = cta_goal
    if extra_notes is not None:
        current["extra_notes"] = extra_notes
    r.brief = CreativeBrief.model_validate(current)
    _persist(r)
    return {"run_id": run_id, "brief": r.brief.model_dump()}


@mcp.tool()
async def add_reference(
    run_id: str,
    kind: str,
    path: str,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Attach a local file as a reference to a run.

    kind ∈ {persona, style, script, voice, music}. `path` must point to a
    file the server can read; we copy it under output/_uploads/{run_id}/
    so the pipeline finds it later.
    """
    valid = {"persona", "style", "script", "voice", "music"}
    if kind not in valid:
        return {"error": f"kind must be one of {sorted(valid)}"}
    src = Path(path).expanduser().resolve()
    if not src.exists() or not src.is_file():
        return {"error": f"file not found: {src}"}

    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}

    dest_dir = (settings.references_dir / run_id).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    seq = len(list(dest_dir.glob(f"{kind}_*")))
    dest = dest_dir / f"{kind}_{seq:02d}{src.suffix}"
    dest.write_bytes(src.read_bytes())

    mime = _guess_mime(dest.suffix.lower())
    ref = Reference(
        kind=kind,  # type: ignore[arg-type]
        path=dest,
        source_url=source_url,
        mime=mime,
        bytes=dest.stat().st_size,
    )
    r.references.append(ref)
    _persist(r)
    return {"run_id": run_id, "reference": ref.model_dump(mode="json")}


@mcp.tool()
async def list_references(run_id: str) -> dict[str, Any]:
    """List all references attached to a run."""
    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    return {
        "run_id": run_id,
        "references": [ref.model_dump(mode="json") for ref in r.references],
    }


@mcp.tool()
async def reassemble(run_id: str) -> dict[str, Any]:
    """Re-run only the final assembler step on existing clips.

    Useful after `regenerate_clip` so the final video.mp4 picks up the
    freshly regenerated clip(s). Reuses the persisted script + audio + subs
    so no extra credit is burned.
    """
    from src.steps.assembler import AssemblerStep
    from src.steps.subtitle_generator import SubtitleGeneratorStep
    from src.models import SubtitleOutput, SubtitleSegment, VoiceOutput

    r = _load_run(run_id)
    if r is None:
        return {"error": f"run {run_id!r} not found"}
    if r.script is None:
        return {"error": "run has no script yet"}

    output_dir = settings.output_dir / run_id
    clips_dir = output_dir / "clips"
    if not clips_dir.exists():
        return {"error": "no clips/ directory — has the video step ever run?"}
    clip_paths = sorted(clips_dir.glob("clip_*.mp4"))
    if not clip_paths:
        return {"error": "no clip_XX.mp4 files in clips/"}

    voice: VoiceOutput | None = None
    audio_path = output_dir / "audio.mp3"
    if audio_path.exists():
        voice = VoiceOutput(audio_path=audio_path, duration_seconds=0.0)

    context: dict[str, Any] = {
        "script": r.script,
        "output_dir": output_dir,
        "video_clips": clip_paths,
        "video_provider": r.provider,
        "references": r.references,
        "voice": voice,
    }
    await AssemblerStep().run(context)
    final = output_dir / "video.mp4"
    r.final_video_path = final
    _persist(r)
    return {"run_id": run_id, "final_video_path": str(final.resolve()), "exists": final.exists()}


def _guess_mime(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".aac": "audio/aac",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".txt": "text/plain",
        ".json": "application/json",
    }.get(suffix, "application/octet-stream")


@mcp.tool()
async def providers_info() -> dict[str, Any]:
    """List available video providers with their cost + capability metadata."""
    return {
        "current": settings.video_provider,
        "available": [
            {
                "id": "seedance",
                "name": "Seedance 2.0",
                "clips": settings.standard_num_clips,
                "clip_duration": settings.standard_clip_duration,
                "supports_soul_id": True,
                "native_audio": False,
            },
            {
                "id": "kling",
                "name": "Kling v3.0",
                "clips": settings.standard_num_clips,
                "clip_duration": settings.standard_clip_duration,
                "supports_soul_id": True,
                "native_audio": False,
            },
            {
                "id": "veo",
                "name": "Veo 3.1",
                "clips": settings.veo_num_clips,
                "clip_duration": settings.veo_clip_duration,
                "supports_soul_id": False,
                "native_audio": True,
            },
            {
                "id": "cinematic_studio_v2",
                "name": "Cinematic Studio v2",
                "clips": settings.standard_num_clips,
                "clip_duration": settings.standard_clip_duration,
                "supports_soul_id": True,
                "native_audio": False,
            },
        ],
    }


def _build_http_app():
    """Return the FastMCP Streamable HTTP ASGI app, wrapped with hard auth.

    Mounted at `/mcp/` inside the main FastAPI app so Claude.ai / Claude
    Desktop can connect over HTTPS at `https://<host>/mcp/` with:
        Authorization: Bearer $MCP_TOKEN

    Three layers of defense (in order):
    1. Optional IP whitelist (env `MCP_ALLOWED_IPS`, comma-separated; empty
       means allow all — controlled at the network edge).
    2. Mandatory Bearer token check against `MCP_TOKEN`.
    3. Sliding-window rate limit per IP (default 30 req / 60 s), so a leaked
       token can't burn the credit budget faster than the operator can rotate
       it.
    """
    # When mounted at "/mcp" the inner Starlette sees requests at "/" — so
    # the MCP endpoint should be the root.
    mcp.settings.streamable_http_path = "/"
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    # FastMCP enables anti-DNS-rebinding by default (whitelist host:port). When
    # we run behind nginx + Cloudflare the public Host doesn't fit that scheme,
    # so we either whitelist explicit hosts via MCP_PUBLIC_HOST or disable the
    # check entirely (safe because the Bearer token gate already authenticates
    # every request).
    extra_hosts = [
        h.strip()
        for h in os.environ.get("MCP_PUBLIC_HOST", "").split(",")
        if h.strip()
    ]
    if extra_hosts:
        base_hosts = list(mcp.settings.transport_security.allowed_hosts)
        mcp.settings.transport_security.allowed_hosts = base_hosts + extra_hosts
        # Auto-derive allowed origins from the listed hosts.
        derived = []
        for h in extra_hosts:
            derived.extend([f"https://{h}", f"http://{h}"])
        base_origins = list(mcp.settings.transport_security.allowed_origins)
        mcp.settings.transport_security.allowed_origins = base_origins + derived
    else:
        # No public host configured → just turn off the rebinding check.
        mcp.settings.transport_security.enable_dns_rebinding_protection = False

    inner = mcp.streamable_http_app()

    expected_token = os.environ.get("MCP_TOKEN", "").strip()
    allowed_ips = {
        ip.strip()
        for ip in os.environ.get("MCP_ALLOWED_IPS", "").split(",")
        if ip.strip()
    }
    rate_max = int(os.environ.get("MCP_RATE_LIMIT_PER_MINUTE", "30"))
    rate_window = 60.0

    # Per-IP sliding window: ip → [timestamps...]
    import collections
    import time as _time

    history: dict[str, collections.deque[float]] = collections.defaultdict(
        lambda: collections.deque(maxlen=rate_max + 8)
    )

    async def _deny(send, status: int, body: bytes, extra_headers=()) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json"), *extra_headers],
            }
        )
        await send({"type": "http.response.body", "body": body})

    async def asgi(scope, receive, send):  # noqa: D401
        if scope["type"] != "http":
            await inner(scope, receive, send)
            return

        # Pull headers + client IP (honour X-Forwarded-For from nginx).
        client_ip = ""
        auth_header = ""
        for name, value in scope.get("headers", []):
            ln = name.lower()
            if ln == b"x-forwarded-for":
                client_ip = (
                    value.decode("latin-1", errors="ignore").split(",")[0].strip()
                )
            elif ln == b"authorization":
                auth_header = value.decode("latin-1", errors="ignore")
        if not client_ip:
            client = scope.get("client") or ("", 0)
            client_ip = client[0] if client else ""

        # 1) IP whitelist (skipped when env unset).
        if allowed_ips and client_ip not in allowed_ips:
            await _deny(
                send,
                403,
                b'{"detail":"client IP not allowed for MCP"}',
            )
            return

        # 2) Token auth — accepts either header OR URL path segment.
        # Path-token mode (used by Claude.ai connector, which can't set
        # custom Authorization headers): URL is
        #     https://<host>/mcp/<MCP_TOKEN>/
        # The asgi sees scope.path == "/<MCP_TOKEN>/..." (relative to the
        # /mcp mount). We strip the token from the path so the inner MCP
        # app sees just "/...".
        if not expected_token:
            await _deny(
                send,
                503,
                b'{"detail":"MCP_TOKEN not configured on the server"}',
            )
            return

        # When mounted at /mcp, Starlette is supposed to strip the prefix,
        # but FastAPI's catch-all sometimes leaves it intact. Handle both
        # cases by always stripping a leading `/mcp/` if present.
        raw_path = scope.get("path", "") or "/"
        root = scope.get("root_path", "") or ""
        path = raw_path
        if root and path.startswith(root):
            path = path[len(root):] or "/"
        elif path.startswith("/mcp/"):
            path = path[len("/mcp"):] or "/"
        parts = path.lstrip("/").split("/", 1)
        path_token = parts[0] if parts and parts[0] else ""
        path_token_ok = bool(path_token) and path_token == expected_token

        header_token_ok = (
            auth_header.startswith("Bearer ")
            and auth_header[7:].strip() == expected_token
        )

        if path_token_ok:
            new_path = "/" + (parts[1] if len(parts) > 1 else "")
            scope = dict(scope)
            scope["path"] = new_path
            scope["raw_path"] = new_path.encode("utf-8")
        elif not header_token_ok:
            await _deny(
                send,
                401,
                b'{"detail":"missing or invalid MCP token"}',
                extra_headers=((b"www-authenticate", b"Bearer"),),
            )
            return

        # 3) Rate limit per IP (sliding window).
        now = _time.monotonic()
        bucket = history[client_ip or "unknown"]
        while bucket and now - bucket[0] > rate_window:
            bucket.popleft()
        if len(bucket) >= rate_max:
            retry = max(1, int(rate_window - (now - bucket[0])))
            await _deny(
                send,
                429,
                b'{"detail":"too many MCP requests; slow down"}',
                extra_headers=((b"retry-after", str(retry).encode()),),
            )
            return
        bucket.append(now)

        await inner(scope, receive, send)

    return asgi


# Public ASGI app the FastAPI main.py mounts at "/mcp"
mcp_http_app = _build_http_app()


def main() -> None:
    """Entry point for `reels-mcp`. Runs stdio MCP transport."""
    # Suppress loguru chatter on stderr because Claude Desktop reads stderr
    # for protocol diagnostics; quiet logs make the channel cleaner.
    if os.environ.get("REELS_MCP_QUIET", "1") != "0":
        logger.remove()
    mcp.run()


if __name__ == "__main__":
    main()
