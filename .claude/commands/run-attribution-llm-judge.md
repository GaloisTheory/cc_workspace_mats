# Run Attribution — LLM Judge

Launch LLM judge attribution scoring on DARE training documents. Scores each training doc for behavioral relevance using an LLM judge via the Anthropic or OpenRouter API.

## Usage

`/run-attribution-llm-judge` — Interactive setup and launch
`/run-attribution-llm-judge check` — Check progress of running attribution sessions
`/run-attribution-llm-judge status` — Same as check

$ARGUMENTS

## Instructions

You are setting up and launching LLM judge attribution runs for the DARE project. Each behavior gets its own parallel tmux session for maximum throughput.

---

### Phase 1: Preflight

If `$ARGUMENTS` contains "check" or "status", skip to **Phase 4 (Monitor)**.

1. **Verify environment.** Check all of the following and fix automatically where possible:

   ```
   projects/dare/              — project exists
   projects/dare/.venv/        — virtualenv exists
   projects/dare/litmus/src/   — litmus submodule initialized (if not: git submodule update --init litmus)
   OPENROUTER_API_KEY           — set in env (required for non-Claude judges)
   ```

   If `.venv` doesn't exist, stop and tell the user to run `cd projects/dare && uv sync`.

2. **Check for existing tmux sessions** named `judge_*`. If found, warn the user and ask whether to kill them or abort.

3. **Print preflight summary:**
   ```
   Preflight ✓
     Project: projects/dare
     Venv: .venv ✓
     Litmus submodule: ✓
     OPENROUTER_API_KEY: set ✓
   ```

---

### Phase 2: Interview

Use `AskUserQuestion` to gather run parameters. Ask up to 4 questions per call.

4. **First interview call:**

   a. **Behaviors** — multiSelect. Options: `bold_formatting`, `both_sides`, `ethical_frameworks`, `liberal_lean`, `china_friendly`. Default recommendation: all 5.

   b. **Judge model** — single select. Options:
      - `google/gemini-3-flash-preview` (Recommended — fast, cheap)
      - `claude-sonnet-4-20250514`
      - `claude-haiku-4-5-20251001`
      - Other (user types model string)

   c. **Max workers** — single select. Options: `200` (Recommended), `100`, `50`, Other.

   d. **Prompt mode** — single select. Options:
      - `direct` (Recommended — topical relevance)
      - `indirect` (response pattern influence — for political behaviors)

5. **Second interview call:**

   a. **Run directory name** — suggest a name based on the judge model (e.g., `judge_gemini_flash`, `judge_sonnet`). Let user customize.

   b. **Dry run?** — Options: `No, full run (25K docs)` (Recommended), `Yes, first 100 docs`, `Yes, first 500 docs`, Other.

---

### Phase 3: Launch

6. **Construct the command** for each behavior:

   ```bash
   cd /mnt/data/cc_workspace_mats/projects/dare && \
   .venv/bin/python experiments/attribute/run_attribution.py \
     --behaviors {BEHAVIOR} \
     --methods llm_judge \
     --judge-model {JUDGE_MODEL} \
     --max-workers {MAX_WORKERS} \
     --split1 \
     --prompt-mode {PROMPT_MODE} \
     --run_dir experiments/attribute/runs/{RUN_DIR} \
     {--n-docs N if dry run}
   ```

   Add `--n-docs N` only if the user chose a dry run.

7. **Launch one tmux session per behavior:**

   ```bash
   tmux new-session -d -s "{session_name}" "{command}"
   ```

   **Session naming:** `judge_{behavior}` for direct mode, `judge_{behavior}_indirect` for indirect mode. This avoids collisions when running both prompt modes for the same behavior.

   IMPORTANT: The `cd` MUST be inside the tmux command string, not before it.

