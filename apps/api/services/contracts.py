"""The upload → analyze use-case.

Orchestration only: extract, segment, analyze, store. Each step lives in its own
module so this reads as the sequence it is, and so every step is independently
testable. Raises domain errors; the HTTP mapping happens in
``api/error_handlers.py``.

Split into two phases so the wait can be reported rather than guessed at.
``begin_upload`` does the cheap, synchronous part — extract and segment — and
returns a stored, pending analysis whose document text is already populated.
``run_analysis`` then runs the model passes, writing progress back to the
repository as each clause returns. The client polls the stored analysis, so the
counter it shows is the number of clauses that have actually been reviewed and
not a timer pretending to be one.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from core.errors import NotFoundError, UnprocessableError, UpstreamError
from core.extraction import extract
from domain.contracts import Analysis, AnalysisStage, AnalysisStatus, Document, Finding
from domain.segmentation import segment
from repositories.analyses import AnalysesRepository
from services.analyzer import analyze_document

logger = logging.getLogger("clausewise.contracts")


class ContractsService:
    def __init__(self, repository: AnalysesRepository) -> None:
        self._repository = repository

    def begin_upload(self, filename: str, data: bytes) -> Analysis:
        """Extract, segment, store as pending. Cheap enough to do in-request."""
        extracted = extract(filename, data)
        clauses = segment(extracted.text)

        if not clauses:
            raise UnprocessableError(
                "No clauses could be identified in this document. It may be a "
                "scan, a form, or not a contract."
            )

        analysis = Analysis(
            id=str(uuid4()),
            document=Document(
                id=str(uuid4()),
                filename=filename,
                text=extracted.text,
                clauses=clauses,
                page_count=extracted.page_count,
                # Carried on the document itself so the second phase can map
                # citations to pages without a side channel between the calls.
                page_breaks=extracted.page_breaks,
            ),
            findings=[],
            status=AnalysisStatus.PENDING,
            # Extraction and segmentation are already done by the time an id
            # exists, so the first stage the client can observe is the risk pass.
            stage=AnalysisStage.ANALYZING,
            clauses_total=len(clauses),
            clauses_done=0,
        )

        logger.info(
            "analysis_queued",
            extra={
                "analysis_id": analysis.id,
                # Not "filename" — that is a reserved LogRecord attribute and
                # logging raises KeyError rather than shadowing it.
                "source_filename": filename,
                "clause_count": len(clauses),
            },
        )
        return self._repository.add(analysis)

    def run_analysis(self, analysis_id: str, *, judge: bool = True) -> None:
        """Run the model passes, reporting progress as clauses return.

        Called as a background task, so it must not raise: a failure has to end
        up on the stored analysis where the client can read it, not in a request
        that nobody is waiting on.
        """
        analysis = self.get(analysis_id)

        def on_clause_done(done: int, findings_so_far: list[Finding]) -> None:
            # Findings are written as they land, not just the counter, so the
            # progress screen can show them arriving. The stored analysis stays
            # `pending` throughout — a partial list must never be mistaken for
            # a finished review.
            self._repository.add(
                analysis.model_copy(update={"clauses_done": done, "findings": findings_so_far})
            )

        def on_judging() -> None:
            self._repository.add(
                analysis.model_copy(
                    update={
                        "stage": AnalysisStage.JUDGING,
                        "clauses_done": analysis.clauses_total,
                        # Keep whatever the risk pass found; the judge pass only
                        # annotates severities, it never adds or removes.
                        "findings": self.get(analysis_id).findings,
                    }
                )
            )

        try:
            result = analyze_document(
                analysis.document.clauses,
                analysis.document.page_breaks,
                judge=judge,
                on_clause_done=on_clause_done,
                on_judging=on_judging,
            )
        except UpstreamError as error:
            # Every clause failed. That is not an empty result — it is a review
            # that did not happen, and it must not read like a clean bill of
            # health.
            logger.exception("analysis_failed", extra={"analysis_id": analysis_id})
            self._repository.add(
                analysis.model_copy(
                    update={
                        "status": AnalysisStatus.FAILED,
                        "stage": AnalysisStage.DONE,
                        "error": str(error),
                    }
                )
            )
            return

        complete = analysis.model_copy(
            update={
                "findings": result.findings,
                "status": AnalysisStatus.COMPLETE,
                "stage": AnalysisStage.DONE,
                "clauses_done": analysis.clauses_total,
                "dropped_ungrounded": result.dropped,
                "clauses_failed": result.clauses_failed,
                "providers_used": sorted(result.providers_used),
            }
        )
        self._repository.add(complete)

        logger.info(
            "analysis_complete",
            extra={
                "analysis_id": analysis.id,
                "source_filename": analysis.document.filename,
                "clause_count": analysis.clauses_total,
                "finding_count": len(result.findings),
                "dropped_ungrounded": result.dropped,
                "clauses_failed": result.clauses_failed,
                "providers_used": sorted(result.providers_used),
            },
        )

    def get(self, analysis_id: str) -> Analysis:
        analysis = self._repository.get(analysis_id)
        if analysis is None:
            raise NotFoundError(
                f"No analysis with id {analysis_id!r}. Results are kept in memory "
                "and do not survive a restart."
            )
        return analysis
