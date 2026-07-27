"""Model providers behind one interface, so the app can fail over between them.

Three adapters: Anthropic (Claude), xAI (Grok), and Groq (open models on fast
inference hardware). All speak the same small protocol, so ``core.llm`` can try
one and fall back to the next without knowing anything about either SDK.

The rule that makes failover safe is **narrowness**. Only
:class:`ProviderUnavailable` triggers a fallback, and it is raised only when the
provider cannot serve *any* request right now: exhausted credit, a missing or
rejected key, or hard capacity limits. Everything else — a malformed request, a
schema the model could not satisfy, a safety refusal — propagates immediately
from the primary provider.

That distinction matters more than it looks. A broad "retry on any error" chain
turns one bug into two bills and hides the bug behind a second provider's
output, which is exactly the kind of quiet wrongness this codebase is built to
avoid.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar, Protocol

from pydantic import BaseModel

from core.config import settings
from core.errors import UpstreamError

logger = logging.getLogger("app.providers")


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    #: Grok, from xAI (x.ai). Keys look like ``xai-...``.
    XAI = "xai"
    #: Open models on Groq's inference hardware (groq.com). Keys are ``gsk_...``.
    #: A different company from xAI despite the near-identical name. Mixing the
    #: two up is by far the most likely misconfiguration here, so both are named
    #: explicitly everywhere rather than hidden behind a generic alias.
    GROQ = "groq"


class ProviderUnavailable(UpstreamError):
    """This provider cannot serve any request right now — try the next one.

    Deliberately narrow. Raised for exhausted credit, a missing or rejected API
    key, and hard capacity refusals. Never for a bad request or a bad response,
    because failing those over would spend money re-running a broken call and
    bury the cause.
    """

    def __init__(self, provider: Provider, reason: str) -> None:
        super().__init__(f"{provider.value} is unavailable: {reason}")
        self.provider = provider
        self.reason = reason


@dataclass(frozen=True)
class Usage:
    """Token counts as reported by the provider, plus a derived cost estimate."""

    provider: Provider
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float | None = None


@dataclass
class Completion[T]:
    """A provider's answer plus which provider actually produced it.

    Provenance travels with the value rather than sitting in a module global,
    because callers run these concurrently across threads — a global "last
    provider used" would be read by the wrong thread often enough to be
    misleading, and misleading provenance is worse than none.
    """

    value: T
    usage: Usage


class LLMProvider(Protocol):
    """What ``core.llm`` needs from a provider. Adapters implement this."""

    name: Provider

    def is_configured(self) -> bool:
        """Whether this provider has the credentials it needs to be tried."""
        ...

    def complete(
        self, *, prompt: str, system: str | None, max_tokens: int, effort: str, cache_system: bool
    ) -> Completion[str]: ...

    def parse[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        system: str | None,
        max_tokens: int,
        effort: str,
        cache_system: bool,
    ) -> Completion[T]: ...


# --- Shared helpers --------------------------------------------------------

# Substrings that mean "this account cannot make calls", checked against the
# provider's error message. String matching is unavoidable here: providers
# report exhausted credit as a generic 400/403 with the detail only in prose,
# so no status code or error type distinguishes it from an ordinary bad request.
# Kept in one visible list rather than scattered through the adapters, so adding
# a newly-observed phrasing is a one-line change.
_EXHAUSTED_MARKERS = (
    "credit balance is too low",
    "insufficient credits",
    "insufficient_quota",
    "exceeded your current quota",
    "billing",
    "payment required",
    "no credits",
)

# Substrings meaning "this key is wrong". Needed because the OpenAI-compatible
# endpoints answer a bad key with a 400, not the 401 the SDK maps to
# AuthenticationError — so without this a wrong key reads as an ordinary bad
# request and never advances the fallback chain. Found the hard way.
_BAD_KEY_MARKERS = (
    "incorrect api key",
    "invalid api key",
    "invalid_api_key",
    "no api key provided",
)


def _looks_exhausted(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _EXHAUSTED_MARKERS)


def _looks_bad_key(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _BAD_KEY_MARKERS)


def classify(exc: Exception, provider: Provider, status: int | None) -> Exception:
    """Decide whether ``exc`` means "this provider is done" or "try again".

    Status is checked **before** the message, and that order is the whole point.
    A 429 is a rate limit: transient, and the single most retryable error there
    is. But rate-limit messages routinely mention "quota" or "tokens per
    minute", so a message-first classifier reads them as exhausted credit,
    marks the provider unavailable, and — because unavailability is explicitly
    not retryable — skips the backoff that would have fixed it. Observed live:
    five of thirteen clauses lost to a free-tier rate limit that one retry each
    would have cleared.

    So: 429 always falls through to the retry layer. Only a non-429 failure gets
    read as a dead account.
    """
    if status == 429:
        return exc

    message = str(exc)
    if _looks_bad_key(message):
        return ProviderUnavailable(provider, "API key rejected")
    if _looks_exhausted(message):
        return ProviderUnavailable(provider, "credit or quota exhausted")
    return exc


def _estimate_cost(
    model: str, pricing: dict[str, tuple[float, float]], inp: int, out: int
) -> float | None:
    """USD estimate from published per-million rates, or None if unknown.

    Returns None rather than 0.0 for an unlisted model — a fabricated zero in a
    cost dashboard is worse than a visible gap.
    """
    rate = pricing.get(model)
    if rate is None:
        return None
    return (inp * rate[0] + out * rate[1]) / 1_000_000


# --- Anthropic -------------------------------------------------------------

MODEL_ANTHROPIC_SMART = "claude-opus-5"
MODEL_ANTHROPIC_BALANCED = "claude-sonnet-5"
MODEL_ANTHROPIC_FAST = "claude-haiku-4-5"

_ANTHROPIC_PRICING: dict[str, tuple[float, float]] = {
    MODEL_ANTHROPIC_SMART: (5.0, 25.0),
    MODEL_ANTHROPIC_BALANCED: (3.0, 15.0),
    MODEL_ANTHROPIC_FAST: (1.0, 5.0),
}


class AnthropicProvider:
    """Claude via the official Anthropic SDK."""

    name = Provider.ANTHROPIC

    def __init__(self, model: str = MODEL_ANTHROPIC_SMART) -> None:
        self.model = model
        self._client: Any = None

    def is_configured(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _get_client(self) -> Any:
        import anthropic

        if self._client is None:
            if not settings.anthropic_api_key:
                raise ProviderUnavailable(self.name, "ANTHROPIC_API_KEY is not set")
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        return self._client

    def _translate(self, exc: Exception) -> Exception:
        """Map an SDK error to ProviderUnavailable when it means "cannot serve"."""
        import anthropic

        if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
            return ProviderUnavailable(self.name, "API key rejected")
        if isinstance(exc, anthropic.APIStatusError):
            return classify(exc, self.name, getattr(exc, "status_code", None))
        return exc

    def _build(
        self, *, prompt: str, system: str | None, max_tokens: int, effort: str, cache_system: bool
    ) -> dict:
        kwargs: dict = {
            "model": self.model,
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
        return kwargs

    def _usage(self, response: Any) -> Usage:
        usage = getattr(response, "usage", None)
        inp = getattr(usage, "input_tokens", 0) or 0
        out = getattr(usage, "output_tokens", 0) or 0
        cached = getattr(usage, "cache_read_input_tokens", 0) or 0
        return Usage(
            provider=self.name,
            model=self.model,
            input_tokens=inp,
            output_tokens=out,
            cached_tokens=cached,
            cost_usd=_estimate_cost(self.model, _ANTHROPIC_PRICING, inp, out),
        )

    def _guard_refusal(self, response: Any) -> None:
        """A safety decline arrives as a normal 200 with empty content."""
        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) or "unspecified"
            # Not ProviderUnavailable: another provider would likely decline the
            # same prompt, and silently shopping a refused request around
            # providers is not behaviour this codebase should have.
            raise UpstreamError(f"Claude declined this request (category: {category}).")

    def complete(
        self, *, prompt: str, system: str | None, max_tokens: int, effort: str, cache_system: bool
    ) -> Completion[str]:
        kwargs = self._build(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            effort=effort,
            cache_system=cache_system,
        )
        try:
            response = self._get_client().messages.create(**kwargs)
        except ProviderUnavailable:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc

        self._guard_refusal(response)
        # Thinking is on by default on the smart tier, so content[0] is often a
        # thinking block rather than the answer.
        text = next(
            (
                b.text
                for b in getattr(response, "content", []) or []
                if getattr(b, "type", "") == "text"
            ),
            "",
        )
        return Completion(value=text, usage=self._usage(response))

    def parse[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        system: str | None,
        max_tokens: int,
        effort: str,
        cache_system: bool,
    ) -> Completion[T]:
        kwargs = self._build(
            prompt=prompt,
            system=system,
            max_tokens=max_tokens,
            effort=effort,
            cache_system=cache_system,
        )
        # The schema goes at the top level as `output_format`, not inside
        # `output_config` — putting the class in `output_config` makes the SDK
        # try to JSON-serialize the Pydantic class itself.
        kwargs["output_format"] = schema

        try:
            response = self._get_client().messages.parse(**kwargs)
        except ProviderUnavailable:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc

        self._guard_refusal(response)
        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise UpstreamError(f"Claude returned no output matching {schema.__name__}.")
        return Completion(value=parsed, usage=self._usage(response))


# --- OpenAI-compatible providers (xAI, Groq) -------------------------------


class OpenAICompatibleProvider:
    """Shared adapter for any endpoint that speaks the OpenAI chat API.

    xAI and Groq are different companies with confusingly similar names, but
    both expose the same wire protocol, so one adapter serves both. Subclasses
    supply a base URL, a default model, and which setting holds the key.

    The OpenAI SDK is used rather than each vendor's own client for one reason
    that matters: ``chat.completions.parse`` converts a Pydantic model into a
    *strict* JSON schema — every field required, ``additionalProperties: false``
    — and validates the reply against it. That is the same server-side guarantee
    the Anthropic adapter relies on, and keeping it identical across providers
    is what makes them substitutable. A fallback that returned unvalidated prose
    would quietly break every caller that depends on structured output.
    """

    name: Provider
    base_url: str
    model: str
    pricing: ClassVar[dict[str, tuple[float, float]]] = {}
    key_setting: str = ""

    def __init__(self, model: str | None = None) -> None:
        if model:
            self.model = model
        self._client: Any = None

    def _api_key(self) -> str | None:
        return getattr(settings, self.key_setting, None)

    def is_configured(self) -> bool:
        return bool(self._api_key())

    def _get_client(self) -> Any:
        import openai

        if self._client is None:
            key = self._api_key()
            if not key:
                raise ProviderUnavailable(self.name, f"{self.key_setting.upper()} is not set")
            self._client = openai.OpenAI(api_key=key, base_url=self.base_url)
        return self._client

    def _translate(self, exc: Exception) -> Exception:
        import openai

        if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
            return ProviderUnavailable(self.name, "API key rejected")
        if isinstance(exc, openai.APIStatusError):
            return classify(exc, self.name, getattr(exc, "status_code", None))
        return exc

    def _messages(self, prompt: str, system: str | None) -> list[dict]:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _usage(self, response: Any) -> Usage:
        usage = getattr(response, "usage", None)
        inp = getattr(usage, "prompt_tokens", 0) or 0
        out = getattr(usage, "completion_tokens", 0) or 0
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", 0) or 0
        return Usage(
            provider=self.name,
            model=self.model,
            input_tokens=inp,
            output_tokens=out,
            cached_tokens=cached,
            cost_usd=_estimate_cost(self.model, self.pricing, inp, out),
        )

    def complete(
        self, *, prompt: str, system: str | None, max_tokens: int, effort: str, cache_system: bool
    ) -> Completion[str]:
        # `effort` and `cache_system` are Anthropic concepts. These endpoints
        # cache automatically and expose no equivalent knob, so both are accepted
        # and ignored rather than translated into a guess that would 400.
        del effort, cache_system
        try:
            response = self._get_client().chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=self._messages(prompt, system),
            )
        except ProviderUnavailable:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc

        return Completion(
            value=response.choices[0].message.content or "", usage=self._usage(response)
        )

    def parse[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        system: str | None,
        max_tokens: int,
        effort: str,
        cache_system: bool,
    ) -> Completion[T]:
        del effort, cache_system
        try:
            response = self._get_client().chat.completions.parse(
                model=self.model,
                max_tokens=max_tokens,
                messages=self._messages(prompt, system),
                response_format=schema,
            )
        except ProviderUnavailable:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc

        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise UpstreamError(f"{self.name.value} declined this request: {message.refusal}")

        parsed = getattr(message, "parsed", None)
        if parsed is None:
            raise UpstreamError(f"{self.name.value} returned no output matching {schema.__name__}.")
        return Completion(value=parsed, usage=self._usage(response))


class XAIProvider(OpenAICompatibleProvider):
    """Grok, from xAI (x.ai). Keys look like ``xai-...``.

    Not to be confused with :class:`GroqProvider` — different company, different
    models, near-identical name.
    """

    name = Provider.XAI
    base_url = "https://api.x.ai/v1"
    model = "grok-4.5"
    key_setting = "xai_api_key"
    pricing: ClassVar[dict[str, tuple[float, float]]] = {
        "grok-4.5": (2.0, 6.0),
        "grok-4.3": (1.25, 2.5),
    }


class GroqProvider(OpenAICompatibleProvider):
    """Open models on Groq's fast inference hardware (groq.com). Keys are ``gsk_...``.

    ``openai/gpt-oss-120b`` is the default because it is the largest model here
    that supports *strict* structured outputs. That is a requirement rather than
    a preference: a model without strict schema support cannot uphold the
    guarantee the rest of the codebase is built on, so it is not a valid
    substitute however capable it otherwise is.
    """

    name = Provider.GROQ
    base_url = "https://api.groq.com/openai/v1"
    model = "openai/gpt-oss-120b"
    key_setting = "groq_api_key"
    pricing: ClassVar[dict[str, tuple[float, float]]] = {
        "openai/gpt-oss-120b": (0.15, 0.75),
        "openai/gpt-oss-20b": (0.10, 0.50),
        "llama-3.3-70b-versatile": (0.59, 0.79),
    }


_BUILDERS: dict[Provider, type] = {
    Provider.ANTHROPIC: AnthropicProvider,
    Provider.XAI: XAIProvider,
    Provider.GROQ: GroqProvider,
}

_REGISTRY: dict[Provider, LLMProvider] = {}


def get_provider(name: Provider) -> LLMProvider:
    """Return the shared adapter for ``name``, building it on first use."""
    if name not in _REGISTRY:
        _REGISTRY[name] = _BUILDERS[name]()
    return _REGISTRY[name]


def reset_providers() -> None:
    """Drop cached adapters. Used by tests that swap credentials."""
    _REGISTRY.clear()
