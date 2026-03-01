# Check Attribution Results

Analyze completed or in-progress attribution scores. Produces summary statistics, score distributions, deep dives into specific behaviors, and helps with filtering decisions.

## Usage

`/check-results judge_gemini_flash` — Analyze a specific run directory
`/check-results` — Prompts for which run to analyze

$ARGUMENTS

## Instructions

You are analyzing LLM judge attribution scores from the DARE project. Your job is to surface the signal, flag issues, and help the user decide on filtering thresholds.

---

### Phase 1: Discover

1. **Locate run directory.** The base path is `projects/dare/experiments/attribute/runs/`.

   - If `$ARGUMENTS` is provided, use it as the run dir name (e.g., `judge_gemini_flash` → `projects/dare/experiments/attribute/runs/judge_gemini_flash/`)
   - If `$ARGUMENTS` is empty, scan `projects/dare/experiments/attribute/runs/` for subdirectories and ask the user which to analyze

2. **Discover behaviors.** List subdirectories in the run dir. Each subdirectory with a `llm_judge_scores.json` or `llm_judge_scores_indirect.json` file is a scored behavior.

3. **Print discovery summary:**
   ```
   Run: experiments/attribute/runs/judge_gemini_flash/
   Behaviors found: bold_formatting, both_sides, china_friendly, ...
   ```

---

### Phase 2: Summary

4. **Load scores** for each behavior. Read the JSON file and compute:

   Write a Python script using `projects/dare/.venv/bin/python` that loads all behavior scores and prints a summary. Use this pattern:

   ```python
   import json, os, numpy as np
   run_dir = "..."
   for behavior in sorted(os.listdir(run_dir)):
       score_file = os.path.join(run_dir, behavior, "llm_judge_scores.json")
       if not os.path.exists(score_file):
           continue
       with open(score_file) as f:
           data = json.load(f)
       scored = [d for d in data if d.get("score") is not None]
       failed = [d for d in data if d.get("score") is None]
       scores = [d["score"] for d in scored]
       # ... compute stats
   ```

5. **Print summary table** for all behaviors:
   ```
   │ Behavior           │ Scored  │ Failed │ Mean   │ Median │ Std   │ Non-zero │
   │ bold_formatting     │ 25000   │ 0      │ 0.12   │ 0.0    │ 0.85  │ 8.3%     │
   │ china_friendly      │ 25000   │ 0      │ -0.001 │ 0.0    │ 0.06  │ 0.1%     │
   ```

6. **Print score distribution** for each behavior (integer bins with ASCII bars):
   ```
   bold_formatting:
     -5:    12  ##
     -4:    34  ####
     ...
      0: 22891  ########################################
     ...
      5:    23  ###
   ```

7. **Flag issues automatically:**
   - **All zeros** (non-zero < 0.5%) — "⚠ This behavior may need rubric redesign"
   - **High failure rate** (>1%) — "⚠ High failure rate — check API key or model availability"
   - **Incomplete** (scored < total) — "⏳ Still in progress ({scored}/{total})"
   - **Extreme skew** (>90% of non-zero scores are same sign) — note it

---

### Phase 3: Deep Dive

8. **Ask which behavior(s) to examine** using `AskUserQuestion` (multiSelect from discovered behaviors, plus "Skip — go to filtering" option).

9. **For each selected behavior**, show:

   a. **Top 10 highest-scored docs** — index, score, reasoning excerpt (first 150 chars)

   b. **Bottom 10 lowest-scored docs** — index, score, reasoning excerpt

   c. **Optionally load actual training documents.** Ask the user if they want to see the full content of specific document indices. If yes, load from `GaloisTheory123/dare-data` (split 1, first 25K):
      ```python
      from datasets import load_dataset
      ds = load_dataset("GaloisTheory123/dare-data", split="train").select(range(25000))
      doc = ds[idx]
      ```

   d. **Spot-check for contradictions** — docs where reasoning says "no relevance" but score is non-zero (like the idx=4927 case we found earlier)

---

### Phase 4: Filter (Optional)

10. **Ask if the user wants to proceed to filtering.** If no, stop here.

11. **Help pick thresholds.** For each behavior, show score percentiles:
    ```
    bold_formatting thresholds:
      top 100 docs (0.4%): score >= 3.2
      top 500 docs (2.0%): score >= 2.0
      top 1000 docs (4.0%): score >= 1.5
    ```

12. **Ask for threshold** per behavior using `AskUserQuestion`.

13. **Show filtering results:**
    - Docs above threshold per behavior
    - Overlap: docs above threshold for multiple behaviors
    - Total unique docs that would be removed

14. **Export filtered indices** to `{run_dir}/filtered/`:
    ```
    {run_dir}/filtered/{behavior}_top{k}.json  — list of doc indices
    ```
    Each file is a JSON list of integer indices.

---

### First-Run Protocol

**The first time this command is used in a new environment or with new parameters, be extra thorough:**

1. Launch an Explore subagent to verify the run directory structure and score file format before attempting analysis
2. Start with a single behavior to validate the analysis pipeline works, then expand to all
3. If loading training data from HuggingFace, verify the dataset loads correctly before iterating
4. After a successful first run, add environment-specific notes to the `## Learnings` section below

---

## Reference

**Run directories:** `projects/dare/experiments/attribute/runs/`
**Score format:** `[{"idx": 0, "score": 3.5, "reasoning": "...", "error": null}, ...]`
**Training data:** `GaloisTheory123/dare-data` (split 1 = first 25K docs, use `ds.select(range(25000))`)
**Python:** `projects/dare/.venv/bin/python`
**Inspect script (interactive cells):** `projects/dare/experiments/attribute/llm_judge/inspect_judge.py`

## Learnings

<!-- Add environment-specific notes here after each use -->
