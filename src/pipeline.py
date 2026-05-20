"""Pipeline orchestrator: runs all steps sequentially with retry."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from loguru import logger
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import VideoProvider, settings
from src.models import CreativeBrief, Reference, RunResult, RunStatus, ScriptOutput
from src.steps import (
    AssemblerStep,
    DirectorStep,
    ScriptGeneratorStep,
    StyleExtractorStep,
    SubtitleGeneratorStep,
    VideoGeneratorStep,
    VoiceGeneratorStep,
)


class Step(Protocol):
    name: str

    async def run(self, context: dict[str, Any]) -> dict[str, Any]: ...


class Pipeline:
    """Runs the 5 steps end-to-end for a given topic."""

    def __init__(self, steps: list[Step] | None = None) -> None:
        # Lip-sync is no longer a separate step: the Higgsfield CLI accepts an
        # `--audio` flag on kling/seedance and fuses lip-sync into the video
        # generation call. See docs/HIGGSFIELD_API.md §4.
        self.steps: list[Step] = steps or [
            ScriptGeneratorStep(),
            StyleExtractorStep(),
            DirectorStep(),
            VoiceGeneratorStep(),
            VideoGeneratorStep(),
            SubtitleGeneratorStep(),
            AssemblerStep(),
        ]

    async def run(
        self,
        topic: str,
        run_id: str | None = None,
        provider: VideoProvider | None = None,
        burn_subtitles: bool = False,
        references: list[Reference] | None = None,
        pause_after: str | None = None,
        soul_id: str | None = None,
        voiceless: bool = False,
        use_keyframes: bool = False,
        brief: CreativeBrief | None = None,
    ) -> RunResult:
        """Run the pipeline end-to-end, or only up through `pause_after`.

        When `pause_after` is set (e.g. "script_generator"), the pipeline runs
        up to and INCLUDING that step, marks the run as `script_ready`, and
        returns so the caller can let a human edit the script before calling
        `resume()` to finish the work.
        """
        run_id = run_id or _new_run_id()
        output_dir = settings.output_dir / run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        chosen_provider: VideoProvider = provider or settings.video_provider
        refs: list[Reference] = list(references or [])

        result = RunResult(
            run_id=run_id,
            topic=topic,
            status=RunStatus.RUNNING,
            output_dir=output_dir,
            provider=chosen_provider,
            references=refs,
            soul_id=soul_id,
            voiceless=voiceless,
            use_keyframes=use_keyframes,
            brief=brief,
        )
        _persist_result(result, output_dir)

        context: dict[str, Any] = {
            "run_id": run_id,
            "topic": topic,
            "output_dir": output_dir,
            "provider": chosen_provider,
            "references": refs,
            "soul_id": soul_id,
            "use_keyframes": use_keyframes,
            "brief": brief,
            # Skip ElevenLabs if either: the provider has native audio (Veo),
            # or the caller explicitly asked for a voiceless cinematic reel
            # (music-only, typography-led — matches the brand-video
            # aesthetic).
            "skip_voice_generation": chosen_provider == "veo" or voiceless,
            "skip_subtitles": not burn_subtitles,
        }

        logger.info(
            f"[pipeline] run_id={run_id} topic={topic!r} provider={chosen_provider} "
            f"refs={[r.kind for r in refs]} soul_id={soul_id} "
            f"pause_after={pause_after} starting"
        )

        await self._execute_steps(result, context, pause_after=pause_after)
        _persist_result(result, output_dir)
        return result

    async def resume(
        self,
        run_id: str,
        edited_script: ScriptOutput,
    ) -> RunResult:
        """Pick up a paused run after the user has edited the generated script."""
        output_dir = settings.output_dir / run_id
        result = _load_result(output_dir)
        if result.status != RunStatus.SCRIPT_READY:
            raise RuntimeError(
                f"cannot resume run {run_id}: status is {result.status.value}, "
                f"expected {RunStatus.SCRIPT_READY.value}"
            )

        result.script = edited_script
        result.status = RunStatus.RUNNING
        result.error = None
        result.finished_at = None
        _persist_result(result, output_dir)

        provider: VideoProvider = result.provider or settings.video_provider  # type: ignore[assignment]
        context: dict[str, Any] = {
            "run_id": run_id,
            "topic": result.topic,
            "output_dir": output_dir,
            "provider": provider,
            "references": list(result.references),
            "soul_id": result.soul_id,
            "use_keyframes": result.use_keyframes,
            "brief": result.brief,
            "script": edited_script,
            # Mirror the same skip rules as `run()` — Veo has native audio,
            # and a voiceless run was the operator's explicit choice (e.g.
            # for a music-only cinematic reel). Both must be honoured here
            # or the voice step runs unexpectedly after `/confirm`.
            "skip_voice_generation": provider == "veo" or result.voiceless,
            "skip_subtitles": True,  # subtitles are off by spec
        }

        logger.info(f"[pipeline] run_id={run_id} resuming with edited script")
        await self._execute_steps(
            result, context, skip_until_after="script_generator"
        )
        _persist_result(result, output_dir)
        return result

    async def _execute_steps(
        self,
        result: RunResult,
        context: dict[str, Any],
        *,
        pause_after: str | None = None,
        skip_until_after: str | None = None,
    ) -> None:
        """Iterate steps. Honors pause/skip semantics and persists state.

        - `pause_after`: stop after the named step succeeds (sets SCRIPT_READY).
        - `skip_until_after`: skip every step up to and including the named one
          (used by `resume()` to bypass already-completed steps).
        """
        output_dir = result.output_dir
        skipping = skip_until_after is not None
        try:
            for step in self.steps:
                if skipping:
                    if step.name == skip_until_after:
                        skipping = False
                    continue
                if step.name == "voice_generator" and context.get("skip_voice_generation"):
                    logger.info(f"[pipeline] step={step.name} skipped (provider has native audio)")
                    continue
                if step.name == "subtitle_generator" and context.get("skip_subtitles"):
                    logger.info(f"[pipeline] step={step.name} skipped (burn_subtitles=False)")
                    continue

                result.current_step = step.name
                _persist_result(result, output_dir)
                context = await _run_step_with_retry(step, context)

                # Persist intermediate artefacts so the detail page can
                # surface them as soon as each step completes (script,
                # shot plan), not just at the end of the run.
                if step.name == "script_generator":
                    result.script = context.get("script") or result.script
                elif step.name == "director":
                    plan = context.get("shot_plan")
                    if plan is not None:
                        result.shot_plan = plan
                _persist_result(result, output_dir)

                if pause_after is not None and step.name == pause_after:
                    result.status = RunStatus.SCRIPT_READY
                    result.current_step = None
                    result.script = context.get("script")
                    logger.info(f"[pipeline] run_id={result.run_id} paused after {step.name}")
                    return

            result.status = RunStatus.DONE
            result.finished_at = datetime.now(UTC)
            result.current_step = None
            result.script = context.get("script") or result.script
            plan = context.get("shot_plan")
            if plan is not None:
                result.shot_plan = plan
            assembled = context.get("assembled")
            if assembled is not None:
                result.final_video_path = assembled.final_video_path
            result.caption_path = context.get("caption_path")
            logger.info(f"[pipeline] run_id={result.run_id} DONE")
        except Exception as exc:
            result.status = RunStatus.FAILED
            result.finished_at = datetime.now(UTC)
            result.error = f"{type(exc).__name__}: {exc}"
            logger.exception(f"[pipeline] run_id={result.run_id} FAILED")


async def _run_step_with_retry(step: Step, context: dict[str, Any]) -> dict[str, Any]:
    # video_generator costs real Higgsfield credits per attempt. A tenacity
    # storm against a deterministic HTTP 500 burned 48 cr in iter 3 before we
    # could stop it. Cap that step at 1 attempt — if the call fails, fix the
    # request and re-run manually rather than retrying blindly. Cheap steps
    # (script, style, voice, subtitle, assembler) keep retries=3 for transient
    # network errors.
    max_attempts = 1 if step.name == "video_generator" else 3
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                logger.info(f"[pipeline] step={step.name} attempt={attempt.retry_state.attempt_number}")
                return await step.run(context)
    except RetryError as exc:  # pragma: no cover - safety
        raise exc.last_attempt.exception()  # type: ignore[misc]
    return context  # unreachable


def _new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


def _persist_result(result: RunResult, output_dir: Path) -> None:
    (output_dir / "result.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )


def _load_result(output_dir: Path) -> RunResult:
    path = output_dir / "result.json"
    if not path.exists():
        raise FileNotFoundError(f"no result.json at {path}")
    return RunResult.model_validate_json(path.read_text(encoding="utf-8"))
