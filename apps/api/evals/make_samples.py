"""Generate the sample contract .docx files from their plain-text sources.

The eval set is committed as readable `.txt` so the labels can be reviewed in a
diff, and the `.docx` files the harness actually reads are generated from them:

    cd apps/api && uv run python -m evals.make_samples

Keeping the source as text means a label's `quote` can be checked against the
contract by eye, and a change to a sample shows up as a readable diff rather
than as an opaque binary blob.

These contracts are synthetic. They are written to contain the risk patterns the
rubric names, which makes them useful for regression-testing the pipeline and
useless as evidence about real-world accuracy — a real eval needs real
agreements. Said plainly here so nobody mistakes one for the other.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document

CONTRACTS_DIR = Path(__file__).parent / "contracts"


def build(source: Path) -> Path:
    document = Document()
    for line in source.read_text(encoding="utf-8").split("\n\n"):
        document.add_paragraph(line.strip())

    target = source.with_suffix(".docx")
    document.save(target)
    return target


def main() -> None:
    sources = sorted(CONTRACTS_DIR.glob("*.txt"))
    if not sources:
        raise SystemExit(f"No .txt sources in {CONTRACTS_DIR}")
    for source in sources:
        print(f"wrote {build(source).name}")


if __name__ == "__main__":
    main()
