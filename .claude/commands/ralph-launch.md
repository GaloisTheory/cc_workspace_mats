# Ralph Launch - Pre-Launch Checklist

Verify everything is ready before running Ralph in a separate terminal.

## Instructions

Run through this checklist to ensure Ralph can run successfully.
Report issues clearly and provide the exact command to run.

### Checklist Items

#### 1. Specs Directory

Check that `specs/` exists and contains spec files:

```bash
ls -la specs/
```

**Pass**: Directory exists with `.md` files
**Fail**: Directory missing or empty → Run `/ralph-specs` first

#### 2. AGENTS.md Validation Commands

Read `AGENTS.md` and verify it has ACTUAL validation commands, not just template placeholders.

**Check for**:
- Real pytest command (not just `# pytest`)
- Real type checker command (mypy/pyright)
- Real linter command (ruff/flake8)

**Pass**: Has concrete, runnable validation commands
**Fail**: Still has template placeholders → Edit `AGENTS.md` with your project's commands

#### 3. Implementation Plan (for build mode)

If user wants to run `ralph build`, check `IMPLEMENTATION_PLAN.md`:

```bash
# Check if file exists and has tasks
grep -c "^\- \[ \]" IMPLEMENTATION_PLAN.md 2>/dev/null || echo "0"
```

**Pass**: File exists with incomplete tasks (`[ ]`)
**Fail**: No incomplete tasks → Run `ralph plan` first, or all tasks are done!

#### 4. Git Working Tree

Check for uncommitted changes:

```bash
git status --porcelain
```

**Pass**: Working tree is clean (empty output)
**Warn**: Uncommitted changes exist → Recommend committing or stashing first

#### 5. Git Remote

Verify we can push to origin:

```bash
git remote -v | grep origin
```

**Pass**: Origin remote configured
**Warn**: No origin → Ralph won't be able to push or create PRs

### Output Format

After running all checks, output a clear summary:

```
═══════════════════════════════════════════════════════════
  Ralph Pre-Launch Checklist
═══════════════════════════════════════════════════════════

✅ specs/ exists with 3 spec files
✅ AGENTS.md has validation commands (pytest, mypy, ruff)
✅ IMPLEMENTATION_PLAN.md has 5 incomplete tasks
✅ Git working tree is clean
✅ Git remote 'origin' configured

═══════════════════════════════════════════════════════════
  All checks passed! Run in a separate terminal:
═══════════════════════════════════════════════════════════

  ralph plan          # Generate implementation plan from specs

  # OR if plan already exists:

  ralph build --max 30   # Start building (30 iterations max)

```

### If Checks Fail

Show what failed and how to fix:

```
═══════════════════════════════════════════════════════════
  Ralph Pre-Launch Checklist
═══════════════════════════════════════════════════════════

✅ specs/ exists with 3 spec files
❌ AGENTS.md has template placeholders
   → Edit AGENTS.md and add your project's actual test commands
✅ IMPLEMENTATION_PLAN.md has 5 incomplete tasks
⚠️  Git has uncommitted changes (2 files)
   → Consider: git stash or git commit
✅ Git remote 'origin' configured

═══════════════════════════════════════════════════════════
  Fix the issues above before running Ralph
═══════════════════════════════════════════════════════════
```

### Mode Detection

Determine which mode the user likely wants:

- **No IMPLEMENTATION_PLAN.md or only template content** → Suggest `ralph plan`
- **IMPLEMENTATION_PLAN.md has incomplete tasks** → Suggest `ralph build`
- **All tasks complete** → Suggest reviewing with `/ralph-review`

### Important Reminders

Include these in your output:

```
📌 Remember:
   • Run ralph commands in a SEPARATE terminal (not here)
   • Ralph spawns fresh Claude Code instances for each iteration
   • Use Ctrl+C to stop Ralph at any time
   • Progress is saved in IMPLEMENTATION_PLAN.md
```
