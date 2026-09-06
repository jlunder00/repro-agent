# Module contracts

These signatures are **fixed**. Implement to them exactly; do not change a
signature without saying so, because other modules are being written against
them concurrently.

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
    Skips download if already extracted unless force. Streams to disk (never
    load into memory). Show progress to stderr. Clean up the tarball after
    extraction. Raise CapsuleError on failure."""

def prepare_tier(capsule_dir: Path, tier: str, work_dir: Path) -> Path:
    """Materialise the agent-visible view of a capsule for a given tier.

    tier="easy":  copy capsule INCLUDING its populated `results/` dir.
    tier="hard":  copy capsule but DELETE the `results/` dir, so the agent
                  cannot read the answers it is supposed to compute.
    Returns the prepared directory. Raise ValueError on unknown tier.
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
             max_tokens: int = 2048, temperature: float = 0.0) -> LLMResponse:
    """One completion via litellm. NO retry logic beyond transport-level
    errors -- the strict single-pass baseline must not smuggle in retries.
    Populate cost_usd from litellm.completion_cost when available, else None."""

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
    at /workspace and cwd=/workspace. Capture stdout/stderr (truncate each to
    the last 20000 chars, noting truncation). Always remove the container
    (--rm). On timeout set timed_out=True and kill the container. Never raise
    on a non-zero exit code -- that is data, not an error."""

def docker_available() -> bool: ...
```

---

## Conventions everyone follows

- No `print` for logging; use `logging.getLogger(__name__)`. CLI output is
  the exception.
- Type-annotate public functions. Docstrings say *why*, not *what*.
- No network or Docker calls at import time.
- Every module must import cleanly with no API key and no Docker present.
- Do not add retry/self-healing behaviour anywhere. The baseline is an
  intentionally strict single-pass control; a hidden retry would invalidate
  the experiment it exists to support.
