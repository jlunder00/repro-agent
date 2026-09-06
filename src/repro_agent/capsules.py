"""Downloading and preparing CORE-bench capsules.

Capsules are code-ocean-style tarballs, anywhere from ~0.1 MB to a couple of
GB. We stream them to disk rather than buffering in memory, and we extract
defensively since the archives come from a third party.
"""

from __future__ import annotations

import logging
import shutil
import sys
import tarfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

CAPSULE_URL = "https://corebench.cs.princeton.edu/capsules/{capsule_id}.tar.gz"

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class CapsuleError(RuntimeError):
    """Raised when a capsule cannot be downloaded, extracted, or prepared."""


def capsule_size_bytes(capsule_id: str, timeout: int = 30) -> int | None:
    """HEAD request; return Content-Length, or None if unavailable."""
    url = CAPSULE_URL.format(capsule_id=capsule_id)
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException:
        logger.warning("HEAD request failed for %s", url, exc_info=True)
        return None

    length = resp.headers.get("Content-Length")
    if length is None:
        return None
    try:
        return int(length)
    except ValueError:
        return None


def _is_within_directory(directory: Path, target: Path) -> bool:
    try:
        directory = directory.resolve()
        target = target.resolve()
    except OSError:
        return False
    return directory == target or directory in target.parents


def _safe_extract(tar: tarfile.TarFile, dest_dir: Path) -> None:
    """Extract `tar` into `dest_dir`, refusing any member that would land
    outside it (path traversal via '..' or an absolute/symlink member).

    `tarfile.extractall(filter="data")` (Python 3.12+) does this natively,
    but the target runtime here is 3.10, so we replicate the essential
    check by hand.
    """
    safe_members = []
    for member in tar.getmembers():
        member_path = dest_dir / member.name
        if not _is_within_directory(dest_dir, member_path):
            logger.warning("Skipping unsafe tar member: %s", member.name)
            continue
        if member.issym() or member.islnk():
            link_target = dest_dir / member.name
            link_target = link_target.parent / member.linkname
            if not _is_within_directory(dest_dir, link_target):
                logger.warning("Skipping unsafe tar link member: %s", member.name)
                continue
        safe_members.append(member)
    tar.extractall(dest_dir, members=safe_members)


def download_capsule(capsule_id: str, dest_dir: Path, *, force: bool = False) -> Path:
    """Download + extract to dest_dir/capsule_id/. Returns that path.
    Skips download if already extracted unless force. Streams to disk (never
    load into memory). Show progress to stderr. Clean up the tarball after
    extraction. Raise CapsuleError on failure."""
    dest_dir = Path(dest_dir)
    capsule_dir = dest_dir / capsule_id

    if capsule_dir.exists() and any(capsule_dir.iterdir()) and not force:
        logger.info("Capsule %s already extracted at %s; skipping", capsule_id, capsule_dir)
        return capsule_dir

    dest_dir.mkdir(parents=True, exist_ok=True)
    if capsule_dir.exists() and force:
        shutil.rmtree(capsule_dir)
    capsule_dir.mkdir(parents=True, exist_ok=True)

    url = CAPSULE_URL.format(capsule_id=capsule_id)
    tar_path = dest_dir / f"{capsule_id}.tar.gz"

    try:
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            total = resp.headers.get("Content-Length")
            total_bytes = int(total) if total is not None else None
            downloaded = 0
            with tar_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes:
                        pct = 100 * downloaded / total_bytes
                        print(
                            f"\r[{capsule_id}] {downloaded / 1e6:.1f}/{total_bytes / 1e6:.1f} MB ({pct:.1f}%)",
                            end="",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"\r[{capsule_id}] {downloaded / 1e6:.1f} MB",
                            end="",
                            file=sys.stderr,
                        )
            print(file=sys.stderr)
    except requests.RequestException as exc:
        tar_path.unlink(missing_ok=True)
        raise CapsuleError(f"Failed to download capsule {capsule_id!r} from {url}: {exc}") from exc

    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            _safe_extract(tar, capsule_dir)
    except tarfile.TarError as exc:
        raise CapsuleError(f"Failed to extract capsule {capsule_id!r}: {exc}") from exc
    finally:
        tar_path.unlink(missing_ok=True)

    _flatten_single_wrapper_dir(capsule_dir)

    return capsule_dir


def _flatten_single_wrapper_dir(capsule_dir: Path) -> None:
    """CORE-bench tarballs commonly wrap their entire contents in one
    top-level directory (often named after the capsule id itself), so a
    naive extract leaves `code/`, `results/`, etc. one level deeper than
    callers (notably prepare_tier) expect. If extraction produced exactly
    one top-level directory and nothing else, hoist its contents up into
    capsule_dir and remove the now-empty wrapper.
    """
    entries = list(capsule_dir.iterdir())
    if len(entries) != 1 or not entries[0].is_dir():
        return

    wrapper = entries[0]
    for child in list(wrapper.iterdir()):
        shutil.move(str(child), str(capsule_dir / child.name))
    wrapper.rmdir()


def prepare_tier(capsule_dir: Path, tier: str, work_dir: Path) -> Path:
    """Materialise the agent-visible view of a capsule for a given tier.

    Mirrors the official CORE-bench harness (benchmark/benchmark.py,
    ~lines 218-233), which applies two independent cuts:

        if tier != "easy":
            empty (not delete) results/
        if tier != "medium":
            remove REPRODUCING.md, environment/, code/run(.sh)

    Read together:
      easy:   results/ stays populated; REPRODUCING.md, environment/, and
              code/run(.sh) are stripped. A pure information-extraction
              task with the reproduction scaffolding removed -- NOT
              "medium plus answers".
      medium: results/ is emptied (kept as an empty dir, not deleted);
              REPRODUCING.md, environment/, and the run scripts are kept.
      hard:   results/ is emptied (kept as an empty dir); REPRODUCING.md,
              environment/, and the run scripts are all stripped.

    Returns the prepared directory. Raise ValueError on unknown tier.
    """
    if tier not in ("easy", "medium", "hard"):
        raise ValueError(f"Unknown tier {tier!r}; expected 'easy', 'medium', or 'hard'")

    capsule_dir = Path(capsule_dir)
    work_dir = Path(work_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    shutil.copytree(capsule_dir, work_dir)

    if tier != "easy":
        results_dir = work_dir / "results"
        if results_dir.exists():
            shutil.rmtree(results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Emptied results/ for tier=%s at %s", tier, work_dir)

    if tier != "medium":
        (work_dir / "REPRODUCING.md").unlink(missing_ok=True)
        environment_dir = work_dir / "environment"
        if environment_dir.exists():
            shutil.rmtree(environment_dir)
        (work_dir / "code" / "run.sh").unlink(missing_ok=True)
        (work_dir / "code" / "run").unlink(missing_ok=True)
        logger.info(
            "Removed REPRODUCING.md, environment/, and run scripts for tier=%s at %s",
            tier,
            work_dir,
        )

    return work_dir
