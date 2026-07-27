---
name: adopt
description: Stand up a new product from this boilerplate — clone the foundation, rename it, strip the example slice, and build the first vertical slice from a spec (a markdown brief, a description, or a link). Use when the owner says "adopt boilerplate", "new project from boilerplate", "start a new repo", or hands over an idea/spec markdown and wants it built on the standard foundation.
argument-hint: "[path to a spec markdown, or a description of what to build]"
---

# Adopt — stand up a new product on this foundation

The boilerplate is a **working** Next.js + FastAPI monorepo with the quality gates,
layering, and agent tooling already wired. Adopting it means: copy it, rename it, delete
the example slice, and replace that slice with the product described in `$ARGUMENTS`.

Do not re-derive the foundation. The value here is that the boring 80% is already
decided and already green — spend the effort on the domain.

## Input

`$ARGUMENTS` is either a path to a spec markdown, or a prose description. If it's empty
or too thin to act on, ask what's being built and who it's for — don't invent a product.

## Steps

### 1. Read the spec and settle the shape

Read the spec in full before touching anything. Extract, and state back in one short
block so the owner can correct you:

- **Product name** → the repo/folder name (kebab-case) and the display name.
- **The one core flow** — the thing that, if it doesn't work, nothing else matters.
- **Explicit non-goals** — what the spec says is out of scope. Respect these; scope creep
  on a first build is the main way these die.
- **What the domain layer actually is** — the nouns and the rules. This becomes
  `apps/api/domain/`.
- **External dependencies** — LLM, storage, third-party APIs, file parsing.

Ask only about decisions that change the work materially and that you cannot infer:
storage backing (in-memory vs a real database), repo visibility, hosting. Make routine
calls yourself and state the assumption.

### 2. Copy the foundation

```bash
# From the parent directory that holds both repos.
cp -r boilerplate <new-name>
cd <new-name>
rm -rf .git node_modules apps/web/node_modules apps/api/.venv
```

Then rename throughout. These are the only places the boilerplate names itself:

| File | Change |
|---|---|
| `package.json` (root) | `"name"` |
| `pnpm-workspace.yaml` | nothing — `apps/*` and `packages/*` already cover it |
| `apps/web/app/layout.tsx` | `metadata.title` / `.description` |
| `apps/web/app/page.tsx` | heading and copy |
| `apps/api/pyproject.toml` | `name`, `description` |
| `apps/api/main.py` | `FastAPI(title=…)` |
| `CLAUDE.md` | every `<!-- ADOPT -->` line, then delete the adoption note at the top |
| `README.md` | rewrite entirely for the product |
| `apps/web/e2e/home.spec.ts` | the heading it asserts on |

### 3. Strip the example slice

The `items` slice exists to demonstrate the layering, not to ship. Delete it once the
real domain replaces it — not before, so you always have a working reference to copy
the shape from:

```
apps/api/domain/items.py            apps/api/repositories/items.py
apps/api/services/items.py          apps/api/api/routes/items.py
apps/api/tests/domain/test_items.py apps/api/tests/api/test_items.py
apps/web/components/items/         apps/web/lib/queries/items.ts
```

Also remove the `items` router from `apps/api/main.py`, its providers from
`apps/api/api/deps.py`, its types and methods from `apps/web/lib/api.ts`, and its fixture
from `apps/api/tests/conftest.py`. Keep the `/health` route and the `health` test.

### 4. Build the first vertical slice

Work **API-first, bottom-up** — each layer is testable before the one above exists:

1. **`apps/api/domain/`** — the models and the pure rules. Write the unit tests here first; this
   is the cheapest place to get the logic right.
2. **`apps/api/repositories/`** — a `Protocol` plus one implementation. In-memory is a legitimate
   first implementation; the point is that the seam exists.
3. **`apps/api/services/`** — the use-case. Raises `core.errors` exceptions, never HTTP ones.
4. **`apps/api/api/routes/` + `deps.py`** — thin route, wired provider. Add a `TestClient`
   assembly test covering the happy path and each error status.
5. **`apps/web/lib/api.ts`** → **`lib/queries/`** → **`components/<domain>/*View.tsx`** →
   **`app/`**. Cover loading, empty, error, and success states — all four, explicitly.
6. **`apps/web/e2e/`** — one spec over the core flow. Not more.

Ship the core flow end to end before adding a second feature. A half-finished second
feature is worth less than a complete first one.

### 5. Verify — every gate, actually run

```bash
pnpm install && pnpm --filter web typecheck && pnpm --filter web lint \
  && pnpm --filter web format:check && pnpm --filter web test \
  && pnpm --filter web build
cd apps/api && uv sync && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

Then run the app and confirm the core flow works in a browser. Report what passed and
what didn't, with the output — never claim green on a gate you didn't run.

### 6. Publish

```bash
git init && git add -A
git commit -m "chore: scaffold <name> from the shared foundation"
gh repo create <name> --public --source=. --remote=origin --push
```

Then work on a feature branch — `main` is protected by convention from the first commit.

## The workspace layout

`apps/web` and `apps/api` are pnpm workspace packages; `packages/` is there for shared
code (types, ui, config) the moment a second consumer appears. Run `pnpm install` at the
**root** — installing inside a package produces a second lockfile and a broken CI cache.
Adding a third app (`apps/docs`, `apps/worker`) needs no restructuring.

## What carries over unchanged

Don't rebuild these; they are the reason to adopt:

- **Layering** — route → service → domain → repository, with `Protocol`-based storage.
- **Error handling** — domain errors in `core/errors.py`, mapped to HTTP once in
  `api/error_handlers.py`. Routes stay try/except-free.
- **`core/llm.py`** — one Claude client with retries, refusal handling, usage/cost
  logging, and schema-enforced structured output via `parse()`.
- **`core/config.py`** — typed settings; no `os.environ` reads scattered around.
- **`lib/api.ts`** — one fetch wrapper with timeouts and typed `ApiError`.
- **Quality gates** — ruff, eslint, prettier, stylelint, tsc strict, vitest, pytest,
  playwright, the pre-commit hook, and CI with path filters.
- **`.claude/`** — skills, commands, and agents.

## Guardrails

- **Never commit to `main`.** Feature branch and PR, from the first change onward.
- **Respect the spec's non-goals.** If you think one is wrong, say so in a sentence and
  build the scoped version anyway — narrowing or widening scope is the owner's call.
- **Don't weaken the gates to make something pass.** No `any`, no `# noqa` without a
  reason on the line, no `ignoreBuildErrors`. Fix the code.
- **Secrets stay in `.env`** (gitignored). Commit `.env.example` with empty values.
