#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/mnt/filesystem-a6/cc_workspace_mats}"
VAULT_PATH="${VAULT_PATH:-${WORKSPACE_ROOT}/projects/dohun_vault}"
SECRETS_FILE="${SECRETS_FILE:-${WORKSPACE_ROOT}/.secrets}"
VAULT_REMOTE="${VAULT_REMOTE:-https://github.com/GaloisTheory/dohun_vault.git}"

mkdir -p "$WORKSPACE_ROOT/projects"

# Source secrets.
if [[ ! -f "$SECRETS_FILE" ]]; then
  echo "AUTH_FAIL: no secrets file"
  echo "secrets file not found at $SECRETS_FILE" >&2
  exit 5
fi
set -a
# shellcheck disable=SC1090
source "$SECRETS_FILE"
set +a

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "AUTH_FAIL: GITHUB_TOKEN unset"
  echo "GITHUB_TOKEN is empty after sourcing $SECRETS_FILE" >&2
  exit 5
fi

# Export so the credential helper subshell can see it. Token never goes in the URL.
export GITHUB_TOKEN
CRED='credential.helper=!f() { echo username=x-access-token; echo "password=$GITHUB_TOKEN"; }; f'

if [[ ! -e "$VAULT_PATH/.git" ]]; then
  if git -c "$CRED" clone "$VAULT_REMOTE" "$VAULT_PATH" >&2; then
    echo "CLONED"
    exit 0
  else
    echo "AUTH_FAIL: clone failed"
    echo "git clone failed for $VAULT_REMOTE" >&2
    exit 5
  fi
fi

# Existing repo: check for local changes before pulling.
status_out="$(git -C "$VAULT_PATH" status --porcelain)"
if [[ -n "$status_out" ]]; then
  echo "DIRTY"
  echo "working tree has uncommitted changes; not pulling" >&2
  exit 3
fi

# Clean: attempt a fast-forward-only pull.
pull_err="$(git -C "$VAULT_PATH" -c "$CRED" pull --ff-only 2>&1 1>/dev/null)" && pull_rc=0 || pull_rc=$?
if [[ "$pull_rc" -eq 0 ]]; then
  echo "CLEAN+PULLED"
  exit 0
fi

echo "$pull_err" >&2
if echo "$pull_err" | grep -qiE 'non-fast-forward|diverge|not possible to fast-forward|cannot fast-forward'; then
  echo "DIVERGED"
  exit 4
fi
if echo "$pull_err" | grep -qiE 'authentication|could not read|permission denied|403|401|fatal: could not read Username|terminal prompts disabled'; then
  echo "AUTH_FAIL: pull failed"
  exit 5
fi

# Unknown failure: fail safe as AUTH_FAIL so callers always STOP.
echo "AUTH_FAIL: pull failed"
exit 5
