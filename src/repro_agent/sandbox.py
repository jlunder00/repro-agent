"""Docker-backed sandbox for running an untrusted capsule command.

Shells out to the `docker` CLI rather than the docker SDK. Each run gets a
uuid4-based container name so a timeout can force-remove it; `--rm` alone
does not clean up when the client times out first.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "python:3.11-slim"

_MAX_OUTPUT_CHARS = 20000

# Prepended to every command. Creates the R user library (install.packages
# only uses R_LIBS_USER if the directory exists) and puts pip's --user bin
# directory on PATH so installed console scripts resolve.
_USER_ENV_PRELUDE = (
    "mkdir -p /tmp/Rlib && export PATH=/tmp/.local/bin:$PATH && "
)


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float


def _truncate(text: str, limit: int = _MAX_OUTPUT_CHARS) -> str:
    """Keep the last `limit` characters and note how many were dropped."""
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    marker = f"[... {dropped} characters truncated ...]\n"
    return marker + text[-limit:]


def run_in_container(command: str, work_dir: Path, *, image: str = DEFAULT_IMAGE,
                     timeout_s: int = 900, network: bool = True) -> ExecResult:
    """Run `command` with bash -lc inside `image`, with work_dir bind-mounted
    at /workspace and cwd=/workspace.

    stdout/stderr are truncated to the last 20000 chars. The container is
    always removed. On timeout, timed_out=True and the container is killed.
    A non-zero exit code does not raise.
    """
    container_name = f"repro-agent-{uuid.uuid4().hex}"
    argv = [
        "docker", "run", "--rm", "--name", container_name,
        # Run as the invoking user. Rootful Docker otherwise leaves
        # root-owned files (e.g. __pycache__) in the bind-mounted work dir,
        # and the next prepare_tier() rmtree then fails with PermissionError.
        "--user", f"{os.getuid()}:{os.getgid()}",
        # That uid has no entry inside the image, so HOME would resolve to
        # "/" and neither pip nor R could install anything (EACCES on
        # /.local and on the system site-library). Give the process a
        # writable home and per-user library paths instead.
        "-e", "HOME=/tmp",
        "-e", "PIP_USER=1",
        "-e", "R_LIBS_USER=/tmp/Rlib",
        "-v", f"{Path(work_dir).resolve()}:/workspace",
        "-w", "/workspace",
    ]
    if not network:
        argv += ["--network", "none"]
    argv += [image, "bash", "-lc", _USER_ENV_PRELUDE + command]

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
    """Force-remove a container left running after a timeout. Never raises."""
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
