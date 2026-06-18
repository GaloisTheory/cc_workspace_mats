---
name: run-lora-execute
description: Execute a reviewed AFT / stacked-LoRA training recipe on Modal. Takes a recipe PR (number) or a configs/aft_runs/*.json path, resolves the merged main commit as the Modal --git-ref, shows the resolved --execute plan plus a rough GPU cost estimate, waits for an explicit in-session confirmation, then runs training and HF verification. It asks whether to continue through evals, grading, aggregation, HF uploads, plotting, and a final PR/push of source-config/plot changes; the default answer is yes, but every paid or irreversible stage remains gated. Spends real money, so every paid step is gated. Use when the user wants to actually run / launch / kick off a recipe on Modal, execute a merged training PR, or continue the post-training eval/plot pipeline. The sibling /run-lora-training authors the recipe and PR; this skill runs it.
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

Default automation scope: ask the user whether to run the whole downstream
pipeline after training (`eval` -> `grade` -> `aggregate` -> `upload` ->
`plot`) and recommend yes when those sections exist in the recipe. This is a
scope decision, not spend authorization: still confirm before each paid Modal
stage, paid grader call, irreversible HF upload, and final PR/push.

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
4. Inspect the recipe's `gpu`, `push_hf`, `export_root`, `uploads`, and
   `plots` fields. Confirm the recorded GPU type/count and Hugging Face
   destinations with the user instead of silently accepting surprising values.
   Adapter uploads go to `GaloisTheory123/MSM-hillclimb`; eval uploads use
   `configs/eval_results_sources.json` (default dataset repo
   `GaloisTheory123/MSM_activations`).

## Phase 1: Preview the real plan (still no spend)

1. Ask the downstream scope question before previewing. Default: include
   `train`, `verify`, and all recipe-defined `eval`, `grade`, `aggregate`,
   `upload`, and `plot` steps. If the user declines, preview only the selected
   steps. If a desired downstream section is absent from the recipe, stop and
   explain that the recipe needs a config/code PR before execution.
2. Dry-run with the **resolved SHA** and write a manifest for the record:
   ```
   PYTHONPATH=src uv run python tools/run_aft_recipe.py <config> --dry-run --git-ref <SHA> --step train --step verify --manifest-out results/manifests/<name>_train.json
   ```
   (Add the downstream steps the user wants to the same or a later preview.)
3. Show the user:
   - the exact `--execute` command(s) that will run,
   - the resolved `--git-ref` SHA and the PR/merge status,
   - a **rough cost estimate**: GPU type (default H100) × number of Modal jobs
     × the per-job `timeout` cap (default 7200s = 2h is a ceiling, not the
     expected runtime) — state explicitly that it's an upper-bound guess,
   - whether `push_hf` is on (writes adapters to
     `GaloisTheory123/MSM-hillclimb`, may overwrite existing artifacts),
   - eval upload destinations: each `source_key`, resolved HF dataset path,
     and whether its revision is already pinned or still `PIN_AFTER_UPLOAD`,
   - plot keys and output directories.

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

## Phase 3: Downstream pipeline (default yes, each stage gated)

Run this phase if the user accepted the downstream scope question (default yes)
or explicitly asks to continue past training. Run in dependency order,
**confirming before each paid or irreversible stage** and stopping on failure:

- `--step eval` — paid Modal generation. Gate + cost note.
- `--step grade` — local grading chunks (may call a paid grader/LLM; check).
- `--step aggregate` — local aggregation.
- `--step upload` — **irreversible**: pushes eval results to HF under the
  recipe's `source_key`s. Gate explicitly; name the destination. Capture the
  commit SHA printed by `tools/upload_hf_folder.py` for each source key.
- Pin uploaded eval sources. After upload, update
  `configs/eval_results_sources.json`, replacing each uploaded source's
  `PIN_AFTER_UPLOAD` (or stale revision, after confirming) with the concrete
  dataset commit SHA printed by the upload helper. Do this before plotting.
- Prepare plotting. All new/changed plotting must be implemented in
  `tools/eval_results_plotting.py`, following its existing conventions:
  declare source-backed plot specs, download CSVs from Hugging Face through
  `configs/eval_results_sources.json`, require concrete pinned revisions, and
  fail fast on missing model/eval rows. Do not make plots by reading local
  result directories directly. If the recipe's `plots[*].plot` key does not
  exist yet, add the minimal plot spec/selection change to that file before
  running the plot step.
- `--step plot` — local figure generation into `notebooks/figures/...`, using
  the pinned HF sources above.

Prefer running one stage, confirming its output looks right, then proceeding —
rather than firing the whole chain blind. Write a manifest (`--manifest-out`)
for each executed stage so there's a durable record of exactly what ran at
which SHA.

## Phase 4: Final PR / cleanup (default yes, gated)

After the run and plots are complete, show the user the local diff and ask for
explicit confirmation to commit, push, and open a PR. Default recommendation:
yes, if there are source-config pins, plotting-code changes, generated figures,
or manifests that should be reviewed.

1. Create or switch to a `codex/...` branch; never commit on `main`.
2. Include only intentional artifacts: usually `configs/eval_results_sources.json`
   revision pins, `tools/eval_results_plotting.py` changes, generated figures
   that repo conventions already track, and relevant manifests. Do not commit
   bulky raw eval result directories unless the user explicitly asks.
3. Commit with the repo's co-author trailer convention, push, and open a PR.
   The PR body should summarize the executed SHA, Modal steps, HF upload
   destinations + pinned revisions, plot keys, and output figure paths.
4. Delete only temporary git worktrees that this workflow created, and only
   after confirming they have no uncommitted work needed for the PR. Never
   delete user-created or ambiguous worktrees.

## Phase 5: Report

Summarize: SHA run against, which steps executed, train losses / job counts
from the Modal output, verification result, any HF uploads (with destinations
and pinned revisions), where plots landed, PR URL if created, and any worktrees
removed. Link the Modal app URL(s) from the run output.

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
- Do not silently choose GPU count/type or Hugging Face destinations; confirm
  what the recipe records before spend.
- Do not plot from local eval outputs. Plot by updating
  `tools/eval_results_plotting.py` and `configs/eval_results_sources.json` so
  figures are reproducible from pinned Hugging Face uploads.
