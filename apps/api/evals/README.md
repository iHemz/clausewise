# Eval harness

A small hand-labelled set that turns "the output looks good" into a number you can
regress against. Change the rubric or the prompt, re-run, and see whether recall moved.

```bash
cd apps/api
uv run python -m evals.make_samples   # regenerate the .docx from the .txt sources
uv run python -m evals.run            # full pipeline, including the judge pass
uv run python -m evals.run --no-judge # analysis only — roughly half the token spend
```

**This makes real Claude calls and costs real money.** It is deliberately not wired into
CI; run it when you change a prompt, the rubric, or the segmenter.

## What it measures

| Metric | Meaning |
| --- | --- |
| Precision | Of the risks flagged, how many were real |
| Recall | Of the labelled risks, how many were found |
| F1 | The harmonic mean — the single number to watch across prompt changes |
| Severity agreement | How often the analyzer's severity matched the human label |
| Dropped (ungrounded) | Findings discarded because the model could not quote its source |

Scoring matches on **(category, overlapping span)**, not exact spans. Two reviewers rarely
bracket an indemnity identically, and penalising that would measure agreement on
punctuation rather than on risk.

**A non-zero dropped count is the honesty gate working**, not a failure. The model
described something it could not point to, so it was not shown to the user.

## Adding a case

1. Write the contract as `contracts/<name>.txt`. Paragraphs are separated by blank lines.
2. Run `uv run python -m evals.make_samples` to produce the `.docx`.
3. Add an entry to `cases.json`:

```json
{
  "name": "<name>",
  "file": "contracts/<name>.docx",
  "labels": [
    { "category": "indemnity", "quote": "<verbatim text from the contract>", "severity": "high" }
  ]
}
```

`quote` must appear **character-for-character** in the extracted text. The harness fails
loudly on a quote it cannot find, because a label that does not match the document is a
broken label, not a model miss.

`category` must be one of the values in `RiskCategory`
([`domain/contracts.py`](../domain/contracts.py)).

## Honest limitations

- **The contracts are synthetic.** They were written to contain the patterns the rubric
  names. That makes them good for catching a regression and worthless as evidence about
  real-world accuracy — a real eval needs real agreements under NDA.
- **The set is tiny** (2 contracts, 17 labels). Treat the numbers as directional. It is
  enough to catch a prompt change that halves recall, which is what it is for.
- **Labels are one person's reading.** Two lawyers would disagree on some severities.
  Severity agreement is a sanity check, not ground truth.
- **There is no inter-rater baseline**, so there is no ceiling to compare the model
  against.

Fixing the first three is the obvious next step, and it needs real contracts more than it
needs more code.
