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


def main() -> None:
    """Entry point for `reels-mcp`. Runs stdio MCP transport."""
    # Suppress loguru chatter on stderr because Claude Desktop reads stderr
    # for protocol diagnostics; quiet logs make the channel cleaner.
    if os.environ.get("REELS_MCP_QUIET", "1") != "0":
        logger.remove()
    mcp.run()


if __name__ == "__main__":
    main()
