"""Shared fixtures.

Nothing here touches the network. A test that calls a real model API is a bug:
it costs money, it is slow, and it makes the suite non-deterministic.

Two layers enforce that, deliberately. The ``stub_llm`` fixture replaces the
model call for tests that want a canned answer — and ``block_real_providers``
below fails the run if anything reaches for a real SDK client anyway.

The second layer exists because the first one silently stopped working once:
the analyzer moved from ``llm.parse`` to ``llm.parse_meta``, the stub kept
patching the old name, and the suite quietly began billing a live account. A
guard that turns that class of mistake into a loud failure is worth far more
than the few lines it costs.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from api.deps import get_analyses_repository
from core.providers import AnthropicProvider, Completion, Provider, Usage, XAIProvider
from main import app
from repositories.analyses import InMemoryAnalysesRepository


@pytest.fixture(autouse=True)
def block_real_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if a test tries to build a real provider client.

    Autouse, so it also protects tests added later that forget to stub.
    """

    def forbidden(self):
        raise AssertionError(
            f"A test tried to open a real {self.name.value} client. Use the "
            "`stub_llm` fixture — the suite must never call a paid API."
        )

    monkeypatch.setattr(AnthropicProvider, "_get_client", forbidden)
    monkeypatch.setattr(XAIProvider, "_get_client", forbidden)


@pytest.fixture
def analyses_repository() -> InMemoryAnalysesRepository:
    return InMemoryAnalysesRepository()


@pytest.fixture
def client(analyses_repository: InMemoryAnalysesRepository):
    app.dependency_overrides[get_analyses_repository] = lambda: analyses_repository
    # The service provider calls get_analyses_repository() directly rather than
    # through Depends, so clear its cache too — otherwise the override is
    # bypassed and tests share one repository.
    get_analyses_repository.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_analyses_repository.cache_clear()


def stub_completion(value: object, provider: Provider = Provider.ANTHROPIC) -> Completion:
    """Wrap a canned value in the envelope a provider would return."""
    return Completion(
        value=value,
        usage=Usage(provider=provider, model="stub", input_tokens=1, output_tokens=1),
    )


@pytest.fixture
def stub_llm(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace the model call with canned responses, dispatched by schema.

    Patched on the reference the analyzer module imported, so both the analysis
    pass and the judge pass see the stub. ``provider`` sets the provenance the
    stub reports, which is how failover behaviour is asserted without a network.
    """

    def install(
        *,
        analysis: object = None,
        judgement: object = None,
        provider: Provider = Provider.ANTHROPIC,
    ) -> None:
        from services import analyzer

        def pick(schema: type) -> object:
            if schema is analyzer.SeverityJudgement:
                if judgement is None:
                    raise AssertionError("Judge pass ran but no judgement was stubbed.")
                return judgement
            if analysis is None:
                raise AssertionError("Analysis pass ran but no analysis was stubbed.")
            return analysis

        def fake_parse_meta(*, schema: type, **_kwargs: object) -> Completion:
            return stub_completion(pick(schema), provider)

        def fake_parse(*, schema: type, **_kwargs: object) -> object:
            return pick(schema)

        monkeypatch.setattr(analyzer.llm, "parse_meta", fake_parse_meta)
        monkeypatch.setattr(analyzer.llm, "parse", fake_parse)

    return install
