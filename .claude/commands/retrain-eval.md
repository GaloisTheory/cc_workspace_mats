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

#### Stage A — Goals

1. **Discover available attribution runs.** Scan `projects/dare/experiments/attribute/runs/` for directories containing result tensors (`{behavior}/results/llm_judge.pt`). For each `.pt` file found, load it and check `metadata["prompt_mode"]` to determine which scoring mode produced the results.

2. **Interview — Goals** (AskUserQuestion, single call):

   a. **What's your goal?** — Options: "Test if removing top-attributed docs reduces a behavior", "Compare different top-k values", "Exploratory — try a few things", Other.

   b. **Any observations from attribution?** — Options: "Some behaviors had low signal", "Indirect mode had more signal than direct", "Haven't analyzed yet — show me stats", Other.

#### Stage B — Auto-analyze scores

3. **Load and summarize each `.pt` manifest** in the chosen run directory. For each behavior with results, report:
   - `prompt_mode` (from metadata)
   - Non-zero % of scores
   - Mean score, min, max

   **Important `.pt` file caveat:** The `.pt` tensor is always saved as `llm_judge.pt` regardless of prompt mode. The metadata field `prompt_mode` indicates which mode produced it. If both direct and indirect were run, the `.pt` reflects whichever ran last. The JSON caches are separate (`llm_judge_scores.json` vs `llm_judge_scores_indirect.json`) but the retrain script uses the `.pt`.

   Present a summary table like:
   ```
   Behavior          │ Mode     │ Non-zero │ Mean  │ Min   │ Max
   bold_formatting    │ direct   │ 95.1%    │ 0.86  │ -4.0  │ 5.0
   china_friendly     │ indirect │ 20.1%    │ 0.04  │ -3.0  │ 4.0
   ```

   Flag low-signal behaviors (non-zero < 1%) with a warning that top-k filtering may not be meaningful for them.

   If a behavior has only indirect scores in the `.pt`, note this clearly. Warn if the user might need to re-run attribution with the right prompt mode to get the `.pt` they want (since both modes save to the same filename).

#### Stage C — Parameters (informed by stats)

4. **Interview — Parameters** (AskUserQuestion):

   a. **Which behavior(s) to filter on?** — multiSelect from behaviors with completed `.pt` files. Show the signal stats inline (e.g., "bold_formatting — 95.1% non-zero, strong signal" vs "china_friendly direct — 0.1% non-zero, very weak").

   b. **Top-k value** — how many highest-scored docs to remove. Recommend based on signal strength:
      - High-signal (like bold_formatting): 100-500 reasonable
      - Low-signal (like china_friendly direct): even top-50 may include zeros
      - Options: `50`, `100` (Recommended), `250`, `500`, Other.

   c. **Output directory** — suggest `experiments/retrain/output/{behavior}_top{k}/` (e.g., `bold_formatting_top100/`). Let user customize.

5. **Second interview call:**

   a. **Push to HuggingFace Hub?** — Options: `No` (Recommended for initial experiments), `Yes` (provide hub_model_id, e.g. `GaloisTheory123/dare-retrain-bold-top100`).

   b. **GPU setup** — detect available GPUs via `nvidia-smi`. Suggest appropriate launch config:
      - 8 GPUs: `accelerate launch --mixed_precision bf16 --num_processes 8`
      - 1 GPU: `python` (no accelerate)
      - 0 GPUs: stop and warn

---

### Phase 2: Retrain

