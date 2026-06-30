---
name: plot-eval-results
description: >-
  Generate, regenerate, or add judge-graded eval-result figures with
  tools/eval_results_plotting.py in the midtraining_generalization repo.
  Interviews the user for which figure(s) they want, classifies the request as
  regenerate-existing / new-figure-of-an-existing-type / new-visual-shape, then
  runs the right path: for an existing plot key it just renders; for a new figure
  it authors a spec in eval_results_specs.py using the plot-type taxonomy, keeps
  every data source pinned to a Hugging Face commit SHA, renders, and verifies the
  output (figures + provenance, byte-diffing against a prior render to catch
  unintended bar movement). Always ends with a self-review that asks how the run
  went and folds the answer back into this skill so it gets sharper each use. Use
  when the user wants to plot / chart / visualize eval results, regenerate a
  figure, add a new eval plot, tweak a figure, or says the plotting "causes too
  many issues." The sibling /run-lora-execute runs full recipe pipelines including
  the plot step and the upload+pin that a new source needs first; this skill
  drives the plotting tool itself.
---

# Plot Eval Results — drive eval_results_plotting.py without the foot-guns

`tools/eval_results_plotting.py` turns judge-graded eval CSVs (pulled from a
pinned Hugging Face dataset) into the paper's bar / delta / line / heatmap
figures. It is **config-driven and reproducibility-strict**, which is exactly why
ad-hoc use "causes too many issues": a new figure usually means authoring a spec,
every data source must be pinned to a commit SHA, and a careless edit can silently
move a published bar. This skill removes that friction by routing each request
down the smallest correct path and gating figure changes.

There are only three kinds of request. Identify which one early — most asks are
the first (cheapest) kind, and jumping straight to editing code is the most common
self-inflicted wound:

- **A. Regenerate an existing figure** — a known `--plot <key>`. No code, just a render.
- **B. New figure of an existing type** — same visual shape as an existing family,
  new data/sources. Author a spec instance; no new renderer.
- **C. New visual shape** — needs a new dataclass + renderer. The biggest cost;
  confirm scope before writing one.

Two hard rules hold for every path: **figures are reproducible only from pinned
Hugging Face sources** (never plot from local result directories), and **changes
to an existing figure are gated on a before/after byte-diff** (the figures back
quantitative claims; a silent bar move is the failure mode, not a crash).

## Phase 0: Locate the repo, the guide, and a working environment

1. **Repo.** This skill lives in the shared `cc_workspace_mats` repo but operates
   on `midtraining_generalization`. Find the project root (the dir containing
   `tools/eval_results_plotting.py`): use the current directory if it qualifies,
   else `projects/midtraining_generalization/` under the workspace root, else ask.
   Do not hardcode the `/mnt/...` prefix — the mount name differs per machine.
   Run every command below from that repo root.
2. **Guide.** Read `tools/EVAL_RESULTS_PLOTTING_GUIDE.md` first — it is the
   canonical plot-type taxonomy (8 families → 3 shapes), the "for a new plot of
   kind X reuse renderer Y" decision table, and the reproducibility contract. If
   it is absent (older checkout), skim `tools/eval_results_specs.py` (the spec /
   registry layer) and `tools/eval_results_plotting.py` (the machinery) to recover
   the families and the `PLOTS` keys; on an even older checkout everything is in
   the single `eval_results_plotting.py`.
3. **Environment.** The tool is standalone (it does not need `src/` on the path).
   It needs `matplotlib` + `huggingface_hub` (+ `safetensors` only for steering
   cosine corrplots). Prefer the repo's `uv` env: `uv run python tools/eval_results_plotting.py ...`.
   If the env lacks the deps, run with `uv run --with matplotlib --with huggingface_hub python ...`.
   Confirm it imports before a real run rather than debugging mid-render.
