"""The single choke-point for every Claude call.

One lazily-built client instead of a fresh ``anthropic.Anthropic(...)`` per
module, one place to add retries and timeouts, and one place where token spend
becomes observable. Callers pick a model tier constant rather than hard-coding
an ID, so a model upgrade is a one-line change here.

Two entry points:

* :func:`complete` — free-text answer.
* :func:`parse` — schema-constrained answer, validated into a Pydantic model by
  the API itself. Prefer this whenever the caller needs structured data; it
  removes the "model wrote prose around the JSON" failure mode entirely.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

import anthropic
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import settings
from core.errors import UpstreamError

logger = logging.getLogger("app.llm")

# Model tiers. Reference these, never a raw ID — swapping a tier is one edit.
MODEL_SMART = "claude-opus-5"
MODEL_BALANCED = "claude-sonnet-5"
MODEL_FAST = "claude-haiku-4-5"

Effort = Literal["low", "medium", "high", "xhigh", "max"]

# USD per 1M tokens (input, output). Used only to derive an estimate for logs;
# token counts themselves come exactly from the API response. Any model absent
# here logs cost as "unknown" rather than a fabricated number.
_PRICING: dict[str, tuple[float, float]] = {
    MODEL_SMART: (5.0, 25.0),
    MODEL_BALANCED: (3.0, 15.0),
    MODEL_FAST: (1.0, 5.0),
}

# Retry only on failures that a second attempt can plausibly fix. A 400 from a
# malformed request is a bug — retrying it just burns time.
_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
)


@lru_cache
def get_client() -> anthropic.Anthropic:
    """Build the client on first use, not at import time.

    Import-time construction would make the whole app — and the test suite —
    fail to start without an API key, even for the endpoints that never call
    Claude. Failing here instead keeps the blast radius at the call site.
    """
    if not settings.anthropic_api_key:
        raise UpstreamError(
            "ANTHROPIC_API_KEY is not set — the LLM is unavailable. "
            "Copy .env.example to .env and add a key."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _log_usage(model: str, response) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    cached = getattr(usage, "cache_read_input_tokens", 0) or 0
    price = _PRICING.get(model)
    cost = f"{(inp * price[0] + out * price[1]) / 1_000_000:.5f}" if price else "unknown"
    logger.info(
        "llm_usage",
        extra={
            "model": model,
            "input_tokens": inp,
            "output_tokens": out,
            "cache_read_tokens": cached,
            "cost_usd": cost,
        },
    )


def _guard_refusal(response) -> None:
    """Raise on a safety refusal instead of letting callers read empty content.

    A declined request comes back as a normal HTTP 200 with
    ``stop_reason == "refusal"`` and no usable content, so code that reaches
    straight for ``content[0]`` fails with a confusing IndexError several frames
    away from the cause.
    """
    if getattr(response, "stop_reason", None) == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) or "unspecified"
        raise UpstreamError(f"The model declined this request (category: {category}).")


def _response_text(response) -> str:
    """Return the first text block, skipping thinking blocks.

    Thinking is on by default on the smart tier, so ``content[0]`` is often a
    thinking block rather than the answer.
    """
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def complete(
    *,
    prompt: str,
    system: str | None = None,
    model: str = MODEL_SMART,
    max_tokens: int = 8000,
    effort: Effort = "high",
    cache_system: bool = False,
) -> str:
    """Ask for a free-text answer.

    ``cache_system`` marks the system prompt as cacheable — worth enabling when
    the same large system prompt is reused across many calls, since cached
    tokens read at roughly a tenth of the input price.
    """
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "output_config": {"effort": effort},
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = (
            [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
            if cache_system
            else system
        )

    try:
        response = get_client().messages.create(**kwargs)
    except anthropic.APIError as exc:
        raise UpstreamError(f"Claude request failed: {exc}") from exc

    _log_usage(model, response)
    _guard_refusal(response)
    return _response_text(response)


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def parse[T: BaseModel](
    *,
    prompt: str,
    schema: type[T],
    system: str | None = None,
    model: str = MODEL_SMART,
    max_tokens: int = 8000,
    effort: Effort = "high",
    cache_system: bool = False,
) -> T:
    """Ask for an answer constrained to ``schema`` and get it back typed.

    The API enforces the schema server-side, so there is no fence-stripping,
    no brace-trimming, and no "model appended a sentence after the JSON" path
    to defend against — the failure mode collapses to a plain validation error.
    """
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "output_config": {"effort": effort, "format": schema},
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = (
            [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
            if cache_system
            else system
        )

    try:
        response = get_client().messages.parse(**kwargs)
    except anthropic.APIError as exc:
        raise UpstreamError(f"Claude request failed: {exc}") from exc

    _log_usage(model, response)
    _guard_refusal(response)

    parsed = getattr(response, "parsed_output", None)
    if parsed is None:
        raise UpstreamError(f"Claude returned no output matching {schema.__name__}.")
    return parsed
