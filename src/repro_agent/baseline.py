"""The strict single-pass baseline.

This module is a *scientific control*, not an attempt at a good agent.  It
walks each capsule through the pipeline exactly once and never looks back:

    prepare -> plan -> execute -> extract -> score

There is deliberately no retry, no reflection, and no re-planning after
observing a failure.  That restraint is the entire point.  The capstone
system will add an iterative execute-observe-diagnose-replan loop, and the
only way to attribute the resulting gain to *that loop* -- rather than to
simply having had more attempts -- is for the control to get exactly one.

Any future edit that adds a retry here breaks the experiment this file
exists to support.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import capsules, llm, scoring
from .dataset import Task
from .sandbox import ExecResult, run_in_container

logger = logging.getLogger(__name__)

# Ordered pipeline stages. Recording the stage a run died at is what lets
# Section 6's failure-mode breakdown say *where* reproduction broke down,
# which is far more actionable than a single pass/fail bit.
STAGES = ("prepare", "plan", "execute", "extract", "score")

MAX_README_CHARS = 8000
MAX_TREE_ENTRIES = 200
MAX_RESULT_CHARS = 12000

# Extensions never worth spending context budget on. Figures are the big one:
# a capsule's results/ is often mostly PNGs, and this project scopes figure
# questions out anyway.
_BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".pdf", ".eps",
    ".svg", ".pkl", ".pickle", ".npy", ".npz", ".h5", ".hdf5", ".pt", ".pth",
    ".zip", ".gz", ".tar", ".bz2", ".xz", ".so", ".o", ".bin", ".mat", ".rds",
}


def _looks_binary(text: str) -> bool:
    """Catch extensionless binaries that the suffix filter would let through.

    A capsule's ``results/output`` is a common shape and is usually text, so
    we sniff content rather than trusting the name: a NUL byte, or a high
    proportion of replacement characters from a failed decode, means binary.
    """
    head = text[:4096]
    if "\x00" in head:
        return True
    return bool(head) and head.count("�") / len(head) > 0.05

PLAN_SYSTEM = (
    "You are helping reproduce the results of a published scientific paper. "
    "You will be shown a code capsule's file listing and README. Respond with "
    "a single shell command that installs any needed dependencies and runs the "
    "analysis. Respond ONLY with JSON of the form {\"command\": \"...\"}."
)

ANSWER_SYSTEM = (
    "You extract numerical and textual results from the output of scientific "
    "code. Answer each question exactly. Respond ONLY with a JSON object whose "
    "keys are the exact question strings given to you and whose values are the "
    "answers. Use bare numbers for numeric answers, with no units or percent "
    "signs. If a value cannot be determined, use null."
)


@dataclass
class StageRecord:
    name: str
    ok: bool
    detail: str = ""
    duration_s: float = 0.0


@dataclass
class RunResult:
    """Everything one capsule-run produced, including how it failed."""

    capsule_id: str
    tier: str
    report: dict[str, Any] = field(default_factory=dict)
    stages: list[StageRecord] = field(default_factory=list)
    counts: dict[str, int] | None = None
    task_correct: bool = False
    cost_usd: float = 0.0
    duration_s: float = 0.0
    failed_stage: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "capsule_id": self.capsule_id,
            "tier": self.tier,
            "report": self.report,
            "counts": self.counts,
            "task_correct": self.task_correct,
            "cost_usd": round(self.cost_usd, 6),
            "duration_s": round(self.duration_s, 2),
            "failed_stage": self.failed_stage,
            "error": self.error,
            "stages": [
                {"name": s.name, "ok": s.ok, "detail": s.detail,
                 "duration_s": round(s.duration_s, 2)}
                for s in self.stages
            ],
        }


def _file_tree(root: Path, limit: int = MAX_TREE_ENTRIES) -> str:
    entries: list[str] = []
    for path in sorted(root.rglob("*")):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root)
        entries.append(f"{rel}/" if path.is_dir() else f"{rel}")
        if len(entries) >= limit:
            entries.append(f"... (listing truncated at {limit} entries)")
            break
    return "\n".join(entries)


def _read_readme(root: Path) -> str:
    """Collect the capsule's human-facing instructions.

    Capsules keep their README under ``code/`` at least as often as at the
    top level (``code/README.txt`` is the common shape), so searching only
    the root would silently hand the planner an empty brief on the hard
    tier -- where the README is the *only* guidance it gets.

    ``REPRODUCING.md`` is included when present, but note the official tier
    preparation deletes it for every tier except medium, so on easy and hard
    this will normally find only the README.
    """
    chunks: list[str] = []
    budget = MAX_README_CHARS
    for directory in (root, root / "code"):
        if not directory.is_dir():
            continue
        for pattern in ("README*", "readme*", "REPRODUCING*"):
            for candidate in sorted(directory.glob(pattern)):
                if not candidate.is_file() or budget <= 0:
                    continue
                text = candidate.read_text(errors="replace")[:budget]
                budget -= len(text)
                rel = candidate.relative_to(root)
                chunks.append(f"--- {rel} ---\n{text}")
    return "\n\n".join(chunks) if chunks else "(no README found)"


def select_result_files(results_dir: Path, questions: list[str],
                        char_budget: int = MAX_RESULT_CHARS) -> str:
    """Choose which files from a capsule's ``results/`` dir to show the model.

    TODO(jason): this is a real design decision and it materially changes how
    strong the easy-tier baseline looks, so it is worth making deliberately
    rather than defaulting.

    The tension: a capsule's ``results/`` directory can hold dozens of files --
    logs, CSVs, figures, serialized models -- and they will not all fit in a
    context window. Three defensible policies:

      1. Naive: concatenate every text-like file until the budget runs out,
         in directory order. Simple and unbiased, but a large log file early
         in the listing can crowd out the one CSV that holds the answer.
      2. Size-first: prefer small files, on the theory that summary metrics
         live in small files while bulk data does not. Cheap heuristic, but
         it will miss answers buried at the end of a long training log.
      3. Question-guided: score each file by lexical overlap between its name
         (or head) and the question text, and take the best-matching ones.
         Most likely to find the answer, but it leaks a little of the question
         into retrieval, which you should disclose when describing the method.

    Whichever you choose, keep the total under ``char_budget`` and skip binary
    files (figures, .pkl, .npz). Implement it here and delete this TODO.
    """
    if not results_dir.is_dir():
        return "(no results directory)"

    chunks: list[str] = []
    remaining = char_budget
    skipped: list[str] = []

    for path in sorted(results_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() in _BINARY_SUFFIXES:
            skipped.append(str(path.relative_to(results_dir)))
            continue
        if remaining <= 0:
            skipped.append(str(path.relative_to(results_dir)))
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            skipped.append(str(path.relative_to(results_dir)))
            continue
        if _looks_binary(text):
            skipped.append(str(path.relative_to(results_dir)))
            continue

        rel = path.relative_to(results_dir)
        body = text[:remaining]
        remaining -= len(body)
        note = "" if len(body) == len(text) else "\n... (file truncated)"
        chunks.append(f"--- results/{rel} ---\n{body}{note}")

    if skipped:
        chunks.append(
            "--- files not shown (binary, unreadable, or over budget) ---\n"
            + "\n".join(skipped)
        )
    return "\n\n".join(chunks) if chunks else "(results directory is empty)"


def _plan_command(prepared: Path) -> tuple[str, llm.LLMResponse]:
    prompt = (
        f"File listing:\n{_file_tree(prepared)}\n\n"
        f"{_read_readme(prepared)}\n\n"
        "Give the single shell command to install dependencies and run the analysis."
    )
    response = llm.complete(prompt, system=PLAN_SYSTEM, max_tokens=1024)
    command = llm.extract_json(response.text).get("command", "").strip()
    if not command:
        raise llm.LLMError("model returned no command")
    return command, response


def _extract_answers(questions: list[str], evidence: str) -> tuple[dict, llm.LLMResponse]:
    prompt = (
        "Questions to answer:\n"
        + "\n".join(f"- {q}" for q in questions)
        + f"\n\nProgram output / results:\n{evidence}\n\n"
        "Return the JSON object mapping each exact question string to its answer."
    )
    response = llm.complete(prompt, system=ANSWER_SYSTEM, max_tokens=2048)
    return llm.extract_json(response.text), response


def run_task(task: Task, tier: str, *, capsule_root: Path, work_root: Path,
             timeout_s: int = 900) -> RunResult:
    """Execute the single-pass pipeline for one capsule at one tier."""
    started = time.time()
    result = RunResult(capsule_id=task.capsule_id, tier=tier)

    def record(name: str, ok: bool, detail: str, t0: float) -> None:
        result.stages.append(StageRecord(name, ok, detail, time.time() - t0))

    # -- prepare ---------------------------------------------------------
    t0 = time.time()
    try:
        downloaded = capsules.download_capsule(task.capsule_id, capsule_root)
        # prepare_tier wipes and rebuilds its destination, so give every
        # (capsule, tier) pair its own directory. Passing a shared root would
        # make each run destroy the previous one's working copy.
        prepared = capsules.prepare_tier(
            downloaded, tier, work_root / f"{task.capsule_id}__{tier}"
        )
        record("prepare", True, str(prepared), t0)
    except Exception as exc:  # noqa: BLE001 - stage failure is data
        record("prepare", False, str(exc), t0)
        result.failed_stage, result.error = "prepare", str(exc)
        result.duration_s = time.time() - started
        return result

    evidence = ""

    if tier == "easy":
        # The easy tier forbids execution: the answers are already on disk and
        # the task is purely one of locating and reading them.
        t0 = time.time()
        try:
            evidence = select_result_files(prepared / "results", task.questions)
            record("plan", True, "read results/ (no execution)", t0)
            result.stages.append(StageRecord("execute", True, "skipped by tier", 0.0))
        except Exception as exc:  # noqa: BLE001
            record("plan", False, str(exc), t0)
            result.failed_stage, result.error = "plan", str(exc)
            result.duration_s = time.time() - started
            return result
    else:
        # -- plan --------------------------------------------------------
        t0 = time.time()
        try:
            command, plan_response = _plan_command(prepared)
            result.cost_usd += plan_response.cost_usd or 0.0
            record("plan", True, command, t0)
        except Exception as exc:  # noqa: BLE001
            record("plan", False, str(exc), t0)
            result.failed_stage, result.error = "plan", str(exc)
            result.duration_s = time.time() - started
            return result

        # -- execute (exactly once; a non-zero exit is not retried) -------
        t0 = time.time()
        exec_result: ExecResult = run_in_container(command, prepared, timeout_s=timeout_s)
        record("execute", exec_result.exit_code == 0,
               f"exit={exec_result.exit_code} timed_out={exec_result.timed_out}", t0)
        evidence = f"[exit code {exec_result.exit_code}]\n" \
                   f"STDOUT:\n{exec_result.stdout}\n\nSTDERR:\n{exec_result.stderr}"

    # -- extract ---------------------------------------------------------
    t0 = time.time()
    try:
        report, answer_response = _extract_answers(task.questions, evidence)
        result.cost_usd += answer_response.cost_usd or 0.0
        result.report = report
        record("extract", True, f"{len(report)} answers", t0)
    except Exception as exc:  # noqa: BLE001
        record("extract", False, str(exc), t0)
        result.failed_stage, result.error = "extract", str(exc)
        result.duration_s = time.time() - started
        return result

    (prepared / "report.json").write_text(json.dumps(report, indent=2))

    # -- score -----------------------------------------------------------
    t0 = time.time()
    counts = scoring.eval_result_json(task.results, report)
    result.counts = counts
    result.task_correct = scoring.task_is_correct(counts)
    record("score", True, json.dumps(counts), t0)

    result.duration_s = time.time() - started
    return result
