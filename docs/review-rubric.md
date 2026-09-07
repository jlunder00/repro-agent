# Proposal rubric review

Reviewed: `proposal/proposal.tex` / `proposal/proposal.pdf` (built 2026-09-06 16:41, 2 pages) against `docs/ASSIGNMENT.md`.
Cross-checked against `README.md`, `results/baseline_*.json`, `work/`, `proposal/figures/baseline_output.png`, `src/repro_agent/baseline.py`, `run_baseline.py`.

## Summary table

| Section | Pts | Verdict | Gap |
|---|---|---|---|
| Basic information | — | Complete | None. All four fields present. |
| 1. Problem Definition | 15 | Partial | Intended user and their situation not stated. |
| 2. Motivation and Scope | 15 | Partial | No "why agentic" justification. No feasibility argument. |
| 3. Runnable Baseline | 25 | Partial | Files containing the implementation not named. Model not named in this section. |
| 4. Test Case and Output | 25 | Partial / inconsistent | Screenshot present and legible, but shows 1/1 and 0/1 while the text says 2/2 and 0/2 with different cost and latency numbers. |
| 5. Reproducibility | 10 | Partial | Python version, Docker daemon requirement, and litellm pin not listed as setup limitations. Hard-tier command not given. |
| 6. Evaluation Plan | 5 | Complete | Contains measured numbers that `results/` does not support (see Factual issues). |
| 7. Limitations and Next Steps | 5 | Complete | Risks and needed help/infrastructure not stated. |
| Length | — | Pass | PDF is 2 pages (`pdfinfo`). |

## Basic information

Template: student name, project title, repository/notebook link, configuration location.
Proposal: "Jason Lunder" / "Agentic Computational Reproducibility of Published Research on CORE-Bench" / `https://github.com/jlunder00/repro-agent` / "`examples/` and `.env.example`".
All four present. The PDF title line ("Agentic Computational Reproducibility for Published Research") differs from the table's project title ("... of Published Research on CORE-Bench"). Cosmetic.
The repository link was not verified as reachable; `git remote` was not checked.

## Section 1. Problem Definition (15)

Template asks for: (a) task, (b) intended user and their situation, (c) input, (d) output, (e) success and failure.

- (a) Task: present. "Verifying a paper's numbers requires a human to install the toolchain, run the code, and check the output. This project automates that with an agentic system."
- (b) Intended user and situation: absent. The only human mentioned is "a human" who currently does the work. No reviewer, replicator, journal, or researcher is named as the user, and no situation is described.
- (c) Input: present. "a code capsule (source plus README and/or Dockerfile) and questions about its reported results."
- (d) Output: present. "a `report.json` mapping each question to an answer."
- (e) Success/failure: present. "every answer matches ground truth under the benchmark's grading rule (§4)" / "any wrong answer, a crash, or no file produced."

Note: the grading rule is described in README §"How answers are graded" but in the proposal only as "the benchmark's grading rule (§4)"; §4 says "prediction interval is a point" without stating the general rule (95% prediction interval from three ground-truth runs). The reader cannot tell from the proposal alone whether a numeric answer succeeds.

## Section 2. Motivation and Project Scope (15)

Template asks for: (a) why the problem matters, (b) why an agentic approach is reasonable, (c) in scope, (d) out of scope, and overall "why it is feasible for a semester capstone project."

- (a) Why it matters: present only implicitly via §1's first sentence ("Published code capsules often fail to run after release..."). §2 itself contains no motivation statement; it opens with a benchmark description.
- (b) Why agentic: absent. The section states "The capstone goal is an iterative pipeline that improves on this" but never argues why iteration/tool use/agency is the right approach rather than, e.g., a single-call model or a rule-based installer. The closest text is in §3: "an iterative loop that observes failures, revises commands, and re-reads documentation" — that describes the system, not why an agent is warranted. §4's three-sequential-errors trace is the evidence for it, but the argument is never made in §2.
- (c) In scope: present. "Python capsules, CPU-only, small capsules."
- (d) Out of scope: present. "R capsules, GPU tasks, vision/figure questions, multi-gigabyte capsules, Azure parallel execution."
- Feasibility: not addressed.

## Section 3. Runnable Baseline (25)

Template asks for: (a) model/tool/framework/library, (b) step by step, (c) why a reasonable starting point, (d) which files contain the implementation.

- (a) Framework: partial. "LLM access goes through `litellm`"; Docker is named. The model is not named in §3; `claude-sonnet-5` appears only in §6. The default model per `src/repro_agent/llm.py` is `anthropic/claude-sonnet-5`.
- (b) Step by step: present. Seven numbered steps.
- (c) Why reasonable: present. Control-condition argument, paragraph 2.
- (d) Files: absent. No file or module is named anywhere in §3 (`run_baseline.py`, `src/repro_agent/baseline.py`, `sandbox.py`, `llm.py`, `capsules.py`, `dataset.py`, `scoring.py`). `run_baseline.py` appears only in §5 as a command. This is an explicit template requirement.

