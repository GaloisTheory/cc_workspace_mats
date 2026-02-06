# Initialize Ralph in a Project

Set up Ralph and define what to build through an interactive interview.

## Usage

`/ralph-init` - Run in current directory
`/ralph-init <path>` - Run in specified project directory (e.g., `/ralph-init projects/my-project`)

$ARGUMENTS

**Target directory:** If `$ARGUMENTS` is provided, all operations target that directory.
Verify the directory exists before proceeding. If it doesn't exist, ask the user if they want to create it.

## Instructions

### Step 1: Determine Target Directory

If `$ARGUMENTS` is provided:
1. Check if the directory exists
2. If not, ask user if they want to create it
3. Use this as the target directory for all subsequent operations

If `$ARGUMENTS` is empty, use the current working directory.

All file paths below are relative to the **target directory**.

### Step 2: Verify Git Repository

Check if the target directory is in a git repository:
```bash
git -C <target-directory> rev-parse --show-toplevel
```

If not a git repo, warn the user and ask if they want to initialize one.

### Step 3: Interactive Interview

#### 3a. Ask the main question:

> **What do you want to build?**
> Describe the main goal or problem you're solving.

Listen for the core outcome, who benefits, and why it matters.

#### 3b. Ask 3-5 clarifying questions (adapt to what they're building):

1. **Scope**: "What's explicitly OUT of scope? What should this NOT do?"
2. **Users/Consumers**: "Who or what will use this? (humans, other code, APIs)"
3. **Constraints**: "Are there specific technologies, patterns, or dependencies to use or avoid?"
4. **Success Criteria**: "How will you know this is working correctly? What are the acceptance criteria?"
5. **Edge Cases**: "What are the tricky scenarios or error cases to handle?"

Don't ask irrelevant questions. Adapt to the project.

#### 3c. Ask about validation:

> **How should we validate the code?** What commands should run after each change?
> (e.g., pytest, mypy, ruff, npm test, cargo test, make check)

Get specific, runnable commands — not vague descriptions.

### Step 4: Generate Files

Check if each file exists first. **Never overwrite existing files** — warn and skip instead.

#### `<target-directory>/spec.md`

Generate a single, detailed specification:

```markdown
# <Project Name>

## Description
[2-3 paragraphs explaining what this project does and why]

## Requirements
- [ ] Requirement 1 (behavioral — WHAT it should do, not HOW)
- [ ] Requirement 2
- [ ] Requirement 3
...

## Acceptance Criteria
- [ ] Given X, when Y, then Z
- [ ] Given A, when B, then C
...

## Non-Goals
- Thing this project explicitly does NOT handle
- Another out-of-scope item

## Technical Constraints
- Relevant libraries, patterns, or constraints
- Dependencies
- Known challenges or risks
```

Guidelines:
- Write behavioral requirements (WHAT to verify)
- Use Given/When/Then for acceptance criteria
- Be specific about edge cases
- Include non-goals to prevent scope creep
- Do NOT prescribe implementation details (HOW to build)

#### `<target-directory>/progress.md`

Create with empty structure:

```markdown
# Progress

## Plan

[No plan yet — first iteration will analyze codebase and create task breakdown]

## Completed Work

[None yet]

## Failed Attempts

[None yet]

## Iteration Log

[Entries added by ralph.sh during execution]
```

#### `<target-directory>/AGENTS.md`

Populate with the actual validation commands from the interview:

```markdown
# AGENTS.md - Operational Guide

## Build & Run

​```bash
<actual install/build commands from interview>
​```

## Validation

Run these after each change to verify your work:

​```bash
<actual validation commands from interview>
​```

## Operational Notes

<!-- Ralph will add patterns discovered during implementation here -->

## Codebase Patterns

<!-- Ralph will add codebase-specific patterns here -->
```

### Step 5: Print Summary

```
Ralph initialized in <target-directory>

Created:
  - spec.md (X requirements, Y acceptance criteria)
  - progress.md
  - AGENTS.md (with validation commands)

Skipped (already exist):
  - <any files that were skipped>

Next step:
  Run ralph.sh in a separate terminal:

    ralph.sh -C <target-directory>
```

## Example Interaction

**User**: `/ralph-init projects/retry-lib`

**Claude**: What do you want to build?

**User**: A Python library for retrying failed function calls with exponential backoff.

**Claude**: Got it! A few questions:
1. Should this work with both sync and async functions?
2. What customization do users need? (max retries, backoff strategy, etc.)
3. Any existing libraries to be compatible with or avoid duplicating?
4. How should we validate? What test/lint commands should run?

**User**: [answers]

**Claude**: *[Generates spec.md, progress.md, AGENTS.md with real content]*

```
Ralph initialized in projects/retry-lib

Created:
  - spec.md (8 requirements, 5 acceptance criteria)
  - progress.md
  - AGENTS.md (pytest, mypy, ruff)

Next step:
  Run ralph.sh in a separate terminal:

    ralph.sh -C projects/retry-lib
```
