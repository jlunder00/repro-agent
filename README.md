# repro-agent — a computational reproducibility baseline

An agentic system for **computationally reproducing published research**: given a
paper's code capsule, install its dependencies, run it, and report the numbers the
paper claims.

This repository contains the **runnable baseline** for a CSE598 capstone proposal.
The baseline is a deliberately strict, single-pass, no-retry pipeline. It is a
scientific control, not an attempt at a strong agent — see
[Why the baseline is intentionally weak](#why-the-baseline-is-intentionally-weak).

Evaluation uses [CORE-Bench](https://github.com/siegelz/core-bench)
(Siegel et al., [arXiv:2409.11363](https://arxiv.org/abs/2409.11363)): 270 tasks
from 90 papers across computer science, social science, and medicine, split
45 papers for training and 45 for testing, with each paper posed at three
difficulty tiers.

For reference, the strongest agent in the original paper (CORE-Agent with
GPT-4o) scored **60.00% / 57.78% / 21.48%** on the easy / medium / hard tiers
*of the 45-paper test split*. The hard tier is where the headroom is.

---

## Quick start

```bash
git clone <this repo> && cd repro-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then add ONE api key (see below)
export $(grep -v '^#' .env | xargs)

# See what would run, without running it (no API key or Docker needed):
python run_baseline.py --list --subset small --limit 5

# Easy tier: answers are read from the capsule's results/ directory.
python run_baseline.py --capsule capsule-4180912 --tier easy

# Hard tier: the pipeline must install dependencies and run the code itself.
python run_baseline.py --capsule capsule-4180912 --tier hard
```

Results are written to `results/baseline_<tier>_<split>.json`.

## Measured baseline results

Two Python capsules (`capsule-9052293`, `capsule-6003668`), `claude-sonnet-5`:

| Tier | Task accuracy | Per-question | $/task | s/task | Failure stage |
|---|---|---|---|---|---|
| easy | **2/2 = 100%** | 2/2 | $0.0034 | 3.0 | — |
| hard | **0/2 = 0%** | 0/2 | $0.0049 | 9.7 | execution (2/2) |

Every hard-tier failure is at the execution stage — none at planning or answer
extraction. That is the actionable finding: the iterative loop should target
dependency and invocation repair first.

### The failure that motivates the project

For `capsule-9052293` the single planning call proposed
`pip install openpyxl pandas && python code/script.py`. It failed, and with no
retry the pipeline reported `null`. The capsule *is* reproducible — but only
through three sequential fixes, each discoverable **only by observing the
previous failure**:

1. `ModuleNotFoundError: xlrd` → install `xlrd`
2. `FileNotFoundError` → the script uses paths relative to `code/`, so `cd code` first
3. `XLRDError: Excel xlsx file; not supported` → `xlrd` 2.x **dropped** `.xlsx`
   support, so pin `xlrd==1.2.0` — an *older* version of what was just installed

With all three, the capsule reproduces `0.844703753651819` exactly. No amount of
up-front planning from a README gets to step 3; you have to run it and read the
traceback. That is the gap the capstone system closes.

## Requirements

| Requirement | Needed for | Notes |
|---|---|---|
| Python 3.10+ | everything | |
| An LLM API key | any real run | `ANTHROPIC_API_KEY` **or** `OPENAI_API_KEY` |
| Docker | `--tier hard` only | must be running; `--tier easy` never executes code |
| Network | capsule download | capsules are fetched from Princeton on first use and cached |

The project is **provider-agnostic** via [litellm](https://github.com/BerriAI/litellm):
set whichever key you already have. Precedence is `REPRO_AGENT_MODEL` >
`ANTHROPIC_API_KEY` > `OPENAI_API_KEY`. Override the model directly with:

```bash
export REPRO_AGENT_MODEL=openai/gpt-4o-mini
```

## The three difficulty tiers

CORE-Bench presents each capsule at three tiers. This baseline implements two of
them; `medium` is out of scope because it requires Docker-in-Docker.

| Tier | `results/` | `REPRODUCING.md`, `environment/`, run scripts | Docker |
|---|---|---|---|
| `easy` | **populated** — answers are on disk | removed | no |
| `medium` | emptied | **kept** (this is where the Dockerfile lives) | yes (DinD) — *not implemented* |
| `hard` | emptied | removed | yes |

`prepare_tier()` reproduces the official rule from `benchmark/benchmark.py`
exactly. Two details are easy to get wrong and both matter:

- The easy tier is **not** "medium plus answers". It also strips the
  reproduction scaffolding, making it a pure information-extraction task.
- The `results/` directory is **emptied, not deleted**, for medium and hard.

Getting this wrong in the permissive direction would hand a hard-tier run a
Dockerfile and reproduction instructions — silently turning it into the medium
tier and inflating the reported score.

## How answers are graded

Grading is ported verbatim from the official CORE-Bench scorer so that numbers
produced here stay comparable to the published leaderboard
(`src/repro_agent/scoring.py`; see `third_party/NOTICE`).

- **Numeric** answers are correct when they fall inside a 95% *prediction interval*
  built from three ground-truth runs of the original code:
  `mean ± t₀.₉₇₅,ₙ₋₁ · s · √(1 + 1/n)`.
  This tolerates genuine run-to-run stochasticity (seeds, GPU nondeterminism)
  while still rejecting wrong answers. Where the three runs agreed exactly, the
  interval collapses to a point and exact equality is required.
- **String** answers are compared case-insensitively; **lists** exactly.
- A **task** counts as correct only if *every* question in it is correct.
  Partially reproducing a paper is not reproducing it.

## Why the baseline is intentionally weak

The pipeline runs each capsule through five stages exactly once:

```
prepare → plan → execute → extract → score
```

It never retries, never reflects on a failure, and never re-plans after observing
an error — even though that is obviously what a competent engineer would do, and
obviously what would raise the score.

That restraint is the experiment. The capstone system will add an iterative
**execute → observe → diagnose → re-plan** loop. If the control were already
allowed to retry, a later improvement could not be attributed to the reasoning
loop rather than to simply having had more attempts. Keeping the control strict
is what makes the eventual comparison interpretable.

**Do not add retry logic to `baseline.py`.** It would silently invalidate the
comparison the whole project is built around.

Because each run records which stage it died at, results also give a failure-mode
breakdown (dependency install vs. execution vs. answer extraction), which is far
more actionable than a single pass/fail bit.

## Repository layout

```
run_baseline.py              CLI entry point
CONTRACTS.md                 fixed module interfaces
src/repro_agent/
    dataset.py               CORE-Bench task loading and subset selection
    capsules.py              capsule download, extraction, per-tier preparation
    llm.py                   provider-agnostic LLM access (litellm)
    sandbox.py               single-shot Docker execution
    baseline.py              the strict single-pass pipeline
    scoring.py               vendored CORE-Bench scorer (MIT, attributed)
examples/                    vendored task metadata + official tier prompts
results/                     run output (JSON)
proposal/                    the LaTeX proposal
third_party/                 upstream licence and attribution
```

## Choosing what to run

Capsules vary from 0.1 MB to 2.4 GB. Two thirds of the test split are under
26 MB, and the default `--subset small` restricts to Python, single-question,
non-figure tasks so a grader can get a result quickly.

```bash
python run_baseline.py --list --subset small --limit 10   # sizes shown, nothing downloaded
```

Downloaded capsules are cached in `capsules/` (git-ignored) and reused across
tiers.

## Known limitations

- **R capsules are out of scope.** Roughly half of CORE-Bench is R; this baseline
  targets Python only.
- **GPU and multi-GB capsules are excluded** from the default subset.
- **Vision/figure questions** (keys containing `fig`) are excluded.
- **Dependency rot is real.** Much of this code is years old and may no longer
  install cleanly on any modern base image — which is itself a finding about the
  state of computational reproducibility, and a headline motivation for the project.
- **`medium` tier is unimplemented** (needs Docker-in-Docker).

## Attribution

CORE-Bench is by Zachary S. Siegel, Sayash Kapoor, Nitya Nadgir, Benedikt Stroebl,
and Arvind Narayanan (arXiv:2409.11363), MIT-licensed. The scoring logic in
`src/repro_agent/scoring.py` is a port of theirs; capsules are downloaded from
their public server. See `third_party/NOTICE`.
