# Clausewise

Upload a contract. Get back every risky clause flagged with a severity, a plain-English
reason, a suggested rewrite, and a **citation pointing at the exact source text** — click
any finding and the contract pane scrolls to and highlights the words it came from.

> Not legal advice. This is a demonstration of grounded document AI, and every finding is
> designed to be checked rather than trusted — which is what the citations are for.

## The idea worth stealing

Most LLM document tools fail the same way: the model says something plausible about a
document and the user has no cheap way to check it. Clausewise makes checking the default.

**Every finding must carry a real character span into the extracted text. If the model
cannot quote what it is flagging, the finding is dropped rather than shown with an
approximate source.** The UI reports the drop count, so you can see what was discarded.

That rule costs recall. It buys the only thing that makes the tool usable by someone whose
professional liability is on the line.

## How it works

```
upload (PDF/DOCX)
  → extract text, preserving character offsets and page boundaries
  → segment into clauses (numbering → headings → paragraphs), spans preserved
  → per clause: one Claude call, schema-constrained, against a fixed risk rubric
  → ground each finding: locate its quote in the clause, or drop it
  → judge pass: a second, independent Claude call re-scores severity
  → render: contract on the left, findings on the right, click to highlight
```

Three decisions carry most of the weight:

**Schema-first, not prose-parsing.** Findings come back through the Anthropic API's
structured-output enforcement against a Pydantic schema
([`services/analyzer.py`](apps/api/services/analyzer.py)). There is no fence-stripping, no
brace-trimming, and no "the model added a sentence after the JSON" repair path — the
failure mode collapses to a plain validation error.

**Grounding is a gate, not a garnish.** `ground_finding` in
[`domain/contracts.py`](apps/api/domain/contracts.py) locates the model's quote in the
clause it claims to have read, tolerating whitespace differences from PDF line-wrapping but
nothing else. No span, no finding. The citation stores the *source* text, not the model's
rendering of it.

**Severity gets a second opinion.** Severity decides what a reviewer reads first, so one
model's guess is a weak input to that ordering. A separate call re-scores each finding from
the clause alone, without seeing the first model's reasoning. Disagreement is **shown**, not
averaged away — a disputed finding is flagged in the UI.

## Running it

Prerequisites: Node 24+, [pnpm](https://pnpm.io), [uv](https://docs.astral.sh/uv/), and an
Anthropic API key.

```bash
pnpm install

cp apps/api/.env.example apps/api/.env      # add ANTHROPIC_API_KEY
cp apps/web/.env.local.example apps/web/.env.local

# Terminal 1 — API on :8000
cd apps/api && uv sync && uv run uvicorn main:app --reload

# Terminal 2 — web on :3000
pnpm --filter web dev
```

Open http://localhost:3000 and drop in a contract. Ready-made samples live in
[`apps/api/evals/contracts/`](apps/api/evals/contracts/) — each one as `.pdf` and `.docx`:

- **`saas-msa.pdf`** — 2 pages, 13 clauses, 10 risk categories. The one to demo with:
  it spans a page break, so findings come back with real page numbers.
- **`contractor-agreement.pdf`** — 1 page. Overbroad IP assignment, a five-year worldwide
  non-compete, an uncapped indemnity.

Both are generated from the `.txt` sources next to them via
`uv run python -m evals.make_samples`, so the text is reviewable in a diff rather than
locked in a binary.

## Evals

A small hand-labelled set that turns "the output looks good" into a number you can regress
against:

```bash
cd apps/api && uv run python -m evals.run
```

It reports precision, recall, F1, severity agreement, and how many findings were dropped as
ungrounded. It makes real Claude calls, so it is deliberately not wired into CI.

Latest run against `claude-opus-5`:

| case                 |    P |    R |   F1 | TP | FP | FN |
| -------------------- | ---: | ---: | ---: | -: | -: | -: |
| saas-msa             | 0.67 | 0.91 | 0.77 | 10 |  5 |  1 |
| contractor-agreement | 0.75 | 1.00 | 0.86 |  6 |  2 |  0 |
| **total**            | 0.70 | 0.94 | 0.80 | 16 |  7 |  1 |

Severity agreement with the human labels: 75% (12/16). Findings dropped as ungrounded: 0.

Read that honestly. Recall is high because the samples were written to contain these
patterns. The 7 false positives are mostly real risks I did not bother to label rather
than hallucinations — which is exactly the ambiguity a two-contract set cannot resolve,
and the reason the numbers are directional rather than a claim.

The contracts are synthetic and the set is tiny (2 contracts, 17 labels) — enough to catch
a prompt change that halves recall, not evidence about real-world accuracy. That limitation
is stated plainly in [`apps/api/evals/README.md`](apps/api/evals/README.md) rather than
buried.

## Architecture

Next.js 16 frontend, FastAPI backend, one-directional layering:

```
apps/web/
  app/                 Server components — routing and composition only
  components/analysis/ Uploader, ContractView (highlighting), FindingCard, AnalysisView
  lib/                 api.ts (the only fetch), queries/, highlight.ts (pure, tested)
apps/api/
  api/routes/          Thin HTTP surface; no business rules, no try/except
  services/            analyzer.py (the two model passes), contracts.py (the use-case)
  domain/              contracts.py (grounding), segmentation.py — pure, no I/O
  repositories/        Storage behind a Protocol
  core/                config, errors, logging, llm, extraction
  evals/               The labelled set and the harness
```

Storage is in-memory: results survive the process, not a restart. The `Protocol` in
[`repositories/analyses.py`](apps/api/repositories/analyses.py) is the seam — moving to
Postgres is one new class and one line in `api/deps.py`.

## Quality gates

```bash
pnpm --filter web typecheck && pnpm --filter web lint \
  && pnpm --filter web test && pnpm --filter web build
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

The tests that matter most assert the honesty invariant: that a citation's `(start, end)`
selects exactly its quote from the document text the API returned alongside it
([`tests/api/test_analyses.py`](apps/api/tests/api/test_analyses.py)), and that an
ungrounded finding is dropped rather than shown
([`tests/services/test_analyzer.py`](apps/api/tests/services/test_analyzer.py)).

No test calls the real Anthropic API — the model is stubbed at the `core.llm` boundary.

## Deliberately out of scope

Multi-file comparison, a clause precedent library, user accounts, in-place redlining, and
e-signature. Scoped out so the core loop — retrieve, reason, stay grounded — could be built
properly rather than three things built badly.

**Next, in order:** real (not synthetic) eval contracts; a precedent library with vector
comparison so a clause can be judged against your own standard rather than a generic
rubric; redlines applied in-document; multi-contract diffing.

## License

MIT
