---
name: ship
description: "Ship: branch, run quality gates, commit, push & PR"
argument-hint: "[branch-name]"
---

# Ship: Branch, Commit, Push & PR

Complete git workflow to ship changes: create a feature branch, run the quality gates, stage and commit with a quality message, push, and create a PR.

**Never commit or push directly to `main`.** Every change goes through a feature branch and a PR — no exceptions, no matter how small.

## Input

- `$ARGUMENTS` - Branch name (e.g., `feat/add-user-auth` or `fix/login-bug`). If blank, AI will suggest based on changes.

## Steps

### 1. Analyze Current State

**AI Task:** Understand what we're shipping:

```bash
git status && git diff --stat && git diff --name-only
```

1. **Review changes:**
   - What files are modified/added/deleted?
   - What is the scope of the changes?
   - Are there any untracked files that should be included?

2. **Verify clean state:**
   - Ensure working directory has changes to commit
   - If no changes, notify the user and stop
   - If already on `main`, that's fine — Step 3 creates the feature branch before anything is committed. Never commit on `main`.

### 2. Determine Branch Name

**AI Task:** Establish the branch name:

1. **If `$ARGUMENTS` provided:**
   - Use the provided branch name
   - Validate it follows convention: `type/description` (e.g., `feat/`, `fix/`, `chore/`, `refactor/`, `docs/`)

2. **If no arguments:**
   - Analyze the changes to determine the type:
     - New functionality → `feat/`
     - Bug fix → `fix/`
     - Refactoring → `refactor/`
     - Documentation → `docs/`
     - Maintenance → `chore/`
   - Generate a descriptive, kebab-case name
   - **Always proceed automatically** — do not ask for confirmation on branch name, commit message, or any other step. Ship without pausing.

### 3. Create Feature Branch

**AI Task:** Create and switch to the new branch:

```bash
git checkout -b [branch-name]
```

- Confirm branch creation
- If branch already exists, notify user and ask how to proceed

### 4. Stage Changes

**AI Task:** Stage all relevant changes:

```bash
git add -A
```

1. **Review staged changes:**

   ```bash
   git diff --cached --stat
   ```

2. **Check for issues:**
   - Warn if staging sensitive files (`.env`, credentials, secrets)
   - Warn if staging large binary files
   - Warn if staging `node_modules` or other ignored patterns

### 5. Run Quality Gates

**AI Task:** Before committing, run the gates for whichever app(s) the change touches. All must pass with zero errors — fix anything that fails and re-run before continuing.

For `apps/web`:

```bash
pnpm --filter web run typecheck
pnpm --filter web run lint
```

For `apps/api`:

```bash
cd apps/api && uv run ruff check .
cd apps/api && uv run ruff format --check .
cd apps/api && uv run pytest
```

Reminder of the non-negotiables to eyeball while you're here:

- Business logic, validation, and LLM orchestration live in `apps/api`; `apps/web` stays a thin client.
- Layers stay one-directional: route → service → domain → repository. Only repositories touch storage.
- Data crossing a boundary is a typed Pydantic model validated at that boundary — never a raw dict.
- Anything the LLM asserts to a user is grounded in retrieved source text, not the model's own recall.
- No secrets, keys, or `.env` files in the diff.
- Any project-specific non-negotiables in the repo's `CLAUDE.md` also apply — read them.

For an extra pass, run `/code-review` on the diff before opening the PR and address any high/critical findings.

### 6. Craft Commit Message

**AI Task:** Generate a quality commit message based on the changes:

1. **Analyze the diff:**

   ```bash
   git diff --cached
   ```

2. **Follow commit message conventions:**
   - **Format:** `type(scope): subject`
   - **Types:** feat, fix, docs, style, refactor, test, chore
   - **Scope:** Optional module/area affected
   - **Subject:** Imperative mood, lowercase, no period, max 72 chars

3. **Generate message structure:**

   ```
   type(scope): brief description of what changed

   - Bullet point explaining why this change was made
   - Another point if multiple related changes
   - Focus on the "why" not the "what"
   ```

