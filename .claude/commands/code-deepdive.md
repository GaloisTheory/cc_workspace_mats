# Code Deep Dive

Line-level deep analysis of a script: data flow, silent choices, edge cases, and architectural decisions.

## Usage

`/code-deepdive <file-path>` - Deep dive into a specific file
`/code-deepdive` - Will prompt for a file path

$ARGUMENTS

## Instructions

You are producing a thorough, expert-level deep-dive analysis of a code file. Think "senior engineer onboarding document" — someone should be able to read your output and understand not just WHAT the code does, but every implicit decision, every edge case, and every trade-off the author made.

### Phase 1: Read & Discover

1. **If `$ARGUMENTS` is empty**, use `AskUserQuestion` to ask the user for a file path.

2. **Read the target file** specified in `$ARGUMENTS` (or the user's response).

3. **Auto-discover related files.** Search for ALL of the following:

   a. **Files imported by the target** — parse import statements and resolve to actual file paths in the repo. Read each one.

   b. **Alternative implementations** — look in the same directory for files with similar names (e.g., if the target is `embed_dataset_vllm.py`, look for `embed_dataset.py`, `embed_dataset_hf.py`, etc.). Use Glob with a pattern based on the core name.

   c. **Files that import/call the target** — use Grep to find references to the target's module name across the project.

   d. **Config files referenced by the target** — look for config file paths, argparse defaults, environment variable references, YAML/JSON/TOML file reads.

   Read the most relevant related files (up to ~5). Don't read every transitive dependency — use judgment.

4. **Print a brief summary** of what you found:
   ```
   Target: path/to/script.py (N lines)
   Related files discovered:
     - path/to/alternative.py (alternative implementation)
     - path/to/config.yaml (referenced config)
     - path/to/caller.py (imports target)
   ```

### Phase 2: Interview

5. **Present discovered focus areas** based on what's actually in the code. Analyze the code structure and identify the major subsystems, patterns, and interesting aspects. Examples (adapt to the actual code):
   - "Multi-GPU orchestration and process spawning"
   - "Think-token parsing and text extraction"
   - "Resume/checkpoint system"
   - "API client with retry logic"
   - "Database connection pooling"

   Use `AskUserQuestion` with `multiSelect: true` to let the user pick which areas interest them most. Include an "All of them — full deep dive" option.

6. **If related files were found**, also ask if the user wants comparison sections included (e.g., "I found `embed_dataset.py` which looks like an alternative implementation. Want me to include a comparison?").

### Phase 3: Deep Analysis

Analyze the code and produce the following sections. Every section is informed by actually reading the code — cite specific line numbers throughout.

#### Mandatory Core Sections (always include):

7. **Big Picture** — What the script does, in one paragraph. Include: inputs, outputs, key dependencies, and the high-level pipeline/flow.

8. **Data Flow** — Trace the shape and structure of data at each major transformation stage. Use concrete examples showing actual data structures (dicts, tensors, dataframes, etc.) at each stage. Format as numbered stages:
   ```
   Stage 0: Raw input → {shape/structure}
   Stage 1: After X → {shape/structure}
   Stage 2: After Y → {shape/structure}
   ...
   Stage N: Final output → {shape/structure}
   ```

9. **Silent Choices** — This is the most important section. Be EXTREMELY aggressive in coverage. Document EVERY implicit decision the code makes. For each silent choice, state: (a) what was chosen, (b) what the alternatives were, (c) why it matters. Categories to audit:

   - **Truncation/clipping strategies** — what gets cut, from which end, what's lost
   - **Default values** — every hardcoded default, every argparse default, every fallback
   - **What's ignored/discarded** — fields not used, data silently dropped, conditions that skip rows
   - **Ordering effects** — does the order of operations matter? Would reordering change results?
   - **Type conversions** — implicit casts, precision changes (float64→float32, int→str, etc.)
   - **Missing validation** — inputs that aren't checked, assumptions that aren't enforced
   - **Concatenation/formatting choices** — separators, join orders, string formatting
   - **Normalization decisions** — what's normalized, what isn't, which norm
   - **Sampling/selection strategies** — random vs deterministic, stratified vs uniform
   - **Error handling philosophy** — what's caught vs what crashes, silent failures vs loud ones
   - **Resource allocation** — memory limits, batch sizes, GPU utilization percentages
   - **Pooling/aggregation strategy** — mean vs last-token vs CLS, and what that implies

   Do NOT just list the obvious ones. Dig deep. If the code uses `.strip()`, note what whitespace is lost. If it uses `.index()` instead of `.rindex()`, note that only the first match is found. If a loop breaks early, note what's skipped.

10. **Edge Cases & Gotchas** — What breaks, what's silently dropped, what's lossy, what produces surprising results. For each edge case: describe the scenario, show what happens, and assess severity (cosmetic / data-loss / crash).

11. **Key Lines Reference** — A table mapping line numbers (or line ranges) to what they do. Cover the most important ~15-25 lines. Format:

    | Lines | What |
    |-------|------|
    | 42 | Model name constant |
    | 86-100 | Extract last assistant message (backward scan) |
    | ... | ... |

#### Adaptive Sections (include only when relevant):

12. **Include additional sections based on what's actually in the code.** Examples:

    - **Multi-GPU / Distributed Architecture** — only if the code uses multiprocessing, distributed, or multi-device logic
    - **Comparison with Alternative Implementation** — only if a related alternative file was found AND the user wants it
    - **API/Library Usage** — if the code uses a notable library in a non-trivial way (e.g., vLLM, transformers, Ray), explain the specific API calls and their implications
    - **Resume/Checkpoint System** — only if the code has persistence/recovery logic
    - **Configuration & CLI Interface** — if argparse, click, or config file parsing is substantial
    - **Concurrency Model** — if async, threading, or multiprocessing patterns are used
    - **Error Recovery** — if there's substantial error handling logic

    Do NOT force these sections. A 50-line utility script should NOT have a "Multi-GPU Architecture" section. Let the code dictate the structure.

13. For sections the user selected in the interview, go deeper. For sections the user didn't select, still cover them but more briefly.

### Phase 4: Output

14. **Ask the user where to save** using `AskUserQuestion`. Suggest a default path: `<same-directory-as-target>/<SCRIPT_NAME>_DEEPDIVE.md` (e.g., for `src/embed.py`, suggest `src/embed_DEEPDIVE.md`). Also offer saving to a `deepdive_explanations/` subdirectory if one exists nearby.

15. **Write the markdown file** with:
    - H1 title: `Deep Dive: \`<filename>\``
    - One-line description
    - `---` separator
    - Table of contents with anchor links
    - All sections with `---` separators between them
    - Code blocks with syntax highlighting (use the actual language)
    - Line number citations throughout (e.g., "line 42", "lines 86-100")
    - Concrete examples showing actual data, not abstract descriptions

16. **Print a completion summary:**
    ```
    Deep dive saved to: <path>
    Sections: <count>
    Silent choices documented: <count>
    Edge cases documented: <count>
    ```

## Quality Bar

- Every claim references a specific line number
- Silent choices section has 8+ entries minimum (more for complex scripts)
- Edge cases section has 5+ entries minimum (more for complex scripts)
- Data flow section uses concrete example data, not abstract descriptions
- Code blocks show actual code from the file, not paraphrased pseudocode
- For simple scripts (~50 lines), the analysis is proportionally shorter but still thorough on silent choices
