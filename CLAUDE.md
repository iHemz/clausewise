# Clausewise — Project Instructions

**What this is:** a contract review tool. Upload a PDF or DOCX and get back every risky
clause with a severity, a plain-English reason, a suggested rewrite, and a citation
pointing at the exact source text. The user is someone deciding whether to sign — a
founder, an ops lead, a lawyer doing a first pass. "Working" means they can click any
finding and land on the words it came from, and check it themselves in seconds.

## The non-negotiable

**Every finding must carry a real character span into the extracted text. If the model
cannot quote what it is flagging, the finding is dropped — not shown with an approximate
source.**

This is the product, not a detail. A citation the reader cannot click through to is not a
citation, and a tool that fabricates one is worse than no tool for someone whose
professional liability is on the line. Concretely:

- `ground_finding` in `apps/api/domain/contracts.py` is the gate. It tolerates whitespace
  differences from PDF line-wrapping and nothing else.
- Extraction **concatenates, never transforms** (`apps/api/core/extraction.py`). No
  de-hyphenation, no smart quotes, no whitespace collapsing — the extracted string is the
  document, and every offset in the system indexes it.
- Segmentation is deterministic and LLM-free, so the same upload always yields the same
  clause boundaries and the evals measure quality rather than noise.
- The citation stores the **source** text, not the model's rendering of it.
- Dropped findings are counted and surfaced in the UI. Do not hide them.

If a change would weaken any of the above to raise recall, it is the wrong change. Say so
and propose something else.

## Model usage

- Every Claude call goes through `apps/api/core/llm.py`. Never construct an
  `anthropic.Anthropic()` elsewhere.
- Use `llm.parse()` with a Pydantic schema for anything structured. The API enforces the
  schema, so there is no JSON to repair — do not add fence-stripping or brace-trimming.
- The analyzer's system prompt is identical for every clause, so it is cached
  (`cache_system=True`). Keep it stable; editing it invalidates the cache for the whole run.
- The judge pass **annotates** severity, never overwrites it. Disagreement is information
  the reviewer should see.
- No test may call the real API. The model is stubbed at the `core.llm` boundary via the
  `stub_llm` fixture.

## Evals

`apps/api/evals/` holds a hand-labelled set and a harness. Run it after any change to a
prompt, the rubric, or the segmenter:

```bash
cd apps/api && uv run python -m evals.run
```

It costs real money and is deliberately not in CI. The contracts are synthetic and the set
is tiny — good for catching a regression, not evidence about real-world accuracy. Keep
that caveat in the README; do not quietly upgrade the claim.

## Quick reference

| Task           | Command                                            |
| -------------- | -------------------------------------------------- |
| Dev (web)      | `pnpm --filter web dev` → http://localhost:3000 |
| Dev (api)      | `cd apps/api && uv run uvicorn main:app --reload` → http://localhost:8000 |
| Typecheck      | `pnpm --filter web typecheck`                 |
| Lint           | `pnpm --filter web lint`                      |
| Format         | `pnpm --filter web format` / `format:check`   |
| Unit tests     | `pnpm --filter web test`                      |
| E2E tests      | `pnpm --filter web test:e2e`                  |
| Build          | `pnpm --filter web build`                     |
| Python lint    | `cd apps/api && uv run ruff check .`                |
| Python format  | `cd apps/api && uv run ruff format .`               |
| Python tests   | `cd apps/api && uv run pytest`                      |

**Package managers:** `pnpm` for `apps/web`, `uv` for `apps/api`. Do not use npm, yarn, or pip.
`pnpm install` runs at the **workspace root**, not inside a package.

## Structure

```
.
├── apps/
│   ├── web/             Next.js 16 · React 19 · TypeScript (strict) · Tailwind v4 · TanStack Query
│   │   ├── app/         Routes. Thin server components — no "use client", no hooks.
│   │   ├── components/  Client logic, grouped by domain, assembled by a *View component.
│   │   ├── lib/         api.ts (the only bridge to the API), queries/, utils.ts
│   │   └── e2e/         Playwright specs
│   └── api/             FastAPI · Python 3.12 · uv
│       ├── api/         routes/ (thin), deps.py (assembly), error_handlers.py
│       ├── core/        config, errors, logging, llm — cross-cutting infrastructure
│       ├── domain/      Pure models and logic. No I/O, no framework imports.
│       ├── services/    Use-cases. Orchestrate domain + repositories; raise domain errors.
│       ├── repositories/ The only layer that touches storage.
│       └── tests/       Mirrors the source tree
├── packages/            Shared workspace packages (types, ui, config) — empty until needed
├── .claude/             skills/, commands/, agents/
├── .husky/              Pre-commit quality gate
└── .github/workflows/   CI
```

## Architecture rules

**`apps/web` flow — enforce it end to end:**
`page (server) → *View (client) → query hook → lib/api.ts → apps/api`

- `app/**` are server components. Adding `"use client"` there is a smell — push the
  interactivity into a `components/<domain>/*View.tsx` instead.
- `lib/api.ts` is the only module that calls `fetch`. Components never do.
- One TanStack Query hook file per domain in `lib/queries/`, with a query-key factory.

**`apps/api` layers — one-directional, no shortcuts:**
`route → service → domain → repository`

- Routes validate shape and delegate. No business rules, no try/except — domain errors
  are mapped to HTTP centrally in `api/error_handlers.py`.
- Services own the use-case and raise `core.errors` exceptions. They never import FastAPI.
- Domain logic is pure: no I/O, no framework, no storage. This is where tests are cheapest.
- Repositories are the only place that touches storage. Services depend on the `Protocol`,
  never a concrete class, so the backing store is swappable.
- Everything crossing a boundary is a Pydantic model, never a raw dict.
- Every Claude call goes through `core/llm.py`. Use `parse()` with a Pydantic schema when
  you need structured data — the API enforces the schema, so there is no JSON to repair.

## Naming (enforced by the pre-commit hook)

- `.tsx` → PascalCase: `ItemCard.tsx`, `ItemsView.tsx`
- `.ts` → lowercase-first: `api.ts`, `use-items.ts`
- Folders → lowercase-first: `components/`, `lib/queries/`
- Next.js reserved names are exempt: `page.tsx`, `layout.tsx`, `route.ts`, `error.tsx`, …
- Python follows PEP 8 (`snake_case`), enforced by ruff.

## Git workflow

**Never commit or push directly to `main`.** Every change goes through a feature branch
and a PR.

1. Check the branch (`git branch --show-current`). If on `main`, branch first.
2. Branch names: `feat/`, `fix/`, `refactor/`, `chore/`, `docs/`, `test/` + kebab-case.
3. Conventional commits: `type(scope): subject`, describing **what changed and why** —
   never how it was built or what tooling was involved.
4. `/ship` does the whole flow: branch → gates → commit → push → PR.

## Before opening a PR

- [ ] `pnpm --filter web typecheck` passes
- [ ] `pnpm --filter web lint` passes
- [ ] `pnpm --filter web format:check` clean
- [ ] `pnpm --filter web test` passes
- [ ] `pnpm --filter web build` succeeds
- [ ] `cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pytest`
- [ ] Verified in the browser — no console errors, no hydration warnings
- [ ] Responsive at ~375px / 768px / 1280px; keyboard-accessible; respects
      `prefers-reduced-motion`

## Helpers

**Skills:** `/ship`, `/test`, `/bugs`, `/principal`, `/triage`, `/tycoon`, `/resolve-conflicts`
**Commands:** `/play`, `/html-transformer`
**Agents:** `code-review`, `research-agent`, `ui-ux-expert`
