# Shared Assistant Commands

This repo stores reusable Claude Code command prompts and shared workspace
defaults. It should stay lightweight and project-agnostic.

## Repository Shape

- `.claude/commands/` contains public slash command prompts.
- `.claude/skills/` contains shared skills (the vault pair, code-redteam, and
  the run-lora-training/run-lora-execute pair);
  these load at session startup, so restart a session to pick up newly added
  skills.
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

- `code-redteam` - adversarial red-team review of a code file: research-validity
  findings ranked by severity, parameter/silent-choice inventory, MD report.
- `vault-capture` - write project memory (STATE.md + session note) into dohun_vault.
- `vault-load` - progressive, manifest-first onboarding from dohun_vault.
- `run-lora-training` - author an AFT/stacked-LoRA training recipe + open a PR
  (no spend, never merges). Project-specific to `midtraining_generalization`.
- `run-lora-execute` - execute a reviewed recipe PR on Modal with confirm-before-
  spend gates. Project-specific to `midtraining_generalization`.

The `run-lora-*` pair is an intentional exception to the "keep commands generic"
rule below: they live here for cross-agent discoverability but target one repo,
so they locate `projects/midtraining_generalization` at runtime rather than
assuming the cwd.

These skills are the single canonical copy. Codex consumes them via symlink
(`~/.codex/skills/{vault-load,vault-capture,code-redteam,run-lora-training,run-lora-execute}` → `.claude/skills/...`), set up by
`scripts/link-codex-skills.sh` — so edit the skill once here and both agents see
it. Keep the `agent`/`last_agent` template fields runtime-neutral so the shared
files read correctly for either agent.

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
