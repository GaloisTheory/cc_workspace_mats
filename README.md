# Shared Assistant Commands

Reusable Claude Code command prompts and workspace defaults.

This repository is intentionally small. It keeps command definitions and shared
configuration that can travel between projects, while project code, logs,
archives, virtual environments, and generated reports stay local or live in
their own repositories.

## Commands

The public slash commands live in `.claude/commands/`:

- `/code-deepdive` - produce a line-level engineering analysis of a code file
- `/code-learn` - work through a coding task with deliberate learning gaps
- `/pyenv-setup` - initialize a Python project environment with `uv`
- `/read-paper` - download and summarize an arxiv paper from source
- `/space-learn` - run a Socratic learning session and generate flashcards

## Skills

The shared skills live in `.claude/skills/` and are loaded at session startup
(restart your session to pick up newly added skills):

- `vault-capture` - write durable project memory (STATE.md + session note) into dohun_vault
- `vault-load` - onboard from dohun_vault with progressive, manifest-first loading

## Local State

The repo ignores local workspace state by default:

- `projects/` for cloned project repositories
- `.venv*/` and `.cache/` for environments and caches
- `.secrets` and `.claude/settings.local.json` for machine-specific settings
- `_local_archive/`, `logbook/`, `writeup/`, and `reports/` for generated or
  historical artifacts

Keep new project-specific commands in the relevant project repo unless they are
general enough to be reused across unrelated projects.
