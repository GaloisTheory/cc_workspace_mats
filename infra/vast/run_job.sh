#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    log "ERROR: ${name} is required"
    exit 2
  fi
}

decode_var() {
  local target="$1"
  local encoded_name="${target}_B64"
  if [ -n "${!encoded_name:-}" ]; then
    printf -v "${target}" '%s' "$(printf '%s' "${!encoded_name}" | base64 -d)"
    export "${target}"
  fi
}

decode_var TRAIN_CMD
decode_var SETUP_CMD
decode_var PRETRAIN_CMD
decode_var POSTTRAIN_CMD
decode_var GIT_REPO
decode_var GIT_REF
decode_var PROJECT_DIR

require_env TRAIN_CMD

WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
REPO_DIR="${REPO_DIR:-${WORKSPACE_DIR}/cc_workspace_mats}"
PROJECT_DIR="${PROJECT_DIR:-${REPO_DIR}}"
SETUP_CMD="${SETUP_CMD:-}"
PRETRAIN_CMD="${PRETRAIN_CMD:-}"
POSTTRAIN_CMD="${POSTTRAIN_CMD:-}"
RUN_NAME="${RUN_NAME:-vast-$(date -u +%Y%m%d-%H%M%S)}"
LOG_DIR="${LOG_DIR:-${WORKSPACE_DIR}/logs/${RUN_NAME}}"
SECRETS_FILE="${SECRETS_FILE:-${WORKSPACE_DIR}/.secrets}"

mkdir -p "${WORKSPACE_DIR}/.cache/huggingface" "${WORKSPACE_DIR}/.cache/torch" "${LOG_DIR}"

if [ -f "${SECRETS_FILE}" ]; then
  log "Loading secrets from ${SECRETS_FILE}"
  set -a
  # shellcheck disable=SC1090
  source "${SECRETS_FILE}"
  set +a
fi

if [ -n "${HF_TOKEN:-}" ] && command -v huggingface-cli >/dev/null 2>&1; then
  log "Logging in to Hugging Face"
  huggingface-cli login --token "${HF_TOKEN}" --add-to-git-credential >/dev/null 2>&1 || true
fi

if [ -n "${WANDB_API_KEY:-}" ] && command -v wandb >/dev/null 2>&1; then
  log "Logging in to W&B"
  wandb login "${WANDB_API_KEY}" >/dev/null 2>&1 || true
else
  export WANDB_MODE="${WANDB_MODE:-disabled}"
fi

if [ ! -d "${REPO_DIR}/.git" ]; then
  require_env GIT_REPO
  log "Cloning ${GIT_REPO} into ${REPO_DIR}"
  git clone "${GIT_REPO}" "${REPO_DIR}"
fi

cd "${REPO_DIR}"

if [ -n "${GIT_REF:-}" ]; then
  log "Checking out ${GIT_REF}"
  git fetch --all --tags
  git checkout "${GIT_REF}"
fi

if [ "${GIT_PULL:-0}" = "1" ]; then
  log "Pulling latest changes"
  git pull --ff-only
fi

if [ "${INIT_SUBMODULES:-1}" = "1" ]; then
  log "Updating submodules"
  git submodule update --init --recursive
fi

if [ -n "${SETUP_CMD}" ]; then
  log "Running setup command"
  bash -lc "cd '${PROJECT_DIR}' && ${SETUP_CMD}" 2>&1 | tee "${LOG_DIR}/setup.log"
fi

if [ -n "${PRETRAIN_CMD}" ]; then
  log "Running pre-training command"
  bash -lc "cd '${PROJECT_DIR}' && ${PRETRAIN_CMD}" 2>&1 | tee "${LOG_DIR}/pretrain.log"
fi

log "GPU inventory"
nvidia-smi 2>&1 | tee "${LOG_DIR}/nvidia-smi.log" || true

log "Starting training: ${TRAIN_CMD}"
set +e
bash -lc "cd '${PROJECT_DIR}' && ${TRAIN_CMD}" 2>&1 | tee "${LOG_DIR}/train.log"
status=${PIPESTATUS[0]}
set -e

if [ -n "${POSTTRAIN_CMD}" ]; then
  log "Running post-training command"
  bash -lc "cd '${PROJECT_DIR}' && ${POSTTRAIN_CMD}" 2>&1 | tee "${LOG_DIR}/posttrain.log" || true
fi

log "Training command exited with status ${status}"
exit "${status}"
