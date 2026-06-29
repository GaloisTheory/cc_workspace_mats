#!/usr/bin/env bash
# Link the shared skills into Codex so Claude and Codex use one canonical
# copy (this repo). Idempotent: safe to re-run. Existing real dirs are backed up
# to <codex-skills>/.bak_skills_<epoch>/ before being replaced with a symlink.
#
# Usage:   bash scripts/link-codex-skills.sh
# Override the Codex skills dir:   CODEX_SKILLS=/path/to/.codex/skills bash scripts/link-codex-skills.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/.claude/skills"
CODEX_SKILLS="${CODEX_SKILLS:-$HOME/.codex/skills}"
SKILLS=(vault-load vault-capture code-redteam run-lora-training run-lora-execute plot-eval-results data-analyst)

mkdir -p "$CODEX_SKILLS"
backup=""
for s in "${SKILLS[@]}"; do
  target="$SRC/$s"
  link="$CODEX_SKILLS/$s"
  if [[ ! -d "$target" ]]; then
    echo "SKIP $s: source missing at $target" >&2
    continue
  fi
  if [[ -L "$link" ]]; then
    rm "$link"
  elif [[ -e "$link" ]]; then
    if [[ -z "$backup" ]]; then
      backup="$CODEX_SKILLS/.bak_skills_$(date +%s)"
      mkdir -p "$backup"
    fi
    mv "$link" "$backup/$s"
    echo "backed up existing $s -> $backup/$s"
  fi
  ln -s "$target" "$link"
  echo "linked $link -> $target"
done

echo "done. verify: ls -la \"$CODEX_SKILLS\" | grep -E 'vault|redteam'"
