#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  OFFER_ID=123 IMAGE=ghcr.io/you/cc-workspace-vast:tag TRAIN_CMD='uv run ...' infra/vast/create_instance.sh

Required env:
  OFFER_ID       Vast offer id from search_offers.sh
  IMAGE          Docker image containing /usr/local/bin/vast-run-job
  TRAIN_CMD      Command to run inside PROJECT_DIR

Common optional env:
  RUN_NAME       Label/log name
  GIT_REPO       Repo URL to clone if /workspace/cc_workspace_mats is absent
  GIT_REF        Branch, tag, or commit to checkout
  PROJECT_DIR    Default: /workspace/cc_workspace_mats
  SETUP_CMD      Default empty. Example: uv sync --frozen
  DISK_GB        Default: 250
  MIN_GPUS       Used only for NUM_GPUS default in example commands
  VAST_ENV       Extra raw -e/-v args passed to Docker, quoted as one string
EOF
}

if [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

: "${OFFER_ID:?Set OFFER_ID}"
: "${IMAGE:?Set IMAGE}"
: "${TRAIN_CMD:?Set TRAIN_CMD}"

encode_env() {
  printf '%s' "$1" | base64 -w0
}

RUN_NAME="${RUN_NAME:-vast-train-$(date -u +%Y%m%d-%H%M%S)}"
DISK_GB="${DISK_GB:-250}"
REPO_DIR="${REPO_DIR:-/workspace/cc_workspace_mats}"
PROJECT_DIR="${PROJECT_DIR:-${REPO_DIR}}"
SETUP_CMD="${SETUP_CMD:-}"
GIT_REPO="${GIT_REPO:-}"
GIT_REF="${GIT_REF:-}"
INIT_SUBMODULES="${INIT_SUBMODULES:-1}"
VAST_ENV="${VAST_ENV:-}"

ENV_ARGS="-e RUN_NAME=${RUN_NAME} -e REPO_DIR=${REPO_DIR} -e INIT_SUBMODULES=${INIT_SUBMODULES}"
ENV_ARGS="${ENV_ARGS} -e PROJECT_DIR_B64=$(encode_env "${PROJECT_DIR}")"
ENV_ARGS="${ENV_ARGS} -e TRAIN_CMD_B64=$(encode_env "${TRAIN_CMD}")"

if [ -n "${SETUP_CMD}" ]; then ENV_ARGS="${ENV_ARGS} -e SETUP_CMD_B64=$(encode_env "${SETUP_CMD}")"; fi
if [ -n "${GIT_REPO}" ]; then ENV_ARGS="${ENV_ARGS} -e GIT_REPO_B64=$(encode_env "${GIT_REPO}")"; fi
if [ -n "${GIT_REF}" ]; then ENV_ARGS="${ENV_ARGS} -e GIT_REF_B64=$(encode_env "${GIT_REF}")"; fi
if [ -n "${PRETRAIN_CMD:-}" ]; then ENV_ARGS="${ENV_ARGS} -e PRETRAIN_CMD_B64=$(encode_env "${PRETRAIN_CMD}")"; fi
if [ -n "${POSTTRAIN_CMD:-}" ]; then ENV_ARGS="${ENV_ARGS} -e POSTTRAIN_CMD_B64=$(encode_env "${POSTTRAIN_CMD}")"; fi
if [ -n "${HF_TOKEN:-}" ]; then ENV_ARGS="${ENV_ARGS} -e HF_TOKEN=${HF_TOKEN}"; fi
if [ -n "${WANDB_API_KEY:-}" ]; then ENV_ARGS="${ENV_ARGS} -e WANDB_API_KEY=${WANDB_API_KEY}"; fi
if [ -n "${OPENAI_API_KEY:-}" ]; then ENV_ARGS="${ENV_ARGS} -e OPENAI_API_KEY=${OPENAI_API_KEY}"; fi
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then ENV_ARGS="${ENV_ARGS} -e ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"; fi
if [ -n "${VAST_ENV}" ]; then ENV_ARGS="${ENV_ARGS} ${VAST_ENV}"; fi

vastai create instance "${OFFER_ID}" \
  --image "${IMAGE}" \
  --disk "${DISK_GB}" \
  --label "${RUN_NAME}" \
  --ssh \
  --direct \
  --env "${ENV_ARGS}" \
  --onstart-cmd "vast-run-job"
