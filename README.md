# MATS Workspace

Shared Claude Code resources and commands for MATS research projects.

This repo provides reusable skills, prompts, and the **Ralph Wiggum** autonomous development loop for use across multiple projects.

## Setup

```bash
# Add ralph to PATH (add to ~/.zshrc)
export PATH="$PATH:$HOME/path/to/099_workspace_setup/ralph"
```

## Usage Flow

### Starting a new project with Ralph

```bash
# 1. Create/navigate to your project
cd ~/projects/my-research-project
git init

# 2. Initialize Ralph files
ralph.sh init
# OR interactively: claude → /ralph-init

# 3. Generate specs (interactive — requires human conversation)
claude
# Then: /ralph-specs
# Discuss your JTBD, answer questions, Claude generates specs/*.md

# 4. Customize AGENTS.md with your project's test/build/lint commands

# 5. Run planning loop
ralph.sh plan
# Reads specs, analyzes codebase, generates IMPLEMENTATION_PLAN.md

# 6. Run building loop
ralph.sh build --max 30
# Creates branch ralph/my-feature-20260201-1430
# Each iteration: pick task → implement → test → commit → repeat
# On completion: pushes branch, creates draft PR

# 7. Review and merge
gh pr view                    # or: claude → /ralph-review
gh pr merge --squash
ralph.sh cleanup              # removes merged worktree branches
```

### Resuming an interrupted session

```bash
ralph.sh build
# > Found existing Ralph session on branch ralph/xyz. Resume? (y/n)
# > y
# Continues from where it left off
```

### Scoped work on a branch

```bash
ralph.sh plan-work "add attention visualization"
ralph.sh build
```

## Structure

```
099_workspace_setup/
├── ralph/
│   ├── ralph.sh              # Main loop script
│   ├── prompts/              # Iteration prompts
│   └── templates/            # Project templates
├── .claude/commands/         # Slash commands (/ralph-*)
└── skills/                   # Reusable Claude Code skills
```
