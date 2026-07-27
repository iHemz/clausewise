---
name: resolve-conflicts
description: Smart merge conflict resolution
---

# Resolve Merge Conflicts

Intelligently resolve git merge conflicts by analyzing both sides of each conflict, understanding the intent behind each change, and producing a correct merged result. **Automatically continues the operation (rebase/merge/cherry-pick) and resolves subsequent conflicts until the entire operation completes — no manual intervention required.**

## Input

- `$ARGUMENTS` - Optional: specific file(s) to resolve. If blank, resolves all conflicted files.

## Steps

### 1. Assess Conflict State

**AI Task:** Determine the current merge state and list all conflicts:

```bash
git status
```

1. **Verify we're in a conflict state:**
   - Check for merge, rebase, or cherry-pick in progress
   - If no conflicts exist, inform the user and STOP

2. **Identify the operation type and store it for the entire loop:**
   - `MERGING` — a `git merge` is in progress → continue command: `git merge --continue`
   - `REBASING` — a `git rebase` is in progress → continue command: `GIT_EDITOR=true git rebase --continue`
   - `CHERRY-PICKING` — a `git cherry-pick` is in progress → continue command: `git cherry-pick --continue`

3. **For rebases, determine the scope:**
   ```bash
   # Count remaining commits to process
   cat .git/rebase-merge/end 2>/dev/null || cat .git/rebase-apply/last 2>/dev/null || echo "unknown"
   cat .git/rebase-merge/msgnum 2>/dev/null || cat .git/rebase-apply/next 2>/dev/null || echo "unknown"
   ```

4. **List all conflicted files:**
   - Files marked as "both modified" or "both added"
   - If `$ARGUMENTS` was provided, filter to only those files

5. **Initialize a resolution log** — an accumulator to track all resolutions across every round. This will be used for the final report.

---

## BEGIN RESOLUTION LOOP

Repeat Steps 2–6 below for each round of conflicts. Each round corresponds to one commit (during rebase) or one merge operation. Continue looping until the operation completes with no more conflicts.

**Track the current round number starting at 1.**

### 2. Gather Context (Per Round)

**AI Task:** Understand what each side of the conflict was trying to accomplish:

1. **Identify the two branches/commits involved:**

   For merge conflicts:
   ```bash
   git log --oneline -5 HEAD
   git log --oneline -5 MERGE_HEAD
   ```

   For rebase conflicts:
   ```bash
   git log --oneline -5 HEAD
   git log --oneline -1 REBASE_HEAD
   ```

2. **Read relevant commit messages** to understand the intent of each side

3. **On the first round only**, check if a PR description exists for additional context:
   ```bash
   gh pr list --state open --head "$(git branch --show-current)" --json title,body --jq '.[0]' 2>/dev/null || echo "No PR found"
   ```

### 3. Analyze Each Conflicted File

**AI Task:** For each conflicted file, perform deep analysis:

1. **Read the file** with conflict markers intact

2. **Identify every conflict block** (delimited by `<<<<<<<`, `=======`, `>>>>>>>`)

3. **Classify each conflict** into one of these categories:

   | Category | Description | Resolution Strategy |
   |----------|-------------|-------------------|
   | **Additive** | Both sides added different things in the same location | Keep both additions in logical order |
   | **Superseding** | One side's change makes the other obsolete | Keep the more complete/recent change |
   | **Divergent** | Both sides changed the same code differently | Synthesize a merged version that satisfies both intents |
   | **Formatting** | Conflict is purely whitespace/formatting | Use the project's style conventions |
   | **Import/Dependency** | Both sides added different imports or deps | Keep all unique imports, deduplicate |
   | **Structural** | File reorganization on one/both sides | Requires careful manual merge considering final structure |

4. **For each conflict block, determine:**
   - What was the original code (before both changes)?
   - What did "ours" change and why?
   - What did "theirs" change and why?
   - Are the changes complementary, contradictory, or independent?

### 4. Resolve Conflicts

**AI Task:** Resolve each conflicted file using the analysis from Step 3:

**Resolution principles (in priority order):**

1. **Correctness** — The resolved code must compile and be logically correct
2. **Completeness** — Don't drop changes from either side unless one truly supersedes the other
3. **Intent preservation** — Honor what each side was trying to accomplish
4. **Convention adherence** — Follow project conventions (read `CLAUDE.md` and the relevant `/docs/` spec if unsure)
5. **Minimal surprise** — The resolution should be what a senior engineer would produce

**For each file:**

1. **Remove all conflict markers** (`<<<<<<<`, `=======`, `>>>>>>>`)
2. **Produce the resolved content** using the Edit tool
3. **Verify no conflict markers remain:**
   ```bash
   grep -rn "^<<<<<<<\|^=======\|^>>>>>>>" [file]
   ```
