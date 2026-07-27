"""Tests for the analysis pipeline with the model stubbed.

The behaviour under test is not "does Claude find the right risks" — that is
what the eval harness measures. It is: **given a model response, does the
pipeline only ever surface findings it can prove?**
"""

from collections.abc import Callable

from domain.contracts import Clause, Severity
from services.analyzer import (
    ClauseAnalysis,
    RawFinding,
    SeverityJudgement,
    analyze_clause,
    analyze_document,
    judge_finding,
)

CLAUSE_TEXT = (
    "8.1 Indemnity. The Supplier shall indemnify the Client against any and all losses "
    "without limitation, howsoever arising, including consequential loss."
)


def a_clause(start: int = 0) -> Clause:
    return Clause(
        id="c1",
        heading="8.1 Indemnity",
        text=CLAUSE_TEXT,
        start=start,
        end=start + len(CLAUSE_TEXT),
    )


def raw(quote: str, severity: Severity = Severity.HIGH) -> RawFinding:
    return RawFinding(
        title="Uncapped indemnity",
        category="indemnity",
        severity=severity,
        reason="The indemnity has no cap, so exposure is unlimited.",
        suggested_rewrite="...indemnify the Client up to the fees paid in the prior 12 months.",
        quote=quote,
    )


def test_a_grounded_finding_is_kept_with_a_real_span(stub_llm: Callable[..., None]):
    stub_llm(analysis=ClauseAnalysis(findings=[raw("without limitation")]))

    findings, dropped = analyze_clause(a_clause(start=500), page_breaks=[])

    assert dropped == 0
    assert len(findings) == 1
    citation = findings[0].citation
    # The span is absolute, into the document, not relative to the clause.
    assert citation.start >= 500
    assert citation.quote == "without limitation"


def test_an_ungrounded_finding_is_dropped_not_shown(stub_llm: Callable[..., None]):
    # The model paraphrased instead of quoting. There is nothing to click
    # through to, so the finding must not reach the user.
    stub_llm(analysis=ClauseAnalysis(findings=[raw("the supplier takes unlimited risk")]))

    findings, dropped = analyze_clause(a_clause(), page_breaks=[])

    assert findings == []
    assert dropped == 1


def test_grounded_and_ungrounded_findings_are_separated(stub_llm: Callable[..., None]):
    stub_llm(
        analysis=ClauseAnalysis(
            findings=[raw("without limitation"), raw("a fabricated obligation")]
        )
    )

    findings, dropped = analyze_clause(a_clause(), page_breaks=[])

    assert len(findings) == 1
    assert dropped == 1


def test_an_empty_analysis_is_a_valid_answer(stub_llm: Callable[..., None]):
    # An unremarkable clause should produce nothing. Manufacturing a finding to
    # look useful is the failure mode this guards.
    stub_llm(analysis=ClauseAnalysis(findings=[]))

    findings, dropped = analyze_clause(a_clause(), page_breaks=[])

    assert findings == []
    assert dropped == 0


def test_a_model_failure_costs_one_clause_not_the_document(monkeypatch):
    from services import analyzer

    def boom(**_kwargs: object):
        raise RuntimeError("upstream exploded")

    monkeypatch.setattr(analyzer.llm, "parse", boom)

    findings, dropped = analyze_clause(a_clause(), page_breaks=[])

    assert findings == []
    assert dropped == 0


def test_the_judge_annotates_rather_than_overwrites(stub_llm: Callable[..., None]):
    stub_llm(
        analysis=ClauseAnalysis(findings=[raw("without limitation", Severity.HIGH)]),
        judgement=SeverityJudgement(severity=Severity.MEDIUM, note="Capped elsewhere."),
    )

    findings, _ = analyze_clause(a_clause(), page_breaks=[])
    judged = judge_finding(findings[0], CLAUSE_TEXT)

    # Disagreement is information for the reviewer, not something to average away.
    assert judged.severity is Severity.HIGH
    assert judged.judge_severity is Severity.MEDIUM
    assert judged.severity_disputed


def test_the_judge_agreeing_is_not_a_dispute(stub_llm: Callable[..., None]):
    stub_llm(
        analysis=ClauseAnalysis(findings=[raw("without limitation", Severity.HIGH)]),
        judgement=SeverityJudgement(severity=Severity.HIGH, note="Unlimited exposure."),
    )

    findings, _ = analyze_clause(a_clause(), page_breaks=[])
    assert not judge_finding(findings[0], CLAUSE_TEXT).severity_disputed


def test_analyze_document_can_skip_the_judge_pass(stub_llm: Callable[..., None]):
    # No judgement is stubbed, so the stub raises if the judge pass runs.
    stub_llm(analysis=ClauseAnalysis(findings=[raw("without limitation")]))

    findings, _ = analyze_document([a_clause()], page_breaks=[], judge=False)

    assert len(findings) == 1
    assert findings[0].judge_severity is None


def test_analyze_document_returns_highest_severity_first(stub_llm: Callable[..., None]):
    stub_llm(
        analysis=ClauseAnalysis(
            findings=[
                raw("consequential loss", Severity.LOW),
                raw("without limitation", Severity.HIGH),
            ]
        )
    )

    findings, _ = analyze_document([a_clause()], page_breaks=[], judge=False)

    assert [f.severity for f in findings] == [Severity.HIGH, Severity.LOW]


def test_a_document_with_no_clauses_makes_no_model_calls():
    # No stub installed — a real call would fail, proving none is made.
    assert analyze_document([], page_breaks=[]) == ([], 0)