4. **Online vs offline.** The config's pinned `default_revision` is usually already
   in the local HF cache, so most families render offline with
   `HF_HUB_OFFLINE=1 ... --local-files-only`. The **steering-comparison** plots need
   network (their `list_repo_files` tree call), and `PIN_AFTER_UPLOAD` sources fail
   fast by design. Knowing this up front keeps an expected offline/pin failure from
   being mistaken for a bug.

## Phase 1: Interview — what do you want, and which path is it?

Ask the user, in one focused question, **which figure(s) they want and to what
end**, and surface the available `--plot` keys (from `PLOTS` / `parse_args` choices
in the machinery file, or the catalog in the guide) so they can point at one rather
than describe it. Then classify:

- The ask names or matches an existing key, or "re-run / refresh / update figure X"
  → **Path A**.
- The ask is "the same kind of plot but for <new run / new layer / new seed / new
  host>" → **Path B** (find the closest existing spec of that family to clone).
- The ask is a genuinely new layout (a shape not in the catalog) → **Path C**.

Do not start editing `eval_results_specs.py` until the request is confirmed to be
B or C. If it is A, skip straight to Phase 2A.

## Phase 2A: Regenerate an existing figure

1. Render the specific key(s); prefer naming keys over `--plot all`:
   ```
   uv run python tools/eval_results_plotting.py --plot <key> --out-dir <dir>
   ```
2. `--plot all` renders **only the standard set**, not everything. Group selectors:
   `all` (standard), `seed-replicates`, `all-10x`, `l11-r1`, `all-trajectories`,
   `steering-sweeps`, `comprehensive-msm-sweep`; plus any individual `key`. State
   which keys a group covers before running it.
3. If the render aborts with `PIN_AFTER_UPLOAD` or a floating-revision error, that
   is **correct behavior**: the source artifact is not uploaded/pinned yet. Do not
   work around it (do not edit the revision to a branch, do not point at a local
   file). The fix is upstream — the data must be uploaded to HF and the source
   pinned to its commit SHA (that is `/run-lora-execute`'s upload+pin step). Report
   that and stop, or pin the SHA if the user already has it.
4. Report where figures + `provenance.json` landed.

## Phase 2B: New figure of an existing type

1. **Pick the family** from the guide's decision table (e.g. grouped bars + delta →
   `PlotSpec`; host × eval ladder → `BaselineCompareSpec`; line over epochs →
   `TrajectorySpec`). Find the closest existing spec of that family to clone.
2. **Confirm the data is on HF and pinned.** Every source the spec references must
   exist in `configs/eval_results_sources.json` with a concrete 40-hex commit SHA.
   If the eval results are not yet uploaded, **stop** — they must be uploaded and
   pinned first (`/run-lora-execute`), because figures are reproducible only from
   pinned HF sources. Never add a `local_path` or a local result dir to "make it
   render."
3. **Author the spec** in `tools/eval_results_specs.py` (the declarative layer;
   it is re-exported into `eval_results_plotting.py`, so existing imports keep
   working). Match the conventions of the sibling specs: a stable `key=`, a `folder=`
   output subdir, `evals`, the family/bar/source structure, and `metric`. Register
   it in the matching registry and, if it should be group-selectable, the relevant
   selector. `delta_bars` defaults to `bars`.
4. **Capture a baseline** if a closely-related key already renders: render it to a
   scratch dir first, so Phase 3 can byte-diff and prove the new spec did not
   perturb a neighbor.
5. **Dry-render** the new key to a scratch `--out-dir`; confirm figures and
   `provenance.json` are written and that `provenance.json` shows `from_hf: true`
   with the pinned SHA for every source.

## Phase 2C: New visual shape

Escalate and confirm scope before writing code — this is the heaviest path. It
needs a new frozen dataclass (in `eval_results_specs.py`), a `render_*` entry point
+ `draw_*` function (in `eval_results_plotting.py`), and a branch in
`render_any_plot`'s isinstance dispatch. **Reuse the shared primitives** rather than
re-rolling them: `ci_bar`, `rate_value_label` / `delta_value_label`,
`symmetric_delta_ylim`, `save_figure`, and `source_provenance`. Spell out the new
shape and the renderer plan to the user, get a go, then build it and verify like
any other change.

