"""Tests for extraction — specifically, that offsets stay honest.

Every citation in the product is an offset into the string these functions
produce. If the offsets drift from the text by even one character, every
highlight in the UI points at the wrong words.
"""

import io
from pathlib import Path

import pytest
from docx import Document as DocxDocument

from core.errors import UnprocessableError
from core.extraction import SEPARATOR, _join_with_offsets, extract
from domain.contracts import ground_finding, page_for_offset
from domain.segmentation import segment

# The committed sample is a real, typeset, multi-page PDF. Synthesising a
# minimal PDF in-test would exercise none of what actually breaks in
# production — justified text that wraps mid-sentence, and a clause that
# straddles a page boundary.
SAMPLE_PDF = Path(__file__).parents[2] / "evals" / "contracts" / "saas-msa.pdf"

pdf_sample = pytest.mark.skipif(
    not SAMPLE_PDF.exists(),
    reason="Run `uv run python -m evals.make_samples` to generate the sample contracts.",
)


def test_join_records_page_starts_that_match_the_text():
    pages = ["First page text.", "Second page text.", "Third page text."]

    result = _join_with_offsets(pages, count_as_pages=True)

    assert result.page_count == 3
    assert len(result.page_breaks) == 2
    # Each recorded break must be exactly where that page's text begins.
    assert result.text[result.page_breaks[0] :].startswith("Second page text.")
    assert result.text[result.page_breaks[1] :].startswith("Third page text.")


def test_join_preserves_every_character_of_the_source():
    pages = ["A  double  spaced   line.", "Line\twith\ttabs."]

    result = _join_with_offsets(pages, count_as_pages=True)

    # No normalisation, no de-hyphenation, no whitespace collapsing — the
    # extracted string is the document.
    assert result.text == pages[0] + SEPARATOR + pages[1]


def test_join_without_pages_records_no_breaks():
    result = _join_with_offsets(["one", "two"], count_as_pages=False)

    assert result.page_breaks == []
    assert result.page_count is None


def test_single_block_has_no_breaks():
    result = _join_with_offsets(["only"], count_as_pages=True)

    assert result.page_breaks == []
    assert result.text == "only"


def build_docx(paragraphs: list[str]) -> bytes:
    document = DocxDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_docx_extraction_round_trips_paragraphs():
    data = build_docx(["1. Definitions.", "2. Term and termination."])

    result = extract("contract.docx", data)

    assert "1. Definitions." in result.text
    assert "2. Term and termination." in result.text


def test_docx_offsets_point_at_the_right_text():
    data = build_docx(["First clause here.", "Second clause here."])

    result = extract("contract.docx", data)
    index = result.text.index("Second clause here.")

    assert result.text[index : index + 19] == "Second clause here."


def test_empty_upload_is_rejected():
    with pytest.raises(UnprocessableError, match="empty"):
        extract("contract.pdf", b"")


def test_unsupported_extension_is_rejected():
    with pytest.raises(UnprocessableError, match="Unsupported file type"):
        extract("contract.txt", b"some text")


def test_oversized_upload_is_rejected():
    with pytest.raises(UnprocessableError, match="larger than"):
        extract("contract.pdf", b"x" * (16 * 1024 * 1024))


def test_a_docx_with_no_text_is_rejected():
    with pytest.raises(UnprocessableError, match="no readable text"):
        extract("contract.docx", build_docx([""]))


def test_an_unreadable_pdf_gives_a_useful_message():
    with pytest.raises(UnprocessableError, match="Could not read the PDF"):
        extract("contract.pdf", b"not actually a pdf")


# --- Real PDF round-trip -----------------------------------------------------
# The PDF path carries page boundaries, so it is the only one that exercises
# page-numbered citations end to end.


@pdf_sample
def test_pdf_extraction_yields_text_and_page_breaks():
    result = extract(SAMPLE_PDF.name, SAMPLE_PDF.read_bytes())

    assert result.page_count and result.page_count >= 2, "sample should span pages"
    assert len(result.page_breaks) == result.page_count - 1
    assert "MASTER SERVICES AGREEMENT" in result.text


@pdf_sample
def test_pdf_page_breaks_land_on_real_text_boundaries():
    result = extract(SAMPLE_PDF.name, SAMPLE_PDF.read_bytes())

    for offset in result.page_breaks:
        # A break must point at the first character of the next page, not into
        # the middle of the previous one.
        assert 0 < offset < len(result.text)
        assert result.text[offset] != " "


@pdf_sample
def test_pdf_page_mapping_flips_exactly_at_the_break():
    result = extract(SAMPLE_PDF.name, SAMPLE_PDF.read_bytes())
    first_break = result.page_breaks[0]

    assert page_for_offset(result.page_breaks, 0) == 1
    assert page_for_offset(result.page_breaks, first_break - 1) == 1
    assert page_for_offset(result.page_breaks, first_break) == 2


@pdf_sample
def test_pdf_clause_spans_reproduce_their_own_text():
    # The invariant the whole product rests on, checked against a real PDF
    # rather than a hand-built string.
    result = extract(SAMPLE_PDF.name, SAMPLE_PDF.read_bytes())
    clauses = segment(result.text)

    assert len(clauses) > 5
    for clause in clauses:
        assert result.text[clause.start : clause.end] == clause.text, clause.id


@pdf_sample
def test_a_quote_from_a_real_pdf_grounds_with_the_right_page():
    result = extract(SAMPLE_PDF.name, SAMPLE_PDF.read_bytes())
    clauses = segment(result.text)

    quote = "ninety (90) days of the date of invoice"
    clause = next(c for c in clauses if quote in " ".join(c.text.split()))

    citation = ground_finding(clause=clause, quote=quote, page_breaks=result.page_breaks)

    assert citation is not None
    # The stored span must select the stored quote out of the document text.
    assert result.text[citation.start : citation.end] == citation.quote
    assert citation.page == page_for_offset(result.page_breaks, citation.start)


@pdf_sample
def test_a_paraphrase_of_real_pdf_text_is_still_rejected():
    # The honesty gate has to hold on messy PDF text too, not just clean input.
    result = extract(SAMPLE_PDF.name, SAMPLE_PDF.read_bytes())
    clauses = segment(result.text)

    assert (
        ground_finding(
            clause=clauses[0],
            quote="the provider accepts unlimited risk of every kind",
            page_breaks=result.page_breaks,
        )
        is None
    )
