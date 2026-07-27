"""The single choke-point for every model call, across every provider.

Callers use :func:`complete` or :func:`parse` and never touch a provider SDK.
This module owns three things they should not have to think about:

* **Retries** — jittered backoff on transient failures (429, 5xx, connection
  drops), which are the normal weather of a concurrent workload.
* **Failover** — if the primary provider cannot serve *any* request, the next
  configured provider takes over. Ordered in ``core.config`` and deliberately
  narrow: see :class:`core.providers.ProviderUnavailable`.
* **Observability** — token usage and estimated cost logged in one place, and
  provenance returned to callers that need to know which provider answered.

Two entry points, each with a metadata variant:

* :func:`complete` / :func:`complete_meta` — free-text answer.
* :func:`parse` / :func:`parse_meta` — schema-constrained answer, validated by
  the provider itself.

Prefer ``parse``. Both providers enforce the schema server-side, which removes
the "model wrote prose around the JSON" failure mode rather than papering over
it with a parser. Use the ``_meta`` variants when it matters *who* answered —
for anything surfaced to a user as a factual claim, it usually does.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_random_exponential

from core.config import settings
from core.errors import UpstreamError
from core.providers import Completion, Provider, ProviderUnavailable, get_provider

logger = logging.getLogger("app.llm")

Effort = Literal["low", "medium", "high", "xhigh", "max"]


def _is_retryable(exc: BaseException) -> bool:
    """Whether a second attempt at the *same* provider could plausibly succeed.

    Decided by HTTP status rather than exception class. Listing classes is the
    obvious approach and it is subtly wrong: Anthropic's ``OverloadedError``
    (529) is a sibling of ``InternalServerError``, not a subclass, so a class
    tuple that looks exhaustive silently drops the most common transient failure
    under concurrency.

    ``ProviderUnavailable`` is explicitly *not* retryable — retrying an
    exhausted account only burns time before the failover that was always going
    to be needed.
    """
    if isinstance(exc, ProviderUnavailable):
        return False
    if type(exc).__name__ in {"APIConnectionError", "APITimeoutError"}:
        return True
    status = getattr(exc, "status_code", None)
    return isinstance(status, int) and (status == 429 or status >= 500)


_RETRY = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(4),
    # Jittered, so concurrent workers don't retry in lockstep and re-collide.
    wait=wait_random_exponential(multiplier=1, max=30),
    reraise=True,
)


def provider_chain() -> list[Provider]:
    """The providers to try, in order, filtered to those actually configured.

    Dropping unconfigured providers here means a missing fallback key is a
    quiet no-op rather than a confusing second failure at the end of a long run.
    An empty chain is a configuration error and is reported as one.
    """
    ordered: list[Provider] = [settings.llm_provider_enum]
    ordered += [p for p in settings.llm_fallback_enums if p not in ordered]

    configured = [p for p in ordered if get_provider(p).is_configured()]
    if not configured:
        raise UpstreamError(
            "No model provider is configured. Set ANTHROPIC_API_KEY (or XAI_API_KEY) "
            "in the API's .env — see .env.example."
        )
    return configured


def _log(completion: Completion, *, fell_back: bool) -> None:
    usage = completion.usage
    logger.info(
        "llm_usage",
        extra={
            "provider": usage.provider.value,
            "model": usage.model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cached_tokens": usage.cached_tokens,
            "cost_usd": f"{usage.cost_usd:.5f}" if usage.cost_usd is not None else "unknown",
            "fell_back": fell_back,
        },
    )


def _run(call, *, what: str) -> Completion:
    """Try each configured provider in turn; return the first that answers.

    ``call`` takes a provider adapter and performs the request. Only
    ``ProviderUnavailable`` advances to the next provider — every other error
    belongs to the caller and is raised immediately, because a bad request
    re-run elsewhere is two bills and a hidden bug.
    """
    chain = provider_chain()
    failures: list[str] = []

    for index, name in enumerate(chain):
        adapter = get_provider(name)
        try:
            completion = _RETRY(call)(adapter)
        except ProviderUnavailable as exc:
            failures.append(f"{name.value}: {exc.reason}")
            remaining = chain[index + 1 :]
            if remaining:
                logger.warning(
                    "provider_failover",
                    extra={
                        "from_provider": name.value,
                        "to_provider": remaining[0].value,
                        "reason": exc.reason,
                        "operation": what,
                    },
                )
            continue

        _log(completion, fell_back=index > 0)
        return completion

    raise UpstreamError(
        f"Every configured provider is unavailable ({'; '.join(failures)}). "
        "Check the API keys and account balances."
    )


def complete_meta(
    *,
    prompt: str,
    system: str | None = None,
    max_tokens: int = 8000,
    effort: Effort = "high",
    cache_system: bool = False,
) -> Completion[str]:
    """Free-text answer, with the provider that produced it."""
    return _run(
        lambda adapter: adapter.complete(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            effort=effort,
            cache_system=cache_system,
        ),
        what="complete",
    )


def complete(
    *,
    prompt: str,
    system: str | None = None,
    max_tokens: int = 8000,
    effort: Effort = "high",
    cache_system: bool = False,
) -> str:
    """Free-text answer.

    ``cache_system`` marks the system prompt as cacheable where the provider
    supports it — worth enabling when the same large system prompt is reused
    across many calls, since cached tokens read at a fraction of the input price.
    """
    return complete_meta(
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
        effort=effort,
        cache_system=cache_system,
    ).value


def parse_meta[T: BaseModel](
    *,
    prompt: str,
    schema: type[T],
    system: str | None = None,
    max_tokens: int = 8000,
    effort: Effort = "high",
    cache_system: bool = False,
) -> Completion[T]:
    """Schema-constrained answer, with the provider that produced it."""
    return _run(
        lambda adapter: adapter.parse(
            prompt=prompt,
            schema=schema,
            system=system,
            max_tokens=max_tokens,
            effort=effort,
            cache_system=cache_system,
        ),
        what="parse",
    )


def parse[T: BaseModel](
    *,
    prompt: str,
    schema: type[T],
    system: str | None = None,
    max_tokens: int = 8000,
    effort: Effort = "high",
    cache_system: bool = False,
) -> T:
    """Ask for an answer constrained to ``schema`` and get it back typed.

    The provider enforces the schema, so there is no fence-stripping, no
    brace-trimming, and no "model appended a sentence after the JSON" path to
    defend against — the failure mode collapses to a plain validation error.
    """
    return parse_meta(
        prompt=prompt,
        schema=schema,
        system=system,
        max_tokens=max_tokens,
        effort=effort,
        cache_system=cache_system,
    ).value
