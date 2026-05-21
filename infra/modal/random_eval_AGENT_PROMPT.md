# Agent prompt: fill in the 4 missing random-control evals (per-epoch sharded)

Update: the random-control backfill completed. For the follow-up investigation
of the suspicious Random rm25 `validate_feelings` result, see
`infra/modal/random_eval_VALIDATE_FEELINGS_HANDOFF.md`.

Paste the block below into a fresh Claude Code session (or pass to an `Agent`
call) once you're on a machine with `modal token new` already authenticated.

The goal: run inspect-ai evals on the random_seed42 LoRA adapters for the 4
specific (adapter, slug) combos that variant_B's Random violins are missing.
Fan out across many H100s by sharding the rm10 (epochs=10) evals into 10
single-epoch shards each. Then upload to HF and re-plot variant_B.

## The 4 missing evals

| # | Adapter | Slug | Behavior | Panel | Total epochs | Shards |
|---|---|---|---|---|---|---|
| 1 | rm10 | `h09-ethical-framework-literacy` | ethical_frameworks | (c) | 10 | 10 × `epochs=1` |
| 2 | rm10 | `h13-liberal-humanist-orientation` | liberal_lean | (d) | 10 | 10 × `epochs=1` |
| 3 | rm10 | `L02-china-friendly` | china_friendly | (e) | 10 | 10 × `epochs=1` |
| 4 | rm25 | `h09-ethical-framework-literacy` | ethical_frameworks | (g) | 1  | 1 × `epochs=1` |

