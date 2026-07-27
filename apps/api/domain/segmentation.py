"""Split extracted contract text into clauses, preserving character spans.

Deliberately heuristic and deliberately not an LLM call. Segmentation runs
before any model sees the document, so it must be deterministic — the same
upload has to produce the same clause boundaries every time, or the eval
harness measures noise instead of quality. It is also free, which matters when
the analyzer makes one call per clause.

The strategy is a ladder: numbered clauses if the contract has them (most do),
then heading-style lines, then plain paragraphs. Every branch returns spans
into the original string, never a rewritten copy.
"""

from __future__ import annotations

import re

from domain.contracts import Clause

# "1.", "1.1", "12.3.4", "Section 4", "ARTICLE VII" — the numbering styles that
# actually show up in commercial contracts, anchored to the start of a line.
_NUMBERED = re.compile(
    r"^[ \t]*(?:"
    r"(?:section|article|clause)\s+[0-9IVXLC]+(?:\.[0-9]+)*"
    r"|[0-9]+(?:\.[0-9]+)*"
    r")[.):]?[ \t]+(?=\S)",
    re.IGNORECASE | re.MULTILINE,
)

# A short line in title case or all caps, on its own — the other common way
# contracts mark a clause boundary.
_HEADING = re.compile(
    r"^[ \t]*([A-Z][A-Z \t&/,'-]{3,60}|[A-Z][\w \t&/,'-]{3,60})[ \t]*$", re.MULTILINE
)

# Below this, a "clause" is almost always a stray line — a page number, a
# signature line, a header/footer artefact — not something worth an LLM call.
MIN_CLAUSE_CHARS = 40

# Above this, one clause would dominate its own analysis prompt and the model
# starts summarising rather than flagging. Long blocks get split on paragraphs.
MAX_CLAUSE_CHARS = 6000


def segment(text: str) -> list[Clause]:
    """Split ``text`` into clauses with spans into ``text``.

    Returns an empty list only for empty input; any real document yields at
    least one clause, because the paragraph fallback always produces something.
    """
    if not text.strip():
        return []

    boundaries = _numbered_boundaries(text)
    if len(boundaries) < 2:
        boundaries = _heading_boundaries(text)
    if len(boundaries) < 2:
        boundaries = _paragraph_boundaries(text)

    return _build_clauses(text, boundaries)


def _numbered_boundaries(text: str) -> list[int]:
    return [match.start() for match in _NUMBERED.finditer(text)]


def _heading_boundaries(text: str) -> list[int]:
    return [match.start() for match in _HEADING.finditer(text)]


def _paragraph_boundaries(text: str) -> list[int]:
    """Offsets of each paragraph start, where a blank line separates paragraphs."""
    boundaries = [0]
    for match in re.finditer(r"\n[ \t]*\n", text):
        boundaries.append(match.end())
    return boundaries


def _build_clauses(text: str, boundaries: list[int]) -> list[Clause]:
    """Turn boundary offsets into clauses, dropping fragments and splitting giants."""
    starts = sorted(set(boundaries))
    if not starts or starts[0] != 0:
        starts.insert(0, 0)

    clauses: list[Clause] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        raw = text[start:end]
        if len(raw.strip()) < MIN_CLAUSE_CHARS:
            continue

        for piece_start, piece_end in _split_if_oversized(text, start, end):
            body = text[piece_start:piece_end]
            # Trim surrounding whitespace by moving the span inward rather than
            # by stripping the string, so offsets keep pointing at real
            # characters in the source.
            lead = len(body) - len(body.lstrip())
            trail = len(body) - len(body.rstrip())
            adjusted_start = piece_start + lead
            adjusted_end = piece_end - trail
            if adjusted_end - adjusted_start < MIN_CLAUSE_CHARS:
                continue

            clauses.append(
                Clause(
                    id=f"c{len(clauses) + 1}",
                    heading=_heading_of(text[adjusted_start:adjusted_end]),
                    text=text[adjusted_start:adjusted_end],
                    start=adjusted_start,
                    end=adjusted_end,
                )
            )

    return clauses


def _split_if_oversized(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Break an over-long span on paragraph edges, keeping offsets exact."""
    if end - start <= MAX_CLAUSE_CHARS:
        return [(start, end)]

    cuts = [start]
    for match in re.finditer(r"\n[ \t]*\n", text[start:end]):
        cuts.append(start + match.end())
    cuts.append(end)

    pieces: list[tuple[int, int]] = []
    piece_start = cuts[0]
    for cut in cuts[1:]:
        if cut - piece_start >= MAX_CLAUSE_CHARS or cut == end:
            pieces.append((piece_start, cut))
            piece_start = cut
    return pieces or [(start, end)]


def _heading_of(clause_text: str) -> str | None:
    """The clause's first line, when it reads like a title rather than prose."""
    first_line = clause_text.split("\n", 1)[0].strip()
    if not first_line or len(first_line) > 90:
        return None
    # A line ending in a sentence period is prose, not a heading — unless it is
    # just the clause number ("4.2.").
    if first_line.endswith(".") and not re.fullmatch(r"[\d.\s]+", first_line):
        return None
    return first_line
