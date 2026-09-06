"""Loading and filtering of the CORE-bench task set.

Tasks are vendored as flat JSON lists under ``examples/`` -- no network
access is needed (or performed) to load them.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

CORE_TEST_JSON: Path = _REPO_ROOT / "examples" / "core_test.json"
CORE_TRAIN_JSON: Path = _REPO_ROOT / "examples" / "core_train.json"


@dataclass(frozen=True)
class Task:
    capsule_id: str
    capsule_title: str
    field: str
    language: str
    task_prompt: str
    results: list[dict]
    capsule_doi: str

    @property
    def questions(self) -> list[str]:
        """Question strings, taken from the first ground-truth run.

        Every entry in ``results`` is a repeated run of the same underlying
        code, so they share the same set (and order) of question keys.
        """
        return list(self.results[0].keys())

    @property
    def n_questions(self) -> int:
        return len(self.questions)

    @property
    def has_vision_question(self) -> bool:
        return any("fig" in q.lower() for q in self.questions)


def _load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_tasks(split: str = "test") -> list[Task]:
    """split in {"test","train"}. Raises ValueError otherwise."""
    if split == "test":
        path = CORE_TEST_JSON
    elif split == "train":
        path = CORE_TRAIN_JSON
    else:
        raise ValueError(f"Unknown split {split!r}; expected 'test' or 'train'")

    raw = _load_json(path)
    tasks = [
        Task(
            capsule_id=entry["capsule_id"],
            capsule_title=entry["capsule_title"],
            field=entry["field"],
            language=entry["language"],
            task_prompt=entry["task_prompt"],
            results=entry["results"],
            capsule_doi=entry["capsule_doi"],
        )
        for entry in raw
    ]
    logger.info("Loaded %d tasks from split=%s (%s)", len(tasks), split, path)
    return tasks


def select_subset(
    tasks: list[Task],
    *,
    language: str | None = "Python",
    max_questions: int | None = None,
    exclude_vision: bool = True,
    capsule_ids: list[str] | None = None,
) -> list[Task]:
    """Filter tasks. `capsule_ids`, when given, overrides all other filters
    and preserves the given order."""
    if capsule_ids is not None:
        by_id = {t.capsule_id: t for t in tasks}
        return [by_id[cid] for cid in capsule_ids if cid in by_id]

    selected = tasks
    if language is not None:
        selected = [t for t in selected if t.language == language]
    if exclude_vision:
        selected = [t for t in selected if not t.has_vision_question]
    if max_questions is not None:
        selected = [t for t in selected if t.n_questions <= max_questions]
    return selected


def summarize(tasks: list[Task]) -> dict:
    """Quick counts by language, field, and total question count. Not part
    of the fixed contract -- just a convenience for eyeballing a subset."""
    by_language: dict[str, int] = {}
    by_field: dict[str, int] = {}
    n_questions = 0
    for t in tasks:
        by_language[t.language] = by_language.get(t.language, 0) + 1
        by_field[t.field] = by_field.get(t.field, 0) + 1
        n_questions += t.n_questions
    return {
        "n_tasks": len(tasks),
        "by_language": by_language,
        "by_field": by_field,
        "n_questions": n_questions,
    }