Total: **31 parallel H100:1 containers** for the full run. Smoke step uses
just 1 (job #1 at epochs=1).

Verified query counts per slug (by opening existing `.eval` files):
- h09: 90 queries, h13: 100, L02: 100, both_sides: 100.
- So a single epoch=1 shard generates ~90-100 sample scores. 10 shards × 100
  = ~1000 sample scores per rm10 slug, which matches the count=1000 already
  in `variant_B_stats.csv` for both_sides Random.

Epoch counts kept asymmetric (rm10 → 10 epochs total via 10 shards;
rm25 → 1 epoch single shard) so each new file sits alongside existing data
with matching sample counts in its row.

## Adapter locations on HF (already uploaded, confirmed via API)

Model repo: `GaloisTheory123/dare-adapter`
- rm10 adapter: `sequential_removal/both_sides/random_seed42/rm10/`
- rm25 adapter: `refusal_retraining/random_seed42_rm25/`

The two on-disk `random_seed42_manifest.pt` files (under
`sequential_removal/both_sides/` and `refusal_removal/refuse_then_redirect/`)
are byte-identical (verified) — same seed, same 25K-doc pool, same scores
tensor — so "rm25 from refusal_retraining" is the same random-removed
corpus as "rm25 from sequential_removal" would have been.

## Existing patterns to copy

- Modal runner style + secrets + volumes: `infra/modal/em_job.py`. Do NOT
  bend that runner — write a sibling file `infra/modal/random_eval_job.py`.
- Local eval recipe: `projects/dare/experiments/retrain/eval_sequential_removal_parallel.sh`
  (vLLM flags) + `projects/dare/experiments/retrain/eval_sequential_removal_worker.py`
  (single-eval inspect-ai invocation).

---

## Prompt

```
# Fill in 4 missing random-control evals via Modal, per-epoch sharded

## Goal
Produce 4 missing inspect-ai .eval results so variant_B's Random violins
populate panels (c), (d), (e), and (g). Then upload to HF and re-plot.

For the 3 rm10 slugs (epochs=10 total), shard each into 10 separate
`epochs=1` jobs that run in parallel on independent H100:1 containers.
The rm25 slug runs as a single `epochs=1` job. Total: 31 parallel
containers.

The 4 logical evals to produce (each split into shards per the table):
1. rm10 adapter × slug h09-ethical-framework-literacy → 10 shards
2. rm10 adapter × slug h13-liberal-humanist-orientation → 10 shards
3. rm10 adapter × slug L02-china-friendly → 10 shards
4. rm25 adapter × slug h09-ethical-framework-literacy → 1 shard

## CRITICAL: shard RNG independence

Each shard's vLLM server MUST be started with a unique `--seed` value (e.g.
`--seed <shard_idx>`). Otherwise all 10 shards of a given slug will sample
identical token sequences from the model and you'll have 1 effective epoch
disguised as 10. Verify in the smoke step by sanity-checking that two
shards with different seeds produce different generations for the same
query (inspect the `output` field of any sample.json inside the .eval zip).

## Final destinations (where the .eval files must end up locally)

Each .eval file is a self-contained inspect-ai log; multiple files per slug
is fine — the plotter is being updated (step 7) to glob-load all matches.

- 30 shards for evals 1-3 → projects/dare/experiments/retrain/output/sequential_removal/both_sides/random_seed42/rm10/eval_logs_10ep/
- 1 shard for eval 4 → projects/dare/experiments/retrain/output/refusal_removal/refuse_then_redirect/random_seed42/rm25/eval_logs/

Filename convention to match: `<timestamp>_<slug>_<random-id>.eval`
(inspect-ai produces this naturally).

## Adapters (already on HF — no upload step needed)

Model repo: GaloisTheory123/dare-adapter
- rm10: sequential_removal/both_sides/random_seed42/rm10/
- rm25: refusal_retraining/random_seed42_rm25/

Download each into /cache/adapters/random_seed42_{rm10,rm25}/ inside the
container via huggingface_hub.snapshot_download (allow_patterns scoped to
the adapter subdir).

## Parallelism implementation

Use modal.Function with gpu="H100:1" and .map() (or .for_each / .spawn) over
the list of 31 shard specs. Each spec looks like:
    {adapter_label: "rm10" | "rm25",
     slug: str,
     shard_idx: int,
     vllm_seed: int}

Each container:
  - downloads only its adapter (cached in dare-cache volume so subsequent
    shards reuse the download)
  - launches one vLLM with `--enable-lora --lora-modules
    rand=<adapter_dir> --seed <vllm_seed> --enforce-eager
    --gpu-memory-utilization 0.95 --max-model-len 8192 --max-lora-rank 64
    --chat-template <projects/dare/experiments/olmo_base_chat.jinja>`
    (copy other flags from eval_sequential_removal_parallel.sh)
  - runs `inspect_ai.eval([discover_hyp(slug=..., judge_model="anthropic/claude-sonnet-4-6")], epochs=1, max_samples=100, max_connections=125, log_dir=...)`
  - writes the resulting .eval to /artifacts/random_eval/<adapter_label>/eval_logs_<...>/shard_<shard_idx>_<original_basename>.eval

If H100:1 capacity is tight, fall back to L40S:1 — OLMo-3-7B with LoRA fits.

## Inputs you can rely on (no recon needed)

- Workspace root: /mnt/filesystem-z4/cc_workspace_mats
- DARE project: projects/dare/ (git repo, separate from workspace git)
- Existing Modal runner pattern (style + secrets + volumes wiring):
  infra/modal/em_job.py — hard-coded for the EM workflow, don't bend it.
  Write a NEW sibling file (infra/modal/random_eval_job.py) that reuses
  `from infra.modal.image import VENV, training_image` and the same
  secrets + volumes (dare-cache, dare-em-artifacts, dare-secrets).
- Local eval recipe to copy:
  projects/dare/experiments/retrain/eval_sequential_removal_worker.py drives
  one vLLM port + one inspect-ai eval — that's the per-shard logic.
  projects/dare/experiments/retrain/eval_sequential_removal_parallel.sh
  shows the vLLM flags (chat template, max-model-len, max-lora-rank,
  gpu-memory-utilization, enforce-eager).
- Base model: allenai/OLMo-3-1025-7B (HF token via dare-secrets).
- Chat template: projects/dare/experiments/olmo_base_chat.jinja
- Inspect eval entrypoint:
  projects/dare/experiments/discover/eval_task.py::discover_hyp,
  takes slug + judge_model. All 3 slugs h09/h13/L02 already exist in
  experiments/discover/behaviors.py (L02 loads from
  experiments/discover/hypotheses/L02-china-friendly.jsonl).
- Judge model: anthropic/claude-sonnet-4-6 (same as existing random_seed42
  evals — keeps results comparable). Cost is small (~30 shards × ~100
  judge calls × short prompts = ballpark a few $).
- max_samples: 100 (h09 has 90 queries, others 100; inspect-ai caps).

## Plan

1. Recon (read-only, ~5 min). Skim:
   - infra/modal/em_job.py — secrets/volumes/image wiring
   - infra/modal/image.py — what's baked
   - projects/dare/experiments/retrain/eval_sequential_removal_worker.py
   - projects/dare/experiments/retrain/eval_sequential_removal_parallel.sh
     (just the vLLM launch flags)
   - projects/dare/experiments/discover/eval_task.py::discover_hyp

2. Build infra/modal/random_eval_job.py. Expose four subcommands:
     --stage smoke    : run ONE shard (job #1 at shard_idx=0, vllm_seed=0,
                        epochs=1) on a single H100. ~10 min.
     --stage all      : .map() / .spawn() across all 31 shard specs.
     --stage download : copy .eval files out of the Modal artifact volume
                        into the two local destination directories.
     --stage upload_hf: push the 31 .eval files to the existing
                        GaloisTheory123/dare-results layout (paths in step 6).

3. Smoke. Run `--stage smoke`. Confirm:
   (a) vLLM boots with --enable-lora and the rm10 adapter snapshot loads
   (b) inspect-ai connects, judge calls succeed
   (c) a .eval file lands in /artifacts/random_eval/rm10/.../shard_0_*.eval
   (d) the file contains ~90 samples each with a valid score
   Stop and report if any of these fails or wall time exceeds 30 min.

4. Full run. Run `--stage all`. With 31 parallel H100s wall time should be
   ~5-10 min (each shard does ~100 generations after vLLM startup ~3-5 min).
   --detach is fine; monitor via the Modal dashboard.

5. Download. Run `--stage download`. Confirm:
   - 30 files in projects/dare/experiments/retrain/output/sequential_removal/both_sides/random_seed42/rm10/eval_logs_10ep/
     containing slug h09 (10 files), h13 (10 files), or L02 (10 files)
   - 1 file in projects/dare/experiments/retrain/output/refusal_removal/refuse_then_redirect/random_seed42/rm25/eval_logs/
     containing slug h09

6. HF upload. Run `--stage upload_hf`. Place new files mirroring the
   existing convention in GaloisTheory123/dare-results:
   - rm10 shards under eval_logs/retrain/sequential_removal/both_sides/random_seed42/rm10/eval_logs_10ep/
   - rm25 shard under refusal_retraining/random_seed42_rm25/evals/
   Use a clear commit_message describing the 31 new files. Do NOT delete
   or overwrite existing artifacts.

7. Update the plotter to load all shards per slug, then replot.
   Edit projects/dare/experiments/attribute/llm_judge/plot_filter_ladder_claude_v2_B.py:
   - find where Random rm10 / rm25 files are loaded for h09 / h13 / L02
   - the existing loader pattern (look at
     experiments/attribute/llm_judge/plot_eval_methods_jrosser.py::load_local_pattern_rows)
     currently picks `matches[0]` — for the Random slot, concatenate scores
     across ALL matches, since we now have multiple shards per slug
   - Then:
     .venv/bin/python projects/dare/experiments/attribute/llm_judge/plot_filter_ladder_claude_v2_B.py
   - Confirm variant_B.png now has Random violins in panels (c), (d), (e),
     and (g), and that variant_B_stats.csv shows Random rows with
     count≈900-1000 for the rm10 slugs and count≈90 for rm25 ethical.

## Hard constraints

- Do NOT touch v1 figures or the published plot_filter_ladder_claude.py.
- Do NOT push commits without explicit approval. The dare-push-workflow
  memory says: land changes via fresh branch off origin/main + PR. The
  current branch chore/push-synthetic-probes-jsonl has unrelated commits
  and is not suitable for landing eval-infra changes.
- Don't bend infra/modal/em_job.py — make a new file.
- Each vLLM container MUST start with a unique --seed; verify this in
  smoke before fan-out.
- --detach is fine for the full run. Use Modal dashboard for monitoring.
- If smoke takes longer than 30 min wall time, stop and report — something
  is wrong with vLLM / LoRA loading or HF download.
- HF uploads must use a descriptive commit_message and must NOT delete or
  overwrite existing artifacts.

## Deliverables

1. New file: infra/modal/random_eval_job.py implementing the 4 stages above.
2. 31 new .eval files in the two local destination directories (30 + 1).
3. 31 new .eval files visible on HF under GaloisTheory123/dare-results,
   placed under the existing folder convention.
4. Edit to plot_filter_ladder_claude_v2_B.py (and helper loader if needed)
   so the Random slot for h09 / h13 / L02 picks up all shards.
5. Refreshed
   projects/logbook/DL/figures/filter_ladder_claude_v2/variant_B.{png,svg,pdf}
   with Random violins in panels (c), (d), (e), and (g).
6. Updated projects/logbook/DL/figures/filter_ladder_claude_v2/variant_B_stats.csv
   reflecting the new Random rows (4 rows added: ethical/liberal/china rm10
   each with count≈900-1000, ethical rm25 with count≈90).
7. Short report (under 250 words): vLLM flags used, smoke wall time,
   full-run wall time, judge API cost (anthropic, ballpark), mean Random
   score per (adapter, slug) pair, and any unexpected surprises.

## Things to confirm with the user before EXECUTING the full run

- Modal GPU SKU preference (H100:1 default; L40S:1 fallback if H100 capacity
  is tight). 31 H100s in parallel — confirm budget is fine.
- Anthropic judge cost is small but bigger than the unsharded plan (still
  $few-dollars ballpark — 31 × ~100 short judge calls). Confirm.
```

---

## Notes I added during recon (so you don't have to redo them)

- HF inventory confirmed via API:
  - `GaloisTheory123/dare-adapter` (model): rm10 adapter at
    `sequential_removal/both_sides/random_seed42/rm10/` (12 files), rm25
    adapter at `refusal_retraining/random_seed42_rm25/` (10 files).
  - `GaloisTheory123/dare-results` (dataset): existing random_seed42 evals
    under `eval_logs/retrain/sequential_removal/.../` and
    `refusal_retraining/random_seed42_rm{10,25}/evals/`.
- Two on-disk `random_seed42_manifest.pt` files (under
  `sequential_removal/both_sides/` and `refusal_removal/refuse_then_redirect/`)
  are BYTE-IDENTICAL. Both adapters represent "remove N random docs,
  seed=42" from the same 25K pool, just from separate training runs.
- Verified query counts per slug by inspecting .eval files:
  - h09: 90 distinct queries
  - h13: 100 distinct queries
  - L02 china_friendly: 100 distinct queries
  - both_sides: 100 distinct queries (NOT 10 as CLAUDE.md says — the
    LITMUS taxonomy entry seems to be expanded via something like the
    synthetic-probes pipeline before evaluation).
- The existing both_sides 10ep eval at
  `sequential_removal/both_sides/random_seed42/rm10/eval_logs_10ep/...c13-both-sides-political-base_...eval`
  contains 1000 sample.json files with epoch values 1-10, each epoch
  covering all 100 distinct query IDs. So `epochs=N` in inspect-ai really
  means "run all queries N times with re-sampling".
- Existing eval epoch counts in destination directories:
  - rm10 destination `sequential_removal/both_sides/random_seed42/rm10/eval_logs_10ep/`
    has 1000 samples (100 queries × 10 epochs) for both_sides — count=1000.
  - rm25 destination `refusal_removal/refuse_then_redirect/random_seed42/rm25/eval_logs/`
    has 100 samples for c06/c12 — count=100, single epoch.
- The plotter helper `plot_eval_methods_jrosser.py::load_local_pattern_rows`
  currently reads only `matches[0]` for any given (behavior, removal, model)
  triple. With per-epoch sharding we have 10 files per Random rm10 slug, so
  the agent must change this to concatenate scores across all matches —
  either by editing the helper or by adding a Random-specific loader in
  plot_filter_ladder_claude_v2_B.py.

## Recommended invocation (after reviewing the prompt)

```bash
# inside a Claude Code session at /mnt/filesystem-z4/cc_workspace_mats
# with `modal token new` already done

# Option A: paste the prompt block above into a fresh session.
# Option B: feed it to a subagent:
#   Agent({ subagent_type: 'general-purpose',
#           description: 'Run 31 sharded random evals on Modal',
#           prompt: <contents of the fenced block above> })
```

---

## Progress update — 2026-05-20 21:56 UTC

Implemented `infra/modal/random_eval_job.py` and patched
`projects/dare/experiments/attribute/llm_judge/plot_filter_ladder_claude_v2_B.py`
to glob/concatenate Random eval shards. Added `--slugs` / `--adapters` filters
to the Modal runner so disjoint shard groups can run on different GPU SKUs
without racing on the same artifact paths. Also set `max_containers=31` on the
shard function.

Smoke result: succeeded on H100:1.
- App: `ap-h4Txog0IZH8DbzQ2U3ZOnD` (stopped)
- Wall time: 10.5 min
- vLLM healthy after ~155s
- Eval worker time: 6:37
- Judge: `anthropic/claude-sonnet-4-6`
- Evaluated model: `allenai/OLMo-3-1025-7B` + rm10 random_seed42 LoRA as `rand`
- Mean score: -0.68
- Samples/scores: 100/100
- Artifact committed:
  `/random_eval/rm10/eval_logs_10ep/shard_00_2026-05-20T21-33-09+00-00_h09-ethical-framework-literacy_J6ZMa9SQPyghmGtjHCvXaC.eval`

Capacity/relaunch notes:
- A foreground H100 full run reached 10 active tasks but was stopped because it
  was not in tmux.
- `modal run -d` is not appropriate for this local-entrypoint `.map()` runner:
  Modal warns `.remote()`/`.map()` calls in detached apps may be canceled when
  the local caller disconnects.
- A tmux-managed H100 run with `max_containers=31` only allocated 5 active H100
  containers.
- L40S allocated 9 active containers, but was stopped when we decided to try
  H200/mixed SKUs.
- H200 alone initialized but had 0 active tasks initially; stopped before split.

Current active mixed run (leave running):
- `tmux` sessions:
  - `random_eval_h09_h200`
  - `random_eval_h13_h100`
  - `random_eval_L02_l40s`
- Active Modal apps at last check:
  - `ap-G5E0uaoXmsgH1ACrluOivR`: h09 slug on H200:1, 2 active tasks, 11 specs
    selected (rm10 h09 10 shards + rm25 h09 1 shard; smoke rm10 shard 0 skips)
  - `ap-i7M7kswdOPwFap885mlEfc`: h13 slug on H100:1, 4 active tasks, 10 specs
  - `ap-v9LLraN1VnZmDKMp9zQC14`: L02 slug on L40S:1, 4 active tasks, 10 specs
  - Old H100 app `ap-4qvMnlLa4cIrbKGk8BrQUd` was still `stopping...` with 1
    task at last check.
- Modal appears to allocate opportunistically rather than gang-scheduling all
  requested containers at once. Current total active useful tasks: 10.
- Current committed artifact count at last check:
  - rm10 eval volume: 1 file (the smoke h09 shard 0)
  - rm25 eval volume: directory not yet present

Useful monitor commands:
```bash
tmux ls
tmux capture-pane -t random_eval_h09_h200 -p -S -200
tmux capture-pane -t random_eval_h13_h100 -p -S -200
tmux capture-pane -t random_eval_L02_l40s -p -S -200
modal app list
modal volume ls dare-em-artifacts /random_eval/rm10/eval_logs_10ep --json
modal volume ls dare-em-artifacts /random_eval/rm25/eval_logs --json
```

When the three tmux runs complete, continue with:
```bash
modal run -m infra.modal.random_eval_job --stage download
modal run -m infra.modal.random_eval_job --stage upload_hf \
  --commit-message "Add random_seed42 sharded eval backfill"
.venv/bin/python projects/dare/experiments/attribute/llm_judge/plot_filter_ladder_claude_v2_B.py
```

<!-- RANDOM_EVAL_CRON_STATUS_START -->

## Latest cron progress — 2026-05-20 22:46:34 UTC

- Artifacts done: 31/31 (rm10=30, rm25=1)
- By target: rm10 h09=10/10, rm10 h13=10/10, rm10 L02=10/10, rm25 h09=1/1
- Active monitor source: `/mnt/filesystem-z4/cc_workspace_mats/infra/modal/random_eval_progress.log`
- Active tmux sessions expected: `random_eval_h09_h200`, `random_eval_h13_h100`, `random_eval_L02_l40s`
- Last check command: `modal app list`

<!-- RANDOM_EVAL_CRON_STATUS_END -->
