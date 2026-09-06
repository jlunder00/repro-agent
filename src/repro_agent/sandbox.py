"""Docker-backed sandbox for running an untrusted capsule command.

Shells out to the `docker` CLI via subprocess rather than depending on the
docker SDK. Each run gets a deterministic, uuid4-based container name so
that a timeout can reliably clean up: `--rm` alone is not sufficient once
the client process itself may be killed or time out before the container
exits on its own.
"""

from __future__ import annotations

import logging
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "python:3.11-slim"

_MAX_OUTPUT_CHARS = 20000


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float


def _truncate(text: str, limit: int = _MAX_OUTPUT_CHARS) -> str:
    """Keep the LAST `limit` characters -- the tail is what matters for
    diagnosing failures -- and note how much was dropped."""
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    marker = f"[... {dropped} characters truncated ...]\n"
    return marker + text[-limit:]


def run_in_container(command: str, work_dir: Path, *, image: str = DEFAULT_IMAGE,
                     timeout_s: int = 900, network: bool = True) -> ExecResult:
    """Run `command` with bash -lc inside `image`, with work_dir bind-mounted
    at /workspace and cwd=/workspace. Capture stdout/stderr (truncate each to
    the last 20000 chars, noting truncation). Always remove the container
    (--rm). On timeout set timed_out=True and kill the container. Never raise
    on a non-zero exit code -- that is data, not an error.
    """
    container_name = f"repro-agent-{uuid.uuid4().hex}"
    argv = [
        "docker", "run", "--rm", "--name", container_name,
        "-v", f"{Path(work_dir).resolve()}:/workspace",
        "-w", "/workspace",
    ]
    if not network:
        argv += ["--network", "none"]
    argv += [image, "bash", "-lc", command]

    started = time.time()
    timed_out = False
    stdout = ""
    stderr = ""
    exit_code = -1

    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        stdout = stdout if isinstance(stdout, str) else stdout.decode(errors="replace")
        stderr = stderr if isinstance(stderr, str) else stderr.decode(errors="replace")
        _force_remove(container_name)

    duration_s = time.time() - started

    return ExecResult(
        exit_code=exit_code,
        stdout=_truncate(stdout),
        stderr=_truncate(stderr),
        timed_out=timed_out,
        duration_s=duration_s,
    )


def _force_remove(container_name: str) -> None:
    """Best-effort cleanup for a container left behind by a timeout.
    `--rm` only removes the container once it exits on its own; a killed
    client process can leave it running, so force-remove explicitly.
    """
    try:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:  # noqa: BLE001 - cleanup must never raise into the caller
        logger.warning("failed to force-remove container %s", container_name, exc_info=True)


def docker_available() -> bool:
    """True only if `docker info` succeeds. Must never raise."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:  # noqa: BLE001 - absence of docker is a normal outcome
        return False
