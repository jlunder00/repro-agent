# Handoff: independent review of the capstone proposal

You have no prior context on this work. Read this file, then the artifacts it
points to, then perform the review described at the end.

## Situation

A CSE598 (Agentic AI) capstone proposal is complete and its baseline runs. The
student is about to rewrite the proposal prose in their own words. Before that
rewrite, the proposal needs one independent check by someone who was not
involved in producing it.

Three earlier review passes already happened. Their reports are in this
directory and their findings have been applied. Do not repeat them; use them to
avoid re-treading ground:

- `review-rubric.md` — compliance against the assignment template
- `review-code.md` — code correctness against the upstream reference
- `review-approach.md` — problem selection and experimental design

## The project

An agentic system for computational reproducibility of published research.
Given a paper's code capsule, install its dependencies, run it, and report the
paper's numerical results.

Evaluated on CORE-Bench (Siegel et al., arXiv:2409.11363): 90 capsules
(45 train / 45 test), Python and R, posed at three difficulty tiers.

The submitted artifact is a **strict single-pass, no-retry baseline**. It is a
control, not an attempt at a good agent. The capstone will add an iterative
loop; holding the control to one attempt is what will let the loop's
contribution be isolated later.

## Measured results

All 90 capsules, both implemented tiers, one run per task, `claude-sonnet-5`:

| Tier | Tasks | Written Q | Vision Q | All Q | Execute stage |
|---|---|---|---|---|---|
| easy | 43/90 (47.8%) | 63/98 (64.3%) | 38/83 (45.8%) | 101/181 (55.8%) | not run |
| hard | 0/90 (0%) | 0/98 | 0/83 | 0/181 (0%) | succeeded 0/90 |

Every number comes from `results/baseline_<tier>_<split>_all.json`.

## Files to read

| Path | What it is |
|---|---|
| `docs/ASSIGNMENT.md` | The verbatim course template and 100-point rubric |
| `proposal/proposal.tex`, `proposal/proposal.pdf` | The submission |
| `README.md` | Repository documentation |
| `src/repro_agent/` | Implementation |
| `results/*.json` | Every reported measurement |

## Facts that are settled — do not re-litigate

- Tier preparation matches the upstream harness exactly, verified against
  `benchmark/benchmark.py`. Easy keeps a populated `results/` but strips
  `REPRODUCING.md`, `environment/`, and run scripts; medium and hard empty
  `results/` rather than deleting it.
- `scoring.py` matches upstream semantics including aborting grading at the
  first non-orderable answer.
- `capsule-9052293` needs **two** sequential fixes, not three: install `xlrd`,
  then pin `xlrd==1.2.0` because `xlrd` 2.x dropped `.xlsx` support. The
  shipped plan already contains `cd code`.
- Base image is a fixed per-language lookup (`python:3.11-slim`,
  `r-base:4.4.1`). It is not an adaptive decision.
- The published CORE-Agent/AutoGPT numbers are context, not a like-for-like
  baseline: different model, year, and harness.

## Known limitations, already disclosed

At most six figures per capsule by sorted filename (13 capsules have more);
result files concatenated in directory order to a character budget; one run per
task with no fixed temperature; all-or-nothing task scoring; medium tier
unimplemented; GPU-flagged capsules run on CPU.

## Your task

1. **Rubric check.** Score the proposal against `docs/ASSIGNMENT.md` section by
   section. The template requires specific elements — Section 3 must name the
   implementation files, Section 1 must state the intended user and both
   success and failure, Section 5 has six required items. Verify each is
   present, not merely gestured at.
2. **Claim verification.** Every factual claim about the code must be true of
   the code, and every number must match `results/`. Report any mismatch with
   the exact file and value.
3. **Length and format.** Must be 1–2 pages and compile cleanly. Confirm the
   figure is legible at its printed size.
4. **Prose readiness.** The student is rewriting in their own words. Flag any
   sentence that is vague, hedged, or asserts more than the evidence supports,
   so it does not get carried into the rewrite.
5. **Anything the three prior reviews missed.**

## Constraints

- Read-only on `src/`, `results/`, and `proposal/`. Report fixes; do not apply
  them.
- Do not spawn subagents.
- Write findings to `docs/review-final.md`: a summary table, then per-issue
  detail with location and suggested fix, then a prioritized must-fix list.
- No mannered speech. Factual statements only. State the defect, its
  consequence, and the fix. No praise, no narrative, no hedging padding.
- Do not invent numbers. If you cannot verify something, mark it unverified.
