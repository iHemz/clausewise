"""Tests for extraction — specifically, that offsets stay honest.

Every citation in the product is an offset into the string these functions
produce. If the offsets drift from the text by even one character, every
highlight in the UI points at the wrong words.
"""

import io

import pytest
from docx import Document as DocxDocument

from core.errors import UnprocessableError
from core.extraction import SEPARATOR, _join_with_offsets, extract


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
