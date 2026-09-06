"""Provider-agnostic LLM completion via litellm.

This module is the only place the baseline talks to a language model. Two
things are non-negotiable here (see CONTRACTS.md):

1. No application-level retries. `complete()` makes exactly one call.  The
   baseline this feeds is a strict single-pass scientific control -- a
   hidden retry here would quietly turn it into a multi-pass system and
   invalidate the comparison it exists to support.
2. No network calls at import time, and the module must import cleanly with
   no API key set. Model/provider resolution only happens when a caller
   actually asks for it.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

import litellm

logger = logging.getLogger(__name__)

# First env var found (in this order) wins, mapped to the model litellm
# should use for that provider.
DEFAULT_MODELS = {
    "ANTHROPIC_API_KEY": "anthropic/claude-sonnet-5",
    "OPENAI_API_KEY": "openai/gpt-4o",
}


class LLMError(RuntimeError):
    """Raised for model resolution failures, transport errors, and
    unparseable responses. Never raised to implement a retry."""


def resolve_model() -> str:
    """Return REPRO_AGENT_MODEL if set, else pick by which API key is present.

    Raises LLMError naming the env vars it looked for so the failure is
    immediately actionable, rather than surfacing as an opaque litellm
    provider error later.
    """
    override = os.environ.get("REPRO_AGENT_MODEL")
    if override:
        return override

    for env_var, model in DEFAULT_MODELS.items():
        if os.environ.get(env_var):
            return model

    checked = ", ".join(DEFAULT_MODELS.keys())
    raise LLMError(
        "No model configured: set REPRO_AGENT_MODEL to an explicit "
        f"litellm model string, or set one of [{checked}] so a default "
        "can be selected."
    )


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None


def complete(prompt: str, *, system: str | None = None, model: str | None = None,
             max_tokens: int = 2048, temperature: float | None = None) -> LLMResponse:
    """One completion via litellm. NO retry logic beyond transport-level
    errors -- the strict single-pass baseline must not smuggle in retries.
    Populate cost_usd from litellm.completion_cost when available, else None.

    ``temperature`` defaults to None and is omitted from the request entirely
    when unset. This is not merely tidiness: newer Anthropic models reject the
    parameter outright ("`temperature` is deprecated for this model"), so
    sending a default 0.0 turns every call into a 400. Callers that genuinely
    need to pin sampling can still pass a value, accepting that it will fail
    on models which have dropped support.
    """
    resolved_model = model or resolve_model()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, object] = {}
    if temperature is not None:
        kwargs["temperature"] = temperature

    try:
        response = litellm.completion(
            model=resolved_model,
            messages=messages,
            max_tokens=max_tokens,
            **kwargs,
        )
    except Exception as exc:  # noqa: BLE001 - transport errors surface as LLMError
        raise LLMError(f"litellm completion failed for model {resolved_model!r}: {exc}") from exc

    text = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0

    try:
        cost_usd: float | None = litellm.completion_cost(completion_response=response)
    except Exception:  # noqa: BLE001 - cost accounting must never crash a run
        logger.debug("completion_cost failed for model %s", resolved_model, exc_info=True)
        cost_usd = None

    return LLMResponse(
        text=text,
        model=resolved_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
    )


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _find_balanced_object(text: str) -> str | None:
    """Scan for the first balanced {...} span, respecting string literals
    and escapes so braces inside JSON string values don't confuse the count.
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        start = text.find("{", start + 1)
    return None


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response, tolerating
    ```json fences and surrounding prose.

    Strategy, in order: whole-string parse; fenced ```json blocks; the
    first balanced {...} span found by brace-counting. Raises LLMError if
    nothing parses.
    """
    candidates: list[str] = [text]
    candidates.extend(m.group(1).strip() for m in _FENCE_RE.finditer(text))
    balanced = _find_balanced_object(text)
    if balanced:
        candidates.append(balanced)

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise LLMError("could not find a parseable JSON object in the model response")
