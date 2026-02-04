# MATS Workspace

Shared resources and configuration for MATS projects.

## Structure

- `ralph/` - Ralph Wiggum autonomous development loop (prompts, templates, main script)
- `skills/` - Reusable Claude Code skills
- `projects/` - Cloned repositories (gitignored, each has its own git history)

## Organization Guidelines

**Project-specific content:** Anything specific to a particular research project should live inside the `projects/<project-name>/` folder within that project's own git repository.

**Workspace-level content:** Only shared resources, reusable skills, and general configuration that applies across multiple projects should live at the workspace root level.

## Ralph Wiggum (Autonomous Development Loop)

This workspace includes the Ralph Wiggum autonomous development methodology.
Ralph is an external bash loop that iteratively feeds prompts to Claude Code
in headless mode, with fresh context each iteration.

### Quick Reference

- `/ralph-init` — Initialize Ralph in a project
- `/ralph-specs` — Interactive requirements gathering (Phase 1)
- `/ralph-launch` — Pre-launch checklist
- `/ralph-review` — Review Ralph's work
- `ralph.sh plan` — Run planning loop (Phase 2, in separate terminal)
- `ralph.sh build` — Run building loop (Phase 3, in separate terminal)

### Key Files (in target projects)

- `specs/*.md` — Requirements (one per topic of concern)
- `IMPLEMENTATION_PLAN.md` — Prioritized task list (generated/managed by Ralph)
- `AGENTS.md` — Operational guide (how to build/test/run)

### Key Files (in workspace)

- `ralph/ralph.sh` — Main loop script
- `ralph/prompts/PROMPT_plan.md` — Planning mode prompt
- `ralph/prompts/PROMPT_build.md` — Build mode prompt
- `ralph/prompts/PROMPT_plan_work.md` — Scoped planning prompt
- `ralph/templates/AGENTS.md.template` — Template for new projects

### Principles

- Each iteration gets fresh context (external loop, not plugin)
- One task per iteration, commit on success
- `IMPLEMENTATION_PLAN.md` is shared state between iterations
- `AGENTS.md` captures operational learnings
- Plan is disposable — regenerate when specs change or approach is wrong
- Slash commands run interactively; `ralph.sh` runs in a separate terminal

## Claude Code Notifications

This workspace has hooks configured to send push notifications when Claude needs input (permission prompts, idle state).

### Setup (one-time per machine)

1. **Install jq** (if not installed):
   ```bash
   apt-get install -y jq  # Linux
   brew install jq        # macOS
   ```

2. **Subscribe to notifications** at: `https://ntfy.sh/claude-code-notify-abc123`
   - Open in browser, or install ntfy app on phone

3. **Add to your shell profile** (`~/.bashrc` or `~/.zshrc`):
   ```bash
   export CLAUDE_NTFY_TOPIC="claude-code-notify-abc123"
   ```

### Per-terminal tab naming (optional)

Set a custom name for each terminal to identify which tab needs attention:
```bash
export CLAUDE_TAB_NAME="my-task-name"
```

Notifications will show: `[my-task-name]: Claude needs your attention`

### How it works

- Hook config: `.claude/settings.json`
- Hook script: `.claude/hooks/notify-input-needed.sh`
- Triggers on: `permission_prompt`, `idle_prompt` events
