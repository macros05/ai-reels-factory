"""Subprocess wrapper around the official `higgsfield` CLI.

We deliberately do not use the `higgsfield-client` Python SDK. The CLI gives
us three things the SDK does not:

1. Browser device-flow auth — no API key in `.env`, no rotation pain.
2. `higgsfield soul-id create` — the only public surface for training
   consistent character IDs.
3. `higgsfield upload create` — uniform upload + UUID we can re-use across
   clips, instead of a fresh CDN upload per call.

Everything we need is exposed through `higgsfield ... --json`, so this
wrapper is a thin asyncio-subprocess shim with tenacity around it.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings


class HiggsfieldError(RuntimeError):
    """Anything the CLI rejected after retries (auth, bad args, server error)."""


class HiggsfieldAuthError(HiggsfieldError):
    """CLI returned `Not authenticated`. Asking the user to re-login is the
    only fix; retrying is a waste of time, so we bypass tenacity for this one.
    """


@dataclass
class CLIResult:
    """Whatever the CLI printed on stdout, plus the parsed JSON if applicable."""

    raw_stdout: str
    raw_stderr: str
    data: Any
    returncode: int


class HiggsfieldCLI:
    """Async wrapper for the `higgsfield` binary.

    Tests inject `runner=` to mock subprocess output; production code defaults
    to `_real_run` which actually invokes the binary.
    """

    # CLI flags that mean "this is not a Python identifier"; we map them in
    # `_to_cli_flag` so callers can pass `start_image=`/`aspect_ratio=` from
    # Python without worrying about the dash conventions.
    _DASH_KEYS: frozenset[str] = frozenset(
        {"start_image", "end_image", "soul_id", "ad_reference_id",
         "brand_kit_id", "folder_id", "style_id", "hook_id", "setting_id",
         "product_ids", "web_product_ids", "batch_size", "aspect_ratio",
         "generate_audio", "slow_motion"}
    )

    def __init__(
        self,
        *,
        binary: str | None = None,
        runner: Any | None = None,
    ) -> None:
        self._binary = binary or settings.higgsfield_cli_path
        self._runner = runner

    # ------------------------------------------------------------------
    # primitives
    # ------------------------------------------------------------------

    async def _run(
        self,
        args: list[str],
        *,
        timeout: float | None = None,
        json_output: bool = True,
        retries: int = 3,
    ) -> CLIResult:
        """Invoke the CLI with retry on transient failures.

        We always pass `--json` for parseability; the CLI honors it on every
        command. `Not authenticated` is fatal — no retry, raises
        HiggsfieldAuthError so the caller can surface a "click the device
        link" message to the operator instead of hammering the server.
        """
        cmd = [self._binary, *args]
        if json_output and "--json" not in args:
            cmd.append("--json")

        runner = self._runner or _real_run
        last_err: Exception | None = None

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(retries),
                wait=wait_exponential(multiplier=1, min=2, max=15),
                retry=retry_if_exception_type(HiggsfieldError),
                reraise=True,
            ):
                with attempt:
                    res = await runner(cmd, timeout=timeout)
                    if res.returncode != 0:
                        if "Not authenticated" in res.raw_stderr:
                            raise HiggsfieldAuthError(
                                "higgsfield CLI not authenticated — run "
                                "`higgsfield auth login` on the host"
                            )
                        last_err = HiggsfieldError(
                            f"higgsfield {' '.join(args)} exited "
                            f"{res.returncode}: {res.raw_stderr.strip()[:500]}"
                        )
                        raise last_err
                    return res
        except RetryError as exc:  # pragma: no cover - tenacity wrap
            raise HiggsfieldError(str(exc)) from exc

        raise HiggsfieldError("unreachable")  # pragma: no cover

    # ------------------------------------------------------------------
    # account
    # ------------------------------------------------------------------

    async def account_status(self) -> dict[str, Any]:
        """Returns `{email, plan, credits}` from `higgsfield account status`."""
        res = await self._run(["account", "status"], retries=1)
        return _as_dict(res.data)

    async def is_authenticated(self) -> bool:
        try:
            await self.account_status()
            return True
        except HiggsfieldAuthError:
            return False

    # ------------------------------------------------------------------
    # upload
    # ------------------------------------------------------------------

    async def upload(self, path: Path | str) -> str:
        """Upload a local file and return its CLI UUID."""
        res = await self._run(["upload", "create", str(path)])
        data = _as_dict(res.data)
        uuid = (
            data.get("id")
            or data.get("upload_id")
            or data.get("uuid")
        )
        if not uuid:
            raise HiggsfieldError(f"upload returned no id: {res.raw_stdout[:300]}")
        logger.info(f"[higgsfield] uploaded {Path(str(path)).name} → {uuid}")
        return str(uuid)

    # ------------------------------------------------------------------
    # generate
    # ------------------------------------------------------------------

    async def generate(
        self,
        job_set_type: str,
        *,
        prompt: str,
        wait: bool = True,
        wait_timeout: str = "20m",
        wait_interval: str = "5s",
        **flags: Any,
    ) -> dict[str, Any]:
        """Run `higgsfield generate create <model> --prompt ... [flags] --wait`.

        Returns the parsed JSON response. With `wait=True` the CLI blocks
        until the job hits a terminal status and emits the result URL in the
        payload (`result_url` or `result.url` depending on model). Caller is
        responsible for `extract_video_url(result)`.
        """
        args: list[str] = ["generate", "create", job_set_type, "--prompt", prompt]
        for key, value in flags.items():
            if value is None or value == "":
                continue
            flag = _to_cli_flag(key)
            if isinstance(value, bool):
                # CLI bool flags are passed as "--flag true|false" per MODELS.md.
                args.extend([flag, "true" if value else "false"])
            elif isinstance(value, (list, tuple)):
                # Repeatable flags like --image <id1> --image <id2>.
                for item in value:
                    args.extend([flag, str(item)])
            else:
                args.extend([flag, str(value)])

        if wait:
            args.extend(["--wait", "--wait-timeout", wait_timeout,
                         "--wait-interval", wait_interval])

        res = await self._run(args, timeout=_parse_duration(wait_timeout) + 60)
        return _as_dict(res.data)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        res = await self._run(["generate", "get", job_id], retries=1)
        return _as_dict(res.data)

    # ------------------------------------------------------------------
    # soul-id (Character training)
    # ------------------------------------------------------------------

    async def soul_id_create(
        self,
        *,
        name: str,
        image_uuids: list[str],
        soul_model: str = "soul-2",
    ) -> dict[str, Any]:
        """Submit a Soul ID training run. Returns `{id, name, status, ...}`.

        Use `soul_id_wait(id)` to block until training finishes (3–5 min on
        Higgsfield's side).
        """
        if not (5 <= len(image_uuids) <= 20):
            raise HiggsfieldError(
                f"soul-id needs 5–20 image uuids, got {len(image_uuids)}"
            )
        flag = "--soul-2" if soul_model == "soul-2" else "--soul-cinematic"
        args = ["soul-id", "create", "--name", name, flag]
        for uuid in image_uuids:
            args.extend(["--image", uuid])
        res = await self._run(args, retries=1)
        return _as_dict(res.data)

    async def soul_id_wait(self, soul_id: str, *, timeout_seconds: int = 900) -> dict[str, Any]:
        """Block until Soul ID training reports a terminal status."""
        res = await self._run(
            ["soul-id", "wait", soul_id],
            timeout=timeout_seconds + 30,
            retries=1,
        )
        return _as_dict(res.data)

    async def soul_id_get(self, soul_id: str) -> dict[str, Any]:
        res = await self._run(["soul-id", "get", soul_id], retries=1)
        return _as_dict(res.data)

    async def soul_id_list(self) -> list[dict[str, Any]]:
        res = await self._run(["soul-id", "list"], retries=1)
        data = res.data
        if isinstance(data, dict) and "items" in data:
            return list(data["items"])
        if isinstance(data, list):
            return list(data)
        return []


# ----------------------------------------------------------------------
# subprocess + parsing helpers
# ----------------------------------------------------------------------


async def _real_run(cmd: list[str], *, timeout: float | None = None) -> CLIResult:
    """Actually invoke the CLI. Separated so tests can stub it."""
    if shutil.which(cmd[0]) is None:
        raise HiggsfieldError(
            f"binary {cmd[0]!r} not found on PATH — install via "
            f"`npm install -g @higgsfield/cli`"
        )
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise HiggsfieldError(f"higgsfield CLI timed out after {timeout}s") from None

    out = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")
    if err:
        # Surface CLI progress / warnings under loguru so the run log shows
        # what the CLI was doing while the pipeline waited.
        for line in err.splitlines():
            line = line.strip()
            if line:
                logger.debug(f"[higgsfield-cli] {line}")
    data: Any = None
    if out.strip():
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = out  # not all subcommands emit JSON even with --json
    return CLIResult(
        raw_stdout=out,
        raw_stderr=err,
        data=data,
        returncode=proc.returncode if proc.returncode is not None else -1,
    )


def _to_cli_flag(key: str) -> str:
    """Map Python kwarg → CLI flag.

    The CLI uses snake_case for most flags (`--aspect_ratio`, `--start_image`
    etc., visible in `MODELS.md`), except a handful that switched to dashes
    in 0.1.40 (e.g. `--start-image`, `--soul-id`). We match the actual CLI
    spelling here.
    """
    dash_map = {
        "start_image": "--start-image",
        "end_image": "--end-image",
        "soul_id": "--soul-id",
    }
    if key in dash_map:
        return dash_map[key]
    return f"--{key}"


def _as_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        # `--json` sometimes returns plain status strings (e.g. soul-id wait).
        return {"raw": data}
    if isinstance(data, list):
        # `higgsfield generate create --wait --json` returns the *list* of
        # completed jobs (each generation is technically a job_set of N=1).
        # If the list has exactly one entry — by far the common case for a
        # single generate call — unwrap it so callers can read `result_url`
        # at the top level without juggling "items". This is the fix that
        # eliminates the tenacity retry loop that previously burned 3× credits.
        if len(data) == 1 and isinstance(data[0], dict):
            return data[0]
        return {"items": data}
    return {}


def _parse_duration(s: str) -> float:
    """Parse '20m' / '90s' / '1h' into seconds for the subprocess timeout."""
    s = s.strip().lower()
    if s.endswith("ms"):
        return float(s[:-2]) / 1000
    if s.endswith("s"):
        return float(s[:-1])
    if s.endswith("m"):
        return float(s[:-1]) * 60
    if s.endswith("h"):
        return float(s[:-1]) * 3600
    return float(s)  # already seconds


def extract_video_url(result: dict[str, Any]) -> str:
    """Pull the mp4 URL out of a `generate --wait --json` result dict.

    The CLI normalises across models, but different jobs put the URL in
    different keys:
      - top-level `result_url` (most video models)
      - top-level `video.url` (some image-to-video variants)
      - inside `jobs[0].result.url` (when --wait returns a job_set with one
        sub-job)
    We accept any of those.
    """
    for key in ("result_url", "url"):
        v = result.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    video = result.get("video")
    if isinstance(video, dict) and isinstance(video.get("url"), str):
        return str(video["url"])
    jobs = result.get("jobs")
    if isinstance(jobs, list) and jobs:
        first = jobs[0]
        if isinstance(first, dict):
            res = first.get("result")
            if isinstance(res, dict) and isinstance(res.get("url"), str):
                return str(res["url"])
            if isinstance(first.get("result_url"), str):
                return str(first["result_url"])
    # Fallback: some CLI responses (e.g. multi-shot job_sets) keep the
    # raw list of jobs under `items` even after `_as_dict` unwraps singles.
    items = result.get("items")
    if isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            for key in ("result_url", "url"):
                v = first.get(key)
                if isinstance(v, str) and v.startswith("http"):
                    return v
    raise HiggsfieldError(f"could not locate result URL in CLI response: {result!r}")


async def download_to_path(url: str, dest: Path, *, timeout: float = 300.0) -> None:
    """Streaming download of a CDN URL into a local file."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as fh:
                async for chunk in resp.aiter_bytes():
                    fh.write(chunk)


def get_higgsfield_cli() -> HiggsfieldCLI:
    """Return a fresh CLI client. Cheap to construct."""
    return HiggsfieldCLI()