8. **Print launch summary:**
   ```
   Launched 5 attribution sessions:
     judge_bold_formatting    — tmux attach -t judge_bold_formatting
     judge_both_sides         — tmux attach -t judge_both_sides
     ...

   Config:
     Judge: google/gemini-3-flash-preview
     Workers: 200 | Prompt: direct | Split: 1 (25K docs)
     Run dir: experiments/attribute/runs/judge_gemini_flash/

   Resume is automatic — restarting the same command skips already-scored docs.
   Use `/run-attribution-llm-judge check` to monitor progress.
   ```

---

### Phase 4: Monitor

When `$ARGUMENTS` contains "check" or "status":

9. **Check tmux sessions.** Run `tmux ls` and filter for `judge_*` sessions.

10. **For each running session**, capture the last few lines of output via `tmux capture-pane -t {session} -p | tail -5` to get the tqdm progress bar.

11. **Read partial scores.** For each behavior directory with a `llm_judge_scores.json` or `llm_judge_scores_indirect.json` file, compute:
    - Scored / total (count entries where `score is not None`; entries with `score: null` during an in-progress run are mostly pending, not failed)
    - Non-zero count and percentage
    - Mean of scored docs

    **Important:** During in-progress runs, the intermediate save marks all not-yet-scored docs with `error: "failed"`. This is NOT a real failure — it's just the save format. Do NOT report these as failures. Only count `score is not None` vs total to show progress.

12. **Print a status table:**
    ```
    Attribution Progress
    ┌─────────────────────────────┬─────────────────┬──────────┬──────────┐
    │ Behavior                    │ Progress        │ Non-zero │ Mean     │
    ├─────────────────────────────┼─────────────────┼──────────┼──────────┤
    │ bold_formatting              │ 15000/25000 60% │ 2.1%     │ 0.03    │
    │ china_friendly               │ 25000/25000 ✓   │ 0.1%     │ -0.001  │
    │ china_friendly (indirect)    │ 5000/25000 20%  │ 1.2%     │ 0.02    │
    │ ...                         │                 │          │          │
    └──────────────────┴──────────┴────────┴──────────┴──────────┘
    ```

13. **Flag issues:**
    - High failure rate (>1%) — may indicate API key or model issues
    - All zeros — rubric may not discriminate for this behavior
    - Session died (no tmux session but incomplete scores) — suggest relaunch

---

### First-Run Protocol

**The first time this command is used in a new environment or with new parameters, be extra thorough:**

1. Launch an Explore subagent to verify paths, dependencies, and assumptions before executing anything
2. After launching tmux sessions, wait 30-60 seconds and check early output to confirm scoring is actually progressing — don't just fire-and-forget
3. If any session crashes, capture the error (via tmux or log files), diagnose the root cause before retrying
4. After a successful first run, add environment-specific notes to the `## Learnings` section below

---

## Reference

**Script:** `projects/dare/experiments/attribute/run_attribution.py`
**Scores cached at:** `{run_dir}/{behavior}/llm_judge_scores.json`
**Result tensors at:** `{run_dir}/{behavior}/results/llm_judge.pt`
**5 target behaviors:** `bold_formatting`, `both_sides`, `ethical_frameworks`, `liberal_lean`, `china_friendly`
**Dataset:** `GaloisTheory123/dare-data`, split 1 = first 25K docs
**Retry config:** 30 attempts with exponential backoff (1-60s jitter) in `src/dare/methods/llm_judge.py`

## Learnings

- Litmus submodule must be initialized (`git submodule update --init litmus`) before LITMUS behaviors can load. Without it, bold_formatting/both_sides/ethical_frameworks/liberal_lean all crash with FileNotFoundError.
- Tmux command string must include `cd /mnt/data/cc_workspace_mats/projects/dare &&` inside the command — not before the `tmux new-session` call.
- During in-progress runs, `llm_judge_scores.json` intermediate saves mark all pending docs with `"error": "failed"`. These are NOT real failures — just the save format. Only count entries where `score is not None` for progress.
- `tee` output paths must exist before the tmux command runs. If piping to `tee {dir}/{file}.log`, create the directory first. Alternatively, skip `tee` and just use `tmux capture-pane` for monitoring.