Step (7) "score with the vendored official scorer" — supported by `src/repro_agent/scoring.py` and `third_party/NOTICE`.

## Section 4. Test Case and Baseline Output (25)

Template asks for: (a) sample input, (b) expected behavior/output, (c) actual baseline output as a screenshot, (d) what worked and what did not.

- (a) Sample input: present. `capsule-9052293`, question "Report the closeness coefficient for location L1."
- (b) Expected output: present. `report.json` containing `0.844703753651819`. Matches `examples/core_test.json` ground truth (three identical runs).
- (c) Screenshot: present (`proposal/figures/baseline_output.png`, 0.62 linewidth). Legible. Shows two runs of `capsule-9052293`: easy `1/1 = 100.0%`, `$0.0009`, `1.7s`; hard `0/1 = 0.0%`, `$0.0053`, `13.5s`.
- (d) What worked / did not: present. Easy correct; hard failed; three-step manual trace.

Inconsistency: the text directly under the figure states "Easy: 2/2 correct, $0.0034 and 3.0 s per task. Hard: 0/2 correct ... " The screenshot shows 1/1 and 0/1 with different cost and latency. The figure caption says "for the same capsule at the easy tier (correct) and the hard tier (incorrect)", i.e. one capsule, while the text reports two. A grader comparing the figure to the text will see the mismatch.

## Section 5. Reproducibility and Run Instructions (10)

Template asks for: (a) dependencies and install, (b) API keys/env vars, (c) exact command, (d) where the input file is, (e) where output appears, (f) known setup limitations.

- (a) Install: present. `pip install -r requirements.txt`. Python version (3.10+, per README) not stated. venv step omitted (acceptable).
- (b) Keys: present. `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` via `.env`. The `export $(grep -v '^#' .env | xargs)` step from README/`.env.example` is not given; copying `.env.example` to `.env` alone does not load the variable (no dotenv loader exists in `src/` or `run_baseline.py`; the code reads `os.environ`).
- (c) Exact command: present for easy tier: `python run_baseline.py --capsule capsule-9052293 --tier easy`. The hard-tier command, which produced the failing half of §4, is not given (`--tier hard`).
- (d) Input location: present. "Capsule metadata and prompt templates are under `examples/`"; capsule "cached in `capsules/`".
- (e) Output location: present. "writes results to `results/`". The filename pattern `results/baseline_<tier>_<split>.json` is not given.
- (f) Known setup limitations: partial. "Docker is required only for `--tier hard`" is the only one. Not stated: Python 3.10+; Docker daemon must be running (`docker info` is checked at `run_baseline.py:83`); `litellm<1.60` pin reason; network access to Princeton server needed on first run; medium tier unimplemented (stated in §6, not §5).

## Section 6. Initial Evaluation Plan (5)

Template asks how the improved system will be compared against the baseline and what evidence would show improvement.
Present: five criteria (task accuracy, per-question accuracy, latency, cost, failure stage), published reference table, measured baseline row.
Gap: no statement of what magnitude or which comparison constitutes "improvement" (e.g. hard-tier task accuracy on the Python/CPU subset, same model, same prompts). The control-condition argument in §3 implies it but §6 does not state it.
The measured numbers in this section are the ones disputed below.

## Section 7. Limitations and Next Steps (5)

Template asks for: weaknesses, expected failure cases, next phase, risks, help/data/infrastructure needed.
Present: weaknesses (dependency rot, sample size, scope, retrieval truncation, stochastic scoring); next phase (four items).
Absent: risks that might make the project difficult; help, data, or infrastructure needed (e.g. API budget for 45-task runs, Docker host, disk for large capsules).
The "Retrieval" limitation is supported by `baseline.py:150-190` (`MAX_RESULT_CHARS = 12000`, sorted path order).

## Factual issues

### F1. Measured numbers are not supported by `results/`

Proposal §4 and §6, README "Measured baseline results": "2 Python capsules ... easy 2/2 = 100% ... $0.0034 and 3.0 s per task; hard 0/2 = 0%, $0.0049 and 9.7 s per task, 2/2 failures at execution."

On disk and in git (`e3238c1`, the only commit touching these files):

| File | n_tasks | n_correct | total_cost_usd | total_duration_s | capsules |
|---|---|---|---|---|---|
| `results/baseline_easy_test.json` | 1 | 1 | 0.0009 | 1.7 | capsule-9052293 |
| `results/baseline_hard_test.json` | 1 | 0 | 0.0053 | 13.5 | capsule-9052293 |

