"""Provider-agnostic LLM completion via litellm.

Constraints (see CONTRACTS.md): `complete()` makes exactly one call with no
application-level retries, since a retry here would invalidate the
single-pass baseline; and the module performs no network access at import
time and imports cleanly with no API key set.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

import litellm

logger = logging.getLogger(__name__)

# Image attachment limits. MAX_IMAGE_EDGE matches the largest edge the
# Anthropic API accepts without server-side downscaling; MAX_IMAGE_BYTES stays
# under the API's per-image cap with margin for base64 expansion.
MAX_IMAGES = 6
MAX_IMAGE_EDGE = 1568
MAX_IMAGE_BYTES = 3_500_000

_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# First env var found (in this order) wins.
DEFAULT_MODELS = {
    "ANTHROPIC_API_KEY": "anthropic/claude-sonnet-5",
    "OPENAI_API_KEY": "openai/gpt-4o",
}


class LLMError(RuntimeError):
    """Raised for model resolution failures, transport errors, and unparseable responses."""


def resolve_model() -> str:
    """Return REPRO_AGENT_MODEL if set, else pick by which API key is present.

    Raises LLMError naming the env vars checked if none is set.
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
    n_images: int = 0


def _encode_image(path: Path) -> str | None:
    """Return a ``data:<mime>;base64,...`` URL for one image, or None to skip it.

    Downscales so the longest edge is at most MAX_IMAGE_EDGE and re-encodes
    (PNG stays PNG; everything else becomes JPEG, with RGBA/P flattened to
    RGB). If the PNG is still over MAX_IMAGE_BYTES it is re-saved as JPEG.
    Any Pillow failure logs a warning and returns None; it never raises.
    """
    mime = _IMAGE_MIME.get(path.suffix.lower())
    if mime is None:
        return None
    try:
        from PIL import Image

        with Image.open(path) as im:
            im.load()
            scale = MAX_IMAGE_EDGE / max(im.size)
            if scale < 1:
                im = im.resize(
                    (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
                )
            keep_png = mime == "image/png"
            buf = io.BytesIO()
            if keep_png:
                im.save(buf, format="PNG", optimize=True)
                if buf.tell() > MAX_IMAGE_BYTES:
                    keep_png = False
                    buf = io.BytesIO()
            if not keep_png:
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                im.save(buf, format="JPEG", quality=85)
                mime = "image/jpeg"
    except Exception:  # noqa: BLE001 - a bad image must not abort the call
        logger.warning("skipping image %s: Pillow could not process it", path, exc_info=True)
        return None
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:{mime};base64,{data}"


def complete(prompt: str, *, system: str | None = None, model: str | None = None,
             max_tokens: int = 2048, temperature: float | None = None,
             images: list[Path] | None = None) -> LLMResponse:
    """One completion via litellm, with no retry logic. cost_usd comes from
    litellm.completion_cost when available, else None.

    ``temperature`` is omitted from the request when None: newer Anthropic
    models reject the parameter ("`temperature` is deprecated for this
    model"), so a default of 0.0 would make every call a 400.

    ``images`` attaches figure files after the prompt as OpenAI-style
    ``image_url`` blocks, which litellm translates for each provider. At most
    MAX_IMAGES are sent (the first after sorting); unsupported or unreadable
    files are skipped. With no images the user content stays a plain string.
    """
    resolved_model = model or resolve_model()

    image_urls: list[str] = []
    if images:
        for path in sorted(images)[:MAX_IMAGES]:
            url = _encode_image(Path(path))
            if url is not None:
                image_urls.append(url)

    messages: list[dict[str, object]] = []
    if system:
        messages.append({"role": "system", "content": system})
    if image_urls:
        content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        content.extend(
            {"type": "image_url", "image_url": {"url": url}} for url in image_urls
        )
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, object] = {}
    if temperature is not None:
        kwargs["temperature"] = temperature

    try:
        response = litellm.completion(
            model=resolved_model,
            messages=messages,
            max_tokens=max_tokens,
            # litellm adds no retries of its own on the Anthropic path, but on
            # the OpenAI path it constructs openai.OpenAI(max_retries=2), which
            # would silently make up to three attempts per call on 429/5xx.
            # The baseline's single-pass claim has to hold on every provider.
            max_retries=0,
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
        n_images=len(image_urls),
    )


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _find_balanced_object(text: str) -> str | None:
    """Return the first balanced {...} span, ignoring braces inside string literals."""
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
    """Return the first JSON object in a model response.

    Tries, in order: the whole string; fenced ```json blocks; the first
    balanced {...} span. Raises LLMError if nothing parses.
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
