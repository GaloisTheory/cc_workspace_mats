# Modal EM Distributed Jobs Runbook

This is workspace-level Modal infrastructure. Keep it here so the same image,
capacity probe, and stage-runner patterns can be reused for projects beyond
DARE.

For the current EM DARE workflow, run commands from the workspace root:

```bash
cd /mnt/filesystem-z4/cc_workspace_mats
```

## Why The Runner Lives Here

The reusable Modal code lives in `infra/modal`. The experiment source lives in
`projects/dare`. A remote Modal job does two separate things:

1. Modal uploads this runner and image definition from the local workspace.
2. The remote container clones `jrosseruk/dare` at `--git-ref` and runs named
   EM stages from that committed source tree.

That is standard practice for dependency-heavy Modal workflows: bake
dependencies into an image, keep source code in git, and clone an explicit ref
at runtime.

## Mental Model

- A Modal function is one remote container invocation.
- A Modal image is the reproducible environment. Here it bakes DARE's
  `projects/dare/uv.lock`, CUDA, torch, and `flash-attn`, but not DARE source
  code.
- A Modal volume is persistent storage across invocations. This workflow uses
  one cache volume at `/cache` and one EM artifact volume at `/artifacts/em`.
- A Modal secret is environment variables injected securely. Do not commit API
  tokens or private dataset names.
- `H100:8` means one container with eight colocated H100s. That is what
  `accelerate launch --num_processes 8` wants: eight processes sharing one
  host, not eight independent containers.

The runner is deliberately not a shell executor. `em_job.py` exposes named
stages for the EM workflow and checks out a committed git ref before running.

## Lesson 1: Install And Auth Modal

You run:

```bash
uv tool install modal
modal token new
modal profile current
```

What this proves:

- `uv tool install modal` puts the Modal CLI on your PATH.
- `modal token new` authenticates this machine.
- `modal profile current` confirms the CLI can read a configured profile.

## Lesson 2: Make DARE Code Visible To Modal

Modal cannot clone local untracked files from your laptop. Commit and push the
DARE experiment code before remote runs:

```bash
cd /mnt/filesystem-z4/cc_workspace_mats/projects/dare
git status --short
git add experiments_EM tests/test_em_testbed.py
git commit -m "Add EM DARE experiment testbed"
git push origin main
```

If the EM code is already committed, this should show nothing to commit. Use a
branch or commit SHA as `--git-ref`; commit SHAs are better for exact
reproduction.

Return to the workspace root afterward:

```bash
cd /mnt/filesystem-z4/cc_workspace_mats
```

## Lesson 3: Capacity Probe

You run:

```bash
PROBE_GPU=H100:8 PROBE_RUNS=3 PROBE_TIMEOUT=900 modal run -m infra.modal.probe_capacity
PROBE_GPU=H200:8 PROBE_RUNS=3 PROBE_TIMEOUT=900 modal run -m infra.modal.probe_capacity
```

What this proves:

- The request reaches Modal.
- Modal can or cannot currently schedule that GPU shape for your account.
- The reported wall time is mostly scheduler queue plus cold start because the
  probe image is intentionally tiny.

Healthy capacity usually returns in minutes or less. A timeout means try
another SKU, smaller count, or reserved capacity.

## Lesson 4: Build The Training Image

You run:

```bash
modal run -m infra.modal.image
```

What this proves:

- Modal can build from the CUDA base image.
- `projects/dare/pyproject.toml` and `projects/dare/uv.lock` resolve cleanly.
- `flash-attn` compiles in the image.
- Torch sees a real H100 in the smoke test.

The first build is slow. Later runs reuse cached image layers until `uv.lock`,
CUDA image, or the flash-attn spec changes.

## Lesson 5: Secrets And Volumes

You run:

```bash
modal secret create dare-secrets \
  HF_TOKEN=... \
  WANDB_API_KEY=... \
  OPENAI_API_KEY=... \
  ANTHROPIC_API_KEY=...
```

Required for the full workflow: `HF_TOKEN`, `WANDB_API_KEY`,
and `OPENAI_API_KEY`. `HF_TOKEN` needs access to the private default finance
dataset configured in `projects/dare/experiments_EM/config.py`.
`ANTHROPIC_API_KEY` is needed only if a chosen attribution method or judge uses
Anthropic. `GITHUB_TOKEN` is optional for private GitHub access.

You can still override the finance dataset without changing code:

