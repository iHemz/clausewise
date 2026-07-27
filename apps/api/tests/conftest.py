"""Shared fixtures.

Nothing here touches the network. A test that calls the real Anthropic API is a
bug: it costs money, it is slow, and it makes the suite non-deterministic. The
model is stubbed at the ``core.llm`` boundary, which is the single point every
Claude call in the codebase passes through.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from api.deps import get_analyses_repository
from main import app
from repositories.analyses import InMemoryAnalysesRepository


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


@pytest.fixture
def stub_llm(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace ``llm.parse`` with canned responses, dispatched by schema.

    Patched on the reference the analyzer module imported, so both the analysis
    pass and the judge pass see the stub.
    """

    def install(*, analysis: object = None, judgement: object = None) -> None:
        from services import analyzer

        def fake_parse(*, schema: type, **_kwargs: object) -> object:
            if schema is analyzer.SeverityJudgement:
                if judgement is None:
                    raise AssertionError("Judge pass ran but no judgement was stubbed.")
                return judgement
            if analysis is None:
                raise AssertionError("Analysis pass ran but no analysis was stubbed.")
            return analysis

        monkeypatch.setattr(analyzer.llm, "parse", fake_parse)

    return install
