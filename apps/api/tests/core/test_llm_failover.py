"""Tests for provider selection and failover.

The behaviour that matters here is not "does it fail over" — it is **when it
refuses to**. A failover chain that is too eager re-runs a broken request on a
second provider: two bills, and the bug hidden behind whatever the fallback
happened to say. So most of these tests assert that something does *not*
happen.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from core import llm
from core.errors import UpstreamError
from core.providers import Completion, Provider, ProviderUnavailable, Usage


class Answer(BaseModel):
    text: str


def completion(provider: Provider, text: str = "ok") -> Completion[Answer]:
    return Completion(
        value=Answer(text=text),
        usage=Usage(provider=provider, model="stub", input_tokens=1, output_tokens=1),
    )


class FakeProvider:
    """A provider adapter whose behaviour each test dictates."""

    def __init__(self, name: Provider, *, configured: bool = True, error: Exception | None = None):
        self.name = name
        self._configured = configured
        self._error = error
        self.calls = 0

    def is_configured(self) -> bool:
        return self._configured

    def complete(self, **_kwargs):
        return self._respond()

    def parse(self, **_kwargs):
        return self._respond()

    def _respond(self):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return completion(self.name)


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch):
    """Install fake adapters and a provider order for one test."""

    def install(
        primary: FakeProvider,
        fallback: FakeProvider | None = None,
        *,
        fallback_names: str | None = None,
    ) -> None:
        registry = {primary.name: primary}
        if fallback is not None:
            registry[fallback.name] = fallback

        monkeypatch.setattr(llm, "get_provider", lambda name: registry[name])
        monkeypatch.setattr(llm.settings, "llm_provider", primary.name.value)
        monkeypatch.setattr(
            llm.settings,
            "llm_fallback_providers",
            fallback_names
            if fallback_names is not None
            else (fallback.name.value if fallback else ""),
        )

    return install


def call() -> Completion[Answer]:
    return llm.parse_meta(prompt="hi", schema=Answer)


def test_the_primary_answers_and_the_fallback_is_never_touched(wire):
    primary = FakeProvider(Provider.ANTHROPIC)
    fallback = FakeProvider(Provider.XAI)
    wire(primary, fallback)

    result = call()

    assert result.usage.provider is Provider.ANTHROPIC
    assert fallback.calls == 0, "a healthy primary must not cost a second call"


def test_exhausted_credit_fails_over(wire):
    primary = FakeProvider(
        Provider.ANTHROPIC,
        error=ProviderUnavailable(Provider.ANTHROPIC, "credit balance exhausted"),
    )
    fallback = FakeProvider(Provider.XAI)
    wire(primary, fallback)

    result = call()

    assert result.usage.provider is Provider.XAI
    assert fallback.calls == 1


def test_a_rejected_key_fails_over(wire):
    primary = FakeProvider(
        Provider.ANTHROPIC, error=ProviderUnavailable(Provider.ANTHROPIC, "API key rejected")
    )
    fallback = FakeProvider(Provider.XAI)
    wire(primary, fallback)

    assert call().usage.provider is Provider.XAI


def test_a_bad_request_does_not_fail_over(wire):
    # The single most important case. A malformed request is a bug in this
    # codebase; re-running it on another provider bills twice and buries the
    # cause behind whatever the fallback said.
    primary = FakeProvider(Provider.ANTHROPIC, error=ValueError("schema is malformed"))
    fallback = FakeProvider(Provider.XAI)
    wire(primary, fallback)

    with pytest.raises(ValueError, match="schema is malformed"):
        call()

    assert fallback.calls == 0


def test_a_refusal_does_not_fail_over(wire):
    # Another provider would likely decline the same prompt too. Shopping a
    # refused request around providers is not behaviour this codebase should
    # have.
    primary = FakeProvider(Provider.ANTHROPIC, error=UpstreamError("declined this request"))
    fallback = FakeProvider(Provider.XAI)
    wire(primary, fallback)

    with pytest.raises(UpstreamError, match="declined"):
        call()

    assert fallback.calls == 0


def test_an_unconfigured_fallback_is_skipped_not_attempted(wire):
    primary = FakeProvider(
        Provider.ANTHROPIC, error=ProviderUnavailable(Provider.ANTHROPIC, "exhausted")
    )
    fallback = FakeProvider(Provider.XAI, configured=False)
    wire(primary, fallback)

    with pytest.raises(UpstreamError, match="Every configured provider is unavailable"):
        call()

    assert fallback.calls == 0, "a provider with no key must not be called"


def test_no_configured_provider_is_a_clear_configuration_error(wire):
    wire(FakeProvider(Provider.ANTHROPIC, configured=False))

    with pytest.raises(UpstreamError, match="No model provider is configured"):
        call()


def test_every_provider_failing_reports_all_the_reasons(wire):
    primary = FakeProvider(
        Provider.ANTHROPIC, error=ProviderUnavailable(Provider.ANTHROPIC, "credit exhausted")
    )
    fallback = FakeProvider(Provider.XAI, error=ProviderUnavailable(Provider.XAI, "key rejected"))
    wire(primary, fallback)

    with pytest.raises(UpstreamError) as excinfo:
        call()

    message = str(excinfo.value)
    assert "credit exhausted" in message
    assert "key rejected" in message


def test_failover_is_disabled_when_no_fallback_is_configured(wire):
    primary = FakeProvider(
        Provider.ANTHROPIC, error=ProviderUnavailable(Provider.ANTHROPIC, "exhausted")
    )
    wire(primary, fallback_names="")

    with pytest.raises(UpstreamError, match="Every configured provider is unavailable"):
        call()


def test_an_unknown_fallback_name_is_ignored_rather_than_fatal(wire):
    # A typo in an optional fallback must not take down a working primary.
    primary = FakeProvider(Provider.ANTHROPIC)
    wire(primary, fallback_names="not-a-provider")

    assert call().usage.provider is Provider.ANTHROPIC


def test_provider_unavailable_is_not_retried_on_the_same_provider(wire):
    # Retrying an exhausted account just delays the failover that was always
    # going to be needed.
    primary = FakeProvider(
        Provider.ANTHROPIC, error=ProviderUnavailable(Provider.ANTHROPIC, "exhausted")
    )
    fallback = FakeProvider(Provider.XAI)
    wire(primary, fallback)

    call()

    assert primary.calls == 1, "an exhausted provider should be tried once, not retried"
