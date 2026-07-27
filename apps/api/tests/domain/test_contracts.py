"""Unit tests for the grounding logic — the rules that decide what is honest.

No fixtures, no I/O, no model. If these pass, a finding shown in the UI provably
points at real text in the uploaded document.
"""

from domain.contracts import (
    Citation,
    Clause,
    Finding,
    RiskCategory,
    Severity,
    find_quote_span,
    ground_finding,
    normalize,
    page_for_offset,
    severity_counts,
    sort_findings,
)

CLAUSE_TEXT = (
    "8.1 Indemnity. The Supplier shall indemnify the Client against any and all "
    "losses without limitation, howsoever arising."
)


def clause(text: str = CLAUSE_TEXT, start: int = 100) -> Clause:
    return Clause(id="c1", heading=None, text=text, start=start, end=start + len(text))


def test_normalize_collapses_whitespace():
    assert normalize("a  \n b\tc ") == "a b c"


def test_find_quote_span_matches_verbatim_text():
    span = find_quote_span(CLAUSE_TEXT, "without limitation")
    assert span is not None
    start, end = span
    assert CLAUSE_TEXT[start:end] == "without limitation"


def test_find_quote_span_tolerates_line_wrapping():
    # PDF extraction wraps mid-sentence constantly; a quote that differs only
    # by whitespace is the same quote.
    wrapped = "The Supplier shall\nindemnify the Client"
    span = find_quote_span(wrapped, "The Supplier shall indemnify the Client")
    assert span is not None
    start, end = span
    assert normalize(wrapped[start:end]) == "The Supplier shall indemnify the Client"


def test_find_quote_span_applies_the_offset():
    span = find_quote_span(CLAUSE_TEXT, "Indemnity", offset=500)
    assert span is not None
    assert span[0] >= 500


def test_find_quote_span_returns_none_for_paraphrase():
    assert find_quote_span(CLAUSE_TEXT, "the supplier accepts unlimited risk") is None


def test_find_quote_span_returns_none_for_empty_quote():
    assert find_quote_span(CLAUSE_TEXT, "   ") is None


def test_ground_finding_returns_absolute_offsets_into_the_document():
    citation = ground_finding(clause=clause(), quote="without limitation", page_breaks=[])
    assert citation is not None
    # Offsets are into the whole document, so they include the clause's start.
    assert citation.start >= 100
    assert citation.quote == "without limitation"


def test_ground_finding_stores_the_source_text_not_the_models_rendering():
    # The model reformatted the whitespace; the citation must carry what the
    # document actually says, not what the model typed.
    wrapped = "The Supplier shall\nindemnify the Client fully and completely here."
    citation = ground_finding(
        clause=clause(wrapped, start=0),
        quote="The Supplier shall indemnify the Client",
        page_breaks=[],
    )
    assert citation is not None
    assert "\n" in citation.quote


def test_ground_finding_rejects_a_quote_that_is_not_in_the_clause():
    # This is the honesty gate: no span, no finding.
    assert ground_finding(clause=clause(), quote="a fabricated obligation", page_breaks=[]) is None


def test_page_for_offset_maps_spans_to_pages():
    breaks = [1000, 2000]
    assert page_for_offset(breaks, 0) == 1
    assert page_for_offset(breaks, 999) == 1
    assert page_for_offset(breaks, 1000) == 2
    assert page_for_offset(breaks, 2500) == 3


def test_page_for_offset_is_none_without_page_information():
    assert page_for_offset([], 42) is None


def _finding(severity: Severity, start: int) -> Finding:
    return Finding(
        clause_id="c1",
        title="Uncapped indemnity",
        category=RiskCategory.INDEMNITY,
        severity=severity,
        reason="Liability is not capped.",
        suggested_rewrite="Cap liability at fees paid in the prior 12 months.",
        citation=Citation(start=start, end=start + 10, quote="some text"),
    )


def test_sort_findings_puts_high_severity_first_then_document_order():
    findings = [
        _finding(Severity.LOW, 10),
        _finding(Severity.HIGH, 900),
        _finding(Severity.MEDIUM, 50),
        _finding(Severity.HIGH, 100),
    ]
    ordered = sort_findings(findings)
    assert [f.severity for f in ordered] == [
        Severity.HIGH,
        Severity.HIGH,
        Severity.MEDIUM,
        Severity.LOW,
    ]
    assert ordered[0].citation.start == 100  # earlier in the document wins the tie


def test_severity_counts_covers_every_level():
    counts = severity_counts([_finding(Severity.HIGH, 0), _finding(Severity.HIGH, 5)])
    assert counts[Severity.HIGH] == 2
    assert counts[Severity.MEDIUM] == 0
    assert counts[Severity.LOW] == 0


def test_severity_disputed_flags_judge_disagreement():
    finding = _finding(Severity.HIGH, 0)
    assert not finding.severity_disputed
    assert finding.model_copy(update={"judge_severity": Severity.LOW}).severity_disputed
    assert not finding.model_copy(update={"judge_severity": Severity.HIGH}).severity_disputed
