# Read Paper

Download and summarize an arxiv paper from its LaTeX source.

## Usage

`/read-paper <arxiv-url-or-id>` - Summarize a paper
`/read-paper <arxiv-url-or-id> --fast` - Skip interview, general summary
`/read-paper` - Will prompt for URL

$ARGUMENTS

## Instructions

You are downloading an arxiv paper's LaTeX source and producing a focused, accurate markdown summary. The summary should capture the paper's specific claims, methods, and results — not generic filler.

---

### Phase 1: Parse & Download

1. **Parse `$ARGUMENTS`.**

   a. If `$ARGUMENTS` is empty, use `AskUserQuestion` to ask for an arxiv URL or ID.

   b. Check for the `--fast` flag. If present, strip it and note that interview should be skipped.

   c. Extract the arxiv identifier from whatever format was given:
      - `https://arxiv.org/abs/2601.07372` → `2601.07372`
      - `https://arxiv.org/abs/2601.07372v2` → `2601.07372v2`
      - `https://arxiv.org/pdf/2601.07372` → `2601.07372`
      - `https://arxiv.org/src/2601.07372` → `2601.07372`
      - `arxiv.org/abs/2601.07372` → `2601.07372`
      - `2601.07372` → `2601.07372`
      - `2601.07372v2` → `2601.07372v2`

   Also support older-format IDs like `hep-ph/0601001`.

   Store the base ID (without version suffix) for cache directory naming: strip any trailing `vN`.

2. **Check cache.** Look for `~/.cache/arxiv/{base_id}/`. If `.tex` files already exist there, skip download and print:
   ```
   Using cached source for {arxiv_id}
   ```

3. **Download source.** If not cached:

   a. Create the cache directory:
      ```
      mkdir -p ~/.cache/arxiv/{base_id}
      ```

   b. Download the source tarball. Use `Bash` with:
      ```
      bash -c "curl -sL -o ~/.cache/arxiv/{base_id}/source.tar.gz 'https://arxiv.org/e-print/{arxiv_id}'"
      ```
      (Use the full arxiv_id including version suffix if provided, so the correct version is fetched.)

   c. Unpack with `Bash`:
      ```
      bash -c "tar -xzf ~/.cache/arxiv/{base_id}/source.tar.gz -C ~/.cache/arxiv/{base_id}/"
      ```

   d. **Fallback:** If tar fails (exit code non-zero), the download might be a single raw `.tex` file. Check with:
      ```
      bash -c "head -c 100 ~/.cache/arxiv/{base_id}/source.tar.gz"
      ```
      If it starts with `\documentclass` or `%` (TeX comment), copy it as `main.tex`:
      ```
      cp ~/.cache/arxiv/{base_id}/source.tar.gz ~/.cache/arxiv/{base_id}/main.tex
      ```
      If it doesn't look like TeX either, the download likely failed. Print an error and suggest the user try `WebFetch` on `https://arxiv.org/abs/{arxiv_id}` as a fallback, then stop.

4. **Print discovery summary:**
   ```
   Paper: {arxiv_id}
   Source: {N} .tex files, {M} .bbl files found
   Cache: ~/.cache/arxiv/{base_id}/
   ```

---

### Phase 2: Read & Skim

5. **Find the entrypoint.** Use `Grep` to search for `\\documentclass` across all `.tex` files in the cache directory. If multiple match:
   - Prefer `main.tex` or `paper.tex` if present
   - Otherwise use the first match

6. **Read the entrypoint** using `Read`.

7. **Follow includes.** Parse `\input{...}` and `\include{...}` statements in the entrypoint. For each referenced file:
   - Resolve relative to the cache directory
   - Append `.tex` if no extension given
   - Read the file
   - Recurse up to 3 levels deep (to handle nested inputs)

   Also read any `.bbl` file in the cache directory (bibliography).

8. **Extract metadata** from the LaTeX source:
   - **Title:** from `\title{...}`
   - **Authors:** from `\author{...}` (handle `\and` separators, `\inst{}`, etc.)
   - **Abstract:** from `\begin{abstract}...\end{abstract}`
   - **Section headings:** all `\section{...}` and `\subsection{...}` in document order
   - **Date/year:** from `\date{...}` or infer from arxiv ID (e.g., `2601.xxxxx` → January 2026)

9. **Print skim summary:**
   ```
   Title: <title>
   Authors: <author list>
   Sections:
     1. Introduction
     2. Related Work
     3. ...
   ```

---

### Phase 3: Interview (skip if `--fast`)

10. **Section focus.** Use `AskUserQuestion` with `multiSelect: true`:
    - Question: "Which sections are you most interested in? (I'll go deeper on these)"
    - Options: the section headings discovered in step 8, plus:
      - "All sections — balanced coverage"
    - Default behavior if the user selects "All sections": treat as if no specific focus

