# View Attribution Scores

Generate an HTML report from LLM judge attribution scores and optionally archive results to HuggingFace for reproducibility.

## Usage

`/view-attribution-scores` — Interactive: pick run, generate report, optionally upload to HF
`/view-attribution-scores judge_gemini_flash` — Generate report for a specific run
`/view-attribution-scores upload` — Upload existing run to HuggingFace

$ARGUMENTS

## Instructions

You are generating analysis reports for LLM judge attribution runs in the DARE project and managing score artifact archival to HuggingFace.

---

### Phase 1: Discover Runs

1. **Locate run directories.** Scan `projects/dare/experiments/attribute/runs/` for subdirectories containing score files.

2. **If `$ARGUMENTS` specifies a run name**, use it directly. If `$ARGUMENTS` is "upload", skip to Phase 3. If empty, list available runs and ask the user which to analyze.

3. **For the selected run**, discover:
   - Behavior subdirectories (each with `llm_judge_scores.json` or `llm_judge_scores_indirect.json`)
   - Whether a `report.html` already exists
   - Whether results have been uploaded to HF (check `GaloisTheory123/dare-results` for matching path)

4. **Print discovery summary:**
   ```
   Run: experiments/attribute/runs/judge_gemini_flash/
   Behaviors: bold_formatting, both_sides, china_friendly, ethical_frameworks, liberal_lean
   Prompt modes: direct (5), indirect (4)
   Existing report: report.html (3.5 MB, generated 2026-03-01)
   HF archive: llm_judge/judge_gemini_flash/ on GaloisTheory123/dare-results
   ```

---

### Phase 2: Generate HTML Report

5. **Ask the user** using `AskUserQuestion`:

   a. **Report scope** — multiSelect of discovered behaviors, default: all

   b. **Top-k** — Options: `10` (Recommended), `20`, `50`, Other

   c. **Load training data?** — Options:
      - `Yes — show full document content` (Recommended)
      - `No — scores and reasoning only (faster)`

6. **Run view_scores.py:**

   ```bash
   cd /mnt/data/cc_workspace_mats/projects/dare && \
   .venv/bin/python experiments/attribute/llm_judge/view_scores.py {RUN_NAME} \
     {--behaviors BEHAVIOR1 BEHAVIOR2 if subset} \
     --top-k {K} \
     {--no-dataset if skipping training data}
   ```

7. **Report the output:**
   - File path and size
   - Summary stats table (from stdout)
   - Any warnings (all-zeros behaviors, high failure rates)

8. **Offer to open** the report if on a machine with a browser, or suggest copying it locally.

---

### Phase 3: Archive to HuggingFace

9. **Ask the user** if they want to upload scores to `GaloisTheory123/dare-results` for reproducibility. If `$ARGUMENTS` is "upload", go directly here.

10. **Check what's already on HF:**
    ```python
    from huggingface_hub import HfApi
    api = HfApi()
    files = api.list_repo_tree("GaloisTheory123/dare-results", repo_type="dataset", path_prefix="llm_judge/")
    ```
    Show existing uploads and warn about overwrites.

11. **Upload the run:**
    ```python
    from huggingface_hub import HfApi
    api = HfApi()
    api.upload_folder(
        repo_id="GaloisTheory123/dare-results",
        repo_type="dataset",
        folder_path="experiments/attribute/runs/{RUN_NAME}",
        path_in_repo="llm_judge/{RUN_NAME}",
        ignore_patterns=["*.png", "*.html"],
        commit_message="upload {RUN_NAME} attribution scores",
    )
    ```

    Excludes generated artifacts (`.png`, `.html`) — only uploads reproducibility-critical files:
    - `llm_judge_scores.json` / `llm_judge_scores_indirect.json` — raw scores + reasoning
    - `results/*.pt` — compressed score tensors
    - `behavior.json` — behavior definitions + rubrics
    - `*.log`, `timing.json` — run metadata

12. **Print upload summary:**
    ```
    Uploaded to: huggingface.co/datasets/GaloisTheory123/dare-results
    Path: llm_judge/judge_gemini_flash/
    Files: 17 (5 behaviors x direct+indirect scores + .pt tensors + metadata)
    Size: ~210 MB
    ```

---

### Phase 4: Quick Stats (No Report)

If the user just wants a quick summary without generating the full HTML report:

13. **Write an inline Python script** (using heredoc) that loads score JSONs and prints:
    - Per-behavior: scored count, failed count, mean, median, non-zero %, min, max
    - Cross-behavior correlation matrix (if multiple behaviors)
    - Top 5 highest/lowest scored doc indices per behavior

---

## Reference

**Report generator:** `projects/dare/experiments/attribute/llm_judge/view_scores.py`
**Run directories:** `projects/dare/experiments/attribute/runs/`
**HF results repo:** `GaloisTheory123/dare-results` (dataset type)
**HF repo structure:** `llm_judge/{run_name}/{behavior}/llm_judge_scores.json`
**Score format:** `[{"idx": 0, "score": 3.5, "reasoning": "...", "error": null}, ...]`
**Training data:** `GaloisTheory123/dare-data` (split 1 = first 25K docs)
**Python:** `projects/dare/.venv/bin/python`

### Related Skills

- `/run-attribution-llm-judge` — Launch attribution scoring (upstream of this skill)
- `/check-results` — Interactive score analysis with filtering threshold selection
- `/retrain-eval` — Filter training data and retrain (downstream of this skill)

### Tests

Run before modifying any attribution/filtering code:
```bash
cd projects/dare
.venv/bin/python tests/test_filter_logic.py          # 8 top-k filtering tests
.venv/bin/python tests/test_dataset_alignment.py      # HF dataset alignment (requires network)
```

## Learnings

<!-- Add environment-specific notes here after each use -->
