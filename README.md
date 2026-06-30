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

- `code-redteam` - adversarial red-team review of a code file (research-validity
  focus): severity-ranked findings, exhaustive parameter/silent-choice inventory,
  markdown report with executive summary
- `vault-capture` - write durable project memory (STATE.md + session note) into dohun_vault
- `vault-load` - onboard from dohun_vault with progressive, manifest-first loading
- `run-lora-training` - author an AFT/stacked-LoRA training recipe and open a PR
  for review (interview -> validated `configs/aft_runs/*.json` -> dry-run -> PR;
  spends nothing, never merges). Targets the `midtraining_generalization` repo.
- `run-lora-execute` - execute a reviewed recipe PR on Modal: resolve the merged
  main SHA as `--git-ref`, preview the plan + rough cost, confirm before every
  paid step, run training + HF verification, then optionally the eval/plot
  pipeline. Targets the `midtraining_generalization` repo.
- `plot-eval-results` - drive `tools/eval_results_plotting.py`: interview for the
  wanted figure, classify it as regenerate / new-figure-of-an-existing-type /
  new-shape, render it with the pinned-HF + byte-diff guardrails, and self-review
  to improve the skill each use. Targets the `midtraining_generalization` repo.
- `plot-training-dynamics` - drive `tools/plot_training_dynamics.py`: render the
  interactive HTML training-dynamics viewer (loss, per-step direction lock-in,
  magnitude growth, cross-run geometry, gradient origin) from per-step LoRA traces
  (local dir or pinned `hf:<repo>@<sha>/<subfolder>`); one run or two to diff.
  Targets the `midtraining_generalization` repo.

### Codex sync

The shared skills are shared with Codex via symlink so there is one canonical
copy (this repo) and no drift. On a fresh machine, run:

```bash
bash scripts/link-codex-skills.sh
```

This points `~/.codex/skills/{vault-load,vault-capture,code-redteam,run-lora-training,run-lora-execute,plot-eval-results,plot-training-dynamics}`
at the repo's `.claude/skills/` dirs (idempotent; backs up any existing real dirs).
Restart Codex afterward to pick up the skills.

## Local State

The repo ignores local workspace state by default:

- `projects/` for cloned project repositories
- `.venv*/` and `.cache/` for environments and caches
- `.secrets` and `.claude/settings.local.json` for machine-specific settings
- `_local_archive/`, `logbook/`, `writeup/`, and `reports/` for generated or
  historical artifacts

Keep new project-specific commands in the relevant project repo unless they are
general enough to be reused across unrelated projects.
