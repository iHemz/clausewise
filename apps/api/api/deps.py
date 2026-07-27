"""The assembly layer — where concrete implementations meet the interfaces.

The only module that knows both which repository implementation is in use and
which service needs it. Routes depend on these providers; tests override them.
"""

from __future__ import annotations

from functools import lru_cache

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


def get_contracts_service() -> ContractsService:
    return ContractsService(get_analyses_repository())
