---
name: run-lora-execute
description: Execute a reviewed AFT / stacked-LoRA training recipe on Modal. Takes a recipe PR (number) or a configs/aft_runs/*.json path, resolves the merged main commit as the Modal --git-ref, shows the resolved --execute plan plus a rough GPU cost estimate, waits for an explicit in-session confirmation, then runs training and HF verification — and, when asked, continues to evals / grading / aggregation / uploads / plots with a confirm gate before each paid or irreversible stage. Spends real money, so every paid step is gated. Use when the user wants to actually run / launch / kick off a recipe on Modal, execute a merged training PR, or continue the post-training eval/plot pipeline. The sibling /run-lora-training authors the recipe and PR; this skill runs it.
---

# Run LoRA Execute — Recipe Execution

The **back half** of the workflow. Input is a recipe that has already been
authored and reviewed (ideally merged) via `/run-lora-training`. This skill
resolves provenance, previews the real commands, **confirms before every paid
Modal step**, then executes. It costs real GPU money and writes to a shared HF
repo, so the confirmation gates are mandatory, not optional.

The runner is `tools/run_aft_recipe.py`. Steps it understands (via `--step`):
`train`, `verify`, `eval`, `grade`, `aggregate`, `upload`, `plot`. Selection
can also be narrowed with `--job <id>`.

## Phase 0: Locate the repo, resolve input + provenance

This skill lives in the shared `cc_workspace_mats` repo but operates on the
`midtraining_generalization` project. Sessions are often rooted in the
workspace, so first locate the project repo root (the dir containing
`tools/run_aft_recipe.py`): use the current directory if it qualifies, else
`projects/midtraining_generalization/` beneath the workspace root (do not
hardcode the `/mnt/...` prefix — the mount name differs per machine), else ask.
`cd` into that repo root; run every command below and all `gh`/`git`
operations from there.

1. Accept either a PR number (`/run-lora-execute 71`) or a config path. From a
   PR, find the changed `configs/aft_runs/*.json` via `gh pr view <n> --json files`.
2. Determine the Modal `--git-ref` — **provenance matters because Modal clones
   the repo at this ref and runs that code, not your working tree:**
   - Preferred: the PR is **merged**. Use the merge commit / current `main` SHA
     (`gh pr view <n> --json mergeCommit,merged,state`, or
     `git rev-parse origin/main` after `git fetch`). This is the intended path —
     the recorded ref is exactly what was reviewed and merged.
   - If the PR is **not merged**, warn clearly that artifacts will reference an
     unmerged commit, and ask the user whether to (a) wait for merge
     [recommended], or (b) proceed against the PR branch head SHA. Only proceed
     on an explicit choice.
   - Resolve to a concrete 40-char SHA, never a moving ref like `main`.
3. Re-validate the recipe before spending anything:
   ```
   PYTHONPATH=src uv run python -c "from tools import run_aft_recipe as r; rec=r.load_recipe('<config>'); r.validate_recipe(rec); print('OK')"
   ```
   A validation failure aborts the run.

## Phase 1: Preview the real plan (still no spend)

1. Dry-run with the **resolved SHA** and write a manifest for the record:
   ```
   PYTHONPATH=src uv run python tools/run_aft_recipe.py <config> --dry-run --git-ref <SHA> --step train --step verify --manifest-out results/manifests/<name>_train.json
   ```
   (Add the downstream steps the user wants to the same or a later preview.)
2. Show the user:
   - the exact `--execute` command(s) that will run,
   - the resolved `--git-ref` SHA and the PR/merge status,
   - a **rough cost estimate**: GPU type (default H100) × number of Modal jobs
     × the per-job `timeout` cap (default 7200s = 2h is a ceiling, not the
     expected runtime) — state explicitly that it's an upper-bound guess,
   - whether `push_hf` is on (writes to `GaloisTheory123/MSM-hillclimb`, may
     overwrite existing artifacts).

## Phase 2: Train (gated)

1. **Require an explicit in-session "go"** from the user before the first paid
   step. A prior approval (e.g. merging the PR) is **not** consent to spend —
   ask here, every time.
2. Run training, scoped to the train step (and a specific `--job` if the user
   wants only one):
   ```
   PYTHONPATH=src uv run python tools/run_aft_recipe.py <config> --execute --git-ref <SHA> --step train
   ```
   Stream output. If a Modal job fails, stop and report — do not silently
   continue to later steps (the runner uses `check=True`, so a failure raises;
   surface it).
3. After training, run the in-config HF verification:
   ```
   PYTHONPATH=src uv run python tools/run_aft_recipe.py <config> --execute --git-ref <SHA> --step verify
   ```
   This checks that every expected adapter file exists on HF and that the
   recorded metadata (seed, epochs, lora_config_name, dataset_*, and the pinned
   hyperparameters) matches the recipe. Report pass/fail explicitly. Note that
   verification checks **metadata identity, not weight hashes or final loss** —
   if the user needs bitwise/loss-level confirmation (e.g. reproducing a prior
   run), do that separately and say so.

## Phase 3: Downstream pipeline (each stage separately gated)

Only if the user asked to continue past training. Run in dependency order,
**confirming before each paid or irreversible stage**:

- `--step eval` — paid Modal generation. Gate + cost note.
- `--step grade` — local grading chunks (may call a paid grader/LLM; check).
- `--step aggregate` — local aggregation.
- `--step upload` — **irreversible**: pushes eval results to HF under the
  recipe's `source_key`s. Gate explicitly; name the destination.
- `--step plot` — local figure generation into `notebooks/figures/...`.

Prefer running one stage, confirming its output looks right, then proceeding —
rather than firing the whole chain blind. Write a manifest (`--manifest-out`)
for each executed stage so there's a durable record of exactly what ran at
which SHA.

## Phase 4: Report

Summarize: SHA run against, which steps executed, train losses / job counts
from the Modal output, verification result, any HF uploads (with destinations),
and where plots landed. Link the Modal app URL(s) from the run output.

## Guardrails (non-negotiable)

- **Confirm before every paid step**, every time, in-session. Merging the PR is
  authorization to *consider* running, not to spend.
- Always run against a concrete resolved SHA, defaulting to the merged `main`
  commit. Warn loudly if running against an unmerged branch.
- Never merge or close PRs. If the PR isn't merged and the user wants the clean
  path, hand back and let them merge.
- Preview (dry-run) before execute, so the user sees the real command and SHA.
- On any Modal failure, stop and report — never paper over a failed job or
  continue to dependent steps.
- Don't disable `push_hf` or change recipe values on the fly to "make it work";
  if the recipe is wrong, send the user back to `/run-lora-training`.
