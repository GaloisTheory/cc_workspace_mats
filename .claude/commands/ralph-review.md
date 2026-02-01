# Ralph Review - Review Build Session Results

Review what Ralph accomplished during a build session.

## Instructions

You are reviewing Ralph's work after a `ralph build` or `ralph plan-work` session.
Provide a clear summary of what was done and what remains.

### 1. Identify the Ralph Branch

Find the current or most recent Ralph branch:

```bash
# Check current branch
git branch --show-current

# Or find ralph/* branches
git branch -a | grep ralph/
```

If not on a ralph/* branch, ask the user which branch to review or check for worktrees:
```bash
git worktree list
```

### 2. Show Branch Diff Summary

Show what changed compared to main:

```bash
# Get the base branch
git merge-base main HEAD

# Summary of changes
git diff main...HEAD --stat

# Number of commits
git rev-list main..HEAD --count
```

### 3. Summarize Completed Work

Read `IMPLEMENTATION_PLAN.md` and extract:

**Completed Tasks** (marked `[x]}):
- List each completed task with a one-line summary
- Note which files were affected

**Incomplete Tasks** (marked `[ ]`):
- List remaining tasks
- Note any blockers or failure notes from previous attempts

**Progress**: X of Y tasks completed (Z%)

### 4. Show Recent Commits

Display the commit history for this branch:

```bash
git log main..HEAD --oneline --no-decorate
```

For more detail on what changed:
```bash
git log main..HEAD --format="%h %s" --stat --no-decorate | head -50
```

### 5. Check Validation Status

If possible, run the validation commands from `AGENTS.md`:

```bash
# Quick check - do tests pass?
pytest --co -q  # Just collect, don't run
ruff check . --statistics
mypy src/ --no-error-summary 2>&1 | tail -5
```

Report any obvious issues.

### 6. Provide Recommendations

Based on the review, suggest one of:

**If all tasks complete and tests pass:**
```
✅ All tasks completed! Ready to merge.

Suggested commands:
  git checkout main
  git merge ralph/branch-name
  git push
  ralph cleanup  # Remove the worktree
```

**If tasks remain but progress was made:**
```
🔄 Progress made, but X tasks remain.

Options:
  1. Continue building: ralph build --resume
  2. Review and adjust specs, then: ralph plan
  3. Manually complete remaining tasks
```

**If stuck or failing:**
```
⚠️ Build session encountered issues.

Review the Notes section in IMPLEMENTATION_PLAN.md for details.
Consider:
  1. Simplifying the failing task
  2. Adding missing dependencies
  3. Adjusting specs to be more achievable
```

### 7. Offer Next Actions

Ask the user what they'd like to do:

> **What would you like to do?**
> 1. Merge this branch to main
> 2. Continue the build session
> 3. View specific file changes
> 4. Regenerate the plan with updated specs
> 5. Something else?

## Example Output

```
═══════════════════════════════════════════════════════════
  Ralph Review: ralph/add-retry-logic-20240115-1423
═══════════════════════════════════════════════════════════

📊 Progress: 4/6 tasks completed (67%)

✅ Completed:
  • Core retry decorator - src/retry/decorator.py
  • Exponential backoff calculation - src/retry/backoff.py
  • Configuration dataclass - src/retry/config.py
  • Unit tests for backoff - tests/test_backoff.py

⏳ Remaining:
  • Async support - blocked: need to decide on anyio vs native
  • Integration tests

📝 Commits (12):
  a1b2c3d feat: add @retry decorator with basic backoff
  d4e5f6g feat: implement exponential backoff calculation
  ...

🧪 Validation:
  • Tests: 23 passed
  • Types: No errors
  • Lint: 2 warnings (unused import)

💡 Recommendation: Continue building or address the async decision.

What would you like to do?
```
