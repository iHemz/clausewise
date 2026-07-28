"""The assembly layer — where concrete implementations meet the interfaces.

The only module that knows both which repository implementation is in use and
which service needs it. Routes depend on these providers; tests override them.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from repositories.analyses import AnalysesRepository, InMemoryAnalysesRepository
from services.contracts import ContractsService


@lru_cache
def get_analyses_repository() -> AnalysesRepository:
    """One repository instance for the process.

    Cached because the in-memory implementation *is* the storage — a fresh
    instance per request would lose every result. A database-backed repository
    would drop the cache and take a session argument instead.
    """
    return InMemoryAnalysesRepository()


def get_contracts_service(
    repository: AnalysesRepository = Depends(get_analyses_repository),
) -> ContractsService:
    """Build the service from whatever repository the request resolves to.

    The repository arrives through ``Depends`` rather than being fetched
    directly, so ``app.dependency_overrides[get_analyses_repository]`` actually
    reaches it. Calling the provider inline instead looks equivalent and is not:
    FastAPI can only substitute what it resolves, so an inline call quietly
    bypasses every override and a test fixture that appears to inject a fake
    injects nothing.
    """
    return ContractsService(repository)