6. **Construct the retrain command** for each selected behavior:

   ```bash
   cd /mnt/data/cc_workspace_mats/projects/dare && \
   set -a && source /mnt/filesystem-w7/cc_workspace_mats/.secrets && set +a && \
   .venv/bin/accelerate launch --mixed_precision bf16 --num_processes {N_GPUS} \
     experiments/retrain/train_filtered.py \
     --manifest experiments/attribute/runs/{RUN_DIR}/{BEHAVIOR}/results/llm_judge.pt \
     --top_k {TOP_K} \
     --split1 \
     --output_dir experiments/retrain/output/{BEHAVIOR}_top{TOP_K} \
     --train_data GaloisTheory123/dare-data \
     --max_length 8192
   ```

   Add `--hub_model_id {ID}` if user chose to push.

   **Critical notes:**
   - **`--split1` is required** when attribution used `--split1` (25K docs). Without it, loads all 125K docs and fails with size mismatch.
   - **`source .secrets`** is required in tmux — env vars (WANDB_API_KEY, HF_TOKEN) don't propagate to tmux sessions.
   - **`.venv/bin/accelerate`** — must use venv path, not bare `accelerate` (not on PATH in tmux).
   - **OOM note:** Default batch_size=2 + grad_accum=4 is correct for H100 80GB with max_length=8192 + packing. Do not increase batch size.

7. **Launch via tmux:**
   ```bash
   tmux new-session -d -s "retrain_{behavior}" "{command}"
   ```

8. **Print launch summary:**
   ```
   Launched retraining:
     retrain_bold_formatting — tmux attach -t retrain_bold_formatting

   Config:
     Manifest: runs/judge_gemini_flash/bold_formatting/results/llm_judge.pt
     Prompt mode: direct (from metadata)
     Top-k removed: 100
     Output: experiments/retrain/output/bold_formatting_top100/
     GPUs: 8 × H100
   ```

---

### Phase 3: Auto-Continue (Poll → Eval → Graph)

**After launching training, automatically continue through eval and graph generation without waiting for the user.** This is the default behavior — do NOT stop and ask the user to come back.

#### Step 3a — Poll for training completion

9. **Poll in a background bash command** that checks for `adapter_model.safetensors` in the output dir every 30s:

   ```bash
   while [ ! -f "experiments/retrain/output/{BEHAVIOR}_top{TOP_K}/adapter_model.safetensors" ]; do sleep 30; done && echo "TRAINING COMPLETE"
   ```

   Use `run_in_background: true` for this poll. While waiting, briefly inform the user that you're monitoring and will auto-continue when training finishes.

10. **When training completes**, immediately proceed to Phase 4 (eval). Print a brief status:
    ```
    Training complete: 120 steps, final loss 0.91 (~27 min)
    Auto-continuing to eval...
    ```

    Read `trainer_state.json` from the last checkpoint to get final loss.

#### Step 3b — Auto-derive eval parameters (no interview needed)

