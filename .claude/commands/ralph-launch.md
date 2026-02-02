# Ralph Launch - Pre-Launch Checklist

Verify everything is ready before running Ralph in a separate terminal.

## Usage

`/ralph-launch` - Run in current directory
`/ralph-launch <path>` - Run in specified project directory (e.g., `/ralph-launch projects/my-project`)

$ARGUMENTS

**Target directory:** If `$ARGUMENTS` is provided, all operations target that directory.
Verify the directory exists before proceeding.

## Instructions

Run through this checklist to ensure Ralph can run successfully.
Report issues clearly and provide the exact command to run.

### 0. Determine Target Directory

If `$ARGUMENTS` is provided:
1. Verify the directory exists
2. Use this as the target directory for all subsequent operations

If `$ARGUMENTS` is empty, use the current working directory.

All file paths below are relative to the **target directory**.

### Checklist Items

#### 1. Specs Directory

Check that `<target-directory>/specs/` exists and contains spec files:

```bash
ls -la <target-directory>/specs/
```

**Pass**: Directory exists with `.md` files
**Fail**: Directory missing or empty → Run `/ralph-specs <target-directory>` first

#### 2. AGENTS.md Validation Commands

Read `<target-directory>/AGENTS.md` and verify it has ACTUAL validation commands, not just template placeholders.

**Check for**:
- Real pytest command (not just `# pytest`)
- Real type checker command (mypy/pyright)
- Real linter command (ruff/flake8)

**Pass**: Has concrete, runnable validation commands
**Fail**: Still has template placeholders → Edit `<target-directory>/AGENTS.md` with your project's commands

#### 3. Implementation Plan (for build mode)

If user wants to run `ralph build`, check `<target-directory>/IMPLEMENTATION_PLAN.md`:

```bash
# Check if file exists and has tasks
grep -c "^\- \[ \]" <target-directory>/IMPLEMENTATION_PLAN.md 2>/dev/null || echo "0"
```

**Pass**: File exists with incomplete tasks (`[ ]`)
**Fail**: No incomplete tasks → Run `ralph plan` first, or all tasks are done!

#### 4. Git Working Tree

Check for uncommitted changes in the target directory:

```bash
git -C <target-directory> status --porcelain
```

**Pass**: Working tree is clean (empty output)
**Warn**: Uncommitted changes exist → Recommend committing or stashing first

#### 5. Git Remote

Verify we can push to origin:

```bash
git -C <target-directory> remote -v | grep origin
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

  cd <target-directory>
  ralph plan          # Generate implementation plan from specs

  # OR if plan already exists:

  cd <target-directory>
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

- **No IMPLEMENTATION_PLAN.md or only template content** → Suggest `cd <target-directory> && ralph plan`
- **IMPLEMENTATION_PLAN.md has incomplete tasks** → Suggest `cd <target-directory> && ralph build`
- **All tasks complete** → Suggest reviewing with `/ralph-review <target-directory>`

### Important Reminders

Include these in your output:

```
📌 Remember:
   • Run ralph commands in a SEPARATE terminal (not here)
   • Ralph spawns fresh Claude Code instances for each iteration
   • Use Ctrl+C to stop Ralph at any time
   • Progress is saved in IMPLEMENTATION_PLAN.md
```
