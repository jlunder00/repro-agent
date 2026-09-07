# Review: problem selection and experimental approach

Scope of this review: `docs/ASSIGNMENT.md`, `proposal/proposal.tex`, `README.md`, `src/repro_agent/`, `results/baseline_*.json`, `examples/core_{test,train}.json`, and the CORE-Bench harness (`agents/AutoGPT-CORE/`, `benchmark/benchmark.py`). Read-only.

## Verdict

The proposal satisfies the assignment (problem is operational, baseline runs, one test case with real output). As a capstone plan it has three defects that will decide whether the final result means anything:

1. **The proposed contribution ("add an iterative execute-observe-diagnose-replan loop") is what CORE-Agent already is.** CORE-Agent is AutoGPT in `--continuous` mode with a $4 budget and a list of best-practice strings. It observes failures and re-plans by construction. A capstone that ends with "iteration beats single-pass" reproduces a 2024 result and is not a contribution.
2. **The eligible task pool is 9 test tasks, not 45, and the default `--subset small` is 5.** All-or-nothing task accuracy on 9 tasks has a resolution of 11 percentage points per task. No claimed improvement smaller than roughly 4 tasks can be distinguished from noise.
3. **The control is not a clean control.** It pins `python:3.11-slim`, which by itself breaks most 2018–2021 capsules regardless of planning quality; it has no GPU filter although the scope says CPU-only, and one of its two measured capsules (`capsule-6003668`) is a GPU task by the harness's own rule; and `results/` on disk contains one task per tier while the proposal reports two.

The project is salvageable. The fix is to narrow the claim from "iteration helps" to a specific mechanism CORE-Agent lacks, widen the task pool to every Python task via a per-question metric, use the train split for development, and make the sandbox environment a variable the agent controls. Details below.

## 1. Problem fit

**Is it a genuine agentic problem?** Yes. Hard-tier CORE-Bench requires acting on an environment (install, run, read output), observing state that is unavailable up front (tracebacks, file layouts, package incompatibilities), and revising plans. The proposal's own trace of `capsule-9052293` is the proof: three sequential failures, each invisible until the previous fix is applied. That is a closed-loop control problem, not a code-generation problem. The easy tier is not agentic (it is document QA over `results/`), and the proposal should stop reporting it as a headline number; it is a sanity check for the extraction stage.

**Is it a SWE-bench variant?** Structurally similar: repository in, artefact out, automated grader. The differences that matter: the agent never edits the paper's code (it edits the environment), the target is a numeric value rather than a passing test, and the failure surface is dependency rot rather than logic bugs. A reviewer will call it "SWE-bench for environments." That label is accurate and not disqualifying, but the proposal should say it explicitly instead of leaving the reviewer to draw the comparison.

**Strongest objection:** "Reproducibility here is measured as 'can an LLM guess pip install lines until an old script runs.' The scientific reproducibility framing is decoration; the actual task is dependency archaeology, and the agent's answer is correct only if the paper's code was deterministic." Best answer: dependency archaeology *is* the dominant cause of computational irreproducibility in practice (the benchmark authors built the benchmark around it), and the metric tolerates run-to-run variance via the prediction interval. The proposal should make this argument itself and drop the broader "verify a paper's numbers" framing, which the system does not do (it reproduces a capsule's output; it never compares to the manuscript's claims).

**Fit with the memory note that the user rejects meta-agentic problems:** this is a problem agents solve, not a problem about agent internals. It fits.

## 2. Novelty and headroom

**What CORE-Agent already does.** From `agents/AutoGPT-CORE/coreagent_hard_gpt4o.sh`: AutoGPT, continuous mode, no cycle limit, `--openai_cost_budget 4`, tool set including `execute_shell`, `open_folder`, file read, and a vision model. It reads README, installs dependencies, runs code, reads tracebacks, and retries until it writes `report.json` or exhausts $4. The "best practices" are prompt strings ("first determine a list of package/dependency requirements... then install"). There is no structured diagnosis, no dependency-version reasoning, no environment selection, no verification of the answer against a second run.

**Conclusion:** the proposed loop as described in §3 and §7 of the proposal ("observes failures, revises commands, and re-reads documentation") is a re-implementation of CORE-Agent's control flow with a different model. It will very likely beat the single-pass baseline. That result is not interesting because it is already published (CORE-Agent 21.48% vs AutoGPT 6.67% on hard is, in effect, that comparison).

**Where the unclaimed space is.** Things CORE-Agent does not do, each of which is a concrete mechanism and can be ablated:

