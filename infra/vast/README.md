# Vast.ai reusable training harness

This directory is project-agnostic. It rents a Vast.ai instance, starts a Docker
image with `uv` installed, then runs whatever `TRAIN_CMD` you provide inside the
chosen `PROJECT_DIR`.

## What I still need from you

1. Create a Vast.ai account, add billing credit, and create an API key.
2. Tell me the container registry you want to use for the image:
   `ghcr.io/<user>/cc-workspace-vast`, Docker Hub, or another registry.
3. Confirm the git remote that Vast should clone. If this workspace is private,
   we need either a deploy key or a read-only token.
4. Provide runtime secrets when launching: at minimum `HF_TOKEN`; usually also
   `WANDB_API_KEY`, and `OPENAI_API_KEY` for eval/judge runs.

Do not bake secrets into the Docker image.

## Local setup

```bash
uv tool install vastai
vastai set api-key "$VAST_API_KEY"
vastai show instances
```

## Build and push the image

Use a pinned tag, not `latest`.

```bash
docker build -f infra/vast/Dockerfile -t ghcr.io/<user>/cc-workspace-vast:cuda128-uv .
docker push ghcr.io/<user>/cc-workspace-vast:cuda128-uv
```

The image intentionally does not copy this repo or run `uv sync`. That keeps it
reusable across projects. If a project has a slow dependency solve/install, make
a project-specific derived image later.

## Find offers

```bash
MIN_GPUS=8 MIN_GPU_RAM_GB=24 OFFER_TYPE=on-demand infra/vast/search_offers.sh
```

Cheaper but preemptible:

```bash
MIN_GPUS=8 MIN_GPU_RAM_GB=24 OFFER_TYPE=bid infra/vast/search_offers.sh
```

Prefer `verified=True`, high `reliability`, enough disk, and good download
bandwidth. Vast volumes can warm-cache a specific host, but they are not portable
across hosts, so Hugging Face/S3/W&B should remain the source of truth.

## Launch a generic job

```bash
export OFFER_ID=<offer-id>
export IMAGE=ghcr.io/<user>/cc-workspace-vast:cuda128-uv
export GIT_REPO=git@github.com:<org>/<repo>.git
export GIT_REF=<branch-or-commit>
export PROJECT_DIR=/workspace/cc_workspace_mats/<project-path>
export SETUP_CMD='uv sync --frozen'
export TRAIN_CMD='uv run python -c "import torch; print(torch.cuda.device_count())"'

infra/vast/create_instance.sh
```

## DARE example

```bash
export OFFER_ID=<offer-id>
export IMAGE=ghcr.io/<user>/cc-workspace-vast:cuda128-uv
export GIT_REPO=git@github.com:<org>/<repo>.git
export GIT_REF=migration/gpu-transfer
export PROJECT_DIR=/workspace/cc_workspace_mats/projects/dare
export SETUP_CMD='uv sync --frozen && MAX_JOBS=16 uv pip install flash-attn --no-build-isolation'
export TRAIN_CMD='uv run accelerate launch --mixed_precision bf16 --num_processes ${GPU_COUNT:-8} experiments/train/train_lora.py --split 1 --base_revision before_midtraining --num_epochs 1 --output_dir experiments/train/output_stage1'

infra/vast/create_instance.sh
```

For filtered retraining:

```bash
export PROJECT_DIR=/workspace/cc_workspace_mats/projects/dare
export SETUP_CMD='uv sync --frozen && MAX_JOBS=16 uv pip install flash-attn --no-build-isolation'
export TRAIN_CMD='uv run accelerate launch --mixed_precision bf16 --num_processes ${GPU_COUNT:-8} experiments/retrain/train_filtered.py --manifest experiments/attribute/runs/probe_v6/bold_formatting/results/probe.pt --top_k 2500 --split1 --output_dir experiments/retrain/output/probe_v6_bold_formatting_top2500 --train_data GaloisTheory123/dare-data --max_length 8192'
```

## Operational notes

- Keep `HF_HOME` and model caches under `/workspace/.cache`; make the Vast disk
  large enough for OLMo, vLLM, checkpoints, and cached datasets.
- Delete instances when finished. Stopped instances still keep billable storage.
- Use on-demand first for a long training run. Move to bid/interruptible only
  after checkpoint/resume behavior is verified.
- DARE currently assumes `flash_attention_2`, so install `flash-attn` in
  `SETUP_CMD` or change the model loading path.
- For private repos, the launched container needs an SSH key or HTTPS token that
  can clone the repo.
