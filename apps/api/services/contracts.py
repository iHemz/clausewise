"""The upload → analyze use-case.

Orchestration only: extract, segment, analyze, store. Each step lives in its own
module so this reads as the sequence it is, and so every step is independently
testable. Raises domain errors; the HTTP mapping happens in
``api/error_handlers.py``.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from core.errors import NotFoundError, UnprocessableError
from core.extraction import extract
from domain.contracts import Analysis, Document
from domain.segmentation import segment
from repositories.analyses import AnalysesRepository
from services.analyzer import analyze_document

logger = logging.getLogger("clausewise.contracts")


class ContractsService:
    def __init__(self, repository: AnalysesRepository) -> None:
        self._repository = repository

    def analyze_upload(self, filename: str, data: bytes, *, judge: bool = True) -> Analysis:
        extracted = extract(filename, data)
        clauses = segment(extracted.text)

        if not clauses:
            raise UnprocessableError(
                "No clauses could be identified in this document. It may be a "
                "scan, a form, or not a contract."
            )

        findings, dropped = analyze_document(clauses, extracted.page_breaks, judge=judge)

        analysis = Analysis(
            id=str(uuid4()),
            document=Document(
                id=str(uuid4()),
                filename=filename,
                text=extracted.text,
                clauses=clauses,
                page_count=extracted.page_count,
            ),
            findings=findings,
            dropped_ungrounded=dropped,
        )

        logger.info(
            "analysis_complete",
            extra={
                "analysis_id": analysis.id,
                # Not "filename" — that is a reserved LogRecord attribute and
                # logging raises KeyError rather than shadowing it.
                "source_filename": filename,
                "clause_count": len(clauses),
                "finding_count": len(findings),
                "dropped_ungrounded": dropped,
            },
        )
        return self._repository.add(analysis)

    def get(self, analysis_id: str) -> Analysis:
        analysis = self._repository.get(analysis_id)
        if analysis is None:
            raise NotFoundError(
                f"No analysis with id {analysis_id!r}. Results are kept in memory "
                "and do not survive a restart."
            )
        return analysis
