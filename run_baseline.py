#!/usr/bin/env python3
"""CLI entry point for the single-pass reproducibility baseline.

Examples
--------
    python run_baseline.py --capsule capsule-9052293 --tier easy
    python run_baseline.py --subset small --tier hard --limit 5
    python run_baseline.py --list
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from repro_agent import baseline, capsules, dataset  # noqa: E402
from repro_agent.sandbox import docker_available  # noqa: E402

REPO_ROOT = Path(__file__).parent
DEFAULT_CAPSULE_DIR = REPO_ROOT / "capsules"
DEFAULT_WORK_DIR = REPO_ROOT / "work"
DEFAULT_RESULTS_DIR = REPO_ROOT / "results"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run the single-pass CORE-Bench reproducibility baseline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--capsule", action="append", default=None,
                   help="Capsule id to run (repeatable). Overrides --subset.")
    p.add_argument("--tier", choices=("easy", "hard"), default="easy",
                   help="easy: read the provided results/. hard: install and run the code.")
    p.add_argument("--split", choices=("test", "train"), default="test")
    p.add_argument("--subset", choices=("all", "python", "small"), default="small",
                   help="'small' = Python, single-question, no figure questions.")
    p.add_argument("--limit", type=int, default=1, help="Max tasks to run.")
    p.add_argument("--timeout", type=int, default=900, help="Per-container timeout (s).")
    p.add_argument("--capsule-dir", type=Path, default=DEFAULT_CAPSULE_DIR)
    p.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    p.add_argument("--out", type=Path, default=None,
                   help="Where to write the results JSON.")
    p.add_argument("--list", action="store_true",
                   help="List the selected tasks and exit without running.")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def choose_tasks(args: argparse.Namespace) -> list[dataset.Task]:
    tasks = dataset.load_tasks(args.split)
    if args.capsule:
        return dataset.select_subset(tasks, capsule_ids=args.capsule)
    if args.subset == "all":
        return tasks[: args.limit]
    if args.subset == "python":
        return dataset.select_subset(tasks, language="Python")[: args.limit]
    return dataset.select_subset(
        tasks, language="Python", max_questions=1, exclude_vision=True
    )[: args.limit]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    tasks = choose_tasks(args)
    if not tasks:
        print("No tasks matched the given selection.", file=sys.stderr)
        return 2

    if args.list:
        for t in tasks:
            size = capsules.capsule_size_bytes(t.capsule_id)
            size_str = f"{size / 1e6:8.1f} MB" if size else "        ? MB"
            print(f"{t.capsule_id}  {size_str}  {t.language:7s} "
                  f"q={t.n_questions}  {t.capsule_title[:60]}")
        return 0

    if args.tier == "hard" and not docker_available():
        print("Docker is required for --tier hard but 'docker info' failed.",
              file=sys.stderr)
        return 3

    args.capsule_dir.mkdir(parents=True, exist_ok=True)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    DEFAULT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    runs = []
    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}] {task.capsule_id} ({args.tier}) "
              f"- {task.capsule_title[:60]}", flush=True)
        result = baseline.run_task(
            task, args.tier,
            capsule_root=args.capsule_dir,
            work_root=args.work_dir,
            timeout_s=args.timeout,
        )
        runs.append(result)
        status = "CORRECT" if result.task_correct else "incorrect"
        where = f" (failed at: {result.failed_stage})" if result.failed_stage else ""
        print(f"    -> {status}{where}  {result.duration_s:.1f}s  "
              f"${result.cost_usd:.4f}", flush=True)

    n_correct = sum(r.task_correct for r in runs)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tier": args.tier,
        "split": args.split,
        "n_tasks": len(runs),
        "n_correct": n_correct,
        "task_accuracy": n_correct / len(runs),
        "total_cost_usd": round(sum(r.cost_usd for r in runs), 4),
        "total_duration_s": round(sum(r.duration_s for r in runs), 1),
        "failure_stages": {
            stage: sum(1 for r in runs if r.failed_stage == stage)
            for stage in baseline.STAGES
        },
        "runs": [r.to_dict() for r in runs],
    }

    out = args.out or DEFAULT_RESULTS_DIR / f"baseline_{args.tier}_{args.split}.json"
    out.write_text(json.dumps(summary, indent=2))

    print(f"\n{'=' * 60}")
    print(f"Task accuracy ({args.tier}): {n_correct}/{len(runs)} "
          f"= {summary['task_accuracy']:.1%}")
    print(f"Total cost: ${summary['total_cost_usd']:.4f}   "
          f"Total time: {summary['total_duration_s']:.1f}s")
    print(f"Results written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
