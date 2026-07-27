"""Unit tests for clause segmentation.

The property that matters most is not "the boundaries are pretty" — it is that
every clause's span points at exactly the text the clause claims to contain.
If that invariant holds, every citation derived from it is correct.
"""

from domain.contracts import Clause
from domain.segmentation import MIN_CLAUSE_CHARS, segment

NUMBERED = """\
1. Definitions. In this Agreement the following terms have the meanings set out below, \
and shall be construed accordingly throughout the document.

2. Term. This Agreement commences on the Effective Date and continues for twelve months, \
renewing automatically for successive twelve month periods.

3. Liability. The Supplier's liability under this Agreement shall be unlimited in respect \
of any breach of confidentiality obligations.
"""

HEADINGS = """\
CONFIDENTIALITY

Each party shall keep confidential all information disclosed by the other party and shall \
not disclose it to any third party at any time.

GOVERNING LAW

This Agreement is governed by the laws of Delaware and the parties submit to the exclusive \
jurisdiction of the Delaware courts.
"""

PARAGRAPHS = """\
The parties agree that all intellectual property created in the course of the engagement \
shall vest absolutely in the Client upon creation.

The Consultant shall not, for a period of three years following termination, engage in any \
business which competes with the Client anywhere in the world.
"""


def assert_spans_are_exact(text: str, clauses: list[Clause]) -> None:
    """Every clause's recorded span must reproduce its own text."""
    for clause in clauses:
        assert text[clause.start : clause.end] == clause.text, clause.id


def test_empty_input_yields_no_clauses():
    assert segment("") == []
    assert segment("   \n\n  ") == []


def test_numbered_contract_splits_on_clause_numbers():
    clauses = segment(NUMBERED)
    assert len(clauses) == 3
    assert clauses[0].text.startswith("1. Definitions")
    assert clauses[2].text.startswith("3. Liability")
    assert_spans_are_exact(NUMBERED, clauses)


def test_heading_contract_splits_on_headings():
    clauses = segment(HEADINGS)
    assert len(clauses) >= 2
    assert any("CONFIDENTIALITY" in c.text for c in clauses)
    assert any("GOVERNING LAW" in c.text for c in clauses)
    assert_spans_are_exact(HEADINGS, clauses)


def test_unstructured_text_falls_back_to_paragraphs():
    clauses = segment(PARAGRAPHS)
    assert len(clauses) == 2
    assert_spans_are_exact(PARAGRAPHS, clauses)


def test_short_fragments_are_dropped():
    # Page numbers and stray lines are not clauses worth an LLM call.
    text = "1. A\n\n2. B\n\n" + ("3. This clause is long enough to survive the filter. " * 3)
    clauses = segment(text)
    assert all(len(c.text) >= MIN_CLAUSE_CHARS for c in clauses)


def test_clause_ids_are_sequential_and_unique():
    clauses = segment(NUMBERED)
    assert [c.id for c in clauses] == [f"c{i + 1}" for i in range(len(clauses))]


def test_spans_do_not_start_or_end_on_whitespace():
    for clause in segment(NUMBERED):
        assert clause.text == clause.text.strip()


def test_headings_are_extracted_where_present():
    clauses = segment(HEADINGS)
    assert any(c.heading and "CONFIDENTIALITY" in c.heading for c in clauses)


def test_oversized_blocks_are_split_on_paragraph_edges():
    huge = "\n\n".join("This is a paragraph of contract text. " * 40 for _ in range(12))
    clauses = segment(huge)
    assert len(clauses) > 1
    assert_spans_are_exact(huge, clauses)
