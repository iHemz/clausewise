---
name: test
description: Write and run tests for the project across the pyramid — unit, assembly/integration, and end-to-end — on both the FastAPI backend (pytest) and the Next.js frontend (Vitest + React Testing Library + Playwright).
argument-hint: "[path or feature to test, or 'setup' to scaffold the tooling]"
---

# Test — the project's testing methodology

The single source of truth for **how we test**. `/principal` (Phase 3) and `/ship` delegate here. Invoke directly to test a module or flow, or with `setup` to scaffold the tooling the first time.

Guiding rule: **a refactor or feature without tests is not done.** Tests pin behavior so we can change code fearlessly.

## The test pyramid

Write many fast unit tests, fewer integration tests, and a small number of end-to-end tests over the flows that actually matter.

| Layer | Backend (`apps/api/`) | Frontend (`apps/web/`) |
|---|---|---|
| **Unit** — one function/component, no I/O | `pytest` (+ `pytest-asyncio` for async) | Vitest + React Testing Library |
| **Assembly/integration** — units wired together, boundaries mocked | FastAPI `TestClient` against routers; repositories + Anthropic mocked | RTL rendering a `*-view.tsx` with query hooks / `api` mocked |
| **End-to-end** — real user flow in a browser | — | Playwright driving the running app |

**What to mock, and what not to.** Never call the real Anthropic API or a real database in unit/integration tests — they cost money, are slow, and are non-deterministic. Mock them at the boundary (`core.llm.client` and the repository providers in `api/deps.py` on the backend; `lib/api.ts` or the query hooks on the frontend). E2E runs against the app but should point at a disposable test database, never production.

## Backend — pytest

**Toolchain:** `pytest`, `pytest-asyncio`, and FastAPI's `TestClient` (ships with FastAPI/Starlette). Tests live in `apps/api/tests/`, mirroring the source tree (`tests/agents/`, `tests/api/`, `tests/core/`). File names: `test_<module>.py`.

**Run:**
```bash
cd apps/api && uv run pytest              # all
cd apps/api && uv run pytest -k <name>    # filter
cd apps/api && uv run pytest --cov=.      # with coverage (needs pytest-cov)
```

**Patterns:**
- **Pure logic first.** Response parsing, scoring/merge, validation — extract these into pure functions and test them exhaustively (happy path + malformed input + edge cases). This is the cheapest, highest-value coverage.
- **Routes via `TestClient`.** Instantiate the FastAPI app, override `get_current_user` with a fake user dependency, and monkeypatch `core.llm.client` and the DB accessor. Assert status codes, validation errors, and the shape of the response.
- **Mock the LLM** by patching the shared client (`core.llm.client`) to return a canned `messages.create` response — never the real API.

**Unit example:**
```python
# apps/api/tests/core/test_llm.py
from core.llm import parse_json_response

def test_strips_markdown_json_fence():
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}

def test_trims_trailing_prose_after_json():
    assert parse_json_response('{"a": 1}\nHope that helps!') == {"a": 1}
```

**Assembly example:**
```python
# apps/api/tests/api/test_items.py
from fastapi.testclient import TestClient
from main import app
from core.auth import get_current_user

app.dependency_overrides[get_current_user] = lambda: {"id": "u1"}
client = TestClient(app)

def test_get_unknown_item_returns_404():
    r = client.get("/items/does-not-exist")
    assert r.status_code == 404
```

## Frontend — Vitest + RTL + Playwright

**Unit/component:** Vitest + React Testing Library + `jsdom`. Test files are **colocated** next to source: `ItemCard.test.tsx`, `api.test.ts` (follow the repo naming rule — `.tsx` PascalCase, `.ts` lowercase-first).

**E2E:** Playwright specs in `apps/web/e2e/`, named `*.spec.ts` (lowercase-first, e.g. `jobs-flow.spec.ts`).

**Run:**
```bash
pnpm --filter web test           # vitest, once
pnpm --filter web test:watch     # vitest, watch mode
pnpm --filter web test:e2e       # playwright
```

**Patterns:**
- **Test behavior, not implementation.** Query by role/text/label as a user would (`getByRole`, `getByText`), not by test IDs or class names, wherever practical.
- **Components in isolation.** Render a `*-view.tsx` or a leaf component with the `api`/query hooks mocked (`vi.mock('@/lib/api', ...)`). Assert what the user sees: loading, empty, error, and success states.
- **E2E over money paths.** Cover the flows whose breakage hurts — the two or three paths that, if broken, make the product worthless. Keep the set small and stable.
- **Cover every UX state** the feature exposes — loading, empty, error, success — matching `/principal` Phase 4's user-first checklist.

**Component example:**
```tsx
// apps/web/components/items/ItemCard.test.tsx
import { render, screen } from '@testing-library/react';
import { ItemCard } from './ItemCard';

it('renders the item name', () => {
  render(<ItemCard item={{ id: '1', name: 'Acme', status: 'ready' }} />);
  expect(screen.getByText('Acme')).toBeInTheDocument();
});
```

## First-time setup (`/test setup`)

Only when the tooling isn't present yet. Add it, wire the scripts, commit one green smoke test per layer to prove the harness works, then ship via `/ship`.

**Backend:**
```bash
cd apps/api && uv add --dev pytest pytest-asyncio pytest-cov
```
Add `[tool.pytest.ini_options]` to `pyproject.toml` with `asyncio_mode = "auto"` and `pythonpath = ["."]`. Create `apps/api/tests/` with a `conftest.py` holding the shared fixtures (fake user override, mocked LLM client, mocked DB).

**Frontend:**
```bash
pnpm --filter web add -D vitest @vitejs/plugin-react jsdom \
  @testing-library/react @testing-library/jest-dom @testing-library/user-event
pnpm --filter web add -D @playwright/test
```
Add `vitest.config.ts` (jsdom environment, `@` path alias, `setupFiles`), a `vitest.setup.ts` importing `@testing-library/jest-dom`, and `playwright.config.ts`. Add scripts to `apps/web/package.json`: `"test": "vitest run"`, `"test:watch": "vitest"`, `"test:e2e": "playwright test"`.

## Definition of done

- New/changed **backend logic** ships with pytest unit tests; new **routes** ship with a `TestClient` assembly test.
- New/changed **frontend components** ship with an RTL test covering their states; **new user-facing flows** get (or extend) a Playwright spec.
- The relevant gate is green before `/ship`: `uv run pytest` and/or `pnpm --filter web test`.
- No test hits a real paid API or a real/production database.
