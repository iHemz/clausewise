"""Eval harness: measure precision and recall against hand-labelled contracts.

Run it deliberately, not in CI — it makes real Claude calls and costs real
money:

    cd apps/api && uv run python -m evals.run
    cd apps/api && uv run python -m evals.run --no-judge   # skip the judge pass

Why this exists. "The output looks good" is not a claim you can defend in a
conversation with a legal-AI team, and it is not a claim you can regress
against. A small labelled set turns prompt changes from vibes into numbers:
change the rubric, re-run, see whether recall moved.

Scoring is per (clause, category). A finding counts as a true positive when the
model flags a category on a clause whose text overlaps the labelled span. That
is deliberately looser than exact-span matching — two reviewers rarely bracket
an indemnity identically, and penalising that would measure agreement on
punctuation rather than on risk.

The set is small and hand-labelled, so treat the numbers as directional. It is
enough to catch a prompt change that halves recall, which is what it is for.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from domain.contracts import Finding
from domain.segmentation import segment
from services.analyzer import analyze_document

EVAL_DIR = Path(__file__).parent
CASES_FILE = EVAL_DIR / "cases.json"


@dataclass
class Label:
    """One risk a human marked in a contract."""

    category: str
    quote: str
    severity: str


@dataclass
class Case:
    name: str
    path: Path
    labels: list[Label]


@dataclass
class Score:
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    dropped_ungrounded: int = 0
    #: Clauses whose analysis call failed outright. Non-zero means the run was
    #: degraded and the scores below understate real recall.
    clauses_failed: int = 0
    severity_agreements: int = 0
    severity_comparisons: int = 0

    @property
    def precision(self) -> float:
        predicted = self.true_positives + self.false_positives
        return self.true_positives / predicted if predicted else 0.0

    @property
    def recall(self) -> float:
        actual = self.true_positives + self.false_negatives
        return self.true_positives / actual if actual else 0.0

    @property
    def f1(self) -> float:
        if not (self.precision and self.recall):
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)

    @property
    def judge_agreement(self) -> float:
        if not self.severity_comparisons:
            return 0.0
        return self.severity_agreements / self.severity_comparisons

    @property
    def severity_agreement_report(self) -> str:
        if not self.severity_comparisons:
            return "n/a"
        return (
            f"{self.judge_agreement:.0%} ({self.severity_agreements}/{self.severity_comparisons})"
        )


def load_cases() -> list[Case]:
    if not CASES_FILE.exists():
        raise SystemExit(f"No eval cases at {CASES_FILE}. See evals/README.md for the format.")
    raw = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    return [
        Case(
            name=entry["name"],
            path=EVAL_DIR / entry["file"],
            labels=[Label(**label) for label in entry["labels"]],
        )
        for entry in raw
    ]


def spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def score_case(case: Case, text: str, findings: list[Finding], dropped: int) -> Score:
    """Match findings against labels on (category, overlapping span)."""
    score = Score(dropped_ungrounded=dropped)

    # Resolve each label's quote to a span in the extracted text. A label whose
    # quote cannot be found means the label is wrong, not the model — fail loudly
    # rather than silently counting it as a miss.
    label_spans: list[tuple[Label, tuple[int, int]]] = []
    for label in case.labels:
        index = text.find(label.quote)
        if index == -1:
            raise SystemExit(
                f"[{case.name}] labelled quote not found in the extracted text — "
                f"fix the label: {label.quote[:80]!r}"
            )
        label_spans.append((label, (index, index + len(label.quote))))

    matched_labels: set[int] = set()
    for finding in findings:
        finding_span = (finding.citation.start, finding.citation.end)
        hit = next(
            (
                i
                for i, (label, span) in enumerate(label_spans)
                if i not in matched_labels
                and label.category == finding.category.value
                and spans_overlap(finding_span, span)
            ),
            None,
        )
        if hit is None:
            score.false_positives += 1
            continue

        matched_labels.add(hit)
        score.true_positives += 1

        expected_severity = label_spans[hit][0].severity
        score.severity_comparisons += 1
        if finding.severity.value == expected_severity:
            score.severity_agreements += 1

    score.false_negatives = len(label_spans) - len(matched_labels)
    return score


def run(*, judge: bool) -> int:
    from core.extraction import extract  # imported late so --help works without deps

    cases = load_cases()
    total = Score()
    rows: list[tuple[str, Score]] = []

    for case in cases:
        if not case.path.exists():
            raise SystemExit(f"[{case.name}] missing contract file: {case.path}")

        extracted = extract(case.path.name, case.path.read_bytes())
        clauses = segment(extracted.text)
        analysis = analyze_document(clauses, extracted.page_breaks, judge=judge)

        score = score_case(case, extracted.text, analysis.findings, analysis.dropped)
        score.clauses_failed = analysis.clauses_failed
        rows.append((case.name, score))

        total.true_positives += score.true_positives
        total.false_positives += score.false_positives
        total.false_negatives += score.false_negatives
        total.dropped_ungrounded += score.dropped_ungrounded
        total.clauses_failed += score.clauses_failed
        total.severity_agreements += score.severity_agreements
        total.severity_comparisons += score.severity_comparisons

    print(f"\n{'case':<28} {'P':>6} {'R':>6} {'F1':>6} {'TP':>4} {'FP':>4} {'FN':>4}")
    print("-" * 62)
    for name, score in rows:
        print(
            f"{name[:28]:<28} {score.precision:>6.2f} {score.recall:>6.2f} "
            f"{score.f1:>6.2f} {score.true_positives:>4} "
            f"{score.false_positives:>4} {score.false_negatives:>4}"
        )
    print("-" * 62)
    print(
        f"{'TOTAL':<28} {total.precision:>6.2f} {total.recall:>6.2f} "
        f"{total.f1:>6.2f} {total.true_positives:>4} "
        f"{total.false_positives:>4} {total.false_negatives:>4}"
    )
    print(f"\nSeverity agreement with labels: {total.severity_agreement_report}")
    print(f"Findings dropped as ungrounded:  {total.dropped_ungrounded}")
    if total.clauses_failed:
        print(
            f"\n!! {total.clauses_failed} clause(s) failed to analyze — this run was "
            "degraded and the scores above understate real recall. Re-run before "
            "drawing any conclusion from them."
        )
    print(
        "\nDropped findings are the honesty gate working: the model described "
        "something it could not quote, so it was not shown."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip the independent severity pass (halves token spend).",
    )
    args = parser.parse_args()
    return run(judge=not args.no_judge)


if __name__ == "__main__":
    sys.exit(main())
