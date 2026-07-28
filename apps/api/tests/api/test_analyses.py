"""Assembly tests — the route, service, extraction, segmentation, and repository
wired together, with only the model stubbed.

These prove the layers connect and that domain errors surface as the right HTTP
status.
"""

import io
from collections.abc import Callable

from docx import Document as DocxDocument
from fastapi.testclient import TestClient

from domain.contracts import Severity
from services.analyzer import ClauseAnalysis, RawFinding, SeverityJudgement

CONTRACT = [
    "1. Definitions. In this Agreement the following capitalised terms carry the "
    "meanings given to them in this clause.",
    "2. Liability. The Supplier shall indemnify the Client against any and all losses "
    "without limitation, howsoever arising.",
]


def build_docx(paragraphs: list[str]) -> bytes:
    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def upload(client: TestClient, data: bytes, name: str = "contract.docx", **params):
    """Start an analysis. Returns the 202 response with the pending analysis."""
    return client.post(
        "/analyses/",
        files={"file": (name, data, "application/octet-stream")},
        params=params,
    )


def analyze(client: TestClient, data: bytes, name: str = "contract.docx", **params) -> dict:
    """Run the full two-phase flow and return the finished analysis.

    TestClient runs background tasks after the response is sent, so by the time
    the POST returns the model passes have already been driven to completion —
    the GET below is the same call the browser makes when polling, without the
    wait.
    """
    started = upload(client, data, name, **params)
    assert started.status_code == 202, started.text
    return client.get(f"/analyses/{started.json()['id']}").json()


def stub_one_finding(stub_llm: Callable[..., None]) -> None:
    stub_llm(
        analysis=ClauseAnalysis(
            findings=[
                RawFinding(
                    title="Uncapped indemnity",
                    category="indemnity",
                    severity=Severity.HIGH,
                    reason="The indemnity has no cap, so exposure is unlimited.",
                    suggested_rewrite="...up to the fees paid in the prior 12 months.",
                    quote="without limitation",
                )
            ]
        ),
        judgement=SeverityJudgement(severity=Severity.HIGH, note="Unlimited exposure."),
    )


def test_health_reports_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_the_upload_is_accepted_before_the_review_runs(
    client: TestClient, stub_llm: Callable[..., None]
):
    # 202, not 200: the review has been accepted, not completed. The response
    # already carries the text and clause count so the UI can show the document
    # and a real denominator while the model passes run.
    stub_one_finding(stub_llm)

    response = upload(client, build_docx(CONTRACT))

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["stage"] == "analyzing"
    assert body["findings"] == []
    assert body["clauses_total"] > 0
    assert body["clauses_done"] == 0
    assert body["document"]["text"], "the text must be readable during the wait"


def test_page_breaks_are_not_exposed_in_the_response(
    client: TestClient, stub_llm: Callable[..., None]
):
    # Derived data the client never reads; every page is already on the
    # citations that need one.
    stub_one_finding(stub_llm)

    body = upload(client, build_docx(CONTRACT)).json()

    assert "page_breaks" not in body["document"]


def test_the_finished_review_carries_findings_with_citations(
    client: TestClient, stub_llm: Callable[..., None]
):
    stub_one_finding(stub_llm)

    body = analyze(client, build_docx(CONTRACT))

    assert body["status"] == "complete"
    assert body["stage"] == "done"
    assert body["clauses_done"] == body["clauses_total"]
    assert body["findings"], "expected at least one finding"

    finding = body["findings"][0]
    assert finding["severity"] == "high"
    assert finding["judge_severity"] == "high"
    assert finding["citation"]["quote"] == "without limitation"


def test_citation_offsets_index_the_returned_document_text(
    client: TestClient, stub_llm: Callable[..., None]
):
    # The contract that the whole product depends on: the span the API returns
    # must select the quote from the text the API returned alongside it.
    stub_one_finding(stub_llm)

    body = analyze(client, build_docx(CONTRACT))
    text = body["document"]["text"]

    assert body["findings"], "the invariant is vacuous with no findings"
    for finding in body["findings"]:
        citation = finding["citation"]
        assert text[citation["start"] : citation["end"]] == citation["quote"]


def test_clause_spans_index_the_returned_document_text(
    client: TestClient, stub_llm: Callable[..., None]
):
    stub_one_finding(stub_llm)

    body = analyze(client, build_docx(CONTRACT))
    text = body["document"]["text"]

    for clause in body["document"]["clauses"]:
        assert text[clause["start"] : clause["end"]] == clause["text"]


