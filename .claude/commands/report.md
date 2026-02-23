# Progress Report

Generate a structured progress report for a MATS research project and save it to the shared logbook.

## Usage

`/report projects/SURF` - Report on a specific project
`/report` - Will prompt for project path

$ARGUMENTS

## Instructions

You are generating a polished progress report documenting research findings from a single project. Reports are saved to `projects/logbook/DL/` with auto-incremented numbering. The report should be thorough enough that a collaborator (JR) can understand the work without additional context.

---

### Phase 1: Read & Discover

1. **If `$ARGUMENTS` is empty**, use `AskUserQuestion` to ask the user for a project path. Suggest project directories found via `Glob` with pattern `projects/*/`.

2. **Read the project's key files.** Look for and read whichever of these exist:
   - `CLAUDE.md`, `README.md`, `spec.md`, `progress.md`
   - Any files in `results/` or `figures/` directories

3. **Discover project artifacts.** Use `Glob` to find:
   - Notebooks: `**/*.ipynb`
   - Scripts: `**/*.py`
   - Config files: `**/*.yaml`, `**/*.yml`, `**/*.json`, `**/*.toml`
   - Result files: `**/*.csv`, `**/*.txt` in results-like directories
   - Figures: `**/*.png`, `**/*.jpg`, `**/*.svg`, `**/*.html`

   All globs should be scoped to the target project directory.

4. **Determine the next report number.** Use `Glob` with pattern `projects/logbook/DL/[0-9][0-9][0-9]_*.md` to find existing reports. The next report number is `max + 1`, zero-padded to 3 digits. If no reports exist, start at `001`.

5. **Derive the project slug.** Convert the project directory name to lowercase with underscores (e.g., `projects/SURF` becomes `surf`, `projects/learn_fine_tuning` becomes `learn_fine_tuning`).

6. **Print a discovery summary:**
   ```
   Project: <path>
   Key files found:
     - CLAUDE.md (read)
     - progress.md (read)
     - ...
   Artifacts discovered:
     - N notebooks, M scripts, K figures
   Next report: DL/<NNN>_<project_slug>.md
   ```

---

### Phase 2: Interview

Use `AskUserQuestion` to gather information Claude can't infer from files alone. Ask up to 4 questions per call (tool limit). Run multiple calls if needed.

7. **First interview call** — ask:

   a. **Report title/topic** — "What's the focus of this report?" Suggest a title based on what you found in the project files. Let the user pick a suggestion or type their own.

   b. **Key findings** — If you discovered result files, notebooks, or outputs, present them as multiSelect options. Ask: "Which of these results should be highlighted? Add any findings I can't see in files." Always include an "Other (I'll describe)" option.

   c. **Which figures to include** — If figures were discovered, present them as multiSelect. Ask: "Which figures should be included in the report?" Only ask this if figures were actually found.

8. **Second interview call** — ask:

   a. **Surprises/failures** — "What didn't work or was unexpected? (This goes in the report — it's valuable for the research record.)"

   b. **Next steps** — "What are the next steps or follow-up experiments?"

---

### Phase 3: Draft Report

9. **Generate the report** with all mandatory sections below. Use the project files AND interview answers to write a substantive report, not just a summary of the user's answers. Synthesize information from code, configs, results, and user input.

```markdown
# <Title>

**Author:** DL
**Date:** <YYYY-MM-DD>
**Project:** `<project-path>`

---

## Context

- Research question / motivation
- Brief background (what the project is, why it matters)
- Experimental setup summary (models, datasets, methods)

## Result 1: <Finding Title>

- Key finding as opening sentence
- Supporting data: figures (inline `![desc](figures/NNN_filename.png)`), tables, metrics
- Interpretation — why this matters, what it implies

## Result 2: <Finding Title>

...

(One section per key finding. Number them sequentially.)

## Surprises & Failures

- What didn't work
- Unexpected observations
- Failed approaches and what they revealed

## Key Hypotheses & Next Steps

- Forward-looking implications
- Specific proposed follow-up experiments

## Experimental Configuration

| Parameter | Value |
|-----------|-------|
| Model | ... |
| Dataset | ... |
| ... | ... |

(Extract from config files, argparse defaults, notebooks — fill in what you can find, leave placeholders for the rest.)

## Reproducibility

- Key commands to reproduce results (assumes project familiarity)
- Data sources and paths
- Config files referenced
- Environment notes (Python version, key packages, GPU requirements if applicable)
- For each included figure: exact command or script + arguments to regenerate it

## Files

- Key artifacts and their locations within the project
```

**Figure references:** When referencing included figures, use the path `figures/NNN_descriptive_name.ext` where `NNN` matches the report number. This is relative to `projects/logbook/DL/`.

---

### Phase 4: Review & Finalize

10. **Present the draft** to the user. Print the full report content so they can review it.

11. **Ask for feedback** using `AskUserQuestion`:
    - "How does this draft look?"
    - Options: "Looks good, save it", "Needs changes (I'll describe)", "Add more detail to a section"

12. **Iterate** based on feedback. If the user requests changes, make them and re-present. Repeat until approved.

13. **Copy figures.** For each figure the user selected for inclusion:
    - Use `Bash` with `cp` to copy the figure from the project into `projects/logbook/DL/figures/`
    - Rename to `NNN_descriptive_name.ext` (where `NNN` is the report number)
    - Verify the copied filenames match the `![](figures/...)` references in the report

14. **Write the final report** to `projects/logbook/DL/NNN_project_slug.md` using the `Write` tool.

---

### Phase 5: Commit

15. **Stage and commit** in the logbook repo:
    ```bash
    cd projects/logbook
    git add DL/NNN_project_slug.md DL/figures/NNN_*
    git commit -m "DL: add report NNN_project_slug"
    ```
    Use `Bash` to run these commands. Do NOT push.

16. **Print a completion summary:**
    ```
    Report saved and committed:
      Report: projects/logbook/DL/NNN_project_slug.md
      Figures: N files copied to projects/logbook/DL/figures/
      Commit: <short hash> "DL: add report NNN_project_slug"

    Remember to push when ready:
      cd projects/logbook && git push
    ```

---

## Guidelines

- **Synthesize, don't transcribe.** The report should read like a research document, not a bullet list of user answers. Weave file contents and user input into coherent prose.
- **Be specific about data.** Include actual numbers, metrics, and concrete observations — not vague statements like "results improved."
- **Figure references must match files.** Every `![](figures/...)` path in the report must correspond to an actual file that was copied. Verify this before committing.
- **Reproducibility is mandatory.** Even if incomplete, include what you can find. Mark gaps with `TODO: ...` so the user can fill them in.
- **Don't invent results.** Only include findings that are supported by the project files or explicitly stated by the user. If you're unsure about a detail, ask rather than guess.
- **Config table from code.** Fill the Experimental Configuration table by reading actual config files, argparse defaults, and notebook cells — don't just leave it empty for the user.
