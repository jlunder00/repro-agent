# repro-agent: a computational reproducibility baseline

An agentic system for computationally reproducing published research: given a
paper's code capsule, install its dependencies, run it, and report the numbers
the paper claims.

This repository contains the runnable baseline for a CSE598 capstone proposal.
The baseline is a single-pass, no-retry pipeline that serves as the control for
the proposed system (see [Design rationale](#design-rationale)).

Evaluation uses [CORE-Bench](https://github.com/siegelz/core-bench)
(Siegel et al., [arXiv:2409.11363](https://arxiv.org/abs/2409.11363)): 270 tasks
from 90 papers across computer science, social science, and medicine, split
45 papers for training and 45 for testing, with each paper posed at three
difficulty tiers.

The strongest agent in the original paper (CORE-Agent with GPT-4o) scored
**60.00% / 57.78% / 21.48%** on the easy / medium / hard tiers of the 45-paper
test split.

---

## Quick start

```bash
git clone <this repo> && cd repro-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then add ONE api key (see below)
export $(grep -v '^#' .env | xargs)

# List what would run, without running it (no API key or Docker needed):
python run_baseline.py --list --subset all --limit 45 --split test

# One capsule, easy tier: answers are read from the capsule's results/ directory.
python run_baseline.py --capsule capsule-9052293 --tier easy

# One capsule, hard tier: the pipeline must install dependencies and run the code.
python run_baseline.py --capsule capsule-9052293 --tier hard

# A full split at one tier (repeat with --split train and --tier hard):
python run_baseline.py --subset all --limit 45 --split test --tier easy
```

Results are written to `results/baseline_<tier>_<split>.json` (override with
`--out`). The committed runs are `results/baseline_<tier>_<split>_all.json`.

## Measured baseline results

All 90 CORE-Bench capsules (45 test + 45 train, Python and R), `claude-sonnet-5`,
one run per task, figures attached as images at the easy tier:

| Tier | Tasks | Written questions | Vision questions | All questions | $/task | s/task | Execute stage |
|---|---|---|---|---|---|---|---|
| easy | 43/90 = 47.8% | 63/98 = 64.3% | 38/83 = 45.8% | 101/181 = 55.8% | $0.0178 | 4.2 | not run |
| hard | 0/90 | 0/98 | 0/83 | 0/181 | $0.0116 | 22.0 | succeeded 0/90 |

Totals: $1.61 for the easy sweep (152 images sent), $1.04 for the hard sweep.

Easy tier by split and language: test Python 15/22, test R 7/23, train Python
17/27, train R 4/18.

Task accuracy is all-or-nothing, so per-question accuracy is reported alongside
it.

### Example failure

For `capsule-9052293` the planning call proposed
`pip install openpyxl pandas && cd code && python script.py`. It failed, and
with no retry the pipeline reported `null`. The capsule reproduces after two
sequential fixes, the second visible only in the traceback left by the first:

1. `ModuleNotFoundError: xlrd` -> install `xlrd`
2. `XLRDError: Excel xlsx file; not supported` -> `xlrd` 2.x dropped `.xlsx`
   support, so pin `xlrd==1.2.0` - an older release of what was just installed

With both, the capsule reproduces `0.844703753651819` exactly.

## Requirements

| Requirement | Needed for | Notes |
|---|---|---|
| Python 3.10+ | everything | |
| An LLM API key | any real run | `ANTHROPIC_API_KEY` **or** `OPENAI_API_KEY` |
| Docker | `--tier hard` only | must be running; `--tier easy` never executes code |
| Network | capsule download | capsules are fetched from Princeton on first use and cached |

The project is provider-agnostic via [litellm](https://github.com/BerriAI/litellm).
Precedence is `REPRO_AGENT_MODEL` > `ANTHROPIC_API_KEY` > `OPENAI_API_KEY`.
Override the model directly with:

```bash
export REPRO_AGENT_MODEL=openai/gpt-4o-mini
```

## The three difficulty tiers

CORE-Bench poses each capsule at three tiers. `prepare_tier()` copies the
capsule and removes files according to the tier, matching the official
`benchmark/benchmark.py`. `results/` here means the capsule's own output
directory, the files the original authors shipped in the tarball.

| Tier | Capsule `results/` | `REPRODUCING.md`, `environment/`, run scripts | Docker |
|---|---|---|---|
| `easy` | kept | removed | not used |
| `medium` | emptied | kept (includes the Dockerfile) | Docker-in-Docker; not implemented |
| `hard` | emptied | removed | required |

On the easy tier the answers are read from the kept `results/` without running
anything. On the hard tier the agent must install dependencies and run the
code with only the README to go on.

## How answers are graded

Grading is ported verbatim from the official CORE-Bench scorer so that numbers
produced here are comparable to the published leaderboard
(`src/repro_agent/scoring.py`; see `third_party/NOTICE`).

- **Numeric** answers are correct when they fall inside a 95% prediction interval
  built from three ground-truth runs of the original code:
  `mean ± t₀.₉₇₅,ₙ₋₁ · s · √(1 + 1/n)`.
  This tolerates run-to-run stochasticity (seeds, GPU nondeterminism). Where
  the three runs agreed exactly, the interval collapses to a point and exact
  equality is required.
- **String** answers are compared case-insensitively; **lists** exactly.
- A **task** counts as correct only if every question in it is correct.

## Design rationale

The pipeline runs each capsule through five stages exactly once:

```
prepare → plan → execute → extract → score
```

It never retries, reflects on a failure, or re-plans after observing an error.

The capstone system will add an iterative execute → observe → diagnose → re-plan
loop. If the control could retry, an improvement could not be attributed to the
reasoning loop rather than to additional attempts.

**Do not add retry logic to `baseline.py`.** It would invalidate the comparison.

Each run records the stage at which it failed, so results also give a
failure-mode breakdown (dependency install vs. execution vs. answer extraction).

## Repository layout

```
run_baseline.py              CLI entry point
src/repro_agent/
    dataset.py               CORE-Bench task loading and subset selection
    capsules.py              capsule download, extraction, per-tier preparation
    llm.py                   provider-agnostic LLM access (litellm), image input
    sandbox.py               single-shot Docker execution
    baseline.py              the single-pass pipeline
    scoring.py               vendored CORE-Bench scorer (MIT, attributed)
examples/                    vendored task metadata + official tier prompts
results/                     run output (JSON)
third_party/                 upstream licence and attribution
```

## Choosing what to run

`--subset all` selects every capsule in a split (45 per split; 22 Python and
23 R in test, 27 Python and 18 R in train). `--subset python` keeps only Python
capsules. `--subset small` selects 5 single-question tasks for smoke tests and
is too small to serve as an evaluation set. `--limit` caps the count; use
`--limit 45` for a full split.

Capsules range from 0.1 MB to 2.4 GB. Size is a download concern, not an
eligibility criterion. GPU-flagged capsules (`"gpu"` in `REPRODUCING.md`) are
not filtered out; they run on CPU.

```bash
python run_baseline.py --list --subset all --limit 45 --split test   # sizes shown, nothing downloaded
```

Downloaded capsules are cached in `capsules/` (git-ignored) and reused across
tiers.

## Known limitations

- **Figure cap.** At most 6 figures are attached per capsule, chosen by sorted
  filename. 17 capsules have more than 6, so a question about a figure outside
  that set stays unanswerable.
- **Result truncation.** Result files are concatenated in directory order up to
  a character budget, so an answer late in a long log can be truncated away.
- **One run per task.** The model is sampled without a fixed temperature, so
  repeated runs are needed before any comparison of arms.
- **All-or-nothing task scoring.** Per-question accuracy is reported alongside
  task accuracy.
- **The base image is a fixed lookup**: `python:3.11-slim` for Python,
  `r-base:4.4.1` for R. The lookup exists so an R capsule is not run without an
  interpreter, which would measure the image choice rather than the plan. Code
  that targets an older interpreter cannot be matched. Image choice should
  become a recorded per-run variable.
- **No GPU execution.** GPU-flagged capsules run on CPU.
- **Dependency rot.** Much of this code is years old and may no longer install
  cleanly on a modern base image.
- **`medium` tier is unimplemented** (needs Docker-in-Docker).

## Attribution

CORE-Bench is by Zachary S. Siegel, Sayash Kapoor, Nitya Nadgir, Benedikt Stroebl,
and Arvind Narayanan (arXiv:2409.11363), MIT-licensed. The scoring logic in
`src/repro_agent/scoring.py` is a port of theirs; capsules are downloaded from
their public server. See `third_party/NOTICE`.
