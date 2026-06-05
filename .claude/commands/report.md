# Progress Report

Generate a structured progress report for a project and save it to a local
reports directory or a user-provided output path.

## Usage

`/report <project-path>` - Report on a specific project
`/report <project-path> --out <output-dir>` - Save into a specific directory
`/report` - Prompt for project path and output directory

$ARGUMENTS

## Instructions

You are generating a polished progress report documenting findings from a
single project. Use the project files plus user input to produce a substantive
record that another collaborator can understand without extra context.

Do not commit, push, or assume a separate logbook repository. Save the final
report as a normal file.

---

### Phase 1: Parse & Discover

1. **Parse `$ARGUMENTS`.**

   - Treat the first non-flag argument as the project path.
   - Support `--out <output-dir>` to choose where reports are written.
   - If the project path is missing, use `AskUserQuestion` to ask for it.
     Suggest nearby directories if obvious.
   - If `--out` is missing, default to `reports/` in the current working
     directory and tell the user they can override it with `--out`.

2. **Read the project's key files.** Look for and read whichever of these exist:
   - `CLAUDE.md`, `AGENTS.md`, `README.md`, `spec.md`, `progress.md`
   - Files in `results/`, `outputs/`, `figures/`, or `docs/`

3. **Discover project artifacts.** Scope all searches to the target project:
   - Notebooks: `**/*.ipynb`
   - Scripts: `**/*.py`, `**/*.sh`, `**/*.ts`, `**/*.tsx`
   - Config files: `**/*.yaml`, `**/*.yml`, `**/*.json`, `**/*.toml`
   - Results: `**/*.csv`, `**/*.tsv`, `**/*.jsonl`, `**/*.txt`
   - Figures/media: `**/*.png`, `**/*.jpg`, `**/*.svg`, `**/*.html`, `**/*.pdf`

4. **Determine the next report filename.**

   - Find existing reports matching `<output-dir>/[0-9][0-9][0-9]_*.md`.
   - The next report number is `max + 1`, zero-padded to 3 digits.
   - If no reports exist, start at `001`.
   - Derive the project slug from the project directory name by lowercasing and
     replacing non-alphanumeric runs with underscores.

5. **Print a discovery summary:**

   ```text
   Project: <path>
   Output: <output-dir>/<NNN>_<project_slug>.md
   Key files found:
     - README.md (read)
     - progress.md (read)
   Artifacts discovered:
     - N notebooks, M scripts, K figures
   ```

---

### Phase 2: Interview

Use `AskUserQuestion` to gather information you cannot infer from files alone.

6. Ask for:

   - **Report title/topic:** suggest a title based on discovered files.
   - **Key findings:** present discovered results or outputs as options when
     available, and let the user add findings you cannot see.
   - **Figures to include:** only ask if figures or visual outputs were found.
   - **Surprises/failures:** ask what did not work or was unexpected.
   - **Next steps:** ask what follow-up work should be captured.

---

### Phase 3: Draft Report

7. **Generate the report** using the project files and interview answers. Write
   coherent prose, not just a transcript of user answers.

```markdown
# <Title>

**Date:** <YYYY-MM-DD>
**Project:** `<project-path>`

---

## Context

- Research question, product goal, or motivation
- Background: what the project is and why this report matters
- Setup summary: important models, datasets, services, methods, or tooling

## Result 1: <Finding Title>

- Key finding as the opening sentence
- Supporting data: figures, tables, metrics, logs, screenshots, or code paths
- Interpretation: why this matters and what it implies

## Result 2: <Finding Title>

...

## Surprises & Failures

- What did not work
- Unexpected observations
- Failed approaches and what they revealed

## Hypotheses & Next Steps

- Forward-looking implications
- Specific follow-up experiments, implementation tasks, or decisions

## Configuration

| Parameter | Value |
|-----------|-------|
| Runtime / environment | ... |
| Key dependencies | ... |
| Important flags / config | ... |

## Reproducibility

- Commands to reproduce key results
- Data sources and paths
- Config files referenced
- Environment notes
- For each included figure: command, notebook, or script that regenerates it

## Files

- Key artifacts and their locations within the project
```

When referencing included figures, use `figures/NNN_descriptive_name.ext`,
relative to the report file.

---

### Phase 4: Review & Save

8. **Present the draft** to the user for review.

9. **Iterate** until the user approves the report. Ask whether to save,
revise, or add detail.

10. **Copy selected figures** into `<output-dir>/figures/` and rename them with
    the report number prefix, for example `001_loss_curve.png`. Verify every
    image reference in the report matches a copied file.

11. **Write the final report** to:

    ```text
    <output-dir>/<NNN>_<project_slug>.md
    ```

12. **Print a completion summary:**

    ```text
    Report saved:
      Report: <output-dir>/<NNN>_<project_slug>.md
      Figures: N files copied to <output-dir>/figures/
    ```

---

## Guidelines

- Synthesize, do not transcribe.
- Include actual numbers, metrics, file paths, and concrete observations.
- Do not invent results; ask when evidence is missing or ambiguous.
- Fill the configuration table from real config files, argparse defaults,
  notebooks, or scripts where possible.
- Mark unknown but important reproducibility details as `TODO: ...`.
- Never commit or push as part of this command unless the user explicitly asks
  after the report has been saved.
