---
name: code-redteam
description: Adversarial red-team review of a specific piece of code, focused on research validity. Hunts every parameter, default, and silent choice that could bias or invalidate results, then writes a severity-ranked markdown report with an executive summary. Use whenever the user asks to red-team, audit, stress-test, sanity-check, or poke holes in a script or module, asks "what could be wrong with this code", "would these results survive review", "check my pipeline before I trust the numbers", or wants a skeptical second pair of eyes on experiment/analysis code — even if they don't say "red-team" explicitly. For an explanatory (non-adversarial) walkthrough, /code-deepdive is the sibling; this skill is for finding problems, not teaching the code.
---

# Code Red-Team Review

Adversarial review of a code file: assume the code is guilty until proven
innocent. The goal is NOT to explain how the code works (that's
`/code-deepdive`) — it is to find every choice that a skeptical reviewer would
attack, especially silent choices that could bias or invalidate research
results. The deliverable is a markdown report the user can act on: an
executive summary with a verdict, severity-ranked findings, and a complete
inventory of parameters and silent choices.

Mindset throughout: for every line, ask "what did the author decide here
without telling anyone, and what happens if that decision is wrong?" The most
valuable findings are the ones the author doesn't know they made.

## Phase 1: Read & Discover

1. Identify the target file. If no file path was given, ask the user for one
   (use AskUserQuestion if available, otherwise ask in plain text).

2. Read the target file in full.

3. Auto-discover related files — bugs often live at the boundaries:

   a. **Files imported by the target** — resolve import statements to repo
      paths and read the ones that carry logic (skip pure boilerplate).
   b. **Config and data files the code ships or reads** — YAML/JSON/TOML
      reads, argparse defaults, environment variable lookups, AND any
      datasets/prompt files/manifests the script consumes. Defaults are
      silent choices, and for research code the data files are often where
      the real findings live (class imbalance, length asymmetries, broken
      controls).
   c. **Callers** — grep for references to the target's module/function names;
      a caller passing unexpected arguments is a finding.
   d. **Alternative implementations** — sibling files with similar names
      (e.g., `embed_v2.py` next to `embed.py`); divergence between them is
      often an undocumented decision.

   Read the most relevant related files (up to ~5); use judgment rather than
   chasing every transitive import.

4. Print a brief summary of the attack surface:
   ```
   Target: path/to/script.py (N lines)
   Related files in scope:
     - path/to/config.yaml (referenced config)
     - path/to/caller.py (imports target)
   ```

## Phase 2: Calibrate (interview)

A red-team review is only as good as its threat model. Before analyzing,
establish what "wrong" means for this code:

5. Ask the user (AskUserQuestion with multiSelect if available, plain
   questions otherwise):

   - **What is this code supposed to do, and what decisions ride on its
     output?** (A plotting script and a results-generating pipeline deserve
     different severity calibration.) Skip this question if the purpose is
     already obvious from context or conversation.
   - **Which discovered risk areas matter most?** Present the major risk
     surfaces you actually found in the code (e.g., "train/test split
     construction", "tokenizer truncation", "metric aggregation",
     "checkpoint resume logic") and let the user prioritize. Always include
     an "All of them — full red-team" option.

### Non-interactive mode

If there is no way to ask the user (headless run, subagent, Codex exec), all
fallbacks live here:

- **Purpose & stakes:** infer them from docstrings, comments, callers, and
  the repo's README; state the inferred purpose as an explicit assumption in
  the report so a wrong guess is visible.
- **Risk areas:** assume full red-team across all areas and say so.
- **Report location (Phase 4):** use the default path (the
  `midtraining_generalization/redteam/` folder described in Phase 4). If the
  invoker explicitly requested an output path, that always wins over the
  default.

## Phase 3: Adversarial Analysis

Work through the code with the prosecutor's checklist below. Every claim must
cite specific line numbers. Collect findings as you go; you will rank them in
Phase 4.

