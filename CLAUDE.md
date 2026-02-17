# MATS Workspace

Shared resources and configuration for MATS projects.

## Structure

- `ralph/` - Ralph Wiggum autonomous development loop (prompts, templates, main script)
- `skills/` - Reusable Claude Code skills
- `projects/` - Cloned repositories (gitignored, each has its own git history)

## Organization Guidelines

**Project-specific content:** Anything specific to a particular research project should live inside the `projects/<project-name>/` folder within that project's own git repository.

**Workspace-level content:** Only shared resources, reusable skills, and general configuration that applies across multiple projects should live at the workspace root level.

## Ralph Wiggum (Autonomous Development Loop)

This workspace includes the Ralph Wiggum autonomous development methodology.
Ralph is an external bash loop that iteratively feeds prompts to Claude Code
in headless mode, with fresh context each iteration.

### Two-Step Workflow

```
Terminal 1 (interactive):  /ralph-init projects/my-app
                           → Interview: what to build, validation commands
                           → Creates spec.md, progress.md, AGENTS.md

Terminal 2 (autonomous):   ralph.sh -C projects/my-app
                           → Loop: reads spec + progress, implements one task per iteration
                           → Stops when spec is satisfied or max iterations reached

Terminal 1 (optional):     /ralph-review projects/my-app
```

### Quick Reference

- `/ralph-init` — Initialize Ralph + interactive interview (creates spec.md, progress.md, AGENTS.md)
- `/ralph-review` — Review Ralph's work after a session
- `ralph.sh` — Run the autonomous loop (in a separate terminal)
- `ralph.sh status` — Show current Ralph state
- `ralph.sh cleanup` — Remove merged worktree branches

### Key Files (in target projects)

- `spec.md` — Project specification (what to build)
- `progress.md` — Task plan, completed work, failed attempts, iteration log
- `AGENTS.md` — Validation commands and operational notes

### Key Files (in workspace)

- `ralph/ralph.sh` — Main loop script
- `ralph/prompts/PROMPT_loop.md` — Unified prompt for each iteration
- `ralph/templates/AGENTS.md.template` — Template for new projects

### Principles

- Each iteration gets fresh context (external loop, not plugin)
- One task per iteration, commit on success
- `progress.md` is shared state between iterations (updated by both Claude and the bash script)
- Failed attempts are recorded so the next iteration tries a different approach
- `AGENTS.md` captures operational learnings
- Slash commands run interactively; `ralph.sh` runs in a separate terminal

## Code Deep Dive (`/code-deepdive`)

A slash command that produces expert-level, line-by-line analysis of any script. Think "senior engineer onboarding document."

### Usage

```
/code-deepdive path/to/script.py
/code-deepdive                      # prompts for file path
```

### What it does (4 phases)

1. **Read & Discover** — reads the target file, auto-discovers imports, alternative implementations, callers, and referenced configs
2. **Interview** — presents focus areas found in the code (multiSelect), asks about comparisons with related files
3. **Deep Analysis** — produces mandatory + adaptive sections:
   - **Mandatory:** Big Picture, Data Flow, Silent Choices, Edge Cases & Gotchas, Key Lines Reference
   - **Adaptive:** Multi-GPU Architecture, Comparison with Alternative, API/Library Usage, Resume System, etc. (only included when relevant)
4. **Output** — saves a `<SCRIPT_NAME>_DEEPDIVE.md` markdown file (asks user for path)

### Key design points

- **Silent Choices** is the most important section — documents every implicit decision (truncation, defaults, ignored fields, ordering effects, type conversions, missing validation, etc.)
- Line number citations throughout — every claim references specific lines
- Adaptive sections prevent bloat — a 50-line utility won't get a Multi-GPU Architecture section
- Quality bar: 8+ silent choices, 5+ edge cases, concrete data examples (not abstract descriptions)

### Key File

- `.claude/commands/code-deepdive.md` — the skill prompt

## Claude Code Notifications

This workspace has hooks configured to send push notifications when Claude finishes a response (Stop hook).

### Setup (one-time per machine)

1. **Install jq** (if not installed):
   ```bash
   apt-get install -y jq  # Linux
   brew install jq        # macOS
   ```

2. **Subscribe to notifications** at: `https://ntfy.sh/claude-dohun-7d57c012`
   - Open in browser, or install ntfy app on phone

3. **`CLAUDE_NTFY_TOPIC`** is exported in `~/.bashrc` (before the interactive guard, so hooks can access it):
   ```bash
   export CLAUDE_NTFY_TOPIC="claude-dohun-7d57c012"
   ```

### Per-terminal tab naming (optional)

Set a custom name for each terminal to identify which tab needs attention:
```bash
export CLAUDE_TAB_NAME="my-task-name"
```

Notifications will show: `[my-task-name]: Claude needs your attention`

### How it works

- Hook config: `.claude/settings.json`
- Hook script: `.claude/hooks/notify-input-needed.sh`
- Hook type: `Stop` (fires when Claude finishes responding and needs input)

## Environment Health Check (GPU Box)

**On every new conversation**, if this looks like a GPU workspace (i.e. `/workspace` exists), verify the following environment variables are exported and available to child processes. If any are missing, alert the user and offer to fix them.

### Required Environment Variables

| Variable | Expected Value | Source |
|----------|---------------|--------|
| `HF_HOME` | `/workspace/.cache/huggingface` | Prevents re-downloading models (~55GB for gemma-3-27b) |
| `HUGGINGFACE_HUB_CACHE` | `/workspace/.cache/huggingface` | Same as above (legacy compat) |
| `TRANSFORMERS_CACHE` | `/workspace/.cache/huggingface` | Same as above (legacy compat) |
| `OPENROUTER_API_KEY` | from `/workspace/.secrets` | API access |
| `HF_TOKEN` | from `/workspace/.secrets` | Gated model downloads |
| `GITHUB_TOKEN` | from `/workspace/.secrets` | Git push access |
| `CLAUDE_NTFY_TOPIC` | `claude-dohun-7d57c012` | Push notifications via ntfy.sh |

### How to Fix

If variables are missing, it means `startup.sh` was run as a script (subshell) rather than sourced, or the bashrc block is missing. Fix with:

```bash
# Immediate fix for current shell
set -a && source /workspace/.secrets && set +a
export HF_HOME=/workspace/.cache/huggingface
export HUGGINGFACE_HUB_CACHE=/workspace/.cache/huggingface
export TRANSFORMERS_CACHE=/workspace/.cache/huggingface
export CLAUDE_NTFY_TOPIC="claude-dohun-7d57c012"
```

### Key Files

- `/workspace/.secrets` — API keys (GITHUB_TOKEN, HF_TOKEN, OPENROUTER_API_KEY)
- `/workspace/startup.sh` — Run once per machine boot; persists env to `~/.bashrc`

### Learnings

- `startup.sh` runs in a **subshell** — its `export`s don't propagate to interactive terminals. The fix is to also write the exports into `~/.bashrc`.
- `source /workspace/.secrets` alone doesn't export — use `set -a` / `set +a` around it.
- Without `HF_HOME` set, HuggingFace downloads models to `~/.cache/` (ephemeral storage) instead of `/workspace/.cache/` (persistent), causing multi-GB re-downloads on every restart.

### Misc 
When asked to modify or update a system (e.g., skills, scripts, configs), identify ALL files that need changes upfront. Do not update some files and forget others — think through the full dependency chain before starting.

When exploring a codebase to debug an issue, timebox exploration to 2-3 minutes. If you haven't converged on a root cause, present your findings and ask the user for direction rather than continuing to dig.