# Generative AI use disclosure

**Course:** CSE598 Agentic AI. **Assignment:** Capstone Project Proposal.
**Student:** Jason Lunder. **Date of work:** 2026-09-06.

## Scope of permission

The course policy permits generative AI use with disclosure and a full
interaction trace. The instructor additionally gave verbal permission for
generative AI to produce the first pass of this assignment, and generative-AI
code authorship is expected for the proposal's runnable baseline.

This document summarises how AI was used. It does not replace the required
full trace; see [Interaction trace](#interaction-trace).

## Tools

| Tool | Role |
|---|---|
| Claude Code (Claude Opus 5) | Orchestrator: held the task, made tool calls, wrote code, ran experiments |
| Claude Sonnet 5 (subagents) | Implementation of individual modules |
| Claude Fable 5.1 (subagents) | Review passes and prose revision |

Roughly 16 subagents were used across brainstorming, research, implementation,
and review. The baseline itself calls `claude-sonnet-5` at run time through
`litellm`.

## What the student decided

- Rejected the first slate of candidate problems. The AI proposed four
  options; the student rejected them on the grounds that they were problems
  *about* agent internals (context compaction, agent memory, self-verifying
  code review) rather than real-world problems an agentic system solves. This
  reframing determined the entire direction of the project.
- Selected computational reproducibility from the second slate of 20
  candidates.
- Chose provider-agnostic LLM access over a single vendor.
- Chose the strict single-pass, no-retry baseline design, accepting that it
  would score poorly, so that the capstone's iterative loop can later be
  isolated as the only changed variable.
- Chose the naive result-file selection policy over question-guided retrieval.
- Directed repository location and publication.
- Repeatedly rejected the sample size as too small, driving the evaluation
  from 2 capsules to 9, then 29, then 70, then all 90.
- Directed the addition of figure/image input.
- Directed the writing style and the review passes.

## What the AI produced

- **Candidate problems.** Four brainstorming agents produced 20 candidates
  across education, bureaucracy, technical operations, and knowledge work,
  each with a proposed baseline, metric, and ground-truth source. The student
  guided the framing and made the selection.
- **All source code** in `src/repro_agent/` and `run_baseline.py`, written to
  interfaces fixed in `CONTRACTS.md`. `scoring.py` is a port of the official
  CORE-Bench grader (MIT, attributed in `third_party/NOTICE`), not original
  work.
- **All experiments.** 180 task-runs across 90 capsules at two tiers, plus the
  supporting downloads and measurements. Every number in the proposal comes
  from a committed file in `results/`.
- **First-pass draft of all seven proposal sections**, in LaTeX. The student
  is rewriting the prose.
- **Review passes.** Three independent agents audited the work against the
  rubric, the upstream reference implementation, and the research literature.
  Their reports are in `docs/review-rubric.md`, `docs/review-code.md`, and
  `docs/review-approach.md`.

## Errors the AI made and corrected

Recording these because they bear on how much the output should be trusted.

- Claimed `capsule-9052293` required three sequential fixes. The shipped plan
  already contained `cd code`, so the relative-path failure never occurred. It
  is two fixes. Corrected in both documents.
- Wrote a `prepare_tier` specification that would have given hard-tier runs a
  Dockerfile and reproduction instructions, silently turning them into the
  medium tier and inflating scores. Caught by reading the upstream harness.
- Ported the official scorer to catch exceptions per key. Upstream aborts
  grading at the first non-orderable answer. The port inflated per-question
  accuracy until corrected.
- Reported two-capsule numbers while the committed results file held one
  capsule, because a screenshot re-run had overwritten it. Caught in review.
- Sent `temperature` to a model that rejects the parameter, and left
  `litellm`'s OpenAI path free to retry twice, which contradicted the
  single-pass claim.

## Verification the student can perform

Every claim in the proposal is checkable without trusting the AI:

```bash
python run_baseline.py --list --subset all --limit 45   # no key needed
python run_baseline.py --capsule capsule-9052293 --tier easy
```

Results in `results/baseline_<tier>_<split>_all.json` carry `generated_at`,
the model string, per-stage timings, and per-question grading counts.

## Interaction trace

The full session transcript is required in addition to this summary. It is
stored locally as Claude Code session `01S4KDmZZRqQLBakaCQ3Xhb7` under
`~/.claude/projects/-mnt-data-2-asu-CSE598/`. Contact the TA for the accepted
submission format for Claude transcripts, as the policy directs.

Note that subagent conversations are recorded separately from the main
transcript, so a complete trace requires the session directory rather than the
main `.jsonl` alone.