4. **Check for merge artifacts by file type:**
   - **TypeScript/React (`apps/web`):** duplicate imports (deduplicate), duplicate component/variable declarations, inconsistent type references, broken import paths
   - **Python (`apps/api`):** duplicate imports, duplicate function/class definitions, drifted Pydantic models, broken module paths

### 5. Stage Resolved Files

**AI Task:** Stage all resolved files:

```bash
git add [resolved-files]
```

Verify staging:
```bash
git status
```

- Confirm all conflicts are resolved
- If some files remain conflicted, go back to Step 3 for those files
- **Append this round's resolutions to the resolution log**

### 6. Continue the Operation

**AI Task:** Automatically continue the git operation and check for new conflicts:

1. **Run the continue command** (determined in Step 1):

   For rebases (suppress editor prompts):
   ```bash
   GIT_EDITOR=true git rebase --continue
   ```

   For merges:
   ```bash
   git merge --continue
   ```

   For cherry-picks:
   ```bash
   git cherry-pick --continue
   ```

2. **Check the result:**

   ```bash
   git status
   ```

   - **If new conflicts exist** → Increment round number, log `"Round N: continuing..."` and **go back to Step 2**
   - **If the operation completed successfully** (no more conflicts, no rebase/merge/cherry-pick in progress) → **Exit the loop and proceed to Step 7**
   - **If the continue command failed for a non-conflict reason** → Log the error and proceed to Step 7 with the error noted

**IMPORTANT:** Do NOT stop to ask the user between rounds. The entire point of this loop is fully autonomous resolution. Only stop if you encounter an unrecoverable error (e.g., binary file conflicts, files deleted on one side and modified on the other with ambiguous intent).

## END RESOLUTION LOOP

---

### 7. Final Validation

**AI Task:** Now that the entire operation is complete, verify the final codebase is correct. Run the gates for whichever app(s) the conflicts touched:

For `apps/web`:
```bash
pnpm --filter web run typecheck 2>&1 | head -50
pnpm --filter web run lint 2>&1 | head -50
```

For `apps/api`:
```bash
cd apps/api && uv run ruff check . 2>&1 | head -50
cd apps/api && uv run pytest 2>&1 | tail -50
```

1. **If type/check errors exist:**
   - Analyze the error
   - Fix the issue (likely a missed dependency from one side of the merge)
   - Re-run validation

2. **If lint errors exist:**
   - Fix automatically where possible (`ruff check --fix` for Python)
   - Re-run validation

3. **Repeat until everything passes cleanly**

4. **If fixes were needed, stage and amend the last commit:**
   ```bash
   git add [fixed-files]
   git commit --amend --no-edit
   ```

### 8. Resolution Report

**AI Task:** Provide a comprehensive summary of ALL resolutions across ALL rounds:

```markdown
## Merge Conflicts Resolved

**Operation:** [merge/rebase/cherry-pick]
**Branches:** `[ours]` <- `[theirs]`
**Total Rounds:** [N]
**Total Conflicts Resolved:** [count]

### Summary by Round

| Round | Commit | Files | Conflicts | Status |
|-------|--------|-------|-----------|--------|
| 1 | `abc1234 feat: add X` | 2 | 3 | Resolved |
| 2 | `def5678 fix: update Y` | 1 | 1 | Resolved |
| 3 | `ghi9012 refactor: Z` | 3 | 5 | Resolved |

### Resolved Files (All Rounds)

| File | Total Conflicts | Primary Strategy | Notes |
|------|----------------|-----------------|-------|
| `path/to/file.ts` | 4 | Additive | Kept both new imports + combined handler logic |
| `path/to/other.ts` | 2 | Superseding | Kept theirs (more complete implementation) |

### Resolution Details

#### Round 1 — `abc1234 feat: add X`

##### `path/to/file.ts`
- **Conflict 1 (lines X-Y):** Both sides added imports — kept all unique imports
- **Conflict 2 (lines X-Y):** Divergent logic changes — synthesized to handle both cases

#### Round 2 — `def5678 fix: update Y`

##### `path/to/other.ts`
- **Conflict 1 (lines X-Y):** Theirs added error handling, ours refactored — applied error handling to refactored code

### Final Validation

- web typecheck / lint: PASS/FAIL/N-A
- api ruff / pytest: PASS/FAIL/N-A
- Post-validation fixes applied: [yes/no — describe if yes]

### Result

The [merge/rebase/cherry-pick] completed successfully. All [N] rounds of conflicts were resolved autonomously.
```

Done.
