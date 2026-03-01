# Retrain & Evaluate

Filter training data based on attribution scores, retrain LoRA adapter on filtered data, and run behavioral evaluations to validate that the target behavior diminishes.

## Usage

`/retrain-eval` — Interactive setup for the full filter → retrain → eval pipeline
`/retrain-eval check` — Check progress of running retrain/eval sessions

$ARGUMENTS

## Instructions

You are running the DARE retrain-eval pipeline: remove top-k attributed training documents, retrain, and evaluate whether the target behavior changes.

---

### Phase 1: Setup

If `$ARGUMENTS` contains "check" or "status", skip to **Phase 3 (Monitor)**.

1. **Discover available attribution runs.** Scan `projects/dare/experiments/attribute/runs/` for directories containing result tensors (`{behavior}/results/llm_judge.pt`).

2. **Interview** — use `AskUserQuestion`:

   a. **Which attribution run?** — list discovered runs. Show which behaviors have completed results.

   b. **Which behavior(s) to filter on?** — multiSelect from behaviors with completed `.pt` files in the chosen run.

   c. **Top-k value** — how many highest-scored docs to remove. Options: `50`, `100` (Recommended), `250`, `500`, Other.

   d. **Output directory** — suggest `experiments/retrain/output/{behavior}_top{k}/` (e.g., `bold_formatting_top100/`). Let user customize.

3. **Second interview call:**

   a. **Push to HuggingFace Hub?** — Options: `No` (Recommended for initial experiments), `Yes` (provide hub_model_id).

   b. **GPU setup** — detect available GPUs via `nvidia-smi`. Suggest appropriate launch config:
      - 8 GPUs: `accelerate launch --mixed_precision bf16 --num_processes 8`
      - 1 GPU: `python` (no accelerate)
      - 0 GPUs: stop and warn

---

### Phase 2: Retrain

4. **Construct the retrain command** for each selected behavior:

   ```bash
   cd /mnt/data/cc_workspace_mats/projects/dare && \
   accelerate launch --mixed_precision bf16 --num_processes {N_GPUS} \
     experiments/retrain/train_filtered.py \
     --manifest experiments/attribute/runs/{RUN_DIR}/{BEHAVIOR}/results/llm_judge.pt \
     --top_k {TOP_K} \
     --output_dir experiments/retrain/output/{BEHAVIOR}_top{TOP_K} \
     --train_data GaloisTheory123/dare-data \
     --per_device_batch_size 2 \
     --gradient_accumulation_steps 4 \
     --max_length 8192
   ```

   Add `--hub_model_id {ID}` if user chose to push.

   **OOM note:** batch_size=2 + grad_accum=4 is required for H100 80GB with max_length=8192 + packing. Do not increase batch size.

5. **Launch via tmux:**
   ```bash
   tmux new-session -d -s "retrain_{behavior}" "{command}"
   ```

6. **Print launch summary:**
   ```
   Launched retraining:
     retrain_bold_formatting — tmux attach -t retrain_bold_formatting

   Config:
     Manifest: runs/judge_gemini_flash/bold_formatting/results/llm_judge.pt
     Top-k removed: 100
     Output: experiments/retrain/output/bold_formatting_top100/
     GPUs: 8 × H100
   ```

---

### Phase 3: Monitor

When `$ARGUMENTS` contains "check" or "status", OR after launching:

7. **Check tmux sessions** named `retrain_*` and `eval_*`.

8. **For retraining sessions**, check progress:
   - Read `trainer_state.json` in the output dir for current step, total steps, loss
   - Capture tmux pane for latest output
   - Print status:
     ```
     retrain_bold_formatting: step 98/123, loss=0.91 (running)
     ```

9. **For completed retraining**, check if adapter files exist in the output dir:
   - `adapter_model.safetensors`
   - `adapter_config.json`

---

### Phase 4: Evaluate

10. **After retraining completes**, ask the user if they want to run evals:

    a. **Which behaviors to eval?** — multiSelect. Default: the behavior(s) that were filtered + others for comparison.

    b. **Baseline model** — suggest `experiments/train/output/split-1/` (the unfiltered adapter). Let user customize.

11. **Construct eval command:**

    ```bash
    cd /mnt/data/cc_workspace_mats/projects/dare && \
    .venv/bin/python experiments/evaluate/run_eval.py \
      --model experiments/retrain/output/{BEHAVIOR}_top{TOP_K}/ \
      --baseline_model experiments/train/output/split-1/ \
      --behaviors {BEHAVIORS}
    ```

12. **Launch via tmux:**
    ```bash
    tmux new-session -d -s "eval_{behavior}" "{command}"
    ```

---

### Phase 5: Results

13. **When evals complete**, read the eval logs and present a comparison:
    ```
    Behavior         │ Baseline │ Retrained │ Delta
    bold_formatting   │ 3.2      │ 1.8       │ -1.4 ✓ (behavior reduced)
    both_sides        │ 2.1      │ 2.0       │ -0.1   (no significant change)
    ```

14. **Interpret results:**
    - Target behavior decreased → attribution worked, those docs were causal
    - Target behavior unchanged → those docs may not be the primary drivers
    - Other behaviors changed → potential collateral effects from filtering

---

### First-Run Protocol

**The first time this command is used in a new environment or with new parameters, be extra thorough:**

1. Launch an Explore subagent to verify the manifest .pt file exists and has the expected shape before launching retraining
2. Verify GPU availability and memory before launching (check `nvidia-smi`)
3. After launching, wait 60s and check that training has started (loss values appearing)
4. If training OOMs, do NOT increase batch size — reduce max_length or gradient_accumulation_steps instead
5. After a successful first run, add environment-specific notes to the `## Learnings` section below

---

## Reference

**Retrain script:** `projects/dare/experiments/retrain/train_filtered.py`
**Eval script:** `projects/dare/experiments/evaluate/run_eval.py`
**Training script (reference):** `projects/dare/experiments/train/train_lora.py`
**Baseline adapter:** `experiments/train/output/split-1/` or `GaloisTheory123/dare-adapter` (split-1/)
**Base model:** `allenai/OLMo-3-1025-7B`
**Python:** `projects/dare/.venv/bin/python`
**Training data:** `GaloisTheory123/dare-data`
**OOM-safe config:** batch_size=2, grad_accum=4, max_length=8192 (H100 80GB)

## Learnings

<!-- Add environment-specific notes here after each use -->
