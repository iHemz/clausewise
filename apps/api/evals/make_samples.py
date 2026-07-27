"""Generate the sample contract .docx and .pdf files from their plain-text sources.

The eval set is committed as readable `.txt` so the labels can be reviewed in a
diff, and the binaries the harness and the demo actually read are generated from
them:

    cd apps/api && uv run python -m evals.make_samples

Keeping the source as text means a label's `quote` can be checked against the
contract by eye, and a change to a sample shows up as a readable diff rather
than as an opaque binary blob.

Both formats come from the same source on purpose. PDF and DOCX take different
code paths through `core.extraction`, and PDF is the one that carries page
boundaries — so it is the format that actually exercises page-numbered
citations. A sample that exists only as DOCX leaves that path untested.

These contracts are synthetic. They are written to contain the risk patterns the
rubric names, which makes them useful for regression-testing the pipeline and
useless as evidence about real-world accuracy — a real eval needs real
agreements. Said plainly here so nobody mistakes one for the other.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate

CONTRACTS_DIR = Path(__file__).parent / "contracts"


def paragraphs_of(source: Path) -> list[str]:
    """Blank-line-separated blocks, which is how the sources are written."""
    text = source.read_text(encoding="utf-8")
    return [block.strip() for block in text.split("\n\n") if block.strip()]


def build_docx(source: Path) -> Path:
    document = Document()
    for block in paragraphs_of(source):
        document.add_paragraph(block)

    target = source.with_suffix(".docx")
    document.save(target)
    return target


def build_pdf(source: Path) -> Path:
    """Render the contract as a realistic multi-page PDF.

    Deliberately typeset like a real agreement — justified serif body, a centred
    title, generous margins — rather than as one tidy wall of text. Justified
    text wraps mid-sentence across lines and across pages, which is exactly what
    the whitespace-tolerant quote matching in ``domain.contracts`` exists to
    handle. An unrealistically clean sample would exercise none of it.
    """
    blocks = paragraphs_of(source)
    target = source.with_suffix(".pdf")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ContractTitle",
        parent=styles["Heading1"],
        fontName="Times-Bold",
        fontSize=14,
        leading=18,
        spaceAfter=16,
        alignment=1,  # centred
    )
    body_style = ParagraphStyle(
        "ContractBody",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=10.5,
        leading=15,
        spaceAfter=10,
        alignment=TA_JUSTIFY,
    )

    document = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
        title=source.stem,
        author="Clausewise sample",
    )

    # The first block is the agreement title; everything after it is body text.
    flowables = [
        Paragraph(block, title_style if index == 0 else body_style)
        for index, block in enumerate(blocks)
    ]
    document.build(flowables)
    return target


def main() -> None:
    sources = sorted(CONTRACTS_DIR.glob("*.txt"))
    if not sources:
        raise SystemExit(f"No .txt sources in {CONTRACTS_DIR}")
    for source in sources:
        print(f"wrote {build_docx(source).name}")
        print(f"wrote {build_pdf(source).name}")


if __name__ == "__main__":
    main()
