# Code review: repro-agent baseline

Scope: `src/repro_agent/*`, `run_baseline.py`, README.md, CONTRACTS.md, `proposal/proposal.tex`, compared against upstream `core-bench/benchmark/evaluations.py` and `benchmark/benchmark.py`. Environment: Python 3.10.12, litellm 1.55.12, Docker 28.1.1 (rootful). All findings below were verified by running code unless marked "by inspection".

The working tree was edited concurrently during the review (uncommitted changes to `run_baseline.py`, `README.md`, `proposal/proposal.tex`, `results/*.json`, `proposal/figures/baseline_output.png`). Findings were re-checked against the on-disk state at the end of the review; where the uncommitted edits already resolve an item, the status column says so.

## Summary

| # | Issue | Severity | Location | Status |
|---|---|---|---|---|
| 1 | Scorer diverges from upstream on a non-numeric value for a numeric key: upstream aborts the whole loop, port continues | High | `scoring.py:90-107` | Confirmed by differential test |
| 2 | Per-run `failed_stage` is `null` when execution fails; README claims each run records the stage at which it failed | High | `baseline.py:272-278`, README "Design rationale" | Confirmed; uncommitted `run_baseline.py` adds a `stage_failures` summary, proposal §3 reworded; README line 144 and the per-run field still wrong |
| 3 | With `OPENAI_API_KEY`, the OpenAI SDK inside litellm retries each request up to 2 times; "never retries" is only true for the Anthropic path | High | `llm.py:83`, litellm `llms/openai/openai.py:280,489` | Confirmed by inspection of installed litellm |
| 4 | Files created by the container are root-owned; the next `prepare_tier` on the same capsule/tier crashes with `PermissionError` | High | `sandbox.py:219-226`, `capsules.py:303-304` | Confirmed by running a container |
| 5 | README §"Example failure" quotes a planned command (`python code/script.py`) that does not match the shipped results file (`cd code && python script.py`); proposal §4 quotes the right command but still lists fix (ii) `cd code`, which that run did not need | Medium | README line 64-69, proposal §4, `results/baseline_hard_test.json` | Confirmed; proposal partially updated, README not |
| 6 | "3.0 s per task" (easy) was the 2-task total; "9.7 s" (hard) did not match the file | Medium | README table, proposal §4 | Resolved in uncommitted edits (now 1.6 s and 10.1 s, matching `results/`) |
| 7 | `import repro_agent.llm` opens an HTTPS connection (litellm fetches its pricing table at import); CONTRACTS forbids network at import time | Medium | `llm.py:17`, litellm `__init__.py:358,375` | Confirmed by strace |
| 8 | Scorer: n=1 ground-truth runs are graded as exact-match by the port, always-wrong upstream (NaN interval) | Medium | `scoring.py:48-49` | Confirmed; no n=1 tasks in dataset |
| 9 | Scorer: boolean ground truth counted as numeric upstream, excluded from totals by the port | Medium | `scoring.py:75` | Confirmed; no bool values in dataset |
| 10 | Scorer: `%`-stripping is destructive upstream and non-destructive in the port | Low | `scoring.py:31-37` | Confirmed; no `%` in dataset strings |
| 11 | Scorer: a key missing from a later ground-truth run zeroes the whole task upstream; port skips the run | Low | `scoring.py:85-88` | Confirmed; no such keys in dataset |
| 12 | Partially-extracted capsule directory is reused on the next run as if complete | Medium | `capsules.py:213-215, 255-261` | Confirmed |
| 13 | Non-`TarError` failures during extraction (e.g. `FileExistsError` from a symlink/dir collision) escape as raw exceptions and leave the partial directory | Medium | `capsules.py:255-261` | Confirmed |
| 14 | Hard-link members can read files outside the destination (linkname is resolved against the archive root by `tarfile`, but checked against the member's parent) | Low | `capsules.py:193-198` | Confirmed |
| 15 | `_flatten_single_wrapper_dir` hoists any single top-level directory, including a non-wrapper such as `code/`; fails if wrapper contains a same-named child | Low | `capsules.py:268-282` | Confirmed |
| 16 | README says the failure breakdown is "dependency install vs. execution vs. answer extraction"; code cannot distinguish install from execution (one shell command) | Medium | README line 144-145; `baseline.py:196-206` | Proposal §3 reworded to "plan, execute, or extract" in uncommitted edits; README not |
| 17 | LLM cost is dropped when `extract_json` fails after a successful completion | Low | `baseline.py:203, 217, 264, 284` | By inspection |
| 18 | `select_result_files` reads entire files into memory before the 4 KB binary sniff | Low | `baseline.py:174-178` | By inspection |
| 19 | `_read_readme` misses mixed-case `Readme.md` | Low | `baseline.py:138` | Confirmed |
| 20 | `prepare_tier` fails on a capsule containing a dangling symlink (`copytree` default) | Low | `capsules.py:305` | Confirmed |
| 21 | `run_in_container` sets no memory/CPU/pids limits; `docker` binary absence raises out of `run_task` uncaught | Low | `sandbox.py:219-226`, `baseline.py:274` | By inspection |
| 22 | `results/baseline_<tier>_<split>.json` is overwritten by every run; the file shipped cannot be tied to the numbers in the proposal without a timestamped copy | Low | `run_baseline.py:548-549` | Confirmed |
| 23 | `tests/` is empty; no test exercises the scorer against upstream, tier preparation, or JSON extraction | Medium | `tests/` | Confirmed |
| 24 | "Prompt templates are under `examples/`" (proposal §5, README layout): `examples/benchmark_prompts.json` is not read by any code; prompts are hard-coded in `baseline.py` | Low | proposal §5, README, `baseline.py:55-68` | Confirmed by grep |
| 25 | Proposal §3 step (5) says answers are extracted from "captured stdout"; code passes stdout and stderr | Low | proposal §3, `baseline.py:277-278` | By inspection |

Counts: High 4, Medium 9, Low 12.

Items verified as correct (no issue): easy/medium/hard cuts in `prepare_tier` match `benchmark.py:218-233` exactly, including emptying (not deleting) `results/` and removing `REPRODUCING.md`, `environment/`, `code/run`, `code/run.sh` on easy and hard; the numeric/list/string branch order and the `fig` vision split match upstream; the prediction-interval formula matches; identical-run point interval requires exact float equality in both; extra reported keys are ignored in both; missing reported keys count as incorrect in both; `extract_json` handles fences, prose, nested braces, braces inside strings, and non-dict JSON; `_truncate` keeps the last 20000 chars; timeout kills the docker client, `docker rm -f` removes the container, and partial stdout is preserved; `--list` runs without a key or Docker; `claude-sonnet-5` is a valid model id and litellm 1.55.12's remote pricing table prices it.

Answer-leak audit for the hard tier: `results/` is emptied; `REPRODUCING.md` and `environment/` are removed; `report.json` from a prior run is destroyed by the `rmtree` in `prepare_tier`; the file listing shown to the model uses relative paths, so the capsule id is not exposed. Remaining paths, identical to upstream: capsule-internal duplicates of results (e.g. `capsule-6003668/code/results/` exists, empty in this case), and container network access, which permits fetching the tarball if the model discovers the id from `metadata/metadata.yml` or code. Neither is a defect relative to upstream, but the README sentence "the answers cannot leak" should be qualified as "removed to the same extent as the official harness".

## Detail

### 1. Scorer: loop-abort semantics on a bad numeric value (High)

Upstream `evaluations.py:80-97`:

```python
try:
    for key in reported_result.keys():
        if key in numeric_keys:
            lower_bound, upper_bound = prediction_interval_bounds[key]
            if (lower_bound <= reported_result[key] <= upper_bound): ...
except Exception:
    pass
```

If `reported_result[key]` is not orderable against a float (`None`, a non-numeric string, a dict), the comparison raises `TypeError`, the `except` catches it outside the loop, and every key not yet visited is left unscored. The port (`scoring.py:94-97`) catches per key and continues.

Differential test, `gt = 3 runs of {"a": ~1.0, "b": ~2.0}`:

| reported | upstream | port |
|---|---|---|
| `{"a": None, "b": 2.0}` | 0/2 | 1/2 |
| `{"a": "N/A", "b": 2.0}` | 0/2 | 1/2 |
| `{"a": {"x":1}, "b": 2.0}` | 0/2 | 1/2 |
| `{"a": 1.0, "b": None}` | 1/2 | 1/2 |
| `{"a": [1], "b": 2.0}` | 2/2 | 1/2 |

The last row: upstream's `'%' in [1]` is a valid membership test, `float([1])` raises and is swallowed, and `np.float64 <= [1] <= np.float64` broadcasts to a one-element boolean array whose truth value is `True`, so a single-element list containing the right number is graded correct upstream. The port's `float([1])` raises and the key is graded wrong.

Consequence: `ANSWER_SYSTEM` instructs the model to emit `null` for undetermined values. On any multi-question task, a `null` for one numeric key changes the score of every later key. Task-level accuracy (all-or-nothing) is unaffected, since one wrong answer already fails the task; per-question accuracy, which the proposal lists as evaluation criterion (ii), is inflated relative to the official scorer. The `--subset small` filter (single question) hides this today.

Fix: reproduce the upstream control flow. Wrap the whole `for key, value in reported.items()` loop in one `try/except Exception: break`-equivalent, remove the per-key `try`, and compare with `lower <= value <= upper` without `float()` coercion so that the same inputs raise. Add a regression test that feeds `{"a": None, "b": correct}` and asserts 0 correct. Document in the docstring that this is a deliberate reproduction of upstream behaviour.

### 2. `failed_stage` is never set for execution failures (High)

`baseline.py:272-278` records `StageRecord("execute", ok=False, ...)` but does not assign `result.failed_stage`. Both runs in `results/baseline_hard_test.json` have `"failed_stage": null` while their `execute` stage has `ok: false`. The committed `run_baseline.py` summary (`failure_stages`) therefore reports `execute: 0` for a run where both tasks failed at execution.

README: "Each run records the stage at which it failed, so results also give a failure-mode breakdown". Proposal §3: "Single-pass execution attributes each failure to one stage (planning, execution, or extraction)". Proposal §6: "2/2 failures at execution and none at planning or extraction". The last number was not produced by the code; it was read off the per-stage `ok` flags by hand.

The uncommitted diff to `run_baseline.py` adds a `stage_failures` summary that counts `ok == False` stages and renames the old counter to `aborted_at`; the revised proposal §3 says "Each stage records success or failure", which is accurate. The per-run `failed_stage` field is still `null`, and README line 144 ("Each run records the stage at which it failed") still describes that field.

Fix: in `run_task`, after `run_in_container`, set `result.failed_stage = "execute"` when `exit_code != 0 or timed_out` (keep proceeding to extraction; document that `failed_stage` is the first non-ok stage, not the abort point), or add a separate `first_failed_stage` field. Commit the `run_baseline.py` change. Regenerate both results files and the figure from the same run, then update README/proposal numbers from those files.

### 3. litellm retries on the OpenAI path (High)

`llm.py` makes one `litellm.completion` call. litellm 1.55.12 itself adds no retries for this call (`litellm.num_retries` is `None`; `main.py:969` only wraps in `completion_with_retries` when set). Provider-level behaviour differs:

- Anthropic (`anthropic/…`): litellm uses its own `HTTPHandler` over `httpx`. The sync `post` (`http_handler.py:487-530`) has no retry; the transport is `None`, so httpx's default `retries=0` applies. The async handler retries once on `ConnectError`/`RemoteProtocolError` but `complete()` uses the sync path. No retry.
- OpenAI (`openai/…`): litellm constructs `openai.OpenAI(max_retries=...)` with `max_retries` defaulting to 2 (`llms/openai/openai.py:280` and `:489 data.pop("max_retries", 2)`). The OpenAI SDK retries 408/409/429/5xx and connection errors with backoff. Up to 3 attempts per call.

CONTRACTS.md and `llm.py` docstring say "No retry logic". README: "It never retries". Proposal §3: "No retries, self-correction, or re-planning at any stage". These are true for the reasoning loop and, on Anthropic, for transport. On OpenAI, transport retries occur.

Fix: pass `max_retries=0` in `litellm.completion(...)` kwargs (litellm forwards it to the OpenAI client via `optional_params`) and `num_retries=0` for clarity. Qualify the claim in README and proposal: "no application-level retries; transport-level retries are disabled (`max_retries=0`)". Add a test that monkeypatches `litellm.completion` and asserts it is called exactly once with `max_retries=0`.

### 4. Root-owned files break the next `prepare_tier` (High)

Docker here is rootful (`docker info`: Server 28.1.1, no rootless flag). `run_in_container` does not pass `--user`, so the model's command runs as uid 0 and anything it writes under `/workspace` (e.g. `code/__pycache__/*.pyc`, downloaded data, output files) is root-owned on the host. Verified: after a container ran `mkdir -p code/__pycache__ && echo hi > code/__pycache__/x.pyc`, `stat` reports `root`, and `shutil.rmtree(work_dir/"code")` raises `PermissionError: [Errno 13] Permission denied: 'x.pyc'`.

`prepare_tier` begins with `shutil.rmtree(work_dir)` (`capsules.py:303-304`). The second hard-tier run of the same capsule fails at the prepare stage with `PermissionError`, recorded as `failed_stage: "prepare"`. The runs in `results/` did not hit this only because both planned commands failed before Python created `__pycache__`; `work/capsule-6003668__hard/code/utils/__pycache__` on disk is user-owned because it came from the capsule tarball.

Fix: add `"--user", f"{os.getuid()}:{os.getgid()}"` to `argv` (with `-e HOME=/tmp` so `pip install --user` has a writable home), or run the container with `--rm` and copy the workspace in rather than bind-mounting it. If root is required for `pip install` into the system site-packages of `python:3.11-slim`, use `--user` with `PIP_TARGET`/`PYTHONUSERBASE` set to a path under `/workspace`, or `chown -R` the workspace inside the container as the last step of the command (fragile if the command fails early). Add a test that runs a container writing a file and then calls `prepare_tier` on the same directory.

### 5. README/proposal failure narrative does not match the shipped results (Medium)

README "Example failure" and proposal §4: "The single planning call proposed `pip install openpyxl pandas && python code/script.py`. It failed … (ii) `FileNotFoundError` → the script uses paths relative to `code/`, so `cd code` first".

`results/baseline_hard_test.json` (generated 2026-09-06T23:56:17Z, the file that will ship) records the plan as `pip install openpyxl pandas && cd code && python script.py`. The committed version (`git show HEAD:results/baseline_hard_test.json`) recorded `python code/script.py`. `code/script.py` opens `TCNS_ANP_TOPSIS.xlsx` and `../results/output_TCNS_ANP_TOPSIS.txt`, both relative to `code/`, so with `cd code` the `FileNotFoundError` in fix (ii) does not occur. On the shipped run the sequence is (i) `xlrd` missing, then (iii) `xlrd==1.2.0`: two fixes, not three.

The revised proposal §4 now quotes the `cd code` command but keeps "three sequential fixes, each visible only after the previous one" including (ii). README lines 64-69 still quote the old command and the three-step narrative.

Fix: make prose and data come from one run. Either describe the shipped run (two fixes) or restore the results file from the run with three. Store container stdout/stderr (not only the exit code) in the results JSON so the narrative is regenerable.

### 6. Per-task latency figures (Medium)

`results/baseline_easy_test.json`: `total_duration_s: 3.1`, `n_tasks: 2`. README table and proposal §4/§6 say "3.0 s per task". Per task is 1.55 s; 3.0 is (approximately) the total. `$0.0034` is correctly per task (0.0067/2).

`results/baseline_hard_test.json`: `total_duration_s: 20.1`, `n_tasks: 2` → 10.05 s/task; README/proposal say 9.7. `$0.0049` matches (0.0097/2).

Status: the uncommitted README and proposal now say 1.6 s (easy) and 10.1 s (hard), which match the on-disk files. Remaining: state that durations include capsule download on the first run (`run_task` timing starts before `download_capsule`).

### 7. Network access at import time (Medium)

`strace -e connect python -c "import repro_agent.llm"` shows a DNS lookup and a TCP connect to 185.199.108.133:443 (raw.githubusercontent.com). Source: litellm `__init__.py:375` calls `get_model_cost_map(url)` at import, which does `httpx.get(url, timeout=5)` unless `LITELLM_LOCAL_MODEL_COST_MAP=True`. CONTRACTS.md: "No network or Docker calls at import time". Offline, import blocks for up to 5 s then falls back to the bundled table; the bundled table in 1.55.12 does not contain `claude-sonnet-5`, so `completion_cost` returns `None` offline and `cost_usd` is silently 0.

Fix: either accept and document the exception in CONTRACTS.md, or set `os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")` before `import litellm` in `llm.py` and vendor a pricing entry for the default models (litellm supports `litellm.register_model({...})`). The second option makes cost reporting deterministic across machines, which matters for the cost comparison in proposal §6.

### 8. Scorer: n=1 ground truth (Medium; latent)

Upstream with one ground-truth run: `np.std(..., ddof=1)` is `nan`, `t.ppf(0.975, 0)` is `nan`, bounds are `nan`, `nan <= x <= nan` is `False`; every numeric answer is wrong. Port (`scoring.py:48-49`) returns `(mean, mean)` and grades exact matches as correct. Differential test: gt `[{"a": 1.0}]`, reported `{"a": 1.0}` → upstream 0/1, port 1/1. All 90 dataset entries have exactly 3 runs, so this is latent.

Fix: match upstream (return `(nan, nan)` for n < 2) or keep the port's behaviour and document it as an intentional divergence that cannot affect CORE-Bench scores. The docstring currently says semantics are "identical"; that statement is false as written.

### 9. Scorer: boolean ground truth (Medium; latent)

Upstream `isinstance(v, (int, float))` is true for `bool`. Port adds `and not isinstance(v, bool)`, which removes bool keys from `numeric_keys` and from both totals. Differential test: gt `[{"b": True}]*3`, reported `{"b": True}` → upstream 1/1, port 0/0. No bool values exist in either split.

Fix: drop the `not isinstance(v, bool)` clause to match upstream, or document the divergence.

### 10. Scorer: `%` stripping (Low; latent)

Upstream mutates `reported_result[key]` to the `%`-stripped string before attempting `float()`; if `float()` fails, the stripped string is what the string comparison sees. Port keeps the original on failure. gt `"50% chance"`, reported `"50% chance"` → upstream 0/1, port 1/1. No dataset string contains `%`.

Fix: apply the strip before the `try`, and return the stripped value on failure, to match upstream.

### 11. Scorer: key absent from a later run (Low; latent)

Upstream builds `mean_result` with `[result[key] for result in gt_result]` and raises `KeyError` if any run lacks the key; the outer `except` prints and returns zero correct for the entire task. Port filters `if key in run`. No such keys exist in the dataset.

Fix: none required; document as a deliberate robustness change.

### 12. Partial capsule directory treated as complete (Medium)

`download_capsule` skips download when `capsule_dir` exists and is non-empty (`capsules.py:213`). A download or extraction interrupted after the first member is written leaves a non-empty directory. Every later run silently uses the partial capsule. Verified with a directory containing a single stray file: `download_capsule` returned it without downloading.

Fix: extract into a temporary sibling directory (`dest_dir/.{capsule_id}.partial`) and `os.rename` to `capsule_dir` only after `_flatten_single_wrapper_dir` succeeds; on any exception `rmtree` the temporary directory. Alternatively write a `.complete` marker file and check for it.

### 13. Non-`TarError` exceptions escape extraction (Medium)

`capsules.py:255-261` catches `tarfile.TarError` only. `tarfile.extractall` raises `OSError` subclasses for filesystem conditions; verified: a member `cap/a/x.txt` following a symlink member `cap/a -> b` raised `FileExistsError` out of `download_capsule` uncaught, leaving `capsule_dir` populated (issue 12). `run_task` catches it as a prepare failure, so the batch survives, but the cached directory is poisoned for future runs.

Fix: catch `(tarfile.TarError, OSError)`, wrap in `CapsuleError`, and clean up per issue 12.

### 14. Hard-link members resolve outside the destination (Low)

For `LNKTYPE` members, `tarfile` resolves `linkname` relative to the extraction root (`os.path.join(path, tarinfo.linkname)`), not the member's parent. `_safe_extract` checks `member_path.parent / member.linkname` for both symlinks and hard links. Verified: member `cap/hl` with linkname `../outside.txt` passed the check (`dest/cap/../outside.txt` is inside `dest`) and extraction created `dest/cap/hl` with the contents of `dest/../outside.txt`, a file outside the destination. This is a read of an outside file into the capsule, not a write outside; write-side traversal (`../evil.txt`, absolute names, absolute and `..` symlinks) is correctly rejected.

Fix: for `member.islnk()`, check `dest_dir / member.linkname`; for `member.issym()`, keep the parent-relative check. Also reject `CHRTYPE`/`BLKTYPE`/`FIFOTYPE` members.

### 15. Wrapper flattening heuristics (Low)

`_flatten_single_wrapper_dir` hoists the contents of any single top-level directory. Verified: a tarball whose only top-level entry is `code/` becomes a capsule with `script.py` at the root and no `code/` directory. Also verified: a wrapper containing a child with the wrapper's own name (`cap/cap/`) raises `shutil.Error: Destination path already exists`. Both are outside observed CORE-Bench layout, but the function is applied to every download.

Fix: hoist only when the single directory is not one of the expected capsule entries (`code`, `results`, `environment`, `data`, `metadata`) or when its name equals `capsule_id`; move children into a fresh temporary directory and rename.

### 16. Failure-stage taxonomy claimed vs implemented (Medium)

README "Design rationale": "failure-mode breakdown (dependency install vs. execution vs. answer extraction)". The pipeline stages are `prepare, plan, execute, extract, score`; the planning call returns one shell command containing both install and run (`pip install … && python …`), executed as one `bash -lc`. Nothing in the code separates an install failure from a run failure. The revised proposal §3 already says "plan, execute, or extract".

Fix: either ask the planner for `{"install": "...", "run": "..."}` and execute them as two container runs (still single-pass; the second is skipped if the first fails), or change the README wording to match the proposal.

### 17. Cost dropped on parse failure (Low)

`_plan_command` and `_extract_answers` return `(parsed, response)`; if `extract_json` raises, the caller's `except` runs before `result.cost_usd += response.cost_usd`, so the tokens spent on the failed call are not billed to the run. Cost per task is criterion (iv) in proposal §6 and will be under-reported precisely on the failures the loop is meant to reduce.

Fix: call `llm.complete` in `run_task` (or return the response via the exception), add cost immediately, then parse.

### 18. Whole-file read before binary sniff (Low)

`select_result_files` calls `path.read_text(errors="replace")` on every non-suffix-excluded file, then inspects the first 4096 characters. A multi-GB `results/` file is read fully into memory before being skipped or truncated to the 12000-char budget.

Fix: open in binary, read `4096` bytes for the sniff, then read at most `remaining` bytes (decode with `errors="replace"`) for the body.

### 19. `Readme.md` not found (Low)

Patterns are `README*`, `readme*`, `REPRODUCING*`. Verified: `code/Readme.md` yields "(no README found)". Case-insensitive glob is not available in `pathlib`; iterate the directory and compare `name.lower().startswith(("readme", "reproducing"))`.

### 20. Dangling symlink in a capsule aborts `prepare_tier` (Low)

`shutil.copytree(capsule_dir, work_dir)` with default `symlinks=False` dereferences symlinks and raises `shutil.Error` on a dangling one. Verified. Pass `symlinks=True` (matches `benchmark.py`'s `copytree` default? No: upstream also uses the default and would fail identically). Either match upstream or pass `symlinks=True`; state which.

### 21. Container resource limits and missing-docker path (Low)

`docker run` has no `--memory`, `--cpus`, or `--pids-limit`; a runaway capsule can exhaust the host until the 900 s timeout. `run_in_container` is called outside any `try` in `run_task` (`baseline.py:274`); `FileNotFoundError` from a missing `docker` binary propagates and aborts the batch (mitigated by the `docker_available()` gate in `run_baseline.py`, not in the library). Add `--memory 8g --pids-limit 1024` (or CLI flags) and catch `OSError` around `run_in_container`, recording it as an execute failure.

### 22. Results file overwritten per run (Low)

`out = DEFAULT_RESULTS_DIR / f"baseline_{args.tier}_{args.split}.json"` is overwritten on every invocation. Between review start and end the file changed from a 1-task run to a 2-task run with different planned commands (issue 5). Write `baseline_{tier}_{split}_{timestamp}.json` and keep a `latest` symlink, or record `argv` and the git commit in the JSON so a shipped number can be traced.

### 23. No tests (Medium)

`tests/` is empty; `pytest tests` reports "no tests ran". The submission's central technical claim is scorer fidelity ("ported verbatim", "directly comparable"), and the review found five divergences (issues 1, 8, 9, 10, 11), one of which affects real multi-question runs. A differential test against a vendored copy of upstream `eval_result_json` (it has no runtime dependencies beyond numpy/scipy once the `backoff`/`openai`/`tqdm` imports are stubbed) would have caught all five. Minimum set to add before submission:

- `test_scoring.py`: parametrised differential test vs upstream over the cases in issues 1, 8-11, plus the two real tasks in `results/`.
- `test_capsules.py`: `prepare_tier` on a synthetic capsule for all three tiers, asserting the exact file set; `_safe_extract` on the hostile tarball used in this review.
- `test_llm.py`: `extract_json` cases above; `complete()` with `litellm.completion` monkeypatched, asserting one call and `max_retries=0`.
- `test_sandbox.py` (skipped without Docker): non-zero exit, timeout, root-ownership regression.

### 24. `examples/benchmark_prompts.json` is unused (Low)

Proposal §5: "Capsule metadata and prompt templates are under `examples/`". README layout: "vendored task metadata + official tier prompts". `grep -rn benchmark_prompts src run_baseline.py` finds nothing; `task_prompt` is loaded into `Task` but never used. The prompts the baseline actually uses are `PLAN_SYSTEM`/`ANSWER_SYSTEM` in `baseline.py:55-68`. State that `benchmark_prompts.json` is reference material, or load it.

### 25. "captured stdout" (Low)

Proposal §3 step (5): "one LLM call extracting answers from captured stdout". `baseline.py:277-278` passes exit code, stdout, and stderr. Change to "captured stdout/stderr".

## Notes on items checked and found consistent

- `prepare_tier` vs `benchmark.py:218-233`: identical cut set per tier. Upstream `os.remove(REPRODUCING.md)` raises if absent; port uses `missing_ok=True`. Upstream `shutil.rmtree(results)` raises if absent; port checks `exists()`. Both differences are strictly more permissive and cannot add files.
- `Task.questions` is `results[0].keys()`, matching upstream's `{json_fields}` substitution.
- `has_vision_question` lowercases (`"fig" in q.lower()`) while the scorer, like upstream, is case-sensitive. No dataset key contains `Fig` without `fig`, so the filter is currently equivalent; it is a filter, not a scorer, so the asymmetry is acceptable.
- `--list --subset small --limit 3` ran in under 10 s with no key and printed sizes from HEAD requests.
- `requirements.txt` pins `litellm<1.60` for Python 3.10; installed 1.55.12 imports cleanly. The `typing.NotRequired` rationale was not verified against a ≥1.60 install (no network install attempted).
- Revised proposal/README dataset claims verified against `examples/core_*.json` and the cached capsules: 22 Python test tasks; 9 without a figure question (`5507257, 8536428, 6049678, 6003668, 9660931, 9052293, 0851068, 9137200, 4180912`); 5 of those single-question; 6 of the 9 have three identical ground-truth runs; 20 Python non-figure train tasks; 2 of 23 R test tasks lack a figure question; `capsule-6003668` and `capsule-9660931` contain "gpu" in `REPRODUCING.md`, matching the harness rule at `benchmark.py:39`. "There is no dotenv loader" is correct. The `litellm<1.60` / `typing.NotRequired` rationale was not verified against a ≥1.60 install.
