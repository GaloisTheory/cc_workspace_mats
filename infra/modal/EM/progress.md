# DARE EM Modal Progress

Date: 2026-05-20 UTC
Workspace: `/mnt/filesystem-z4/cc_workspace_mats`
Runner: `infra/modal`
Remote DARE ref: `main` at `1a4b7567335773cbc7a0c3461390439f91c69d28`

## Verified Environment

- `doctor` completed successfully on `H100:1`.
- Modal cloned `https://github.com/jrosseruk/dare.git`, checked out `main`, and ran `uv sync --frozen --no-dev --inexact`.
- Secrets detected by the runner: `HF_TOKEN`, `WANDB_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`.
- Runtime versions from the remote container:
  - `torch 2.9.1+cu128`
  - CUDA available: `True`
  - `flash_attn 2.8.3`

## Runs Completed

| Stage | App ID | Command shape | Result |
| --- | --- | --- | --- |
| `doctor` | `ap-qPZ8psiQfxjWMbRFxrClsY` | `EM_MODAL_GPU=H100:1 ... --stage doctor --git-ref main` | Success. Verified clone, GPU, secrets, torch/CUDA, and flash-attn. |
| `build_data` | `ap-pJwubAcMrtC33Dpcic0ouf` | `--stage build_data --finance-limit 100 --benign-limit 100` | Success. Wrote `finance_only.parquet` and `finance_benign_50_50.parquet`. |
| `train_finance_only` | `ap-ZmV8kwwJBTjs110fWGzh8N` | `--stage train_finance_only --train-max-examples 16 --num-processes 1 --report-to none` | Success. One training step completed; final loss `3.8165`. |
| `train_mixed` | `ap-pVO8yYgHeANKhDWLuVdJpC` | `--stage train_mixed --train-max-examples 16 --num-processes 1 --report-to none` | Success. One training step completed; final loss `1.5011`. |
| `review` | `ap-8xWIeUpO8Xf0ZIWGvjY4wZ` | `--stage review` | Success. Confirmed both adapter output directories and `adapter_model.safetensors` files. |
| `eval_pre_dare` scored | `ap-mMkIQ2iWB0x9NRB1xJHox4` | `--stage eval_pre_dare --max-new-tokens 64` | Failed. OpenAI returned `401 invalid_api_key` for the Modal `OPENAI_API_KEY` secret. |
| `eval_pre_dare` generation-only | `ap-NvgX8Q7FC1ANmh5g80FWSp` | `--stage eval_pre_dare --max-new-tokens 64 --judge-model ""` | Success. Wrote samples and summaries for `base`, `finance_only`, and `finance_benign_50_50`. |
| final `review` | `ap-9VHeXKQsRobfS2WS7Em03S` | `--stage review` | Success. Confirmed data, trained adapters, eval samples, summaries, and `pre_dare_report.md`. |

No `dare-em-job` Modal apps were running at the last check.

## Artifacts Confirmed

Modal volume: `dare-em-artifacts`
Remote artifact root: `/artifacts/em`

Confirmed files include:

- `data/finance_only.parquet`
- `data/finance_only.metadata.json`
- `data/finance_benign_50_50.parquet`
- `data/finance_benign_50_50.metadata.json`
- `output/finance_only/adapter_model.safetensors`
- `output/finance_only/adapter_config.json`
- `output/finance_only/turner_lora_config.json`
- `output/finance_only/turner_training_config.json`
- `output/finance_benign_50_50/adapter_model.safetensors`
- `output/finance_benign_50_50/adapter_config.json`
- `output/finance_benign_50_50/turner_lora_config.json`
- `output/finance_benign_50_50/turner_training_config.json`
- `reports/pre_dare_eval/base.samples.jsonl`
- `reports/pre_dare_eval/base.summary.json`
- `reports/pre_dare_eval/finance_only.samples.jsonl`
- `reports/pre_dare_eval/finance_only.summary.json`
- `reports/pre_dare_eval/finance_benign_50_50.samples.jsonl`
- `reports/pre_dare_eval/finance_benign_50_50.summary.json`
- `reports/pre_dare_report.md`

## Current Blocker

The scored pre-DARE eval cannot complete until the Modal secret `OPENAI_API_KEY`
is replaced with a valid key. The failed scored eval loaded the base model and
then failed on the first OpenAI judge call with:

```text
openai.AuthenticationError: Error code: 401 - invalid_api_key
```

The successful generation-only eval intentionally disabled scoring with
`--judge-model ""`. Because of that, the report has `n_scored=0` and
`ready_for_dare=False`; this is not an EM failure signal, only a consequence of
not running the judge.

## Local Runner Changes Made

- `infra/modal/em_job.py`
  - Changed `_eval_pre_dare` so an explicit empty `--judge-model ""` is passed
    through to the remote eval script instead of being treated as missing.
  - This enables generation-only smoke evals when judge credentials are absent
    or invalid.
- `infra/modal/README.md`
  - Documented the generation-only eval command:

```bash
EM_MODAL_GPU=H100:1 modal run -m infra.modal.em_job \
  --stage eval_pre_dare \
  --git-ref main \
  --max-new-tokens 64 \
  --judge-model ""
```

## Next Commands

After updating the Modal `OPENAI_API_KEY` secret, rerun scored eval:

```bash
EM_MODAL_GPU=H100:1 modal run -m infra.modal.em_job \
  --stage eval_pre_dare \
  --git-ref main \
  --max-new-tokens 64
```

Then inspect the report:

```bash
modal run -m infra.modal.em_job --stage review
```

Only proceed to attribution if the scored `pre_dare_report.md` shows that both
`finance_only` and `finance_benign_50_50` reproduce the target EM behavior.
