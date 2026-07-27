"""Text extraction from PDF and DOCX, with character offsets preserved.

The whole product rests on this file being honest. Every finding cites a
`(start, end)` span into the string produced here, so if extraction silently
reorders, drops, or rewrites text, every citation downstream points somewhere
wrong — and the tool becomes confidently incorrect, which is worse than useless
for a lawyer.

Two rules, therefore:

1. **Concatenate, never transform.** Pages and paragraphs are joined with a
   known separator and nothing else. No de-hyphenation, no smart quotes, no
   whitespace collapsing. The extracted string *is* the document as far as the
   rest of the system is concerned.
2. **Record page boundaries as offsets** while joining, so a span can be mapped
   back to a page number without a second pass over the file.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pdfplumber
from docx import Document as DocxDocument

from core.errors import UnprocessableError

# Separator between pages/paragraphs. Two newlines is enough for the segmenter
# to see a boundary, and its length is fixed so offset arithmetic stays exact.
SEPARATOR = "\n\n"

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


@dataclass
class ExtractedText:
    """Extraction output: the canonical text plus where each page begins."""

    text: str
    # Offset at which each page after the first starts. `page_breaks[0]` is the
    # start of page 2. Empty for formats without pages (DOCX).
    page_breaks: list[int] = field(default_factory=list)
    page_count: int | None = None


def extract(filename: str, data: bytes) -> ExtractedText:
    """Dispatch on file extension and extract text with offsets."""
    if not data:
        raise UnprocessableError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UnprocessableError(
            f"File is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit."
        )

    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return _extract_pdf(data)
    if lowered.endswith(".docx"):
        return _extract_docx(data)
    raise UnprocessableError(
        f"Unsupported file type: {filename!r}. Upload a .pdf or .docx contract."
    )


def _extract_pdf(data: bytes) -> ExtractedText:
    pages: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
    except UnprocessableError:
        raise
    except Exception as exc:
        raise UnprocessableError(f"Could not read the PDF: {exc}") from exc

    if not any(page.strip() for page in pages):
        raise UnprocessableError(
            "No text could be extracted. This looks like a scanned PDF — "
            "clausewise needs a text-based document, not images of one."
        )

    return _join_with_offsets(pages, count_as_pages=True)


def _extract_docx(data: bytes) -> ExtractedText:
    try:
        document = DocxDocument(io.BytesIO(data))
    except Exception as exc:
        raise UnprocessableError(f"Could not read the DOCX: {exc}") from exc

    # Paragraph text only. Tables are deliberately skipped for the MVP rather
    # than flattened into a misleading linear order — a citation into a
    # mis-ordered table would point at the wrong clause.
    blocks = [paragraph.text for paragraph in document.paragraphs]
    if not any(block.strip() for block in blocks):
        raise UnprocessableError("The DOCX contains no readable text.")

    return _join_with_offsets(blocks, count_as_pages=False)


def _join_with_offsets(blocks: list[str], *, count_as_pages: bool) -> ExtractedText:
    """Join blocks with SEPARATOR, recording where each subsequent one starts.

    Written as an explicit accumulation rather than `SEPARATOR.join(...)` so the
    boundary offsets are derived from the same arithmetic that builds the
    string — the two cannot drift apart.
    """
    parts: list[str] = []
    breaks: list[int] = []
    cursor = 0

    for index, block in enumerate(blocks):
        if index > 0:
            parts.append(SEPARATOR)
            cursor += len(SEPARATOR)
            if count_as_pages:
                breaks.append(cursor)
        parts.append(block)
        cursor += len(block)

    return ExtractedText(
        text="".join(parts),
        page_breaks=breaks,
        page_count=len(blocks) if count_as_pages else None,
    )