- **Date-aware dependency resolution.** Every capsule has a publication date (via `capsule_doi` / Code Ocean metadata) and its original `environment/Dockerfile` names a base image with a Python version (`miniconda3:4.12.0-python3.9-ubuntu20.04`, `miniconda3:4.7.10-cuda10.1-cudnn7-ubuntu18.04`). The hard tier strips the Dockerfile, but the DOI date is not stripped. Resolving `pip install X` to the newest release of X that predates the capsule date (via PyPI's JSON API release timestamps) fixes the `xlrd==1.2.0` class of failure *before* the traceback, not after three retries. This is a tool, not a prompt. It is straightforwardly measurable: run with and without the resolver.
- **Environment selection as an action.** The baseline hard-codes `python:3.11-slim`. An agent that infers the Python version from `setup.py`, `requirements.txt` syntax, `print` statements, f-strings, `tensorflow==1.x`, etc. and picks a base image accordingly is doing something CORE-Agent cannot (CORE-Agent runs in one fixed ubuntu-dind container with Python 3.10).
- **Typed failure diagnosis.** Classify the traceback (`ModuleNotFoundError`, `FileNotFoundError` with relative path, version-incompatibility, missing data, timeout) and dispatch to a fixed repair for each class, with a budget per class. This gives a failure-mode breakdown before and after, which is the analysis the proposal already promises (§6 item v) but cannot deliver with a free-form loop.
- **Answer verification.** The metric is exact match for deterministic capsules (6 of 9 eligible test tasks). An agent that runs the code twice and checks agreement, or checks that the extracted value has the same precision as the printed value, addresses the extraction failure mode that no leaderboard agent addresses.
- **Cost-bounded pass@budget curves.** Report accuracy as a function of dollar budget (0.01, 0.10, 0.50, 1, 4). CORE-Agent reports one point at $4. A curve is a stronger result than a point and is cheap to produce because the loop already tracks cost.

Pick one or two of these and make them the claim. "Date-aware resolution + environment selection vs. a free-form ReAct loop at equal budget" is a capstone-sized question with a yes/no answer.

## 3. Experimental design validity

**Claim under test:** a strict single-pass control isolates the marginal value of iteration.

**What the control actually isolates:** the difference between one attempt with prompt P1 in environment E1 and *k* attempts with a different prompt set P2, different tool surface, and (if not fixed) different environment. The proposal says "holding model, prompts, and one-shot budget fixed and varying only iteration." None of those are currently fixed:

- **Prompts.** The treatment will need different prompts (it must receive tracebacks and prior commands). Prompt difference is unavoidable; the mitigation is a *second* control: the treatment loop with `max_iterations=1`. That is the correct single-pass control, not `baseline.py`. Keep `baseline.py` as the assignment artefact; use loop-with-k=1 as the experimental control.
- **Environment.** `sandbox.py` pins `python:3.11-slim`. Capsule base images observed: Python 3.9 and a CUDA 10.1 / TF1 image from 2019. Under 3.11, `tensorflow<2.12`, `numpy<1.23`, old `scikit-learn`, `xlrd`, and anything with a C extension built for 3.6–3.8 will fail to install. Many "execution" failures attributed to planning are base-image failures. Either fix the image at something old (3.8) for both arms, or make image selection an agent action in both arms and report it.
- **Budget.** The correct comparison at k>1 is at equal *cost*, not equal attempt count. Report cost per task for both arms and show accuracy at matched cost; otherwise "iteration helps" reduces to "spending more helps."
- **Model.** Internal comparison at a fixed model is valid. Comparison to the published table (GPT-4o, 2024) is not, and the proposal's Table in §6 invites it. State that the published numbers are context only and that the only valid comparisons are between arms in this project on the same model, task set, and grader.
- **Task selection.** The baseline's two capsules were hand-picked. `capsule-6003668` (`split_mnist.py`, TensorFlow, `REPRODUCING.md` mentions GPU) is a GPU task by the harness rule (`"gpu" in REPRODUCING.md` → `uses_gpu=True`; `benchmark/benchmark.py:36-40`), which the stated scope excludes. There is no GPU filter in `dataset.py`. Add one (the rule requires the capsule to be downloaded; cache the flag).
- **Results on disk vs. proposal.** `results/baseline_easy_test.json` and `results/baseline_hard_test.json` each contain `n_tasks: 1` (capsule-9052293 only). The proposal and README report 2/2 and 0/2 with costs averaged over two capsules. Either the second run was not saved or the files were overwritten. Re-run and commit both, or correct the proposal to n=1.
- **Seed / temperature.** `llm.complete` sends no temperature. Runs are non-deterministic. For the final claim, run each arm ≥3 times per task and report mean ± range, or the difference between arms will be inside sampling noise.

**Is n=2 defensible for the proposal?** Yes; the assignment requires one concrete test case. It is a demonstration and the proposal says so.

**What n is needed for the capstone claim?** With all-or-nothing task accuracy and 9 eligible test tasks, one task = 11 pp. Detecting a 20 pp improvement (the gap between AutoGPT and CORE-Agent on hard is ~15 pp) with any confidence requires either many more tasks or repeated runs. Practical target: all 9 Python non-vision test tasks × 3 runs per arm (27 task-runs per arm), plus the 20 Python non-vision train tasks used for development only. Report per-question accuracy on all 22 Python test tasks (26 written questions) as the secondary metric (see §4). Do not tune on test.

## 4. Metric risk

The grader (`scoring.py`, port of `benchmark/evaluations.py`) does the following: numeric answers must fall in `mean ± t₀.₉₇₅,₂ · s · √(4/3)` over three ground-truth runs; strings case-insensitive; lists exact; a task is correct only if every question is.

Failure modes for this project's argument:

- **Point intervals.** 6 of the 9 eligible test tasks and 14 of the 20 eligible train tasks have all three ground-truth runs identical, so the interval collapses to a point and the answer must match to full float precision (`0.844703753651819`). Consequences: (a) any run-to-run nondeterminism the original authors happened not to hit (BLAS threading, hash seeds, dict order under a different Python) produces a wrong answer with correct execution; (b) the extraction stage must copy the number verbatim from output, and any rounding in the printed output vs. the stored result file fails. This is the failure mode the iterative loop cannot fix; it needs a verification step. Measure it: for each correct execution, record whether the extracted value was inside the interval, and separately whether it matched to 4 significant figures. Report both.
- **All-or-nothing with many questions.** One eligible test task has 8 questions, two have 3. An agent that gets 7/8 scores 0 on that task. On a 9-task set, this compresses the visible range. Per-question accuracy is required as a secondary metric to show progress; the proposal already lists it (§6 ii) but must make it primary for development and secondary for the final comparison, with task accuracy reported alongside for leaderboard comparability.
- **No partial credit for correct execution with wrong extraction.** The stage breakdown (`failed_stage`) partially covers this, but `baseline.py` records `failed_stage=None` when execution exits non-zero (see `results/baseline_hard_test.json`: `execute.ok=false`, `failed_stage=null`). Fix: set `failed_stage="execute"` on non-zero exit so the breakdown is trustworthy.
- **Stochastic capsules with wide intervals.** 3 of 9 eligible test tasks are stochastic. The interval can be wide enough that a plausible guess from the README passes without running anything. Guard against this: log whether an answer was produced from execution output or from documentation, and exclude documentation-only answers from the "reproduced" count (or report them separately). CORE-Bench does not do this; doing it is a small methodological contribution.
- **Perfect agent < 100%.** With a 95% PI, ~5% of faithful reproductions of stochastic capsules fall outside. Irrelevant at n=9 but mention it once.

Secondary metric recommendation: **written-question accuracy over all 22 Python test tasks (26 questions)**, reported next to task accuracy over the 9 fully-eligible tasks. This uses the grader's existing written/vision split (`correct_written_answers` / `total_written_questions`) and adds 4 tasks and 5 questions from vision-flagged tasks without touching vision. Also report execution success rate (exit 0 and results/ non-empty) as a process metric independent of the grader.

## 5. Scope realism

Counts from `examples/core_test.json` and `examples/core_train.json` (this review's own tally):

| Split | Total | Python | Python, no `fig` question | Python, no `fig`, 1 question (`--subset small`) | Point-interval among eligible |
|---|---|---|---|---|---|
| test | 45 | 22 | **9** | **5** | 6 / 9 |
| train | 45 | 27 | **20** | 8 | 14 / 20 |

Eligible test tasks: capsule-5507257 (1q), 8536428 (8q), 6049678 (3q, stochastic), 6003668 (1q, stochastic, **GPU**), 9660931 (1q, notebook→HTML), 9052293 (1q), 0851068 (1q, bash script), 9137200 (3q), 4180912 (2q, stochastic). Applying the CPU-only rule removes at least 6003668; the GPU status of the other 8 is unknown until downloaded (the flag lives in `REPRODUCING.md`). Expect the CPU-only, Python, non-vision test pool to be **6–8 tasks**.

R is 23 of 45 test tasks, but only 2 R test tasks are non-vision, so adding R does not help under the current vision exclusion. The vision exclusion, not the language exclusion, is what shrinks the pool: 13 of 22 Python test tasks have a figure question.

**What the scope should be:**

- Development set: all 20 Python non-vision train tasks (14 point-interval, 6 stochastic; 8 single-question). This is where the loop is built and where failure classes are catalogued. Currently the proposal does not mention the train split at all.
- Final evaluation set: all 22 Python test tasks, scored on written questions, plus the 9 (or 6–8 after GPU filter) fully-eligible tasks for task-level accuracy. Vision questions are left unanswered (`null`), which the grader counts as wrong; report task accuracy over the eligible subset only.
- Drop the `--subset small` default. Five tasks is not an evaluation set.
- Drop the "under 26 MB" framing. Size is a download-time concern, not an eligibility criterion; the largest eligible test capsule should be checked (HEAD requests via `capsule_size_bytes`) and included unless it is multi-GB.
- Medium tier: leave unimplemented. It requires Docker-in-Docker and adds no information about the loop that hard does not.
- GPU: keep excluded, but implement the filter. If the CPU-only pool falls below 6 test tasks, run GPU-flagged tasks on CPU anyway with a long timeout and report them as a separate row; TF/PyTorch training on small datasets (MNIST split) often finishes on CPU.

## 6. Ranked risks

1. **Contribution is indistinguishable from CORE-Agent.** Likelihood high if the plan stays as written. *Mitigation:* commit to one named mechanism (date-aware dependency resolution is the strongest: cheap to build, directly addresses the observed failure, absent from CORE-Agent) and design the ablation around it: free-form loop vs. loop + resolver at equal budget.
2. **Task pool too small for any statistical claim.** 6–9 test tasks. *Mitigation:* per-question metric on all 22 Python test tasks; ≥3 runs per arm per task; develop on the 20 train tasks; report a pass@budget curve rather than a single number so the result is a shape, not a point estimate.
3. **Base-image confound masks the effect.** `python:3.11-slim` fails old capsules before planning matters. *Mitigation:* make image selection an action available to both arms, or fix both arms on `python:3.8` and state it. Record the chosen image per run.
4. **Point-interval exact-match failures dominate residual errors.** After execution is fixed, extraction precision becomes the bottleneck and the loop cannot address it. *Mitigation:* extraction reads the results file, not stdout, when the code writes one; verification run for deterministic capsules; report 4-sig-fig agreement as a diagnostic.
5. **Compute cost and wall-clock.** 22 tasks × 2 arms × 3 runs × up to 900 s timeouts is ~33 h of container time if every run times out; API cost at $0.50–$2.59 per task (published figures) is $60–$350 per full sweep. *Mitigation:* per-task cost caps; cache successful environment builds per capsule across runs; run train-set development at k=1 run.
6. **Dependency rot outruns any resolver.** Some packages' old wheels are gone from PyPI or need compilers absent from slim images. *Mitigation:* catalogue failure classes on train; report the fraction that is unfixable-in-principle so it is not counted against the loop.
7. **Results provenance.** Committed `results/` contradict the proposal's reported n. *Mitigation:* every reported number must have a committed JSON with a `generated_at` and model string; add a `--out` flag so runs do not overwrite each other.
8. **Model drift.** `claude-sonnet-5` via litellm; if the alias moves during the semester, arms run on different models. *Mitigation:* pin a dated model ID in `.env` and record `LLMResponse.model` in every run (already stored; surface it in the summary).

## Recommended changes to the proposal and plan

Proposal text (`proposal/proposal.tex`):

1. §2/§7: replace "an iterative pipeline that improves on this" with a named mechanism. Suggested: "a loop with typed failure diagnosis and date-aware dependency resolution, evaluated against the same loop without those components at equal cost."
2. §3: replace the claim that `baseline.py` isolates iteration with: `baseline.py` is the assignment baseline; the experimental control is the capstone loop at `max_iterations=1`; prompts and environment are shared between arms.
3. §4/§6: correct the reported n to match committed results, or commit the second capsule's results. Remove `capsule-6003668` from CPU-only claims or label it GPU.
4. §5/§6: state the evaluation set explicitly: dev = 20 Python non-vision train tasks; test = 22 Python test tasks (written-question accuracy) and the 6–9 CPU-only fully-eligible tasks (task accuracy), ≥3 runs per arm.
5. §6: add execution-success rate, pass@budget curve, and 4-sig-fig agreement as metrics; mark the published table as context, not a comparison target.
6. §2: say "SWE-bench for environments" once and explain the difference.

Code (`src/repro_agent/`), for the next phase, not this proposal:

7. `dataset.py`: add a GPU filter (needs `REPRODUCING.md` from the downloaded capsule; cache the result in a JSON sidecar).
8. `baseline.py`: set `failed_stage="execute"` on non-zero exit; currently the failure-stage histogram undercounts execution failures.
9. `sandbox.py`: accept an image parameter from the caller and record it in `RunResult`; add a network-off option for the execution step after install so answers cannot come from the internet.
10. `run_baseline.py`: `--out` path and `--runs N`; default subset to `python`, not `small`.
11. Log the provenance of each answer (from execution output vs. from README/manuscript) so documentation-only "reproductions" can be separated.
