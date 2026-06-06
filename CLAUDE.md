# Shared Assistant Commands

This repo stores reusable Claude Code command prompts and shared workspace
defaults. It should stay lightweight and project-agnostic.

## Repository Shape

- `.claude/commands/` contains public slash command prompts.
- `.claude/skills/` contains shared skills (currently the vault pair); these
  load at session startup, so restart a session to pick up newly added skills.
- `.claude/settings.json` contains sanitized shared defaults only.
- `projects/` is a local-only container for cloned repositories.
- `skills/` is reserved for optional local skills and keeps only `.gitkeep`
  tracked by default.

Do not add project code, model artifacts, logs, generated reports, virtual
environments, caches, or secrets to this repo.

## Public Commands

- `/code-deepdive` - line-level analysis of a script or module.
- `/code-learn` - scaffolded coding for deliberate practice.
- `/pyenv-setup` - Python environment setup with `uv`.
- `/read-paper` - arxiv source download and paper summary.
- `/space-learn` - Socratic learning session with flashcard output.

## Public Skills

- `vault-capture` - write project memory (STATE.md + session note) into dohun_vault.
- `vault-load` - progressive, manifest-first onboarding from dohun_vault.

## Maintenance Guidelines

- Keep commands generic. If a command depends on a specific project, dataset,
  machine path, or collaborator workflow, keep it in that project instead.
- Keep personal hooks, notification topics, API keys, and machine-specific
  paths in `.claude/settings.local.json` or shell config, not tracked files.
- When adding a command, document it in both `README.md` and this file.
- Before committing, check for leaked specificity with:

```bash
rg -n "TOKEN|SECRET|API_KEY|https://.*@" README.md CLAUDE.md .claude
```

Some generic setup commands may mention environment variable names as examples;
actual secret values must never be tracked.