## Phase 3: Verify

1. The render completed and wrote figures to `<out-dir>/<folder>/...` with a
   `provenance.json` beside them.
2. **Gate figure changes on a byte-diff.** For any change that could affect an
   existing figure (editing a shared spec, a renderer, a constant, or the config),
   render the affected keys to a scratch dir *before* and *after* the change and
   `cmp` the PNGs — they must be byte-identical unless a visual change was the
   explicit intent. PNG output is deterministic, so a diff means a real change.
   (See the regression-harness notes the guide / project memory describe.)
3. **Reproducibility check.** Every source in the new/changed `provenance.json` is
   `from_hf: true` with a pinned SHA, or a deliberate `from_hf: false` local source
   the user accepted. No floating revisions.

## Phase 4: Skill self-review & improvement (always run this)

This is the point of the skill: it should get better every time it is used, for
both Claude and Codex.

1. **Self-assess.** Note where this run stalled, backtracked, guessed, or hit a
   step that was wrong or missing here — environment/venv surprises, a selector
   that did not do what the docs implied, a pinning error that was confusing, an
   interview question that missed the real intent.
2. **Ask the user**, briefly and concretely: "How did that go — any friction, wrong
   turns, or missing context I should bake into this skill so next time is
   smoother?" Prefer specifics over a yes/no.
3. **Improve this file.** Turn the user's answer + your own observations into
   concrete edits to **this** skill (`.claude/skills/plot-eval-results/SKILL.md` in
   the `cc_workspace_mats` repo — the canonical copy Codex shares via symlink). Add
   a gotcha to *Known gotchas*, fix a command, sharpen an interview question, or
   correct a step. Propose the diff, get a quick OK (it is a tracked, cross-agent
   file), apply it, and add a dated one-line entry to the *Changelog*. Keep edits
   small and specific — accumulated one-liners beat rewrites.
4. If a learning is about the **tool** rather than the skill (a real bug or missing
   guardrail in `eval_results_plotting.py`), say so and offer to fix the tool /
   open an issue instead of only documenting it here.

## Known gotchas (living — Phase 4 appends here)

- `--plot all` renders only the standard set, not every figure. Name keys or the
  right group selector.
- `PIN_AFTER_UPLOAD` / floating-revision aborts are correct, not bugs — the data
  must be uploaded to HF and pinned to a SHA first (`/run-lora-execute`). Do not
  point the source at a branch or a local file to force a render.
- The steering-comparison plots need network for their vector-file listing; other
  families render offline against the cached pinned revision. An offline failure on
  steering is expected, not a regression.
- System Python often lacks `matplotlib` / `huggingface_hub`; use the repo's `uv`
  env (the tool does not need `src/` on the path).
- The spec/registry layer lives in `eval_results_specs.py` (re-exported into
  `eval_results_plotting.py`); add new specs there.

## Changelog

- 2026-06-24: initial version.

## Guardrails (non-negotiable)

- Figures are reproducible **only** from pinned Hugging Face sources. Never plot
  from local result directories, and never relax a source to a branch or a
  `local_path` to make a render succeed.
- Do not work around `PIN_AFTER_UPLOAD` or floating-revision errors; they are the
  reproducibility contract doing its job. Route to upload+pin upstream.
- Gate any change that can touch an existing figure on a before/after PNG byte-diff.
  These figures back paper claims; a silent bar movement is the real failure.
- When the user only wants an existing figure refreshed (Path A), render it — do
  not re-author specs.
- Always run Phase 4. Edits to this skill go through a quick user OK because it is a
  tracked file shared by Claude and Codex; never rewrite it wholesale silently.
