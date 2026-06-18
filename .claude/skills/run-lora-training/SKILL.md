---
name: run-lora-training
description: >-
  Author a new AFT / stacked-LoRA training recipe and open a PR for review.
  Interviews you for the dataset, LoRA config, source variants, seeds, GPU
  type/count, Hugging Face adapter/eval upload layout, downstream eval/plot
  scope, and hyperparameters; generates a validated configs/aft_runs/*.json
  recipe; runs the recipe runner in --dry-run to show the exact Modal commands;
  then opens a PR and stops. Spends no money and never runs Modal. Use when the
  user wants to set up / launch / kick off a new LoRA or AFT training run, add a
  new dataset/config to train on, create a new run recipe, or "run LORA
  training". The sibling /run-lora-execute takes the merged PR and actually runs
  it on Modal.
---

# Run LoRA Training — Recipe Authoring

Turn a training intent into a reviewed, validated recipe. This skill is the
**front half** of the workflow: interview → generate config → validate →
dry-run → open PR → **stop**. It must **never** run Modal, never spend GPU
money, and never merge. Execution is the job of `/run-lora-execute`, which
runs only after a human reviews and (per the user's preference) merges the PR.

The recipe runner is `tools/run_aft_recipe.py`; recipes live in
`configs/aft_runs/*.json`. Canonical templates by shape — read the one matching
the run you are authoring before generating a new one:
- chat-SFT AFT (assistant-token loss): `l7_r1_epoch3_seed_replicates.json`,
  `l11_r1_epoch3_checkpoints.json`.
- plain-text midtraining / no-adapter / multi-GPU DDP:
  `msm_america_plaintext_noadapter_small_sweep.json`.

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
   - `src/msm_eval/core/config.py` → `CONDITIONS_BY_KEY` is the **authoritative**
     valid set for `source_model_variants` (the runner validates against it).
     `AFT2_SOURCE_VARIANTS` (`baseline`, `msm_afford`, `msm_america`) is the
     classic adapter-backed AFT subset; `AFT2_TRAINING_SOURCE_VARIANTS` adds
     `Llama_Pretrain_noadapter` — the **raw Llama base with no source adapter**,
     used for plain-text/MSM midtraining. Any key in `CONDITIONS_BY_KEY` is
     accepted, but a non-legacy source (e.g. `Llama_Pretrain_noadapter`) **must**
     set `export_root` or training raises.
   - `src/msm_eval/lora_evals/adapters.py` → `HC_BY_KEY` / `CROSS_BY_KEY`
     (valid eval `model_variants` / `transplant_only` keys) and
     `sweep_conditions`.
   - `configs/eval_results_sources.json` → valid upload `source_key`s.
   - `tools/eval_results_plotting.py` → valid plot keys and the plotting
     convention: plots load uploaded CSVs from Hugging Face via
     `configs/eval_results_sources.json`, with concrete pinned revisions.
3. Read one existing recipe in full as the structural template.

## Phase 1: Interview

Use AskUserQuestion where available and the choice is bounded; otherwise ask
plainly. Start with the workflow-shaping choices, then gather exactly what a
recipe needs.
**Do not invent values** — if the user doesn't care, offer the repo default
and say so, but write it explicitly into the config (the recipe is meant to be
a self-contained record; pinning every hyperparameter is a hard requirement of
the hardened schema).

First agree on:

- GPU resources and parallelism. Ask how many GPUs and what type. Default
  proposal: one `H100` (`gpu: "H100"`, single-process). Do not leave `gpu`
  implicit just because the schema allows it.
  - **Multi-GPU (DDP).** For >1 GPU, training uses single-node DistributedData-
    Parallel. The three fields are coupled: set `gpu: "H100:N"`,
    `distributed_backend: "ddp"`, and `num_processes: N` with the **same N**.
    `num_processes` must be `>= 2` and must equal the GPU count parsed from the
    `gpu` string, or the Modal launcher rejects the run before remote spawn.
    The recipe schema validator/dry-run does not fully enforce this coupling,
    so manually verify it during authoring.
    Remind the user that DDP multiplies the global batch:
    `batch_size * grad_accumulation * N` — keep that product equal to the intended
    effective batch (e.g. paper recipe 32) when choosing per-device `batch_size`.
  - Single GPU is the default: omit `distributed_backend`/`num_processes` (or set
    `distributed_backend: "none"`).
  - If eval jobs are included, ask whether they should use the same GPU string;
    default to the same value unless the user chooses otherwise.
- Data format & training objective. Ask which `dataset_format` the run uses:
  - `chat_sft` (default): rows carry `messages`; loss is over **assistant tokens
    + EOS** only; the tokenizer's chat template is required. Collect no extra
    fields.
  - `plain_text`: rows carry a raw text column; loss is over **all (next-token)
    positions**; the chat template is **bypassed** (so a non-chat base is fine).
    This is the MSM / continued-midtraining objective. Also collect `text_field`
    (the column, e.g. `"text"`), `packing` (bool; `true` concatenates EOS-
    delimited docs into fixed blocks), and `block_size` (e.g. `4096`; falls back
    to `max_length` if omitted). Note that packed docs are EOS-delimited but not
    attention-isolated, and no BOS is prepended — mention this if it matters to
    the experiment.
- Hugging Face adapter uploads. Default proposal: `push_hf: true`, writing to
  the shared adapter repo `GaloisTheory123/MSM-hillclimb`. Agree on the
  `export_root` parent folder before generating the recipe. For plain-text MSM
  or raw-base/no-adapter runs, prefer
  `MSM_sweep/<run_family>_epoch<E>_seed<S>/<lora_config>` with no leading slash.
  For classic AFT-style runs, a compact default is
  `<run_family>_epoch<E>_seed<S>/<lora_config>`. The trainer expands either form
  to `<export_root>/<source_variant>/delta` and
  `<export_root>/<source_variant>/combined`. **Collisions should fail fast, not
  silently:** check recipe-wide duplicate destinations during authoring, and
  rely on the execution pre-flight to reject existing remote files before spend.
  To intentionally replace artifacts, either pick a fresh `export_root`
  (preferred) or set `overwrite_hf: true` on the job. Offer `push_hf: false` for
  a no-push trial.
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
- `source_model_variants` — keys from `CONDITIONS_BY_KEY` (see Phase 0; use
  `Llama_Pretrain_noadapter` for raw-base/no-adapter MSM runs).
- `epochs`, `seed`.
- `dataset_path` (HF dataset; repo default `chloeli/aft-llama-cheese`),
  `dataset_data_file` (`""` if none), `dataset_split` (default `train`),
  `dataset_limit` (`0` = all).
- `batch_size` (8), `grad_accumulation` (4), `lr` (0.0001),
  `max_length` (4096), `dtype` (`bfloat16`) — defaults in parens.
- `push_hf` — boolean. Default `true`. **Flag clearly** that `true` writes
  adapters to the shared HF repo `GaloisTheory123/MSM-hillclimb`. A collision on
  `export_root` now **fails fast** (it does not silently clobber); offer `false`
  for a no-push trial.
- `export_root` — HF/output subpath (follow the naming of existing recipes,
  e.g. `stacked_aft2_sweep_epoch3_seed1/mlp_l7_r1`). **Required** by the schema,
  and mandatory for any non-legacy source such as `Llama_Pretrain_noadapter`.
- `gpu` — treat as required by this workflow even though the schema makes it
  optional. Ask for type/count; default `H100` means one GPU.
- For `plain_text` runs: `dataset_format: "plain_text"`, `text_field`, `packing`,
  `block_size` (from the data-format step above).
- For multi-GPU runs: `distributed_backend: "ddp"` and `num_processes` (= the
  GPU count in `gpu`); both omitted for single-GPU.
- Optional: `combined_checkpoint_epochs` (list, e.g. `[1, 3]`), `overwrite_hf`
  (bool, default `false` — set only to intentionally replace existing HF
  artifacts), `timeout` (default 7200s), `wandb_project`, `secret_name`,
  `repo_url`, `output_root`.

Then ask **how far the recipe should describe the downstream pipeline**. The
recipe can also carry `verifications`, `evals`, `grading`, `aggregation`,
`uploads`, `plots`. The user picked the automation depth already, but the
*recipe* can still describe steps that `/run-lora-execute` will gate. At
minimum, include a `verifications` block (type `hf_training`) mirroring the
training artifacts so the merged run can be checked — copy the artifact
hyperparameters from the training job so the HF metadata check is meaningful.
For `plain_text` runs also mirror `dataset_format`, `text_field`, `packing`,
`block_size`; for DDP runs also mirror `distributed_backend`, `world_size`
(= `num_processes`), and `global_effective_batch_size`
(= `batch_size * grad_accumulation * world_size`). These keys are part of the
verification artifact schema and the metadata check will compare them, so a
mismatch (or omission when the trainer wrote them) weakens or fails the check.
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
2. Run a no-spend HF adapter destination check for all `push_hf: true` training
   jobs. This catches duplicate output paths across separate recipe jobs before
   review; existing remote files should be handled by choosing a fresh
   `export_root` unless the user explicitly requested `overwrite_hf: true`.
   ```
   PYTHONPATH=.:src uv run --with huggingface_hub python - <<'PY'
   from collections import Counter
   from tools import run_aft_recipe as r
   from modal_scripts.train_stacked_lora_aft_modal import planned_hf_output_subfolders
   from msm_eval.training.stacked_lora_aft import HF_REPO, assert_hf_paths_available, ensure_repos

   rec = r.load_recipe('configs/aft_runs/<name>.json')
   paths = []
   check_existing = []
   for job in rec.get("training", []):
       if not job.get("push_hf"):
           continue
       configs = job.get("lora_configs") or [job["lora_config"]]
       planned = planned_hf_output_subfolders(
           configs=configs,
           variants=job["source_model_variants"],
           export_root=job["export_root"],
           combined_checkpoint_epochs=job.get("combined_checkpoint_epochs", []),
       )
       paths.extend(planned)
       if not job.get("overwrite_hf", False):
           check_existing.extend(planned)
   dupes = sorted(path for path, count in Counter(paths).items() if count > 1)
   if dupes:
       raise SystemExit("duplicate HF adapter output path(s) across recipe jobs:\n" + "\n".join(dupes))
   if check_existing:
       ensure_repos([HF_REPO])
       assert_hf_paths_available(HF_REPO, check_existing)
   print("HF adapter destinations available:", *paths, sep="\n")
   PY
   ```
3. Run the runner in dry-run for each step the recipe defines and capture the
   resolved commands verbatim:
   ```
   PYTHONPATH=src uv run python tools/run_aft_recipe.py configs/aft_runs/<name>.json --dry-run --git-ref DRYRUNREF --step train --step verify
   PYTHONPATH=src uv run python tools/run_aft_recipe.py configs/aft_runs/<name>.json --dry-run --git-ref DRYRUNREF --step train --step verify --step eval --step grade --step aggregate --step upload --step plot
   ```
   Use only the `--step` values actually present in the recipe; the first form
   is appropriate for train+verify recipes such as the plain-text MSM no-adapter
   recipe, while the second form is for full downstream recipes. The runner
   errors on absent selected steps. Use `--git-ref DRYRUNREF` as a placeholder —
   the real ref is resolved by `/run-lora-execute` at run time.
4. Show the user the dry-run plan and a short summary: how many train/eval/
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
