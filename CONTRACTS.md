# Module contracts

These signatures are fixed. Do not change a signature without saying so;
other modules are written against them.

Python 3.10. Package root is `src/repro_agent/`. Run via `PYTHONPATH=src`.

---

## `repro_agent/dataset.py`  (owner: agent A)

```python
CORE_TEST_JSON: Path   # examples/core_test.json, resolved relative to repo root
CORE_TRAIN_JSON: Path  # examples/core_train.json

@dataclass(frozen=True)
class Task:
    capsule_id: str          # e.g. "capsule-4180912"
    capsule_title: str
    field: str               # "Computer Science" | "Social Sciences" | "Medical Sciences"
    language: str            # "Python" | "R"
    task_prompt: str
    results: list[dict]      # ground-truth runs; question -> answer
    capsule_doi: str

    @property
    def questions(self) -> list[str]: ...      # keys of results[0]
    @property
    def n_questions(self) -> int: ...
    @property
    def has_vision_question(self) -> bool: ...  # any key containing "fig"

def load_tasks(split: str = "test") -> list[Task]:
    """split in {"test","train"}. Raises ValueError otherwise."""

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
```

## `repro_agent/capsules.py`  (owner: agent A)

```python
CAPSULE_URL = "https://corebench.cs.princeton.edu/capsules/{capsule_id}.tar.gz"

def capsule_size_bytes(capsule_id: str, timeout: int = 30) -> int | None:
    """HEAD request; return Content-Length, or None if unavailable."""

def download_capsule(capsule_id: str, dest_dir: Path, *, force: bool = False) -> Path:
    """Download + extract to dest_dir/capsule_id/. Returns that path.
    Skips download if already extracted unless force. Streams to disk.
    Shows progress on stderr. Removes the tarball after extraction.
    Raises CapsuleError on failure."""

def prepare_tier(capsule_dir: Path, tier: str, work_dir: Path) -> Path:
    """Copy a capsule into work_dir and apply the tier's cuts, matching
    benchmark/benchmark.py in the official harness.

    easy:   results/ kept populated; REPRODUCING.md, environment/ and
            code/run(.sh) removed.
    medium: results/ emptied (kept as an empty dir); the rest kept.
    hard:   results/ emptied; REPRODUCING.md, environment/ and run scripts
            removed.
    Returns the prepared directory. Raises ValueError on unknown tier.
    """

class CapsuleError(RuntimeError): ...
```

## `repro_agent/llm.py`  (owner: agent B)

```python
DEFAULT_MODELS = {   # first env var found wins
    "ANTHROPIC_API_KEY": "anthropic/claude-sonnet-5",
    "OPENAI_API_KEY": "openai/gpt-4o",
}

def resolve_model() -> str:
    """Return REPRO_AGENT_MODEL if set, else pick by which API key is present.
    Raise LLMError with an actionable message if no key is found."""

@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None

def complete(prompt: str, *, system: str | None = None, model: str | None = None,
             max_tokens: int = 2048, temperature: float | None = None) -> LLMResponse:
    """One completion via litellm. No retry logic. cost_usd comes from
    litellm.completion_cost when available, else None. temperature is omitted
    from the request when None; newer Anthropic models reject the parameter."""

def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response, tolerating ```json
    fences and surrounding prose. Raise LLMError if none parses."""

class LLMError(RuntimeError): ...
```

## `repro_agent/sandbox.py`  (owner: agent B)

```python
DEFAULT_IMAGE = "python:3.11-slim"

@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float

def run_in_container(command: str, work_dir: Path, *, image: str = DEFAULT_IMAGE,
                     timeout_s: int = 900, network: bool = True) -> ExecResult:
    """Run `command` with bash -lc inside `image`, with work_dir bind-mounted
    at /workspace and cwd=/workspace. Capture stdout/stderr, truncated to the
    last 20000 chars. Always remove the container (--rm). On timeout set
    timed_out=True and kill the container. Never raise on a non-zero exit
    code."""

def docker_available() -> bool: ...
```

---

## Conventions everyone follows

- No `print` for logging; use `logging.getLogger(__name__)`. CLI output is
  the exception.
- Type-annotate public functions.
- No network or Docker calls at import time.
- Every module must import cleanly with no API key and no Docker present.
- Do not add retry/self-healing behaviour anywhere. The baseline is a
  single-pass control; a retry would invalidate the comparison.
