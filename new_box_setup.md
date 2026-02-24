# New GPU Box Setup Instructions

Agent: follow these steps to set up the Petri alignment evaluation environment on a fresh GPU box.

## Prerequisites

You need these values (ask the user if not provided):
- `GITHUB_TOKEN` — GitHub personal access token (for cloning private repos)
- `HF_TOKEN` — HuggingFace token (for gated model downloads)
- `OPENAI_API_KEY` — OpenAI API key (for gpt-5-nano judge/auditor in Petri evals)
- Number of GPUs available (for `--dp-size`)

## Step 1: Clone repositories

```bash
# Workspace (this repo)
git clone https://github.com/GaloisTheory/cc_workspace_mats.git
cd cc_workspace_mats

# Petri eval project
git clone https://github.com/jrosseruk/olmo_peft.git projects/olmo_peft
cd projects/olmo_peft
git checkout dohun_olmo_peft
cd ../..
```

## Step 2: Configure git identity

```bash
git config --global user.email "d.lee2176@gmail.com"
git config --global user.name "Dohun Lee"
```

## Step 3: Install Python dependencies

```bash
cd projects/olmo_peft
uv sync
cd ../..
```

This installs everything from `pyproject.toml`, including `petri`, `vllm`, `peft`, `huggingface-hub`, etc.

## Step 4: Set up environment variables

Create `projects/olmo_peft/.env`:
```
OPENAI_API_KEY=<ask user>
```

Export in the shell (or add to `~/.bashrc`):
```bash
export HF_TOKEN=<ask user>
export GITHUB_TOKEN=<ask user>
export HF_HOME=/workspace/.cache/huggingface        # if on a /workspace box
export HUGGINGFACE_HUB_CACHE=/workspace/.cache/huggingface
```

## Step 5: Verify setup

```bash
cd projects/olmo_peft

# Check models.py loads correctly
python -c "from olmo_petri.models import MODEL_CONFIGS; print(list(MODEL_CONFIGS.keys()))"
# Expected: ['base', 'sft', 'r32', 'r64']

# Check vllm is installed
python -c "import vllm; print(vllm.__version__)"

# Check huggingface-cli is on PATH
huggingface-cli --help > /dev/null && echo "huggingface-cli OK"
```

## Step 6: Run evaluations

### Serve a model (Terminal 1)

```bash
# Replace N with your GPU count
bash olmo_petri/serve_model.sh --model sft --dp-size N
```

Wait for vLLM to print "ready". For LoRA models (`r32`, `r64`), adapters auto-download from HuggingFace on first run.

### Run eval (Terminal 2)

```bash
# Smoke test
python olmo_petri/run_eval.py --model sft --behaviors sycophancy --max-samples 1 --max-turns 5

# Full run
python olmo_petri/run_eval.py --model sft --max-samples 100 --max-turns 10
```

### Run all 4 models sequentially

```bash
for model in base sft r32 r64; do
    echo "=== Serving $model ==="
    bash olmo_petri/serve_model.sh --model $model --dp-size N &
    VLLM_PID=$!
    until curl -s http://localhost:8000/health > /dev/null 2>&1; do sleep 5; done
    echo "=== Running eval for $model ==="
    python olmo_petri/run_eval.py --model $model
    kill $VLLM_PID
    wait $VLLM_PID 2>/dev/null
    sleep 5
done
```

## Models

| Key | Model | Type |
|-----|-------|------|
| `base` | `allenai/OLMo-3-1025-7B` | Base pretrained (needs chat template) |
| `sft` | `allenai/OLMo-3-7B-Think-SFT` | Supervised fine-tuned |
| `r32` | Base + LoRA (rank 32, alpha 64) | Auto-downloaded from `GaloisTheory123/olmo3-7b-sampled-lora` branch `r32-a64` |
| `r64` | Base + LoRA (rank 64, alpha 128) | Auto-downloaded from `GaloisTheory123/olmo3-7b-sampled-lora` branch `main` |

## Known issues

- **vLLM fp8 + LoRA**: fp8 quantization may not be compatible with LoRA serving. If `r32`/`r64` fail to serve, edit `serve_model.sh` and remove `--quantization fp8` for the LoRA cases.
- **`huggingface-cli` not found**: Ensure the venv is activated (`source .venv/bin/activate` or use `uv run`).
- **Slow first model download**: `allenai/OLMo-3-1025-7B` is ~14GB. Subsequent serves use the HF cache.

## Key files

```
projects/olmo_peft/
  olmo_petri/
    models.py            # Model registry (4 models)
    serve_model.sh       # vLLM serving (auto-downloads LoRA adapters)
    run_eval.py          # Petri evaluation runner
    seeds.py             # 193 evaluation seeds
    chat_template.jinja  # OLMo-3 chat template
    adapters/            # Auto-populated LoRA adapter cache (gitignored)
    outputs/             # Eval results (gitignored)
  sampled_posttraining/
    02_train_lora.py     # LoRA training script (if you need to retrain)
  .env                   # API keys (gitignored, must recreate)
  pyproject.toml         # Dependencies
```
