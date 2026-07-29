"""Storage for completed analyses.

In-memory for the MVP: an analysis is worth keeping only long enough to share a
result link, and the demo has to run anywhere without provisioning a database.
The `Protocol` is what services depend on, so moving to Postgres means adding a
second class and changing one line in `api/deps.py` — nothing above this layer
knows the difference.

**This is what pins the API to a single always-running process.** State lives in
this worker, and an upload spans two requests — a POST that returns 202 and
starts a background task, then GETs that poll it. Run two instances and the
polls hit a process that never saw the POST; let the host stop an idle instance
and the background task dies after the 202 has already been sent. `fly.toml`
therefore sets one machine with auto-stop off, and both settings become
unnecessary the moment this is backed by shared storage.
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