def test_ungrounded_findings_are_reported_as_dropped(
    client: TestClient, stub_llm: Callable[..., None]
):
    stub_llm(
        analysis=ClauseAnalysis(
            findings=[
                RawFinding(
                    title="Invented risk",
                    category="indemnity",
                    severity=Severity.HIGH,
                    reason="Paraphrased rather than quoted.",
                    suggested_rewrite="Cap the indemnity.",
                    quote="this sentence is nowhere in the contract",
                )
            ]
        ),
    )

    body = analyze(client, build_docx(CONTRACT), judge=False)

    assert body["findings"] == []
    assert body["dropped_ungrounded"] > 0


def test_the_judge_pass_can_be_disabled(client: TestClient, stub_llm: Callable[..., None]):
    # No judgement stubbed — the stub raises if the judge pass runs.
    stub_llm(
        analysis=ClauseAnalysis(
            findings=[
                RawFinding(
                    title="Uncapped indemnity",
                    category="indemnity",
                    severity=Severity.HIGH,
                    reason="No cap.",
                    suggested_rewrite="Cap it.",
                    quote="without limitation",
                )
            ]
        )
    )

    body = analyze(client, build_docx(CONTRACT), judge=False)

    assert body["findings"][0]["judge_severity"] is None


def test_a_result_can_be_fetched_again_by_id(client: TestClient, stub_llm: Callable[..., None]):
    stub_one_finding(stub_llm)

    analysis_id = upload(client, build_docx(CONTRACT)).json()["id"]
    fetched = client.get(f"/analyses/{analysis_id}")

    assert fetched.status_code == 200
    assert fetched.json()["id"] == analysis_id


def test_an_unknown_id_returns_404(client: TestClient):
    assert client.get("/analyses/does-not-exist").status_code == 404


def test_an_unsupported_file_type_returns_422(client: TestClient):
    response = upload(client, b"plain text", name="contract.txt")
    assert response.status_code == 422
    assert "Unsupported file type" in response.json()["detail"]


def test_an_empty_file_returns_422(client: TestClient):
    assert upload(client, b"", name="contract.pdf").status_code == 422


def test_a_document_with_no_clauses_returns_422(client: TestClient):
    # Too short to segment into anything meaningful.
    assert upload(client, build_docx(["Hi."])).status_code == 422


# --- The progress signal ----------------------------------------------------
# The progress screen names the step it is on and counts clauses as they land.
# Every number it shows comes from here, so if these drift the UI starts
# reporting a review that isn't happening.


def test_progress_is_written_back_as_clauses_land(
    client: TestClient, stub_llm: Callable[..., None], analyses_repository
):
    stub_one_finding(stub_llm)

    body = analyze(client, build_docx(CONTRACT))

    stored = analyses_repository.get(body["id"])
    assert stored is not None
    # The denominator is the real clause count, and the numerator reaches it —
    # a counter that stops short would leave the UI stuck mid-review forever.
    assert stored.clauses_total == len(stored.document.clauses)
    assert stored.clauses_done == stored.clauses_total
    assert stored.stage.value == "done"


def test_a_failed_review_ends_as_failed_rather_than_empty(
    client: TestClient, monkeypatch, analyses_repository
):
    from services import analyzer

    def boom(**_kwargs: object):
        raise RuntimeError("no provider")

    monkeypatch.setattr(analyzer.llm, "parse_meta", boom)

    body = analyze(client, build_docx(CONTRACT), judge=False)

    # The background task cannot raise into a request nobody is waiting on, so
    # the failure has to land on the stored analysis instead. Reading "complete"
    # with zero findings here would be the worst outcome the product has.
    assert body["status"] == "failed"
    assert body["stage"] == "done"
    assert body["findings"] == []
    assert body["error"]


def test_the_document_is_readable_before_any_model_call(
    client: TestClient, stub_llm: Callable[..., None]
):
    # The point of splitting the upload: the minute of waiting is spent on
    # something, because the extracted contract is already on the 202.
    stub_one_finding(stub_llm)

    body = upload(client, build_docx(CONTRACT)).json()

    text = body["document"]["text"]
    assert "Definitions" in text
    for clause in body["document"]["clauses"]:
        assert text[clause["start"] : clause["end"]] == clause["text"]
