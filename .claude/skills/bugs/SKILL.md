---
name: bugs
description: AI-Optimized Bug Exploration & Fix Planning System - comprehensive 5-phase debugging workflow
argument-hint: "[bug description]"

---

# AI-Optimized Bug Exploration & Fix Planning System

This document establishes a structured methodology for debugging software issues through systematic root cause analysis and solution design.

## Core Framework

The system operates as a **Senior Software Debugging Specialist** combining root cause analysis, system architecture understanding, impact assessment, and solution design. The specialist can autonomously explore codebases, read relevant code, and present multiple fix approaches with transparent trade-off analysis.

## Project Context

**Stack:** Next.js 16 frontend (pnpm, TypeScript, TanStack Query) · FastAPI backend (Python, uv) · the database layer

**Frontend data flow:** `page (server component) → *View component (client) → queryFn/mutationFn → lib/api.ts → backend`

**Next.js 16 specifics:**
- Middleware is in `apps/web/proxy.ts` (not `middleware.ts` — this version renamed it)
- `NEXT_PUBLIC_*` env vars are inlined at build time; they must be non-sensitive in Vercel for `vercel pull` to download them
- Turbopack is the default bundler

**Key quality gates (run before shipping any fix):**
```bash
# Frontend
pnpm --filter web run typecheck   # tsc --noEmit
pnpm --filter web run lint        # eslint

# Backend
cd apps/api && uv run ruff check .
cd apps/api && uv run pytest
```

**Shipping:** All fixes go through a branch + PR using `/ship` — never directly to `main`.

## Investigation Process (5 Phases)

**Phase 1: Clarification** — Ask 1-3 targeted questions only if critical information is missing (reproduction steps, scope, context, impact). Skip if the bug is clear.

**Phase 2: Root Cause Investigation** — Delegate systematic investigation to an "Explore" agent, which:
- Reads memory files (`C:\Users\ajayi\.claude\projects\...\memory\`) for project context
- Traces the data flow: frontend component → query hook → api.ts → backend route → DB
- Checks Vercel runtime logs (via MCP) for production errors
- Identifies the exact file and line where the failure originates

**Phase 3: Root Cause Presentation** — Present findings with:
- Exact file:line reference
- Problem statement (what is wrong and why)
- Evidence (code snippet or log output)

**Phase 4: Solution Options** — Present 2-3 fix approaches with:
- Effort estimate
- Risk level (does it touch auth / DB schema / shared UI primitives?)
- Affected files
- Whether quality gates need re-running after

**Phase 5: Recommendation & Next Steps** — Pick the best approach based on the complexity score below, then act.

## Complexity-to-Action Decision

| Complexity | Action |
|---|---|
| **1-2** | Fix inline immediately, run relevant quality gate, then `/ship` |
| **3-6** | Fix inline (multi-file), run all quality gates, then `/ship` |
| **7+** | Present the approach and confirm with the user before implementing — scope is large enough to warrant alignment first |

## Key Principles

- Give specific `file:line` references — never vague observations
- Honest effort and risk estimates, not optimistic ones
- For production errors: always check Vercel runtime logs via the Vercel MCP tools before guessing
- Never propose a fix that doesn't address the identified root cause
- Skip the Explore agent only for trivial single-file fixes
- Backend bugs: verify with `uv run pytest` and `ruff check` before shipping
- Frontend bugs: verify with `tsc --noEmit` and `eslint` before shipping
