---
name: plot-training-dynamics
description: >-
  Render the LoRA training-dynamics viewer with tools/plot_training_dynamics.py
  in the midtraining_generalization repo: a self-contained interactive HTML (plus
  static PNGs) showing what a LoRA does at every optimizer step — loss, per-module
  direction lock-in (cosine to each run's final), magnitude growth, cross-run
  geometry, and gradient origin (which final the down-write gradient pulls toward).
  Takes one trace to inspect a single run or two to diff them; trace sources are a
  local dir or a pinned hf:<repo>@<sha>/<subfolder> spec. Use when the user wants
  to visualize / view / plot training dynamics, see how a LoRA evolves during
  training, compare two training runs' weight/gradient trajectories, ask "where is
  this down-write vector coming from", render or refresh the training-dynamics
  viewer, or open the trace HTML. Traces come from a training run with
  snapshot_every_steps + capture_grads (authored via /run-lora-training, executed
  via /run-lora-execute); the sibling /plot-eval-results is for judge-graded EVAL
  figures, not weight/gradient trajectories.
---

# Plot Training Dynamics — drive plot_training_dynamics.py

`tools/plot_training_dynamics.py` turns per-step **training traces** (LoRA factor
snapshots + the live gradients that drove each step) into an interactive view of
*what the adapter is doing at every stage of training*. It answers questions like
"when does the direction lock in vs the magnitude grow?" and "baseline and
msm_america train on identical data yet learn different L7 down-write vectors —
where does that difference come from, as a training-time thing?"

It is **CPU-only** and **reproducibility-strict** (HF trace specs must be pinned
to a commit SHA). It does not train or call Modal — it only reads traces that a
training run already produced.

## 0. Locate the repo + environment

This skill lives in the shared `cc_workspace_mats` repo but operates on the
`midtraining_generalization` project. Find the project repo root (the dir
containing `tools/plot_training_dynamics.py`): use the current dir if it
qualifies, else `projects/midtraining_generalization/` under the workspace root
(do **not** hardcode the `/mnt/...` prefix — the mount name differs per machine).
`cd` there and run the commands below from there. Prefer a clean worktree if the
primary checkout is dirty/protected.

Deps: `numpy`, `matplotlib`, `safetensors`, and (for `hf:` specs) `huggingface_hub`.
Run with the workspace venv or uv, e.g.
`uv run --with huggingface_hub python tools/plot_training_dynamics.py ...`.

## 1. What a trace is (and where it comes from)

A trace is a `delta/trace/` folder produced by a training run that set
`snapshot_every_steps` (and usually `capture_grads`) — see the instrumentation in
`src/msm_eval/training/stacked_lora_aft.py`. Contents:

- `trace_factors.safetensors` — each LoRA factor stacked over snapshots,
  shape `(T, *factor_shape)`, float16, plus an int64 `__steps__` index
  (step 0 = pre-training init, where PEFT sets LoRA `B=0`).
- `trace_grads.safetensors` — same layout for the captured `.grad` tensors
  (present only when the run set `capture_grads`).
- `trace_steps.json` — per-step scalars (loss/lr/grad norms) + run/config metadata
  (`lora_config`, `scaling`, `layers`, `target_modules`, hyperparameters, ...).

The trace rides the run's normal `delta/` upload, so on HF it sits at
`<export_root>/<variant>/delta/trace/`.

**To make a new trace:** author a recipe with `snapshot_every_steps: 1` (and
`capture_grads: true`) via `/run-lora-training`, then run it via
`/run-lora-execute`. Use a fresh `export_root` prefix so you never overwrite
pinned adapters. Snapshots are cheap for low-rank adapters (rank-1 L7 ≈ 484 tiny
snapshots over an epoch-3 run).

## 2. Render the viewer

```
python tools/plot_training_dynamics.py \
  --trace <SPEC_A> --label <A> [--trace <SPEC_B> --label <B>] \
  --out-dir results/training_dynamics [--rolling 5] [--no-png] [--watch SECONDS]
```

- `--trace` (repeatable, max 2): a local trace dir **or** a pinned HF spec
  `hf:<repo>@<40-char-sha>/<subfolder-to-the-trace-dir>`. Floating refs
  (`main`/`latest`/...) are rejected — always pin a SHA. Pass it **twice to diff**
  two runs; the order sets which run is "A" (first) in cross-run charts.
- `--label`: one per `--trace`, in order (used in titles/legends).
- `--no-png`: write only the HTML viewer (skip the static PNGs).
- `--watch SECONDS`: re-render when a **local** trace changes and embed an
  auto-refresh so an open browser tab updates itself (HF specs are immutable, so
  watch is ignored for them) — handy for "update when the run ends" if the trace
  is synced locally.

Output: a self-contained `training_dynamics.html` (inlined data + a small
vanilla-JS/SVG renderer — hover for values, click a legend entry to toggle a
series; opens by double-click, fully offline), `fig01..fig05*.png` (unless
`--no-png`), and `provenance.json`. The tool prints a provenance block (source,
config, layer, scaling, snapshot/step counts, grads y/n).

Worked example (the L7-r1 epoch-3 traced run on HF):

```
SHA=2383c9502591f29cde03083cc329ecc22aadd8bf
BASE="hf:GaloisTheory123/MSM-hillclimb@$SHA/stacked_aft2_trace_epoch3/mlp_l7_r1"
uv run --with huggingface_hub python tools/plot_training_dynamics.py \
  --trace "$BASE/msm_america/delta/trace" --label msm_america \
  --trace "$BASE/baseline/delta/trace"    --label baseline \
  --out-dir results/training_dynamics
```

## 3. Reading the views

Direction convention (matches `notebooks/22_l7r1_adapter_cheese_vector_corrplot.py`):
**down_proj → unit `B[:,0]`** (residual-space "write" vector); **gate/up → unit
`A[0,:]`** ("read"). Because PEFT inits `B=0`, the down-write vector starts at zero
and its sign is physical and comparable across runs (no sign-canonicalization).

- **Loss** — per-step loss (+ rolling mean), both runs, and their delta.
- **Direction** — per module, each run's per-step direction cosine to a *reference
  final*. With two runs the reference is **both** finals (so each chart shows where
  each run heads: the matching run climbs to 1.0, the other settles at the
  cross-run value); with one run it's that run's own final. Rising fast = the
  direction locks early.
- **Magnitude** — per module, `||scaling·B@A||_F` over steps. Pair with Direction
  for the classic "direction locks early, magnitude keeps growing".
- **Cross-run geometry** (two runs) — per-step cosine between the two runs'
  evolving directions, + the final cross-run cosine annotation.
- **Gradient origin** — the down-write **descent** direction (`-grad`) cosine to
  each reference final (which final the gradient pulls toward over training), plus
  (two runs) the cross-run `dL/dB_down` cosine. Peaks early then decays to ~0 once
  the direction is set and later steps only grow magnitude.

Notes: rank-1 is the first-class case; for r>1 the direction uses the top singular
vector (sign arbitrary across steps — read with care). Step-0 down-write is `B=0`,
so its cosine is NaN and is drawn as a gap.

## 4. Verify / gotchas

- Confirm the HTML has the expected sections; in two-run mode there are 6 direction
  charts (3 modules × 2 finals) and 3 gradient panels. The tool raises if two run
  labels collide into the same chart id — pass distinct labels.
- If gradient panels are missing, the trace had no `trace_grads.safetensors` (run
  without `capture_grads`); everything else still renders.
- A plain HTML refresh reloads the same file from disk — to see a re-render, open
  the newly written file (or use `--watch`).

## 5. Keep this skill sharp

If a run surfaces a rough edge (a confusing chart, a missing metric, an
environment snag), fix `tools/plot_training_dynamics.py` and fold the lesson back
into this SKILL.md so the next agent starts ahead. Plot-only changes to that tool
should still go through the repo's review gate (`/simplify` + an independent
adversarial review) and a PR.
