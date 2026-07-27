"""The contract domain: documents, clauses, findings, and their citations.

Pure models and pure functions — no I/O, no framework, no Claude. Everything
here is testable without a fixture, which is the point: the rules that decide
whether a finding is trustworthy should be the easiest thing in the codebase to
verify.

The load-bearing idea is the **citation**. A finding without a real character
span pointing back into the extracted text is unverifiable, and an unverifiable
finding is worse than no finding — a lawyer cannot check it, so they must either
trust it blindly or ignore the tool. Every finding carries a span, and
:func:`ground_finding` is what enforces that.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RiskCategory(StrEnum):
    """The fixed rubric the analyzer scores against.

    A closed set, not free text: it makes findings comparable across contracts,
    keeps the model from inventing a new category per document, and lets the
    eval harness measure precision and recall per category.
    """

    UNLIMITED_LIABILITY = "unlimited_liability"
    AUTO_RENEWAL = "auto_renewal"
    UNILATERAL_TERMINATION = "unilateral_termination"
    IP_ASSIGNMENT = "ip_assignment"
    NON_COMPETE = "non_compete"
    INDEMNITY = "indemnity"
    GOVERNING_LAW = "governing_law"
    PAYMENT_TERMS = "payment_terms"
    CONFIDENTIALITY = "confidentiality"
    LIMITATION_OF_LIABILITY = "limitation_of_liability"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.HIGH: 0,
    Severity.MEDIUM: 1,
    Severity.LOW: 2,
}


class Citation(BaseModel):
    """A character span in the extracted document text, plus where it appeared.

    Offsets are into `Document.text` — the single canonical string the whole
    pipeline shares — so the frontend can highlight the exact source without
    re-deriving anything.
    """

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    page: int | None = Field(default=None, ge=1)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def _end_after_start(self) -> Citation:
        if self.end <= self.start:
            raise ValueError("Citation end must be greater than start.")
        return self


class Clause(BaseModel):
    """One segmented section of the contract, with its span preserved."""

    id: str
    heading: str | None
    text: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    page: int | None = Field(default=None, ge=1)


class Finding(BaseModel):
    """One risk identified in one clause, grounded in a real citation."""

    clause_id: str
    title: str = Field(min_length=1, max_length=120)
    category: RiskCategory
    severity: Severity
    reason: str = Field(min_length=1, max_length=400)
    suggested_rewrite: str = Field(min_length=1)
    citation: Citation
    # Populated only when the independent judge pass runs. Kept separate from
    # `severity` so the UI can show that a second model agreed or disagreed
    # rather than silently overwriting the first model's call.
    judge_severity: Severity | None = None
    judge_note: str | None = None

    @property
    def severity_disputed(self) -> bool:
        """Whether the judge disagreed with the analyzer's severity."""
        return self.judge_severity is not None and self.judge_severity != self.severity


class Document(BaseModel):
    """An uploaded contract after extraction and segmentation."""

    id: str
    filename: str
    text: str
    clauses: list[Clause]
    page_count: int | None = None


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class Analysis(BaseModel):
    """A document plus everything the pipeline concluded about it."""

    id: str
    document: Document
    findings: list[Finding]
    status: AnalysisStatus = AnalysisStatus.COMPLETE
    # Findings the model produced but that failed grounding. Surfaced rather
    # than hidden — an honest tool shows what it threw away and why.
    dropped_ungrounded: int = 0
    # Clauses whose analysis call failed outright. Non-zero means the document
    # was only partly reviewed, which the reader must know before trusting a
    # short findings list.
    clauses_failed: int = 0
    error: str | None = None


# --- Pure logic ------------------------------------------------------------

# Collapse any run of whitespace so a quote that differs from the source only
# by line wrapping still matches. PDF extraction inserts newlines mid-sentence
# constantly, so an exact-match-only rule would drop most valid citations.
_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def find_quote_span(haystack: str, quote: str, *, offset: int = 0) -> tuple[int, int] | None:
    """Locate ``quote`` inside ``haystack``, tolerating whitespace differences.

    Returns absolute ``(start, end)`` offsets — ``offset`` is added to both, so
    a caller searching within a single clause gets coordinates into the whole
    document. Returns ``None`` when the quote genuinely is not present, which is
    the signal that the model paraphrased instead of quoting.
    """
    if not quote.strip():
        return None

    # Fast path: the quote appears verbatim.
    exact = haystack.find(quote)
    if exact != -1:
        return offset + exact, offset + exact + len(quote)

    # Slow path: match on normalized text, then map back to raw offsets. Build
    # an index from each normalized position to its position in the original so
    # the returned span still points at real characters in the source.
    raw_positions: list[int] = []
    normalized_chars: list[str] = []
    previous_was_space = False
    for index, char in enumerate(haystack):
        if char.isspace():
            if previous_was_space or not normalized_chars:
                continue
            normalized_chars.append(" ")
            raw_positions.append(index)
            previous_was_space = True
        else:
            normalized_chars.append(char)
            raw_positions.append(index)
            previous_was_space = False

    normalized_haystack = "".join(normalized_chars).strip()
    # `.strip()` may have removed a leading space; re-align the index if so.
    leading = len("".join(normalized_chars)) - len("".join(normalized_chars).lstrip())
    raw_positions = raw_positions[leading:]

    normalized_quote = normalize(quote)
    match = normalized_haystack.find(normalized_quote)
    if match == -1 or not normalized_quote:
        return None

    start_raw = raw_positions[match]
    last_index = match + len(normalized_quote) - 1
    if last_index >= len(raw_positions):
        return None
    end_raw = raw_positions[last_index] + 1
    return offset + start_raw, offset + end_raw


def page_for_offset(page_breaks: list[int], offset: int) -> int | None:
    """Which 1-indexed page ``offset`` falls on.

    ``page_breaks[i]`` is the offset at which page ``i + 2`` starts, so the page
    number is one more than the count of breaks at or below the offset.
    """
    if not page_breaks:
        return None
    page = 1
    for break_offset in page_breaks:
        if offset >= break_offset:
            page += 1
        else:
            break
    return page


def ground_finding(
    *,
    clause: Clause,
    quote: str,
    page_breaks: list[int],
) -> Citation | None:
    """Turn a model-supplied quote into a verified citation, or reject it.

    This is the honesty gate. The model is asked to quote the exact text it is
    flagging; if that text cannot be located in the clause it claims to have
    read, the finding is dropped rather than shown with an approximate or
    fabricated span. A citation the reader cannot click through to is not a
    citation.
    """
    span = find_quote_span(clause.text, quote, offset=clause.start)
    if span is None:
        return None

    start, end = span
    return Citation(
        start=start,
        end=end,
        page=page_for_offset(page_breaks, start),
        # Store the source text, not the model's rendering of it — that way the
        # quote shown in the UI is provably what the document says.
        quote=clause.text[start - clause.start : end - clause.start],
    )


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Highest severity first, then document order.

    A reviewer reads top-down, so the ordering is the product: the clause most
    likely to cost them money should be the first thing they see.
    """
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_ORDER[f.severity], f.citation.start),
    )


def severity_counts(findings: list[Finding]) -> dict[Severity, int]:
    counts = dict.fromkeys(Severity, 0)
    for finding in findings:
        counts[finding.severity] += 1
    return counts


SegmentKind = Literal["numbered", "heading", "paragraph"]
