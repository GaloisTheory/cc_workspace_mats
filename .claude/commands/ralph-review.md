# Ralph Review - Review Build Session Results

Review what Ralph accomplished during a session.

## Usage

`/ralph-review` - Run in current directory
`/ralph-review <path>` - Run in specified project directory (e.g., `/ralph-review projects/my-project`)

$ARGUMENTS

**Target directory:** If `$ARGUMENTS` is provided, all operations target that directory.
Verify the directory exists before proceeding.

## Instructions

You are reviewing Ralph's work after a session. Provide a clear summary of what was done and what remains.

### 0. Determine Target Directory

If `$ARGUMENTS` is provided:
1. Verify the directory exists
2. Use this as the target directory for all subsequent operations

If `$ARGUMENTS` is empty, use the current working directory.

All file paths and git commands below operate in/on the **target directory**.

### 1. Read Project State

Read these files from the target directory (in parallel):

- **`spec.md`** — The project specification
- **`progress.md`** — Task plan, completed work, failed attempts, iteration log
- **`AGENTS.md`** — Validation commands

### 2. Show Progress Summary

From `progress.md`, extract and display:

**Completed Tasks** (marked `[x]`):
- List each completed task with a one-line summary

**Incomplete Tasks** (marked `[ ]`):
- List remaining tasks

**Failed Attempts**:
- List any failed attempts with the approach tried and error

**Iteration Log**:
- Show the iteration log entries (commits, errors, etc.)

**Progress**: X of Y tasks completed (Z%)

### 3. Show Git Activity

If on a branch other than main, show what changed:

```bash
# Summary of changes
git -C <target-directory> diff main...HEAD --stat

# Recent commits
git -C <target-directory> log main..HEAD --oneline --no-decorate
```

If on main, show recent commits:
```bash
git -C <target-directory> log --oneline -10
```

### 4. Check Validation Status

If possible, run the validation commands from `AGENTS.md`:

```bash
# Quick check — just collect tests, don't run them all
cd <target-directory> && <validation commands from AGENTS.md>
```

Report any obvious issues.

### 5. Provide Recommendations

Based on the review, suggest one of:

**If all tasks complete and tests pass:**
```
All tasks completed! Ready to merge or ship.
```

**If tasks remain but progress was made:**
```
Progress made, but X tasks remain.

Options:
  1. Continue: ralph.sh -C <target-directory>
  2. Review and adjust spec.md, then continue
  3. Manually complete remaining tasks
```

**If stuck or failing:**
```
Build session encountered issues. Review the Failed Attempts
section in progress.md for details.

Consider:
  1. Simplifying the failing task
  2. Adding missing dependencies
  3. Adjusting spec.md to be more achievable
```

### 6. Offer Next Actions

Ask the user what they'd like to do:

> **What would you like to do?**
> 1. Continue the build session
> 2. View specific file changes
> 3. Adjust the spec and re-run
> 4. Something else?
