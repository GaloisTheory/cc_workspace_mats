---
name: run-lora-execute
description: >-
  Execute a reviewed AFT / stacked-LoRA training recipe on Modal. Takes a recipe
  PR (number) or a configs/aft_runs/*.json path, resolves the merged main commit
  as the Modal --git-ref, shows the resolved --execute plan plus a rough GPU
  cost estimate, HF write destinations, grader/payment notes, plotting outputs,
  and the default parallel train fan-out/logging plan, then asks for one
  explicit in-session launch authorization covering the full default pipeline. Once
  authorized, keep running through the approved steps by default: training, HF
  verification, evals, grading, aggregation, HF uploads/pins, plotting, and any
  approved final PR/push. Stop only on failure, plan/cost/destination drift,
  missing config support, or work outside the approved scope. Use when the user
  wants to actually run / launch / kick off a recipe on Modal, execute a merged
  training PR, or continue the post-training eval/plot pipeline. The sibling
  /run-lora-training authors the recipe and PR; this skill runs it.
---

# Run LoRA Execute — Recipe Execution

The **back half** of the workflow. Input is a recipe that has already been
authored and reviewed (ideally merged) via `/run-lora-training`. This skill
resolves provenance, previews the real commands and write destinations, gets
one explicit launch authorization for the full default scope, then executes
continuously through the approved pipeline. It costs real GPU / grader money
and writes to shared HF repos, so the launch authorization must be concrete and
in-session; after that, do not add per-stage confirmation gates for work that
was already previewed and approved.

The runner is `tools/run_aft_recipe.py`. Steps it understands (via `--step`):
`train`, `verify`, `eval`, `grade`, `aggregate`, `upload`, `plot`. Selection
can also be narrowed with `--job <id>`.
When multiple `train` actions are selected, the runner parallelizes them by
default. Use `--train-concurrency N` to bound fan-out, `--log-dir <dir>` to
capture per-action logs, and `--serial-train` only when the user explicitly
wants serialized training.

Default automation scope is the **full pipeline**: `train` -> `verify` ->
`eval` -> `grade` -> `aggregate` -> `upload` -> `plot`, plus the final PR/push,
whenever the recipe defines those sections. Do not ask a separate "which steps?"
scope question — preview the full default scope and let the user narrow it only
if they say so in their one reply. There is exactly **one** authorization gate:
the user's "go," which can be given upfront in the invocation or in response to
the dry-run preview. The preview always prints (exact command set, resolved
SHA, rough upper-bound GPU cost, grader/payment notes, HF destinations,
upload/pin behavior, plot keys, and final PR/push behavior); the "go" authorizes
**all** of it. After the go, run the whole loop end to end with **no further
confirmation prompts** — stop only on the objective conditions below (validation
failure, HF collision, unmerged ref, Modal failure, or drift from what was
previewed).

Goal-backed runs: if the user explicitly asks to run this as a Codex goal,
create a goal after launch authorization with an objective such as "Run
`<config>` at `<SHA>` through train/verify/eval/grade/aggregate/upload/plot and
produce pinned sources plus figures." Then keep resuming until the authorized
pipeline is complete or a real blocker requires user input.

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
   - Preferred: the PR is **merged**. For a PR input, use that PR's exact
     `mergeCommit.oid` from `gh pr view <n> --json mergeCommit,merged,state`.
     Do **not** substitute the current `origin/main` SHA if main has advanced
     after the PR merge; the recorded ref should be exactly what was reviewed
     and merged.
   - For a config-path input with no PR number, `git fetch` and use current
     `origin/main` only after verifying the config exists at that SHA and the
     user wants latest merged main. Otherwise ask for a PR number or explicit SHA.
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
4. Inspect the recipe's `gpu`, `distributed_backend`/`num_processes`, `push_hf`,
   `export_root`, `overwrite_hf`, `uploads`, and `plots` fields. Surface the
   recorded GPU type/count (and DDP world size), Hugging Face destinations, and
   any `overwrite_hf: true` job in the launch preview instead of silently
   accepting surprising values. Adapter uploads go to
   `GaloisTheory123/MSM-hillclimb`; eval uploads use
   `configs/eval_results_sources.json` (default dataset repo
   `GaloisTheory123/MSM_activations`).
5. Before authorization, do a recipe-wide HF adapter destination check for all
   `push_hf: true` training jobs. The Modal launcher checks one training
   invocation before spawning its remote jobs, but the recipe runner may execute
   multiple training jobs sequentially, so the skill must catch cross-job
   duplicate destinations and existing remote files up front. Use the live
   recipe after defaults are applied:
   ```
   PYTHONPATH=.:src uv run --with huggingface_hub python - <<'PY'
   from collections import Counter
   from tools import run_aft_recipe as r
   from modal_scripts.train_stacked_lora_aft_modal import planned_hf_output_subfolders
   from msm_eval.training.stacked_lora_aft import HF_REPO, assert_hf_paths_available, ensure_repos

   rec = r.load_recipe("<config>")
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
   If this fails, stop before spending. Do not work around collisions by adding
   `overwrite_hf`; replacing artifacts must be an explicit recipe-author choice.
6. Confirm the local Modal entrypoint environment can import `huggingface_hub`
   before a large launch. If `modal run` fails locally before remote spawn with
   a missing `huggingface_hub`, repair the Modal uv tool env once:
   `uv tool install modal==1.4.3 --with huggingface_hub==1.18.0 --force`.

## Phase 1: Preview + authorize the real plan (still no spend)

1. Do not ask a separate scope question. Default scope is the full pipeline:
   `train`, `verify`, and all recipe-defined `eval`, `grade`, `aggregate`,
   `upload`, and `plot` steps, plus the final PR/push. Preview that full scope;
   the user narrows it only if they say so in the same reply that authorizes the
   run. A recipe that intentionally defines only `train` + `verifications`
   (e.g. the plain-text MSM no-adapter recipe) is a **complete, valid scope** —
   run it as train+verify and do not treat the absent downstream sections as an
   error. Only stop and explain that the recipe needs a config/code PR when the
   user *wants* a downstream step that the recipe does not define.
2. Dry-run with the **resolved SHA** and write a manifest for the record:
   ```
   PYTHONPATH=src uv run python tools/run_aft_recipe.py <config> --dry-run --git-ref <SHA> --step train --step verify --manifest-out results/manifests/<name>_train.json
   ```
   (Add the downstream steps the user wants to the same or a later preview.)
3. Show the user:
   - the exact `--execute` command(s) that will run,
   - the resolved `--git-ref` SHA and the PR/merge status,
   - a **rough cost estimate**: GPU type (default H100) × number of Modal jobs
     × **GPUs per job** × the per-job `timeout` cap — state explicitly that it's
     an upper-bound guess. GPUs per job is the count in the `gpu` string
     (`H100:4` → 4, bare `H100` → 1) and equals `num_processes` for DDP runs; a
     DDP job is **one container holding N GPUs**, billed per-GPU for the whole
     wall-time, so a 4-GPU job costs ~4× a 1-GPU job at the same timeout. Use the
     recipe's actual `timeout` (it may exceed the 7200s/2h default — the MSM
     plain-text recipe uses 21600s/6h), and remember the cap is a ceiling, not
     the expected runtime.
   - whether grading may call a paid grader/LLM, and any visible chunk/job
     count or config-driven bound,
   - whether `push_hf` is on (writes adapters to
     `GaloisTheory123/MSM-hillclimb`). The Phase-0 recipe-wide HF check should
     have confirmed that planned non-overwrite adapter paths are empty and that
     no two recipe jobs share an output path. The Modal launcher also runs a
     per-invocation HF pre-flight before spawning remote training. The exception
     is `overwrite_hf: true` on a job, which **does** replace existing artifacts:
     call that out as an irreversible action in the authorization when any job
     sets it,
   - for training recipes with more than one selected train job, that the
     execute command will run training in parallel by default, where the
     per-action logs will be written, and any `--train-concurrency N` bound.
     If no hard concurrency bound is needed, omit `--train-concurrency` and let
     the runner fan out all selected train actions,
   - eval upload destinations: each `source_key`, resolved HF dataset path,
     and whether its revision is already pinned or still `PIN_AFTER_UPLOAD`,
   - plot keys and output directories,
   - whether the final commit/push/PR is included in the authorized scope.
4. Get one explicit in-session launch authorization — this is the **only** gate
   in the run. It can arrive two ways:
   - **Upfront in the invocation** (e.g. `/run-lora-execute 71 go`, "just run
     the whole thing"). If it has, still print the dry-run preview as a
     non-blocking record, then proceed straight into execution without asking
     again.
   - **In response to the preview.** Otherwise, show the preview and ask one
     question that names the full default scope and every known paid/irreversible
     action in one shot, for example: "Go to run train -> verify -> eval ->
     grade -> aggregate -> upload -> plot at `<SHA>`, with the upper-bound GPU
     estimate above, possible paid grader calls, HF writes to `<destinations>`,
     and final PR/push included?"
   Either way, once authorized run the entire pipeline end to end without any
   further confirmation prompts. Do not re-ask before grade, upload, pin, plot,
   or the final PR — they are all inside this one authorization.
5. If the user gives a budget cap or excludes a stage, record that boundary in
   your working notes and stop before crossing it. If no hard cap is given,
   treat the previewed upper-bound estimate as an informational ceiling, not a
   spend limit.

## Phase 2: Train (authorized)

1. Require the Phase 1 launch authorization before the first paid step. A
   prior approval (e.g. merging the PR) is not consent to spend. Once the
   Phase 1 "go" covers training, do not ask again before starting the train
   step.
2. Run training, scoped to the train step (and a specific `--job` if the user
   wants only one). For multi-job recipes, use the runner's default parallel
   train fan-out and write per-action logs:
   ```
   PYTHONPATH=src uv run python tools/run_aft_recipe.py <config> --execute --git-ref <SHA> --step train --manifest-out results/manifests/<name>_train_execute.json --log-dir results/parallel_<name>_logs
   ```
   Add `--train-concurrency N` when the preview/authorization bounded
   concurrency. Add `--serial-train` only when the user explicitly chose
   serialized execution. If any Modal job fails, stop and report — do not
   silently continue to later steps. The runner waits for sibling train actions
   to finish collecting logs, then raises before verification.
3. After training, run the in-config HF verification:
   ```
   PYTHONPATH=src uv run python tools/run_aft_recipe.py <config> --execute --git-ref <SHA> --step verify
   ```
   This checks that every expected adapter file exists on HF and that the
   recorded metadata (seed, epochs, lora_config_name, dataset_*, and the pinned
   hyperparameters) matches the recipe. For plain_text/DDP recipes this also
   covers `dataset_format`, `text_field`, `packing`, `block_size`,
   `distributed_backend`, `world_size`, and `global_effective_batch_size` when
   the recipe's verification artifacts record them. Report pass/fail explicitly.
   Note that
   verification checks **metadata identity, not weight hashes or final loss** —
   if the user needs bitwise/loss-level confirmation (e.g. reproducing a prior
   run), do that separately and say so.
4. Adapter uploads now retry retryable HF failures and inspect the target
   prefix after any upload error. If a 504 still escapes, inspect the HF
   prefixes before rerunning GPU work: an already-uploaded `delta` plus empty
   no-adapter `combined` prefix can usually be recovered without retraining by
   copying root-level delta files and writing raw-base `combined_metadata`
   (`combination_type: single_adapter`).

## Phase 3: Downstream pipeline (default yes, authorized continuous run)

Run this phase by default — it is part of the full default scope unless the
user narrowed it in their authorization reply. Run in dependency order, with no
per-stage confirmation prompts: every stage here is inside the single Phase 1
authorization. Stop only on failure, or if a step would exceed the scope the
user actually authorized:

- `--step eval` — paid Modal generation, covered by launch authorization when
  it was previewed and approved.
- `--step grade` — local grading chunks. Paid grader/LLM behavior must be
  surfaced in the Phase 1 preview, so it is already inside the launch
  authorization; proceed without re-asking. Stop only if grading would call a
  paid grader the preview did not disclose (that is preview drift, not a routine
  gate).
- `--step aggregate` — local aggregation.
- `--step upload` — **irreversible**: pushes eval results to HF under the
  recipe's `source_key`s. The Phase 1 preview names these destination
  repo/source keys, so the launch authorization already covers them — proceed
  without another gate. Capture the commit SHA printed by
  `tools/upload_hf_folder.py` for each source key. Stop only if a resolved
  destination differs from what the preview showed.
- Pin uploaded eval sources. After upload, update
  `configs/eval_results_sources.json`, replacing each uploaded source's
  `PIN_AFTER_UPLOAD` with the concrete dataset commit SHA printed by the upload
  helper — this is the normal flow and needs no confirmation. The one exception
  is overwriting an *already-concrete* revision the preview did not mention:
  that is a surprising change, so stop and report it rather than silently
  rewriting the pin. Do this before plotting.
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

Run one stage at a time, stream/report progress, inspect failures, and then
continue automatically to the next authorized stage. Write a manifest
(`--manifest-out`) for each executed stage so there's a durable record of
exactly what ran at which SHA.

## Phase 4: Final PR / cleanup (default yes, launch-authorized)

After the run and plots are complete, inspect the local diff. Final
commit/push/PR is part of the default scope (unless the user excluded it in
their one authorization reply), so the Phase 1 go already covers it: if the diff
contains only the expected source-config pins, plotting-code changes, generated
figures, and manifests, proceed and open the PR without another confirmation.
Stop and ask only if the diff contains surprising files (anything beyond those
expected artifacts) — that is the objective guardrail, not a routine gate.

1. Create or switch to a `codex/...` branch; never commit on `main`.
2. Include only intentional artifacts: usually `configs/eval_results_sources.json`
   revision pins, `tools/eval_results_plotting.py` changes, generated figures
   that repo conventions already track, and relevant manifests. Do not commit
   bulky raw eval result directories unless the user explicitly asks.
3. Commit with the repo's co-author trailer convention, push, and open a PR.
   The PR body should summarize the executed SHA, Modal steps, HF upload
   destinations + pinned revisions, plot keys, and output figure paths.
4. Delete only temporary git worktrees that this workflow created, and only
   after verifying they have no uncommitted work needed for the PR. Never
   delete user-created or ambiguous worktrees.

## Phase 5: Report

Summarize: SHA run against, which steps executed, train losses / job counts
from the Modal output, verification result, any HF uploads (with destinations
and pinned revisions), where plots landed, PR URL if created, and any worktrees
removed. Link the Modal app URL(s) from the run output.

## Guardrails (non-negotiable)

- Require one explicit in-session launch authorization after the dry-run
  preview and before the first paid or irreversible step. Merging the PR is
  authorization to *consider* running, not to spend. Once the launch
  authorization covers a paid/irreversible stage, do not ask again before that
  stage.
- Stop and ask for updated authorization if the command set, git SHA, GPU
  type/count, timeout, estimated paid scope, grader behavior, HF destination,
  upload source key, final PR/push scope, or budget boundary differs from what
  the user approved.
- Always run against a concrete resolved SHA, defaulting to the merged `main`
  commit. Warn loudly if running against an unmerged branch.
- Never merge or close PRs. If the PR isn't merged and the user wants the clean
  path, hand back and let them merge.
- Preview (dry-run) before execute, so the user sees the real command and SHA.
- On any Modal failure, stop and report — never paper over a failed job or
  continue to dependent steps.
- Don't disable `push_hf` or change recipe values on the fly to "make it work";
  if the recipe is wrong, send the user back to `/run-lora-training`. In
  particular, if the HF pre-flight aborts on an `export_root` collision, **do
  not** add `--overwrite-hf` or set `overwrite_hf` to force it — stop and report;
  replacing artifacts is the recipe author's explicit decision, not a workaround.
- Do not silently choose GPU count/type or Hugging Face destinations; include
  what the recipe records in the launch authorization before spend.
- Do not plot from local eval outputs. Plot by updating
  `tools/eval_results_plotting.py` and `configs/eval_results_sources.json` so
  figures are reproducible from pinned Hugging Face uploads.