4. **Quality checklist:**
   - Does it explain WHY, not just WHAT?
   - Is it clear to someone unfamiliar with the context?
   - Would this help in a git blame 6 months from now?

### 7. Commit Changes

**AI Task:** Create the commit:

```bash
git commit -m "$(cat <<'COMMIT'
type(scope): brief description

- Explanation of why this change was made
- Additional context if needed

COMMIT
)"
```

- Verify commit was created successfully
- If pre-commit hooks fail, fix issues and retry

### 8. Push to Remote

**AI Task:** Push the branch to origin:

```bash
git push -u origin HEAD
```

- Confirm push was successful
- If push fails (e.g., branch exists on remote), notify user

### 9. Create Pull Request

**AI Task:** Create the PR using the GitHub CLI (`gh`):

1. **Gather PR details:**
   - Title: Use the commit subject line
   - Body: Expand on the changes with context in this format:

     ```
     ## Summary

     - Brief bullet point of what this PR does
     - Another point if needed

     ## Changes

     - List of specific changes made

     ## Test Plan

     - [ ] Manual testing steps
     - [ ] Any automated tests added/updated
     ```

2. **Create PR using `gh` CLI:**

   ```bash
   gh pr create --base main --title "type(scope): subject from commit" --body "$(cat <<'EOF'
   ## Summary

   - Brief bullet point of what this PR does
   - Another point if needed

   ## Changes

   - List of specific changes made

   ## Test Plan

   - [ ] Quality gates pass (web: typecheck + lint / api: ruff + pytest)
   - [ ] Manual testing steps
   - [ ] Any automated tests added/updated
   EOF
   )"
   ```

   - `--base main`: Target branch (use repo default if different)
   - `--title`: Commit subject line
   - `--body`: PR description (use heredoc or inline string; escape as needed for shell)

3. **Capture and display the PR URL from the command output**

### 10. Ship Report

**AI Task:** Provide a summary of what was shipped:

```markdown
## Shipped Successfully

**Branch:** `[branch-name]`
**Commit:** `[short-hash]` - [commit subject]

### Changes Shipped

| File      | Change   |
| --------- | -------- |
| `[file1]` | Modified |
| `[file2]` | Added    |

### Pull Request

**URL:** [PR URL]
**Title:** [PR title]

### Current State

- Staying on `[branch-name]` branch for further work if needed

### Next Steps

- [ ] Wait for CI checks to pass
- [ ] Request review if needed
- [ ] Merge when approved
```

---

## Branch Naming Convention

| Prefix      | Use Case         | Example                      |
| ----------- | ---------------- | ---------------------------- |
| `feat/`     | New feature      | `feat/form-m-prep-sheet`     |
| `fix/`      | Bug fix          | `fix/packing-list-parsing`   |
| `refactor/` | Code refactoring | `refactor/compliance-agent`  |
| `docs/`     | Documentation    | `docs/agent-pipeline`        |
| `chore/`    | Maintenance      | `chore/update-deps`          |
| `test/`     | Test additions   | `test/classifier-edge-cases` |

## Commit Message Examples

**Good:**

```
feat(classifier): ground HS-code lookup in retrieved tariff text

- Classifier now cites the retrieved tariff line for each HS code
- Stops the agent guessing codes from the model's own knowledge
- Cuts the kind of misclassification that triggers port delays
```

**Bad:**

```
updated classifier stuff
```

## Troubleshooting

**Pre-commit hook fails:**

- Fix the issues reported
- Run the command again

**Branch already exists:**

- Choose a different name, or
- Delete the existing branch if safe: `git branch -D [name]`

**Push rejected:**

- Pull latest changes and resolve conflicts
- Force push only if you know what you're doing

**PR creation fails:**

- Ensure GitHub CLI is installed: `gh --version`
- Ensure you're authenticated: `gh auth status`
- Ensure your GitHub token has repo write permissions (e.g. `gh auth login`)

Done.
