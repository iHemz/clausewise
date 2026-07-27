"""Storage for completed analyses.

In-memory for the MVP: an analysis is worth keeping only long enough to share a
result link, and the demo has to run anywhere without provisioning a database.
The `Protocol` is what services depend on, so moving to Postgres means adding a
second class and changing one line in `api/deps.py` — nothing above this layer
knows the difference.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Protocol

from domain.contracts import Analysis


class AnalysesRepository(Protocol):
    def add(self, analysis: Analysis) -> Analysis: ...

    def get(self, analysis_id: str) -> Analysis | None: ...


class InMemoryAnalysesRepository:
    """Bounded process-local storage.

    Contract text is large, so an unbounded dict is a slow memory leak on a
    small host. Oldest entries are evicted once the cap is reached — acceptable
    because these are demo results, not records of account.
    """

    def __init__(self, max_entries: int = 100) -> None:
        self._analyses: OrderedDict[str, Analysis] = OrderedDict()
        self._max_entries = max_entries

    def add(self, analysis: Analysis) -> Analysis:
        self._analyses[analysis.id] = analysis
        self._analyses.move_to_end(analysis.id)
        while len(self._analyses) > self._max_entries:
            self._analyses.popitem(last=False)
        return analysis

    def get(self, analysis_id: str) -> Analysis | None:
        analysis = self._analyses.get(analysis_id)
        if analysis is not None:
            # Reading counts as use, so an actively-viewed result is not the
            # next thing evicted.
            self._analyses.move_to_end(analysis_id)
        return analysis