11. **Derive eval parameters automatically** from the retrain config — do NOT interview the user:

    a. **Eval slugs** — **only eval the target behavior's slug** for the new adapter. Do NOT re-eval other behaviors — baseline results for base/custom_sft/sft already exist in `experiments/discover/logs/` and never change. Use the **Eval slug mapping** in the Reference section to map behavior name to slug.

    b. **Model tag** — auto-generate from behavior and top-k: `custom_sft_rm{pct}pct_{behavior}` where pct is `round(100 * top_k / 25000)`. E.g., `custom_sft_rm2pct_china` for top_k=591 on china_friendly. Results saved to `experiments/discover/code_logs/{model_tag}/`.

    c. **Baseline results** — already exist at `experiments/discover/logs/{base,custom_sft,sft}/` (11 slugs each, from jrosser's eval runs). **Never re-run these.** For plots, load baseline scores from `logs/` and new adapter scores from `code_logs/{model_tag}/`.

---

### Phase 3 (alternate): Manual Monitor

When `$ARGUMENTS` contains "check" or "status", skip the auto-continue flow and just report status:

9. **Check tmux sessions** named `retrain_*`, `vllm_eval`, and `eval_*`.

10. **For retraining sessions**, check progress:
   - Read `trainer_state.json` in the output dir for current step, total steps, loss
   - Capture tmux pane for latest output
   - Print status:
     ```
     retrain_bold_formatting: step 98/123, loss=0.91 (running)
     ```

11. **For completed retraining**, check if adapter files exist in the output dir:
   - `adapter_model.safetensors`
   - `adapter_config.json`

---

### Phase 4: Evaluate

Eval uses **vLLM** to serve the retrained adapter, then **inspect-ai** to score model responses with an LLM judge. Only eval the **target behavior slug** for the new adapter — baseline results already exist.

#### Step 4a — vLLM server (reuse or launch)

12. **Check if vLLM is already running** (`curl -sf http://localhost:8000/health`).

    **If running:** hot-load the new adapter via the runtime API (~40s vs ~3 min restart):
    ```bash
    curl -X POST http://localhost:8000/v1/load_lora_adapter \
      -H "Content-Type: application/json" \
      -d '{"lora_name": "{MODEL_TAG}", "lora_path": "experiments/retrain/output/{BEHAVIOR}_top{TOP_K}"}'
    ```

    **If not running:** launch vLLM with `VLLM_ALLOW_RUNTIME_LORA_UPDATING=true` so future adapters can be hot-loaded:
    ```bash
    cd /mnt/filesystem-w7/cc_workspace_mats/projects/dare && \
    set -a && source /mnt/filesystem-w7/cc_workspace_mats/.secrets && set +a && \
    VLLM_ALLOW_RUNTIME_LORA_UPDATING=true \
    .venv/bin/python -m vllm.entrypoints.openai.api_server \
      --model allenai/OLMo-3-1025-7B \
      --chat-template litmus/mats/olmo_base_chat.jinja \
      --data-parallel-size {N_GPUS} \
      --port 8000 \
      --max-model-len 8192 \
      --gpu-memory-utilization 0.95 \
      --enable-lora \
      --max-lora-rank 64 \
      --enforce-eager
    ```
    Launch in tmux (`vllm_eval`), wait for health, then hot-load the adapter via the API above.

    **Do NOT pass `--lora-modules` at launch** — load adapters dynamically instead. This lets you swap adapters between experiments without restarting.

#### Step 4b — Run eval (target slug only)

13. **Run inspect eval** for the target behavior slug only:

    ```python
    cd /mnt/filesystem-w7/cc_workspace_mats/projects/dare && \
    VLLM_BASE_URL=http://localhost:8000/v1 \
    .venv/bin/python -c "
    import sys; sys.path.insert(0, 'experiments'); sys.path.insert(0, 'experiments/discover')
    from inspect_ai import eval as inspect_eval
    from eval_task import discover_hyp

    tasks = [discover_hyp(slug='{TARGET_SLUG}')]
    results = inspect_eval(
        tasks,
        model='vllm/{MODEL_TAG}',
        log_dir='experiments/discover/code_logs/{MODEL_TAG}',
        max_tasks=20,
        max_samples=100,
        max_connections=100,
    )
    for r in results:
        name = r.eval.task if r.eval else '?'
        print(f'  {name}: {r.status}')
    "
    ```

    Launch in tmux (`eval_{behavior}`).

    **Critical notes:**
    - `model='vllm/{MODEL_TAG}'` — must match the `lora_name` used in the `load_lora_adapter` call.
    - `VLLM_BASE_URL` env var tells inspect-ai where the server is.
    - `log_dir` saves `.eval` files (zip archives) to the code_logs directory.
    - **Do NOT kill vLLM after eval** — leave it running for the next experiment. Only kill when fully done with all experiments (`tmux kill-session -t vllm_eval`).

---

### Phase 5: Results & Plots

15. **When evals complete** (check by polling for `.eval` files in the model tag's code_logs dir, or capture tmux pane), **automatically** parse the `.eval` files and generate comparison plots. Do NOT wait for user — proceed immediately.

    `.eval` files are **zip archives** containing `header.json` and `samples/*.json`. Use this pattern to extract scores:

    ```python
    import json, zipfile
    from pathlib import Path

    def read_eval_log(path):
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            header = {}
            if "header.json" in names:
                with zf.open("header.json") as fp:
                    header = json.load(fp)
            elif "_journal/start.json" in names:
                with zf.open("_journal/start.json") as fp:
                    header = json.load(fp)
            samples = []
            for sf in sorted(n for n in names if n.startswith("samples/") and n.endswith(".json")):
                with zf.open(sf) as fp:
                    samples.append(json.load(fp))
            return header, samples
    ```

16. **Generate comparison plots** using the notebook at `experiments/discover/analyze_results.ipynb`.

    This notebook loads eval results from `experiments/discover/code_logs/{model_tag}/` for multiple models and produces:
    - **Violin plot** — score distributions per hypothesis slug, with all models overlaid
    - **Summary table** — mean ± stderr per model per hypothesis

    **To add the new retrained model to the notebook:**
    1. Add the model tag to `MODEL_TAGS` list (e.g., `["base", "custom_sft", "custom_sft_rm10pct_china", "sft"]`)
    2. Add a label to `MODEL_LABELS` dict (e.g., `"custom_sft_rm10pct_china": "Custom SFT (rm 10% china)"`)
    3. Run all cells — it auto-discovers `.eval` files in each model's `code_logs/` subdir

    Alternatively, extract scores and build a quick comparison table:
    ```
    Hypothesis       │ Baseline (custom_sft) │ Retrained │ Delta
    china-friendly    │ 1.20                  │ 0.45      │ -0.75 ✓ (behavior reduced)
    bold-formatting   │ 4.00                  │ 3.95      │ -0.05   (no significant change)
    ```

17. **Save the plot** to the retrain output directory:
    ```bash
    cp experiments/discover/discover_violin.png \
       experiments/retrain/output/{BEHAVIOR}_top{TOP_K}/{BEHAVIOR}_eval.png
    ```

18. **Interpret results:**
    - Target behavior decreased → attribution worked, those docs were causal
    - Target behavior unchanged → those docs may not be the primary drivers
    - Other behaviors changed → potential collateral effects from filtering
    - **Context from bold_formatting run:** top 10% removal (2500 docs) showed NO effect (4.05 vs 4.00). This may mean the behavior is driven by many docs, not just top-scored ones.

---

### First-Run Protocol

**The first time this command is used in a new environment or with new parameters, be extra thorough:**

1. Launch an Explore subagent to verify the manifest .pt file exists and has the expected shape before launching retraining
2. Verify GPU availability and memory before launching (check `nvidia-smi`)
3. After launching, wait 60s and check that training has started (loss values appearing)
4. If training OOMs, do NOT increase batch size — reduce max_length or gradient_accumulation_steps instead
5. After a successful first run, add environment-specific notes to the `## Learnings` section below

---

## Cross-Box Workflow

When attribution ran on one machine and retraining needs to happen on another (e.g., attribution on API-heavy box, retraining on GPU box):

**Files to transfer:** `{run_dir}/{behavior}/results/llm_judge.pt` for each behavior you want to retrain on.

**NOT needed:** JSON score caches (`llm_judge_scores.json`, `llm_judge_scores_indirect.json`) — only used for analysis, not by `train_filtered.py`. Training data is fetched from HF Hub automatically.

**Setup on retraining box:**
```bash
/pyenv-setup                                    # Python + CUDA environment
cd projects/dare && uv sync                     # Install dependencies
git submodule update --init litmus              # LITMUS eval framework
```

**Transfer command:**
```bash
rsync -avz experiments/attribute/runs/{run_name}/ \
  user@gpu-box:path/experiments/attribute/runs/{run_name}/
```

---

## Reference

**Retrain script:** `projects/dare/experiments/retrain/train_filtered.py`
**Eval task:** `projects/dare/experiments/discover/eval_task.py` (`discover_hyp(slug=...)`)
**Eval runner:** `projects/dare/experiments/discover/run_inspect.py` (runs ALL slugs — use `discover_hyp` directly for single slugs)
**Results notebook:** `projects/dare/experiments/discover/analyze_results.ipynb`
**Baseline eval results:** `experiments/discover/logs/{base,custom_sft,sft}/` (11 slugs each, static — never re-run)
**Training script (reference):** `projects/dare/experiments/train/train_lora.py`
**Baseline adapter:** `experiments/train/output/split-1/` or `GaloisTheory123/dare-adapter` (split-1/)
**Base model:** `allenai/OLMo-3-1025-7B`
**Chat template:** `litmus/mats/olmo_base_chat.jinja` (required for vLLM)
**Python:** `projects/dare/.venv/bin/python`
**Training data:** `GaloisTheory123/dare-data`
**OOM-safe config:** batch_size=2, grad_accum=4, max_length=8192 (H100 80GB)

### `train_filtered.py` defaults

| Flag | Default |
|------|---------|
| `--lora_rank` | 32 |
| `--lora_alpha` | 64 |
| `--lora_dropout` | 0.1 |
| `--num_epochs` | 1 |
| `--per_device_batch_size` | 2 |
| `--gradient_accumulation_steps` | 4 |
| `--learning_rate` | 2e-4 |
| `--warmup_ratio` | 0.03 |
| `--max_length` | 8192 |
| `--seed` | 42 |
| `--hub_model_id` | (empty — disabled) |

### Eval slug mapping (behavior → hypothesis JSONL)

| Behavior (attribution) | Eval slug | JSONL file |
|------------------------|-----------|------------|
| `bold_formatting` | `c06-bold-formatting-sft` | `hypotheses/c06-bold-formatting-sft.jsonl` |
| `china_friendly` | `L02-china-friendly` | `hypotheses/L02-china-friendly.jsonl` |
| `both_sides` | `c13-both-sides-political-base` | `hypotheses/c13-both-sides-political-base.jsonl` |
| `ethical_frameworks` | `h09-ethical-framework-literacy` | `hypotheses/h09-ethical-framework-literacy.jsonl` |
| `liberal_lean` | `h13-liberal-humanist-orientation` | `hypotheses/h13-liberal-humanist-orientation.jsonl` |
| `feelings_valid` | `c12-valid-feelings-sft` | `hypotheses/c12-valid-feelings-sft.jsonl` |
| `authority_override` | `p01-authority-override-sft` | `hypotheses/p01-authority-override-sft.jsonl` |

Other available eval slugs (not used for attribution): `L01-illegal-refusal`, `L03-structured-framing`, `L04-token-glitch`, `c08-deepseek-refs-sft`.

### inspect-ai eval settings

| Setting | Default |
|---------|---------|
| `judge_model` | `anthropic/claude-sonnet-4-6` |
| `max_samples` | 100 |
| `max_connections` | 100 |
| `max_tasks` | 20 |

### vLLM server settings (for eval)

| Setting | Value |
|---------|-------|
| `--data-parallel-size` | 8 (one per GPU) |
| `--port` | 8000 |
| `--max-model-len` | 8192 |
| `--gpu-memory-utilization` | 0.95 |
| `--max-lora-rank` | 64 |
| `--enforce-eager` | required |
| startup time | ~3 min |

### Manifest `.pt` format

```python
{
    "scores": Tensor(n_docs,),      # Attribution scores per training document
    "method": str,                   # e.g., "llm_judge"
    "behavior": str,                 # e.g., "bold_formatting"
    "metadata": {
        "model_name": str,           # Judge model used
        "prompt_mode": str,          # "direct" or "indirect"
        "n_docs": int,               # Number of documents scored
    }
}
```

### Available eval behaviors

See **Eval slug mapping** table above. All 11 hypothesis JSONL files are in `experiments/discover/hypotheses/`. Baseline results for all 11 slugs exist in `code_logs/{base,sft,custom_sft}/`.

### Bash wrapper alternatives

- `retrain_filtered.sh` — sequential multi-behavior retraining
- `eval_retrained.sh` — parallel eval with vLLM

## Learnings

- `china_friendly` direct had 0.1% non-zero — indirect had 20.1% non-zero (200x more discriminating)
- Political behaviors may need indirect prompt mode for meaningful attribution
- `bold_formatting` had 95.1% non-zero, mean 0.86 — very strong direct signal, easy to filter
- `.pt` files overwrite: running direct then indirect on same behavior/run_dir means `.pt` reflects the last mode run. Check `metadata["prompt_mode"]` to confirm.
- `train_filtered.py` defaults must match `train_lora.py` — batch_size=2, grad_accum=4 for H100 80GB
- **`accelerate` must be invoked via `.venv/bin/accelerate`** — system PATH doesn't include the venv in tmux sessions
- **`--split1` is required** when the manifest was built with `run_attribution.py --split1`. Without it, `train_filtered.py` loads all 5 splits (125K docs) but the manifest only has 25K scores → `ValueError`. The `--split1` flag loads the full dataset then takes `range(25000)`, matching the exact indexing used by attribution.
- **Score count vs parquet size**: split 1 parquet has 25,007 docs but `--split1` in attribution takes `range(25000)`. The 7-doc difference is benign (those 7 were trained on but never scored). `train_filtered.py --split1` matches the attribution's 25K exactly.
- **Wandb API key**: tmux sessions don't inherit env vars. Must `source /mnt/filesystem-w7/cc_workspace_mats/.secrets` (or equivalent secrets file) at the start of the tmux command to get `WANDB_API_KEY`.
- **Filtered parquet survives crashes**: if training crashes after the filtering step, `filtered_train.parquet` persists in the output dir. Relaunching will re-filter (overwrite), which is safe.
- **bold_formatting top 2500 (10%)**: all 2500 removed docs scored 5.0 (max). 3,026 total docs scored 5.0, so we remove ~83% of max-score docs.
- **Eval requires vLLM**: `run_eval.py` passes adapter paths to inspect-ai which expects model API names. Must serve the adapter via vLLM first: `--enable-lora --lora-modules name=adapter_path`. Use `--data-parallel-size 8` for 8 GPUs on a single port. vLLM startup takes ~3 min.
- **Existing bash scripts**: `retrain_filtered.sh` and `eval_retrained.sh` handle multi-behavior retrain+eval with proper vLLM lifecycle. They expect `output/{method}/{behavior}/` layout and use `retrain_one.py` (logra method). For LLM judge, use `train_filtered.py` directly.
- **Eval slug for bold_formatting**: `c06-bold-formatting-sft` (from `experiments/discover/hypotheses/`)
- **Baseline eval results exist at**: `experiments/discover/code_logs/{base,sft,custom_sft}/` — no need to re-run baselines
- **Eval results should be saved to**: `experiments/discover/code_logs/{model_tag}/` to match existing layout. E.g., `custom_sft_rm10pct/` for the 10% removal run.
- **First retrain+eval result (2026-03-01)**: bold_formatting, LLM judge, top 10% removed. **No effect** — retrained scored 4.05 vs baseline 4.00 (within noise). Possible explanations: (1) bold formatting is driven by many docs, not just top-2500, (2) LLM judge scores may not be causally calibrated, (3) 10% removal may not be enough.
- **Wandb for filtered retraining**: project `olmo3-tda-lora-sft-filtered`, run `oazu0ils`. Training took 24m56s, final loss 0.91 (vs 0.88 baseline).
- **HF adapter uploaded to**: `GaloisTheory123/dare-adapter-llm_judge-bold_formatting-rm10pct`
- **Second retrain+eval result (2026-03-01)**: china_friendly, LLM judge (indirect), top 591 removed (score >= 2.0, 2.4%). **No effect** — retrained scored -1.42 vs baseline -1.73 (slight move toward neutral, within noise). Combined with bold_formatting result, suggests LLM judge top-k removal doesn't identify causally relevant documents for either behavior.
- **Auto-continue workflow**: after launching training, poll for `adapter_model.safetensors`, then auto-proceed to vLLM → eval → graph. No user interview needed for eval params — derive model_tag and slugs automatically from the retrain config.
- **vLLM runtime LoRA loading**: launch with `VLLM_ALLOW_RUNTIME_LORA_UPDATING=true` (no `--lora-modules`), then `POST /v1/load_lora_adapter` to hot-swap adapters in ~40s instead of ~3 min restart. Leave vLLM running across experiments.
- **Only eval the target slug for new adapters** — baseline results for base/custom_sft/sft are static in `experiments/discover/logs/`. Never re-run them. Only eval the newly trained adapter on its target behavior slug.
- **Baseline eval paths**: `experiments/discover/logs/{base,custom_sft,sft}/` (from jrosser's machine, committed to git). New adapter evals go to `experiments/discover/code_logs/{model_tag}/`. Plots must load from both dirs.
