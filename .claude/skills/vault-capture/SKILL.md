---
name: vault-capture
description: Write durable project memory into the dohun_vault repo. STATE.md is the current snapshot; sessions are append-only evidence. Use when ending a work session or recording decisions, progress, blockers, or handoff notes for a project so the next agent can resume without re-deriving context. Requires an explicit project slug.
---

# Vault Capture

Write durable project memory into `dohun_vault` WITHOUT loading old history by
default. `STATE.md` is the curated current snapshot; session notes are
append-only evidence. The manifest-first flow keeps context small — read the
manifest, then selectively open only what you need.

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

Require an explicit project slug (e.g. `tda_olmo`). Ask the user if it is
missing. Do NOT infer the slug from the current working directory.

## 2. Prepare

Run `scripts/prepare_vault.sh` (no args). It clones the vault if missing,
otherwise stops on a dirty working tree, otherwise `pull --ff-only`. Its first
stdout line is a status token:

- `CLONED` or `CLEAN+PULLED` — proceed.
- `DIRTY` (exit 3), `DIVERGED` (exit 4), `AUTH_FAIL` (exit 5) — STOP and tell
  the user exactly what happened. Do NOT merge, rebase, or force anything.

## 3. Read (manifest-first)

Run `scripts/context_manifest.py <project>` to list the project's root files
(`STATE.md`/`README.md`/`AGENTS.md` with line + byte sizes) and sessions
newest-first (filename, title, line + byte size) WITHOUT printing file bodies.
If it exits 2, the project is missing — it prints available slugs; ask the user
before creating a new project dir.

Then load progressively:

1. Read `<project>/STATE.md` first.
2. Read `README.md` only if unfamiliar with the project or `STATE.md` lacks
   orientation.
3. Read the newest session only when a concrete missing detail remains. Read up
   to three sessions only when still necessary.

Do NOT read every session.

If this session changed durable *working norms* (code style, compute policy,
how to work on the project), update `<project>/AGENTS.md` — not `STATE.md`.
`AGENTS.md` is the working contract; `STATE.md` is the current-state snapshot.

## 4. Capture

Ask only for missing info. Prefer ONE combined question covering: the session
focus, invisible context (things not visible in the diff/logs), and what the
next agent must not miss.

Get the session path from
`scripts/allocate_session_path.py <project> "<focus>"`. It prints a unique
UTC-timestamped, slugified path under `<project>/sessions/` and creates the
parent dir, but NOT the file. Write to exactly that path.

Write ONE dense session note, **40-80 lines**, starting at byte 1 with YAML
frontmatter:

```yaml
---
type: session
project: <slug>
date: <YYYY-MM-DD>
agent: <your runtime: claude or codex>
slug: <session-slug>
title: <human-readable title>
tags: [session, agent-memory, <project>]
---
```

The H1 is the human-readable title. Include these sections: summary, completed
work, decisions/rationale, files/artifacts, commands/results, blockers/
questions, next actions, and what to load next time.

Style:

- Use `[[wikilinks]]` for vault notes and backticked paths for
  code/logs/branches/commits.
- Keep command output to one command line plus 1-3 key result lines; link long
  logs rather than pasting them.

## 5. Rewrite STATE.md

REWRITE `<project>/STATE.md` as a curated snapshot (**50-90 lines**) — not a
log. Frontmatter:

```yaml
---
project: <slug>
updated: <YYYY-MM-DD>
last_agent: <your runtime: claude or codex>
phase: <current phase>
---
```

Cover: where we are, in progress, next priority, blockers/questions, recent
decisions, key files, and latest sessions.

## 6. Dry run

If the user asks for a dry run, do NOT write, commit, or push. Present a concise
preview of the session note and STATE.md changes instead.

## 7. Commit and push

Validate scoped to `<project>/` only:

```bash
git -C "$VAULT_PATH" status --short
git -C "$VAULT_PATH" diff --stat -- <project>/
git -C "$VAULT_PATH" diff --check -- <project>/
git -C "$VAULT_PATH" diff --name-status -- <project>/
```

Commit ONLY this project's changes. Push using the same one-shot
credential-helper pattern as `prepare_vault.sh` (token from `.secrets`, never
stored). If the push is rejected, STOP and tell the user. Do NOT merge, rebase,
or force-push.
