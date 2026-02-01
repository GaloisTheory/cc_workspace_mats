# MATS Workspace

Shared resources and configuration for MATS projects.

## Structure

- `skills/` - Reusable Claude Code skills
- `projects/` - Cloned repositories (gitignored, each has its own git history)

## Organization Guidelines

**Project-specific content:** Anything specific to a particular research project should live inside the `projects/<project-name>/` folder within that project's own git repository.

**Workspace-level content:** Only shared resources, reusable skills, and general configuration that applies across multiple projects should live at the workspace root level.