```bash
modal run -m infra.modal.em_job --stage build_data --git-ref main \
  --finance-data some-org/some-other-finance-dataset
```

The runner creates these volumes automatically if missing:

- `dare-cache`: mounted at `/cache`.
- `dare-em-artifacts`: mounted at `/artifacts`; EM outputs live under
  `/artifacts/em`.

## Lesson 6: First Runner Check

You run:

```bash
modal run -m infra.modal.em_job --stage doctor --git-ref main
```

What this proves:

- The workspace-level runner submits successfully.
- The remote container can clone the DARE ref.
- The baked environment can run `uv sync --frozen --no-dev --inexact` against
  that ref, preserving baked extras like `flash-attn`.
- The volume mounts exist.
- Expected secrets are present or missing, without printing values.
- The finance dataset source is either the default from DARE config or an
  `EM_FINANCE_DATASET` override.
- GPUs are visible through `nvidia-smi`.
- Torch, CUDA, and `flash-attn` still import after runtime repo sync.

By default GPU stages request `H100:8`. Override at import time if needed:

```bash
EM_MODAL_GPU=H200:8 modal run -m infra.modal.em_job --stage doctor --git-ref main
```

## Lesson 7: EM Workflow Stages

Start with cheap smoke limits:

```bash
modal run -m infra.modal.em_job --stage build_data --git-ref main \
  --finance-limit 100 --benign-limit 100

modal run -m infra.modal.em_job --stage train_finance_only --git-ref main \
  --train-max-examples 16 --report-to none

modal run -m infra.modal.em_job --stage train_mixed --git-ref main \
  --train-max-examples 16 --report-to none

modal run -m infra.modal.em_job --stage eval_pre_dare --git-ref main \
  --max-new-tokens 64
```

If the judge API key is unavailable or you only want to smoke-test model
generation and adapter loading, disable scoring explicitly:

```bash
modal run -m infra.modal.em_job --stage eval_pre_dare --git-ref main \
  --max-new-tokens 64 --judge-model ""
```

Then remove smoke limits for full runs:

```bash
modal run -m infra.modal.em_job --stage build_data --git-ref main
modal run -m infra.modal.em_job --stage train_finance_only --git-ref main --detach
modal run -m infra.modal.em_job --stage train_mixed --git-ref main --detach
modal run -m infra.modal.em_job --stage eval_pre_dare --git-ref main
modal run -m infra.modal.em_job --stage review
```

Only run attribution after reviewing the pre-DARE report and confirming both
finance-only and mixed adapters reproduce the target behavior:

```bash
modal run -m infra.modal.em_job --stage attribute --git-ref main
modal run -m infra.modal.em_job --stage build_filtered --git-ref main
modal run -m infra.modal.em_job --stage retrain_grid --git-ref main --detach
modal run -m infra.modal.em_job --stage review
```

For attribution smoke tests:

```bash
modal run -m infra.modal.em_job --stage attribute --git-ref main \
  --attribute-n-docs 32 --methods contrastive_probe
```

## Lesson 8: Monitor And Debug

- Logs stream in the terminal for attached runs.
- `--detach` leaves the Modal app running after your terminal disconnects; use
  the Modal dashboard or CLI logs to inspect it.
- A failed invocation can be rerun by repeating the same stage. Artifacts are
  in the volume, so later stages can resume from previous outputs.
- If a command fails before the EM script starts, check `doctor`: wrong git ref,
  missing secret, no GPU capacity, or image build failure.
- If a training stage fails after launch, inspect the `accelerate` traceback and
  rerun with `--train-max-examples 16 --report-to none`.

## Stage Reference

| Stage | What it runs | Writes |
| --- | --- | --- |
| `doctor` | checkout, secret presence checks, `nvidia-smi` | nothing |
| `build_data` | `experiments_EM/train/build_datasets.py` | `/artifacts/em/data` |
| `train_finance_only` | 8-process LoRA on finance data | `/artifacts/em/output/finance_only` |
| `train_mixed` | 8-process LoRA on 50/50 data | `/artifacts/em/output/finance_benign_50_50` |
| `eval_pre_dare` | generation, judging, pre-DARE report | `/artifacts/em/reports` |
| `attribute` | gated DARE attribution | `/artifacts/em/attribute_runs` |
| `build_filtered` | rm50 dataset builder | `/artifacts/em/data/filtered` |
| `retrain_grid` | filtered retraining commands | `/artifacts/em/output/filtered` |
| `review` | artifact listing and report printout | nothing |
