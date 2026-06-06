---
name: vault-load
description: Onboard from the dohun_vault repo with progressive loading. STATE.md is the handoff contract; session notes are optional detail. Use at the start of a work session to resume a project, recover context, or answer a question about prior progress, decisions, blockers, or key files. Requires an explicit project slug.
---

# Vault Load

Onboard from `dohun_vault` with **progressive loading**. `STATE.md` is the
handoff contract; session notes are optional detail. Carry forward a compact
summary — not raw session text.

## Environment (ENV-overridable defaults)

The helper scripts read these; override via env if needed:

- `WORKSPACE_ROOT` = `/mnt/filesystem-a6/cc_workspace_mats`
- `VAULT_PATH` = `${WORKSPACE_ROOT}/projects/dohun_vault`
- `SECRETS_FILE` = `${WORKSPACE_ROOT}/.secrets`
- `VAULT_REMOTE` = `https://github.com/GaloisTheory/dohun_vault.git`

Helper scripts live in `scripts/` relative to this skill directory.
`GITHUB_TOKEN` is read from `.secrets` via a one-shot credential helper and is
never stored on disk.

## 1. Inputs

Require an explicit project slug. Ask the user if it is missing. Do NOT infer
the slug from the current working directory.

## 2. Prepare

Run `scripts/prepare_vault.sh` (no args). Its first stdout line is a status
token:

- `CLONED` or `CLEAN+PULLED` — proceed.
- `DIRTY` (exit 3), `DIVERGED` (exit 4), `AUTH_FAIL` (exit 5) — STOP and tell
  the user. Do NOT merge, rebase, or force anything.

## 3. Load (progressive)

Run `scripts/context_manifest.py <project>` to list root files and recent
session sizes WITHOUT printing bodies. If the project does not exist (exit 2),
it prints available slugs — ask the user which listed slug to use.

Read in this order, stopping as soon as you have enough:

1. `<project>/STATE.md` — the handoff contract.
2. `<project>/AGENTS.md` if it exists — the project's working contract (how to
   work here: code style, compute, guardrails). Always load this when present.
3. `README.md` only if unfamiliar with the project or `STATE.md` lacks
   orientation.
4. The newest session only if `STATE.md` points to it or leaves a concrete
   missing detail.
5. Older sessions only to answer a specific question. Stop at three sessions
   unless the user asks for deeper history.

The vault-root `AGENTS.md` is the vault operating manual — read it only when
changing vault conventions, not for normal project work.

If `STATE.md` or a session is larger than ~100 lines / ~10 KB (per the
manifest), inspect headings and relevant sections first rather than reading the
whole file.

Carry forward a compact summary, open questions, decisions, and file refs — not
raw session text.

## 4. Response

Briefly state what you loaded, then summarize: current phase, next priority,
blockers, recent decisions, key files/artifacts, and which sessions you read.
Keep it concise so the user can redirect you straight into work.
