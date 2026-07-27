"""Tests for the analysis pipeline with the model stubbed.

The behaviour under test is not "does Claude find the right risks" — that is
what the eval harness measures. It is: **given a model response, does the
pipeline only ever surface findings it can prove?**
"""

from collections.abc import Callable

import pytest

from core.errors import UpstreamError
from domain.contracts import Clause, Severity
from services.analyzer import (
    ClauseAnalysis,
    RawFinding,
    SeverityJudgement,
    analyze_clause,
    analyze_document,
    judge_finding,
)
from tests.conftest import stub_completion

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

    result = analyze_clause(a_clause(start=500), page_breaks=[])

    assert result.dropped == 0
    assert not result.failed
    assert len(result.findings) == 1
    citation = result.findings[0].citation
    # The span is absolute, into the document, not relative to the clause.
    assert citation.start >= 500
    assert citation.quote == "without limitation"


def test_an_ungrounded_finding_is_dropped_not_shown(stub_llm: Callable[..., None]):
    # The model paraphrased instead of quoting. There is nothing to click
    # through to, so the finding must not reach the user.
    stub_llm(analysis=ClauseAnalysis(findings=[raw("the supplier takes unlimited risk")]))

    result = analyze_clause(a_clause(), page_breaks=[])

    assert result.findings == []
    assert result.dropped == 1
    assert not result.failed


def test_grounded_and_ungrounded_findings_are_separated(stub_llm: Callable[..., None]):
    stub_llm(
        analysis=ClauseAnalysis(
            findings=[raw("without limitation"), raw("a fabricated obligation")]
        )
    )

    result = analyze_clause(a_clause(), page_breaks=[])

    assert len(result.findings) == 1
    assert result.dropped == 1


def test_an_empty_analysis_is_a_valid_answer(stub_llm: Callable[..., None]):
    # An unremarkable clause should produce nothing. Manufacturing a finding to
    # look useful is the failure mode this guards.
    stub_llm(analysis=ClauseAnalysis(findings=[]))

    result = analyze_clause(a_clause(), page_breaks=[])

    assert result.findings == []
    assert result.dropped == 0
    assert not result.failed


def test_a_model_failure_is_recorded_not_swallowed(monkeypatch):
    from services import analyzer

    def boom(**_kwargs: object):
        raise RuntimeError("upstream exploded")

    monkeypatch.setattr(analyzer.llm, "parse_meta", boom)

    result = analyze_clause(a_clause(), page_breaks=[])

    # A failure must stay distinguishable from a clean clause, or a broken
    # pipeline reads to the user as "no risks found".
    assert result.findings == []
    assert result.failed


def test_a_document_where_every_clause_fails_raises(monkeypatch):
    from services import analyzer

    def boom(**_kwargs: object):
        raise RuntimeError("no API key")

    monkeypatch.setattr(analyzer.llm, "parse_meta", boom)

    # The worst possible outcome for this product would be returning an empty
    # findings list here: the user would read a clean bill of health from a run
    # in which nothing was actually reviewed.
    with pytest.raises(UpstreamError, match="failed to analyze"):
        analyze_document([a_clause()], page_breaks=[], judge=False)


def test_a_partly_failed_document_still_returns_with_the_count(monkeypatch):
    from services import analyzer

    calls = {"n": 0}

    def flaky(**_kwargs: object):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return stub_completion(ClauseAnalysis(findings=[raw("without limitation")]))

    monkeypatch.setattr(analyzer.llm, "parse_meta", flaky)

    result = analyze_document([a_clause(), a_clause(start=1000)], page_breaks=[], judge=False)

    # Partial failure is survivable, but the count travels with the result so
    # the reader knows the document was only partly reviewed.
    assert result.clauses_failed == 1
    assert len(result.findings) == 1


def test_the_judge_annotates_rather_than_overwrites(stub_llm: Callable[..., None]):
    stub_llm(
        analysis=ClauseAnalysis(findings=[raw("without limitation", Severity.HIGH)]),
        judgement=SeverityJudgement(severity=Severity.MEDIUM, note="Capped elsewhere."),
    )

    judged = judge_finding(analyze_clause(a_clause(), page_breaks=[]).findings[0], CLAUSE_TEXT)

    # Disagreement is information for the reviewer, not something to average away.
    assert judged.severity is Severity.HIGH
    assert judged.judge_severity is Severity.MEDIUM
    assert judged.severity_disputed


def test_the_judge_agreeing_is_not_a_dispute(stub_llm: Callable[..., None]):
    stub_llm(
        analysis=ClauseAnalysis(findings=[raw("without limitation", Severity.HIGH)]),
        judgement=SeverityJudgement(severity=Severity.HIGH, note="Unlimited exposure."),
    )

    findings = analyze_clause(a_clause(), page_breaks=[]).findings
    assert not judge_finding(findings[0], CLAUSE_TEXT).severity_disputed


def test_analyze_document_can_skip_the_judge_pass(stub_llm: Callable[..., None]):
    # No judgement is stubbed, so the stub raises if the judge pass runs.
    stub_llm(analysis=ClauseAnalysis(findings=[raw("without limitation")]))

    result = analyze_document([a_clause()], page_breaks=[], judge=False)

    assert len(result.findings) == 1
    assert result.findings[0].judge_severity is None


def test_analyze_document_returns_highest_severity_first(stub_llm: Callable[..., None]):
    stub_llm(
        analysis=ClauseAnalysis(
            findings=[
                raw("consequential loss", Severity.LOW),
                raw("without limitation", Severity.HIGH),
            ]
        )
    )

    result = analyze_document([a_clause()], page_breaks=[], judge=False)

    assert [f.severity for f in result.findings] == [Severity.HIGH, Severity.LOW]


def test_a_document_with_no_clauses_makes_no_model_calls():
    # No stub installed — a real call would fail, proving none is made.
    result = analyze_document([], page_breaks=[])
    assert result.findings == []
    assert result.clauses_failed == 0


def test_provenance_travels_with_the_result(stub_llm: Callable[..., None]):
    from core.providers import Provider

    stub_llm(
        analysis=ClauseAnalysis(findings=[raw("without limitation")]),
        provider=Provider.XAI,
    )

    result = analyze_document([a_clause()], page_breaks=[], judge=False)

    # Which model produced a finding is part of what the finding is, so it has
    # to survive all the way to the caller rather than living in a log line.
    assert result.providers_used == {"xai"}
