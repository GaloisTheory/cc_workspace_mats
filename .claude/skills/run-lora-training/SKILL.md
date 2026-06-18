---
name: run-lora-training
description: Author a new AFT / stacked-LoRA training recipe and open a PR for review. Interviews you for the dataset, LoRA config, source variants, seeds, GPU type/count, Hugging Face adapter/eval upload layout, downstream eval/plot scope, and hyperparameters; generates a validated configs/aft_runs/*.json recipe; runs the recipe runner in --dry-run to show the exact Modal commands; then opens a PR and stops. Spends no money and never runs Modal. Use when the user wants to set up / launch / kick off a new LoRA or AFT training run, add a new dataset/config to train on, create a new run recipe, or "run LORA training". The sibling /run-lora-execute takes the merged PR and actually runs it on Modal.
---

# Run LoRA Training — Recipe Authoring

Turn a training intent into a reviewed, validated recipe. This skill is the
**front half** of the workflow: interview → generate config → validate →
dry-run → open PR → **stop**. It must **never** run Modal, never spend GPU
money, and never merge. Execution is the job of `/run-lora-execute`, which
runs only after a human reviews and (per the user's preference) merges the PR.

The recipe runner is `tools/run_aft_recipe.py`; recipes live in
`configs/aft_runs/*.json`. Two existing recipes are the canonical templates:
`l7_r1_epoch3_seed_replicates.json` and `l11_r1_epoch3_checkpoints.json`. Read
at least one before generating a new one.

All commands assume the repo root of `midtraining_generalization` and the
`PYTHONPATH=src uv run ...` convention used throughout the repo.

Never make silent resource or artifact-placement decisions. The recipe is the
reviewable contract for GPU shape and Hugging Face destinations, so ask first
and then write the agreed values explicitly.

## Phase 0: Locate the repo

This skill lives in the shared `cc_workspace_mats` repo but operates on the
`midtraining_generalization` project. Sessions are often rooted in the
workspace, so do not assume the current directory is the project.

1. Find the project repo root (the dir containing `tools/run_aft_recipe.py`):
   - if the current directory has it, use that;
   - else look for `projects/midtraining_generalization/` beneath the workspace
     root (do not hardcode the `/mnt/...` prefix — the mount name differs per
     machine);
   - else ask the user for the path.
   `cd` into that repo root and run every command below from there.
2. Read the schema source of truth so values are valid against the *current*
   registries (they change over time — never hardcode from memory):
   - `tools/run_aft_recipe.py` — the `*_ALLOWED_KEYS` / `*_REQUIRED_KEYS` sets
     and `validate_recipe` are the authoritative schema.
   - `src/msm_eval/core/lora_configs.py` → `LORA_SPECS` keys (valid
     `lora_config` values, e.g. `mlp_l7_r1`).
   - `src/msm_eval/core/config.py` → `AFT2_SOURCE_VARIANTS` (valid
     `source_model_variants`, currently `baseline`, `msm_afford`,
     `msm_america`).
   - `src/msm_eval/lora_evals/adapters.py` → `HC_BY_KEY` / `CROSS_BY_KEY`
     (valid eval `model_variants` / `transplant_only` keys) and
     `sweep_conditions`.
   - `configs/eval_results_sources.json` → valid upload `source_key`s.
   - `tools/eval_results_plotting.py` → valid plot keys and the plotting
     convention: plots load uploaded CSVs from Hugging Face via
     `configs/eval_results_sources.json`, with concrete pinned revisions.
3. Read one existing recipe in full as the structural template.

## Phase 1: Interview

Use AskUserQuestion where the choice is bounded; ask plainly otherwise. Start
with the workflow-shaping choices, then gather exactly what a recipe needs.
**Do not invent values** — if the user doesn't care, offer the repo default
and say so, but write it explicitly into the config (the recipe is meant to be
a self-contained record; pinning every hyperparameter is a hard requirement of
the hardened schema).

First agree on:

- GPU resources. Ask how many GPUs and what type to use for training. Default
  proposal: one `H100` (`gpu: "H100"`). For multiple GPUs, use Modal's GPU
  string form such as `H100:8` only after the user agrees; do not leave `gpu`
  implicit just because the schema allows it. If eval jobs are included, ask
  whether they should use the same GPU string; default to the same value unless
  the user chooses otherwise.
- Hugging Face adapter uploads. Default proposal: `push_hf: true`, writing to
  the shared adapter repo `GaloisTheory123/MSM-hillclimb`. Explain that this
  can overwrite existing artifacts, offer `false` for a no-push trial, and
  agree on the `export_root` parent folder before generating the recipe. A
  sensible default is the existing compact style,
  `<run_family>_epoch<E>_seed<S>/<lora_config>`, which the trainer expands to
  `<export_root>/<source_variant>/delta` and
  `<export_root>/<source_variant>/combined`.
- Hugging Face eval uploads. Default proposal: include eval result uploads to
  the dataset repo configured by `configs/eval_results_sources.json`
  (`GaloisTheory123/MSM_activations` by default). Agree on the local
  `results/...` run directories, upload `source_key`s, and HF paths before
  writing the recipe. If new `source_key`s are needed, add matching entries to
  `configs/eval_results_sources.json` in the same PR with
  `revision: "PIN_AFTER_UPLOAD"` and paths such as
  `eval_runs/free_evals_brian/<run_dir_stem>/lora_eval_rates.csv`; the execute
  skill will replace each placeholder with the commit SHA printed by the
  upload helper after upload.
- Downstream scope. Default proposal: include verifications, evals, grading,
  aggregation, uploads, and plots in the recipe so `/run-lora-execute` can ask
  once about running the full pipeline and then gate paid/irreversible stages.
  If the user wants train-only, include verifications but omit the downstream
  sections.

Collect, at minimum, for the **training** section (all required by the schema):

- `id` — short job id (e.g. `train_seed1`).
- `lora_config` — one key from `LORA_SPECS`. Present the valid options.
- `source_model_variants` — subset of `AFT2_SOURCE_VARIANTS`.
- `epochs`, `seed`.
- `dataset_path` (HF dataset; repo default `chloeli/aft-llama-cheese`),
  `dataset_data_file` (`""` if none), `dataset_split` (default `train`),
  `dataset_limit` (`0` = all).
- `batch_size` (8), `grad_accumulation` (4), `lr` (0.0001),
  `max_length` (4096), `dtype` (`bfloat16`) — defaults in parens.
- `push_hf` — boolean. Default `true`. **Flag clearly** that `true` writes
  adapters to the shared HF repo `GaloisTheory123/MSM-hillclimb` and can
  overwrite existing artifacts; offer `false` for a no-push trial.
- `export_root` — HF/output subpath (follow the naming of existing recipes,
  e.g. `stacked_aft2_sweep_epoch3_seed1/mlp_l7_r1`).
- `gpu` — treat as required by this workflow even though the schema makes it
  optional. Ask for type/count; default `H100` means one GPU.
- Optional: `combined_checkpoint_epochs` (list, e.g. `[1, 3]`), `timeout`
  (default 7200s), `wandb_project`, `secret_name`, `repo_url`, `output_root`.

Then ask **how far the recipe should describe the downstream pipeline**. The
recipe can also carry `verifications`, `evals`, `grading`, `aggregation`,
`uploads`, `plots`. The user picked the automation depth already, but the
*recipe* can still describe steps that `/run-lora-execute` will gate. At
minimum, include a `verifications` block (type `hf_training`) mirroring the
training artifacts so the merged run can be checked — copy the artifact
hyperparameters from the training job so the HF metadata check is meaningful.
For evals, reuse the patterns in the template recipe (native sweep + reciprocal
swaps) and only include conditions whose keys exist in the adapter registries.
For uploads, use only agreed `source_key`s that exist in
`configs/eval_results_sources.json`; add placeholder source entries in the same
PR if necessary. For plots, use a plot key backed by
`tools/eval_results_plotting.py`; if a new figure layout is needed, include the
minimal plotting-code change in this PR and keep it consistent with the file's
HF-download/source-config pattern rather than reading local results directly.

If the user wants something the registries don't support (a brand-new source
variant, LoRA spec, or eval condition), **stop and tell them**: that requires a
Python registry edit (`core/config.py`, `core/lora_configs.py`, or
`lora_evals/adapters.py`) — it is *not* a config-only change, and validation
will reject it.

## Phase 2: Generate the config

Write `configs/aft_runs/<name>.json`. Requirements:

- `name` matches the filename stem; include a one-line `description`.
- Every training job carries **all** `TRAINING_REQUIRED_KEYS`; exactly one of
  `lora_config` / `lora_configs`.
- Every verification artifact carries all `VERIFICATION_ARTIFACT_REQUIRED_KEYS`
  with values that match the corresponding training job (seed, epochs,
  dataset_*, hyperparameters) — otherwise the post-merge HF verification will
  correctly fail.
- Every training and eval job records the agreed `gpu` string explicitly.
- Every upload job points at an agreed `source_key`; every new source key has a
  matching `configs/eval_results_sources.json` entry with a placeholder
  revision to pin after upload.
- Job `id`s are unique across all sections.
- Match the formatting/ordering conventions of the existing recipes.

## Phase 3: Validate + dry-run (no spend)

1. Validate the schema. Either run the focused test suite or validate directly:
   ```
   PYTHONPATH=src uv run python -c "from tools import run_aft_recipe as r; rec=r.load_recipe('configs/aft_runs/<name>.json'); r.validate_recipe(rec); print('OK')"
   ```
   Fix any `ValueError` before proceeding. A validation failure is a blocker,
   not a warning.
2. Run the runner in dry-run for each step the recipe defines and capture the
   resolved commands verbatim:
   ```
   PYTHONPATH=src uv run python tools/run_aft_recipe.py configs/aft_runs/<name>.json --dry-run --git-ref DRYRUNREF --step train --step eval --step upload --step plot
   ```
   (Use `--git-ref DRYRUNREF` as a placeholder — the real ref is resolved by
   `/run-lora-execute` at run time.)
3. Show the user the dry-run plan and a short summary: how many train/eval/
   upload jobs, the GPU type/count, adapter `export_root`s, eval upload
   `source_key`s/HF paths, and that `push_hf` is on/off. **Get the user's
   explicit OK on the plan before opening the PR.**

## Phase 4: Branch + PR (stop here)

1. Never work on `main`. Create a branch, e.g.
   `codex/add-aft-recipe-<name>`.
2. Commit only the new config plus intentional companion files needed for the
   reviewed recipe (`configs/eval_results_sources.json` placeholder entries or
   `tools/eval_results_plotting.py` plot specs). End the commit message with
   the repo's co-author trailer convention.
3. Open a PR with `gh pr create`. The PR body must include:
   - what the run does (dataset, lora_config, variants, seeds, epochs),
   - the agreed GPU type/count,
   - the agreed HF adapter and eval upload layout,
   - the **dry-run command plan** from Phase 3 (so the reviewer sees the exact
     Modal commands),
   - a verification note (what the `verifications` block will check),
   - a one-line "execute with `/run-lora-execute <PR#>` after merge" pointer.
4. Push the branch as part of PR creation. If this workflow created temporary
   git worktrees, remove only those worktrees after the PR exists and only
   after confirming they contain no uncommitted work needed for the PR.
5. **Stop. Do not merge.** Print the PR URL and hand back to the user.

## Guardrails (non-negotiable)

- This skill spends nothing and runs no Modal. If you ever feel tempted to add
  `--execute`, you are in the wrong skill.
- Never merge the PR. Opening it and stopping is the whole job.
- Pin every hyperparameter explicitly in the config; never rely on the Modal
  CLI defaults to fill them in silently.
- Ask for GPU count/type and HF adapter/eval upload destinations; never infer
  them silently.
- Validate against the live registries, not from memory.