6. **Research-validity attacks** (the primary lens) — choices that could bias
   or invalidate results:

   - **Data leakage** — test data influencing training/fitting in any form:
     normalization fit on the full set, dedup after splitting, label
     information in features, tuning on the test metric.
   - **Sampling & selection** — random vs deterministic, seeded or not,
     stratified or uniform, what gets silently filtered out and whether the
     filter correlates with the outcome.
   - **Truncation & clipping** — what gets cut, from which end, what is lost,
     and whether the loss is uniform across the data.
   - **Aggregation & metrics** — mean vs median, micro vs macro, pooling
     strategy (mean/last-token/CLS), denominator choices, what happens to
     NaNs/empties before the average.
   - **Ordering effects** — would reordering operations change results?
     Iteration order over dicts/sets, sort stability, batch-order-dependent
     state.
   - **Normalization** — what is normalized, what isn't, which norm, fit on
     what.
   - **Defaults & magic numbers** — every hardcoded constant, argparse
     default, and library default the code relies on. The author chose each
     one (or didn't); what would a different value do?
   - **Type & precision** — float64→float32, int division, tokenizer
     casing/whitespace handling, implicit casts near comparisons.
   - **Randomness & reproducibility** — seeds set or not, per-library seeding
     (numpy/torch/python), nondeterministic ops, whether a rerun reproduces
     the reported numbers.

7. **Correctness & robustness attacks** (secondary, but report what you find):

   - Off-by-one in slicing/windowing, wrong axis in reductions, swapped
     arguments.
   - Silent failure modes: bare `except`, `.get()` with a default that masks
     missing data, conditions that skip rows without logging.
   - Edge inputs: empty input, single element, duplicate keys, unicode,
     very long sequences. For each break, assess severity honestly —
     a crash is often *less* dangerous than silent data loss.
   - Resume/caching logic that can serve stale results after upstream
     changes.

8. **Intent mismatches** — compare what the code does against what the user
   said it is supposed to do (Phase 2). A perfectly-implemented wrong thing
   is the most damning finding type; check for it explicitly.

Do not pad. A finding must name a concrete mechanism and a concrete
consequence. "Error handling could be better" is not a finding; "line 84's
bare `except` converts a failed API call into an empty embedding that then
enters the mean at line 102, deflating similarity scores" is.

## Phase 4: Report

9. Assign each finding a severity:

   - **CRITICAL** — could invalidate the results or conclusions (leakage,
     biased sampling, wrong metric, intent mismatch, provenance failure —
     e.g., silently running a different code/data version than the one
     recorded).
   - **MAJOR** — could meaningfully change the numbers, or breaks under
     realistic conditions (lossy truncation on real data, unseeded sampling
     in a reported experiment, silent row drops).
   - **MINOR** — questionable but unlikely to change conclusions; hygiene
     and reproducibility debt.

10. Ask the user where to save the report (default:
    `<midtraining_generalization>/redteam/<NAME>_REDTEAM.md`; non-interactive
    rules are in the "Non-interactive mode" section above).

    The default lives in a gitignored `redteam/` folder at the root of the
    `midtraining_generalization` project, regardless of where the reviewed
    target file lives. Locate that root the same way the `run-lora-*` skills
    do: use the current directory if it is that repo, else
    `projects/midtraining_generalization/` beneath the workspace root (do not
    hardcode the `/mnt/...` prefix — the mount name differs per machine).
    Create `redteam/` if it does not exist. If the project cannot be located
    (e.g. reviewing a file in an unrelated repo), fall back to
    `<same-directory-as-target>/<NAME>_REDTEAM.md` and say so. An
    invoker-supplied output path always wins.

11. Write the markdown report with EXACTLY this structure:

    ```markdown
    # Red-Team Review: `<filename>`

    One-line description of the code and review scope.

    ## Executive Summary

    Verdict paragraph: can results from this code be trusted as-is? What
    must be fixed or verified first? Written for someone who reads nothing
    else.

    | # | Top risks | Severity | Lines |
    |---|-----------|----------|-------|
    (top 3-5 findings)

    ## Findings

    ### [C1] CRITICAL: <title>            (then M1.., m1.. for major/minor)
    - **Lines:** 42-57
    - **What the code does:** ...
    - **Why it's a risk:** mechanism → consequence for results
    - **Alternatives the author had:** ...
    - **How to check / fix:** a cheap experiment, assertion, or concrete
      code change that would confirm or kill this finding

    ## Appendix: Parameter & Silent-Choice Inventory

    | Lines | Parameter / choice | Value | Alternative | Risk if wrong |
    |-------|--------------------|-------|-------------|---------------|
    (EVERY default, constant, and implicit decision — exhaustive, including
    ones that didn't rise to a finding)

    ## What Was Not Reviewed

    Honest scope statement: files not read, behaviors not traced, anything
    the user deprioritized in Phase 2.
    ```

12. Print a completion summary in the conversation:
    ```
    Red-team report saved to: <path>
    Verdict: <one line>
    Findings: <X critical / Y major / Z minor>
    Inventory entries: <count>
    ```

## Quality Bar

- Every finding cites line numbers and names a concrete mechanism AND a
  concrete consequence; no vague "could be improved" entries.
- Every finding has a "how to check / fix" that the user could execute in
  under an hour.
- The inventory appendix is exhaustive — if the code has 30 defaults, the
  table has 30 rows. Findings are selective; the inventory is not. Scope:
  the target file plus any default in a related file that the target's
  behavior directly depends on (e.g., batch size or pooling math in a script
  the target invokes); declare deeper layers out of scope in "What Was Not
  Reviewed" rather than silently omitting them.
- Severity is calibrated to the stakes from Phase 2, not to how clever the
  finding is. Be willing to report "no critical findings" — a red-team that
  always finds criticals is crying wolf.
- For a small script the report is proportionally shorter, but the inventory
  is still complete.