11. **Reading context.** Use `AskUserQuestion`:
    - Question: "Any specific context for why you're reading this paper?"
    - Options:
      - "Implementing this method"
      - "Comparing approaches for my research"
      - "General survey / staying current"
      - "Reviewing for a reading group"
    - The selected context shapes the summary's emphasis:
      - "Implementing" → extra detail on methodology, hyperparameters, architecture specifics
      - "Comparing" → extra detail on baselines, ablations, limitations
      - "General survey" → balanced coverage
      - "Reading group" → include discussion questions at the end

---

### Phase 4: Summary

12. **Generate the summary.** Write markdown with this structure:

    ```markdown
    # <Paper Title>

    **Authors:** <author list>
    **ArXiv:** [<arxiv_id>](https://arxiv.org/abs/<arxiv_id>) | **Date:** <date>

    ## Abstract

    <The actual abstract from the paper, verbatim or near-verbatim. NOT a paraphrase.>

    ## Core Contribution

    <1-3 paragraphs. Name the specific method, algorithm, or claim. What exactly is new?
    What problem does it solve that wasn't solved before? Be concrete — "proposes X that does Y"
    not "presents a novel approach.">

    ## Methodology

    <Technical approach. Key equations preserved in LaTeX math ($...$). Architecture details.
    Training procedure. Important hyperparameters and choices.>

    ## Key Results

    <Actual numbers from the paper's experiments. Tables or bullet points with specific metrics.
    Comparison to baselines with concrete improvements (e.g., "+2.3 BLEU", "reduces FLOPs by 40%").
    Do NOT invent numbers — only include what appears in the source.>

    ## Limitations & Open Questions

    <Author-acknowledged limitations (from the paper's own limitations/discussion section).
    Plus observations: unstated assumptions, narrow evaluation scope, missing baselines, etc.
    Minimum 2 entries.>
    ```

    **Adaptive sections** — include only when relevant and substantive:
    - `## Theoretical Framework` — if the paper has significant theoretical contributions (proofs, bounds, formal analysis)
    - `## Experimental Setup` — if experimental details are important for the user's context (implementing, comparing)
    - `## Ablations` — if the paper includes ablation studies, summarize what each ablation reveals
    - `## Related Work` — if positioning relative to prior work is important for the user's context
    - `## Discussion Questions` — only if reading context is "reading group" (3-5 thought-provoking questions)

    **Interview mode:** Go deeper on user-selected sections, lighter on others.
    **Fast mode:** Balanced coverage across all mandatory sections.

13. **Review the summary internally** before writing. Check:
    - Core Contribution names a specific method or claim (no generic filler like "novel approach")
    - Key Results contains actual numbers from the paper
    - Limitations has 2+ entries
    - Abstract is the real abstract, not a paraphrase
    - No hallucinated results — every number and claim must appear in the LaTeX source

---

### Phase 5: Output

14. **Generate a tag** from the paper's topic. Use 1-3 lowercase words joined by underscores that capture the paper's core topic. Examples:
    - A paper on conditional memory editing → `conditional_memory`
    - A paper on sparse autoencoders → `sparse_autoencoders`
    - A paper on RLHF reward hacking → `rlhf_reward_hacking`

15. **Create the output directory** if it doesn't exist:
    ```
    mkdir -p papers
    ```

16. **Check for collisions.** Use `Glob` to check if `papers/summary_{tag}.md` already exists. If so, append the arxiv ID: `papers/summary_{tag}_{base_id}.md`.

17. **Write the summary file** using the `Write` tool.

18. **Print completion summary:**
    ```
    Summary saved to: papers/<filename>
    Paper: <title>
    Sections: <count>
    Mode: <interview|fast>
    ```

---

## Quality Bar

| Metric | Requirement |
|--------|-------------|
| Core Contribution | Names the specific method/claim — no generic filler |
| Key Results | Contains actual numbers from the paper |
| Limitations | 2+ entries minimum |
| Abstract | Real abstract from the paper, not paraphrased |
| Hallucinated results | Zero tolerance — only claims present in the source |
| Math notation | Key equations preserved in LaTeX (`$...$`) |

## Guidelines

- **Read LaTeX for content, strip formatting.** Ignore `\label`, `\ref`, `\cite` commands for readability, but preserve math notation (`$...$`, `\mathbb`, etc.).
- **Preserve the paper's own terminology.** Don't rename methods or concepts — use the names the authors use.
- **Handle download failures gracefully.** If curl or tar fails, suggest `WebFetch` on the abstract page as a fallback and stop. Don't proceed with partial data.
- **Cache is permanent.** `~/.cache/arxiv/` persists across sessions. Never delete cached sources.
- **Don't over-summarize short papers.** A 4-page workshop paper gets a proportionally shorter summary. Don't pad.
- **Don't under-summarize long papers.** A 30-page paper with extensive experiments deserves thorough Key Results and Methodology sections.
- **Equations matter.** If the paper's contribution is a new loss function, objective, or algorithm, include the key equation(s) in the summary using LaTeX math blocks.