No results file for `capsule-6003668` exists in `results/`. `work/capsule-6003668__{easy,hard}/report.json` exist (13:55), containing `0.98` (easy) and `null` (hard), so a second-capsule run occurred, but its summary JSON was overwritten by the later single-capsule runs (hard at 13:57, easy at 16:43). The "$0.0034 / 3.0 s" and "$0.0049 / 9.7 s" per-task averages cannot be derived from any file in the repository. The 6003668 easy answer `0.98` against ground truth `[0.982, 0.815, 0.978]` is plausibly inside the prediction interval, but its correctness is not recorded anywhere.

Effect: the proposal reports a 2-capsule result while the repo contains a 1-capsule result, and the screenshot shows the 1-capsule result.

### F2. "Failures at execution" is not what the pipeline records

Proposal §6: "2/2 failures at execution and none at planning or extraction." README: "Both hard-tier failures occurred at the execution stage."

`baseline.py:270-276`: a non-zero exit in the execute stage records `ok=False` in `stages` but never sets `result.failed_stage`. `failed_stage` is only set on exceptions in prepare/plan/extract. Consequently `results/baseline_hard_test.json` has `"failed_stage": null` and `"failure_stages": {... "execute": 0 ...}` for a run whose execute stage shows `exit=1`. The failure-stage attribution claimed in §3 ("Single-pass execution attributes each failure to one stage") and §6 is not produced by the code's summary; it has to be inferred from the per-stage `ok` flags.

### F3. Screenshot vs text (see §4)

Figure: 1/1, $0.0009, 1.7 s; 0/1, $0.0053, 13.5 s. Text: 2/2, $0.0034, 3.0 s; 0/2, $0.0049, 9.7 s.

### F4. Unverified external claims

- "Published successful tasks averaged $0.54 versus $2.59 for failures" — attributed to nothing in the proposal; not in `references.bib` notes. Not checked against the paper.
- "roughly two-thirds of the test split is under 26 MB" — sizes come from HEAD requests (`capsules.py:29`); no cached size list exists in the repo to verify. README makes the same claim.
- Published table (60.00 / 57.78 / 21.48 etc.) — cited to Siegel et al. Table 5; not checked.
- "R capsules (about half of CORE-Bench)" — `examples/core_test.json`: 23 R, 22 Python of 45. Supported for the test split.

### F5. Overclaims

- §1 "This project automates that with an agentic system." The delivered artifact is a non-agentic single-pass pipeline; the agentic system is future work. Minor.
- §3 "the pipeline runs unmodified with an Anthropic or OpenAI key" — supported by `llm.py` `DEFAULT_MODELS`; the OpenAI path was not exercised in any results file.
- §5 "`--list` prints the selection and capsule sizes without downloading or a key" — supported (`run_baseline.py:73-80`), but it does require network (HEAD requests).

## Required fixes, prioritized

1. Reconcile §4/§6/README numbers with `results/`. Either (a) re-run `--capsule capsule-9052293 --capsule capsule-6003668` at both tiers so `results/baseline_{easy,hard}_test.json` contain 2 tasks and the averages, then re-take the screenshot; or (b) change the text to the 1-capsule figures the files and screenshot already show (1/1, $0.0009, 1.7 s; 0/1, $0.0053, 13.5 s). Option (a) is out of scope for this review to execute; the choice is the author's.
2. §3: name the implementation files. One sentence listing `run_baseline.py` and `src/repro_agent/{baseline,sandbox,llm,capsules,dataset,scoring}.py` satisfies the template.
3. §1: add the intended user and situation (e.g. a reviewer or replicator with a capsule and paper but no working environment).
4. §2: add a "why agentic" sentence; the §4 sequential-error trace is the evidence and can be referenced.
5. §6/§3: fix the failure-stage claim. Either change `baseline.py` so a non-zero execute exit sets `failed_stage="execute"` (this is a code change outside this review's scope) or reword the proposal to "the execute stage exited non-zero in both runs" and drop "failure_stages" as an evidence source.
6. §5: add `--tier hard` command, the `export $(grep -v '^#' .env | xargs)` step, Python 3.10+, running Docker daemon, and the result filename pattern.
7. §7: add one clause each for risks and needed infrastructure/budget.
8. §2: add one sentence on why the problem matters and feasibility (the section currently starts with the benchmark description).
9. Cite the source for "$0.54 versus $2.59".
10. Align the PDF title line with the table's project title.

Items 1-2 affect the two 25-point sections. Item 1 is the most serious: the proposal's headline measured result disagrees with both the committed results files and the screenshot in the same section.
