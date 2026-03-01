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

## Scaffolded Coding (`/code-learn`)

A slash command for learning-by-doing: Claude writes code with deliberate gaps for unfamiliar concepts, reviews your solutions, and generates a learning log.

### Usage

```
/code-learn implement a LoRA fine-tuning loop
/code-learn add evaluation harness to this project
/code-learn                                        # prompts for task
```

### What it does (5 phases)

0. **Setup & Calibration** — discovers context (imports, related files), asks which concepts you're comfortable with via multiSelect interview
1. **Collaborative Plan** — generates annotated step plan:
   - **[scaffold]** — unfamiliar concepts: code with TODO gaps for you to fill
   - **[review]** — partially familiar: complete code with prediction questions first
   - **[implement]** — familiar: Claude writes freely
2. **Scaffolded Implementation** — core loop: writes files with `TODO(learn)` placeholders, you edit in your IDE, say `"check"` for review
3. **Checkpoint Questions** — conceptual synthesis questions every 2-3 scaffolded steps
4. **Learning Log** — generates markdown with stats, key decisions, misconceptions, checkpoint Q&A, and flashcard seeds for `/space-learn`

### Commands during a session

| Command | What it does |
|---------|-------------|
| `"check"` | Claude reads your file edits and reviews them |
| `"hint"` | Progressive hint (3 levels before suggesting reveal) |
| `"show me"` | Reveal solution with full explanation |
| `"faster"` | Switch to normal Claude Code for current section |
| `"learn"` | Switch back to learning mode |

### Key design points

- Gaps target **unfamiliar** concepts (based on calibration) — familiar code is written normally
- TODO comments explain what concept they test, not what code to write
- Review is Socratic: incorrect answers get diagnostic questions, not corrections
- Learning log includes line-number references and actual user answers
- Flashcard seeds are compatible with `/space-learn` for Anki generation

### Key File

- `.claude/commands/code-learn.md` — the skill prompt

## Read Paper (`/read-paper`)

A slash command that downloads an arxiv paper's LaTeX source and produces a focused markdown summary with actual claims, methods, and results from the paper.

### Usage

```
/read-paper https://arxiv.org/abs/2601.07372   # summarize a paper
/read-paper 2601.07372 --fast                   # skip interview, general summary
/read-paper                                      # prompts for URL
```

### What it does (5 phases)

1. **Parse & Download** — extracts arxiv ID from any URL format, downloads LaTeX source via `e-print` API, caches at `~/.cache/arxiv/{id}/`. Handles both tarballs and single-file submissions.
2. **Read & Skim** — finds the entrypoint (`\documentclass`), follows `\input`/`\include` recursively, extracts title/authors/abstract/sections
3. **Interview** (skipped with `--fast`) — asks which sections to focus on (multiSelect) and reading context (implementing, comparing, survey, reading group)
4. **Summary** — generates markdown with mandatory sections (Abstract, Core Contribution, Methodology, Key Results, Limitations) plus adaptive sections (Theoretical Framework, Ablations, Discussion Questions, etc.)
5. **Output** — saves to `papers/summary_{topic_tag}.md` with collision handling

### Key design points

- Downloads **LaTeX source** (not PDF) for precise extraction of equations, tables, and claims
- Source cached permanently at `~/.cache/arxiv/` — repeat reads are instant
- Interview context shapes depth: "implementing" gets extra methodology detail, "reading group" gets discussion questions
- Quality bar: actual numbers from the paper, real abstract (not paraphrased), zero hallucinated results
- Key equations preserved in LaTeX math notation (`$...$`)

### Key File

- `.claude/commands/read-paper.md` — the skill prompt

## Progress Reports (`/report`)

A slash command that generates structured progress reports for MATS research projects and saves them to the shared logbook repo (`projects/logbook`).

### Usage

```
/report projects/SURF          # report on a specific project
/report                        # prompts for project path
```

### What it does (5 phases)

1. **Read & Discover** — reads project key files (`CLAUDE.md`, `progress.md`, etc.), discovers notebooks, scripts, figures, and result files. Determines next report number.
2. **Interview** — asks about report focus, key findings, figures to include, surprises/failures, and next steps
3. **Draft Report** — generates a polished report with mandatory sections:
   - **Context**, **Numbered Results** (with inline figures), **Surprises & Failures**, **Key Hypotheses & Next Steps**, **Experimental Configuration** (auto-filled from configs), **Reproducibility**, **Files**
4. **Review & Finalize** — presents draft for review, iterates on feedback, copies figures to logbook
5. **Commit** — stages and commits in the logbook repo (does NOT push)

### Naming convention

- Reports: `DL/NNN_project_slug.md` (e.g., `DL/001_surf_red_teaming.md`)
- Figures: `DL/figures/NNN_descriptive_name.png` (prefixed with report number)

### Key design points

- Synthesizes project files AND user input into coherent prose (not just bullet lists)
- Experimental Configuration table auto-populated from config files and argparse defaults
- Reproducibility section includes commands to regenerate each figure
- Figure references verified against actual copied files before committing

### Key File

- `.claude/commands/report.md` — the skill prompt

## DARE Workflow Commands

Three slash commands for the DARE attribution → retrain → eval cycle. Designed for repeated use across multiple machines.

### `/run-attribution-llm-judge`

Launch LLM judge attribution scoring on training documents. Interactive setup: picks behaviors, judge model, workers, prompt mode, then launches parallel tmux sessions (one per behavior).

```
/run-attribution-llm-judge                # interactive setup + launch
/run-attribution-llm-judge check          # monitor running sessions
```

### `/check-results`

Analyze completed attribution scores. Summary stats, score distributions, top-k/bottom-k docs with reasoning, issue detection (all-zeros, high failures), and filtering threshold selection.

```
/check-results judge_gemini_flash         # analyze a specific run
/check-results                            # prompts for which run
```

### `/retrain-eval`

Filter training data based on attribution scores, retrain LoRA adapter, and run behavioral evals. Guides through top-k selection, launches retraining via tmux, then evals with baseline comparison.

```
/retrain-eval                             # interactive setup
/retrain-eval check                       # monitor retraining/eval progress
```

### Key design points

- **First-run protocol** — each command verifies environment, launches subagents to check assumptions, and monitors early output before trusting the process
- **Learnings section** — each command file has a `## Learnings` section that accumulates environment-specific notes (e.g., "litmus submodule must be initialized")
- **Key files:** `.claude/commands/run-attribution-llm-judge.md`, `.claude/commands/check-results.md`, `.claude/commands/retrain-eval.md`

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

**Always clarify ambiguous requests before implementing.** If a request is even remotely unclear — the scope, the desired UX, what "done" looks like — ask the user to clarify rather than guessing. Getting the right thing built on the first try is far more valuable than shipping something fast that misses the point.