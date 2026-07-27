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
    return client.post(
        "/analyses/",
        files={"file": (name, data, "application/octet-stream")},
        params=params,
    )


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


def test_upload_returns_findings_with_citations(client: TestClient, stub_llm: Callable[..., None]):
    stub_one_finding(stub_llm)

    response = upload(client, build_docx(CONTRACT))

    assert response.status_code == 200
    body = response.json()
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

    body = upload(client, build_docx(CONTRACT)).json()
    text = body["document"]["text"]

    for finding in body["findings"]:
        citation = finding["citation"]
        assert text[citation["start"] : citation["end"]] == citation["quote"]


def test_clause_spans_index_the_returned_document_text(
    client: TestClient, stub_llm: Callable[..., None]
):
    stub_one_finding(stub_llm)

    body = upload(client, build_docx(CONTRACT)).json()
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

    body = upload(client, build_docx(CONTRACT), judge=False).json()

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

    body = upload(client, build_docx(CONTRACT), judge=False).json()

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
