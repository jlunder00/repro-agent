"""Answer scoring, ported from the official CORE-Bench harness.

The grading semantics here are deliberately identical to
``benchmark/evaluations.py`` in https://github.com/siegelz/core-bench
(MIT, Copyright (c) 2024 Zachary Siegel).  See ``third_party/NOTICE``.

Keeping these semantics byte-for-faithful is the whole point: it is what
lets a score produced by this repository be compared against the numbers
published in arXiv:2409.11363 rather than against a metric we invented.

The one substantive rule worth stating plainly, because it is easy to get
wrong: a *numeric* answer is counted correct when it falls inside a 95%
prediction interval built from the three ground-truth runs of the original
paper's code,

    mean +/- t(0.975, n-1) * s * sqrt(1 + 1/n)

which tolerates the genuine run-to-run stochasticity of scientific code
(random seeds, GPU nondeterminism) while still rejecting wrong answers.
Where the three runs agreed exactly the interval collapses to a point and
exact equality is required.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np
from scipy.stats import t as student_t


def _coerce_number(value: Any) -> Any:
    """Best-effort numeric coercion of a reported answer.

    Mirrors the upstream leniency: a model that answers ``"96.1%"`` or
    ``"96.1"`` is not punished for formatting.  Anything that will not
    parse is left untouched so it can still match as a string.
    """
    if isinstance(value, str):
        stripped = value.replace("%", "") if "%" in value else value
        try:
            return float(stripped)
        except (TypeError, ValueError):
            return value
    return value


def _prediction_interval(samples: List[float]) -> tuple[float, float]:
    """95% prediction interval for a new observation given `samples`.

    Note this is a *prediction* interval, not a confidence interval on the
    mean -- the extra ``1 +`` under the radical accounts for the variance of
    the new observation itself, which is what we are actually grading.
    """
    n = len(samples)
    mean = float(np.mean(samples))
    if n < 2:
        return (mean, mean)
    std = float(np.std(samples, ddof=1))
    t_value = float(student_t.ppf(0.975, n - 1))
    half_width = t_value * std * math.sqrt(1.0 + 1.0 / n)
    return (mean - half_width, mean + half_width)


def eval_result_json(
    gt_result: List[Dict[str, Any]],
    reported_result: Dict[str, Any],
) -> Dict[str, int]:
    """Grade one capsule's ``report.json`` against its ground-truth runs.

    Args:
        gt_result: the ``results`` list from the CORE-Bench dataset entry --
            one dict per ground-truth run of the original code.
        reported_result: the agent's ``report.json``, question -> answer.

    Returns counts of correct/total, split into "written" and "vision"
    questions.  Upstream treats any question whose key contains ``fig`` as a
    vision question; this project scopes vision questions out, but the split
    is preserved so totals stay comparable.
    """
    correct_written = 0
    correct_vision = 0

    first_run = gt_result[0]
    numeric_keys = [k for k, v in first_run.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    list_keys = [k for k, v in first_run.items() if isinstance(v, list)]
    string_keys = [k for k, v in first_run.items() if isinstance(v, str)]

    all_keys = numeric_keys + list_keys + string_keys
    total_written = len([k for k in all_keys if "fig" not in k])
    total_vision = len([k for k in all_keys if "fig" in k])

    reported = {k: _coerce_number(v) for k, v in reported_result.items()}

    intervals = {
        key: _prediction_interval([run[key] for run in gt_result if key in run])
        for key in numeric_keys
    }

    for key, value in reported.items():
        is_correct = False
        if key in numeric_keys:
            lower, upper = intervals[key]
            try:
                is_correct = bool(lower <= float(value) <= upper)
            except (TypeError, ValueError):
                is_correct = False
        elif key in list_keys:
            is_correct = value == first_run[key]
        elif key in string_keys:
            is_correct = str(value).lower() == str(first_run[key]).lower()

        if is_correct:
            if "fig" in key:
                correct_vision += 1
            else:
                correct_written += 1

    return {
        "correct_written_answers": correct_written,
        "correct_vision_answers": correct_vision,
        "total_written_questions": total_written,
        "total_vision_questions": total_vision,
    }


def task_is_correct(counts: Dict[str, int]) -> bool:
    """A task scores only if *every* one of its questions was answered correctly.

    This all-or-nothing rule is upstream's, and it is strict on purpose:
    partially reproducing a paper's results is not reproducing them.
    """
    return (
        counts["correct_written_answers"] == counts["total_written_questions"]
        and counts["correct_vision_answers"] == counts["total_vision_questions"]
        and (counts["total_written_questions"] + counts["total_vision_questions"]) > 0
    )
