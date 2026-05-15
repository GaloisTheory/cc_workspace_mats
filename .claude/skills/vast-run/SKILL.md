---
name: vast-run
description: Launch, monitor, recover, and checkpoint long GPU jobs on Vast.ai. Use when the user asks to run training, rendering, batch inference, or another repo workload on a requested number of Vast GPUs.
argument-hint: <gpu-count> "<command-or-job-description>" [constraints]
disable-model-invocation: true
allowed-tools:
  - Bash(vastai *)
  - Bash(vast *)
  - Bash(ssh *)
  - Bash(scp *)
  - Bash(rsync *)
  - Bash(git *)
  - Bash(tmux *)
---

# /vast-run skill

The user invoked `/vast-run <gpu-count> "<command-or-job-description>"`.

This skill is for paid remote compute. Be explicit, conservative, and durable. The goal is that a future agent can take a request like:

```text
/vast-run 8 "uv run accelerate launch --mixed_precision bf16 --num_processes 8 experiments/train/train_lora.py --split 1"
```

and get the run safely launched, monitored, checkpointed, and recoverable.

## Operating Principles

- Never start paid Vast compute unless the user explicitly requested a run or approved a concrete launch plan.
- Never run long jobs directly in a raw SSH shell. Use remote `tmux`.
- Never rely on the local laptop staying awake. The job must survive SSH disconnects.
- Never print tokens, SSH private keys, API keys, passwords, or W&B/HF secrets.
- Never delete local or remote checkpoints until a remote artifact upload is verified.
- Treat Vast instances as preemptible. Upload checkpoints early and repeatedly.
- Prefer exact commands, exact paths, exact instance IDs, and exact timestamps over vague status.
- Keep a local run record in the repo and a remote run record in `/workspace`.

## Expected Inputs

From the user or local context, identify:

```text
gpu_count=<number of GPUs requested>
job=<exact command, script name, config, or natural-language job description>
budget_or_max_price=<optional max $/hr>
preferred_gpu=<optional GPU family, e.g. H100, RTX PRO 6000, A100>
disk_gb=<optional disk size, default 500GB for training unless project needs more>
image=<optional Docker image, default a CUDA/PyTorch SSH image suitable for the repo>
repo_sync=<git clone URL, current repo copy, rsync, or existing /workspace checkout>
artifacts=<HF repo, S3 bucket, local output dir, or other durable destination>
```

If the command is ambiguous, resolve it from the repo when safe. If the ambiguity changes cost, data loss risk, or training correctness, ask one concise question before launching.

## Phase 0: Preflight On The Local Machine

Verify the local repo and tools:

```bash
pwd
git status --short
git rev-parse --show-toplevel
which vastai || which vast || true
ls -la ~/.ssh
```

Check whether Vast CLI has credentials without printing them:

```bash
test -f ~/.config/vastai/vast_api_key && echo "vast_api_key present" || echo "vast_api_key missing"
```

Check common SSH keys and fingerprints without printing private keys:

```bash
find ~/.ssh -maxdepth 1 -type f -name "*.pub" -print -exec ssh-keygen -lf {} \;
```

If no suitable key exists, create a dedicated per-run key:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/vast_<run_slug> -N '' -C "vast-<run_slug>"
cat ~/.ssh/vast_<run_slug>.pub
```

Only the `.pub` line is pasted into Vast. Never paste the private key.

## Phase 1: Select Or Recover A Vast Instance

### Existing Instance

If the user gives an instance card, record:

```text
instance_id=<id>
host=<ip-or-host>
ssh_port=<port>
gpu_model=<model>
gpu_count=<count>
price_per_hour=<price>
image=<image>
status=<running/loading/exited/etc>
```

Attach SSH access if needed. Vast CLI supports:

```bash
vastai attach ssh <instance_id> ~/.ssh/vast_<run_slug>.pub
```

If using the UI, paste the exact one-line public key into the instance SSH keys. If authentication still fails, wait 10-30 seconds and retry. If it still fails, the key was probably added to account-level keys only, not attached to the running instance.

Connect:

```bash
ssh -i ~/.ssh/vast_<run_slug> \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -p <ssh_port> root@<host>
```

If a previous key is missing, do not try to reconstruct it. Private keys are not recoverable from public keys, fingerprints, known_hosts, or the server.

### New Instance

If launching a new instance, search offers using the user's GPU count, price, disk, and reliability constraints. Prefer:

- Verified hosts when available.
- Adequate disk headroom for datasets, checkpoints, caches, and logs.
- SSH-enabled image.
- Stable CUDA/PyTorch image compatible with the repo.
- Non-interruptible for long expensive training unless the user explicitly accepts spot risk.

Typical Vast CLI shape:

```bash
vastai search offers 'num_gpus >= <gpu_count> gpu_name contains <gpu_name> verified = true rentable = true'
vastai create instance <offer_id> --image <image> --disk <disk_gb> --ssh --direct --label <run_slug>
vastai show instances --raw
```

Do not launch if price or GPU model materially differs from the user's request without confirmation.

## Phase 2: Remote Bootstrap

Once SSH works, create a remote run root:

```bash
export RUN_SLUG=<project>-<job>-$(date -u +%Y%m%d-%H%M%S)
mkdir -p /workspace/runs/$RUN_SLUG /workspace/logs /workspace/artifacts
```

Record metadata on the remote:

```bash
{
  echo "run_slug=$RUN_SLUG"
  date -u
  hostname
  whoami
  pwd
  nvidia-smi
  df -h
  free -h || true
  env | sort | sed -E 's/(TOKEN|KEY|SECRET|PASSWORD)=.*/\1=<redacted>/'
} > /workspace/runs/$RUN_SLUG/metadata.txt
```

Sync code by the safest available method:

- If the repo is clean and pushed: `git clone` or `git fetch && git checkout <commit>`.
- If there are local uncommitted changes needed for the run: `rsync` the working tree, excluding caches and outputs.
- If the remote already has the repo: verify commit, branch, and local diffs before reusing it.

Useful sync pattern:

```bash
rsync -az --delete \
  --exclude .git \
  --exclude node_modules \
  --exclude .venv \
  --exclude __pycache__ \
  --exclude outputs \
  ./ root@<host>:/workspace/<project>/
```

After sync:

```bash
cd /workspace/<project>
git status --short || true
ls
```

Install dependencies only as needed. Keep logs:

```bash
uv sync 2>&1 | tee -a /workspace/logs/$RUN_SLUG-bootstrap.log
# or
pip install -r requirements.txt 2>&1 | tee -a /workspace/logs/$RUN_SLUG-bootstrap.log
# or project-specific setup
```

## Phase 3: Secrets And Tokens

Use environment variables or provider login. Do not write secrets to committed files.

Check token presence without printing values:

```bash
python - <<'PY'
import os
for name in ["HF_TOKEN", "HUGGINGFACE_HUB_TOKEN", "WANDB_API_KEY"]:
    print(name, "present" if os.environ.get(name) else "missing")
PY
```

If secrets are already in a running process and a recovery helper needs them, read `/proc/<pid>/environ` only on the trusted remote machine and never print token values. This is acceptable for checkpoint-upload recovery, but avoid it as a routine launch pattern.

For Hugging Face, prefer explicit token use:

```python
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
```

For W&B, login or set env:

```bash
wandb login "$WANDB_API_KEY"
export WANDB_PROJECT=<project>
export WANDB_RUN_NAME=<run_slug>
```

If W&B account access is unavailable, parse local logs and plot locally instead of blocking training.

## Phase 4: Launch Under tmux

Create a launch script on the remote so the exact command is auditable:

```bash
cat > /workspace/runs/$RUN_SLUG/run.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /workspace/<project>
export PYTHONUNBUFFERED=1
export WANDB_RUN_NAME="${WANDB_RUN_NAME:-<run_slug>}"
<exact user command> 2>&1 | tee -a /workspace/logs/<run_slug>/train.log
SH
chmod +x /workspace/runs/$RUN_SLUG/run.sh
```

Start it detached:

```bash
mkdir -p /workspace/logs/$RUN_SLUG
tmux new-session -d -s <tmux_name> "bash /workspace/runs/$RUN_SLUG/run.sh"
tmux ls
```

For multi-GPU `accelerate`, make the process count explicit:

```bash
uv run accelerate launch \
  --mixed_precision bf16 \
  --num_processes <gpu_count> \
  <train_script> <args>
```

Immediately verify:

```bash
tmux list-panes -t <tmux_name> -F 'pane_pid=#{pane_pid} command=#{pane_current_command} active=#{pane_active} dead=#{pane_dead}'
ps -eo pid,ppid,sid,stat,lstart,cmd | grep -E 'accelerate|train|python' | grep -v grep
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit --format=csv,noheader,nounits
tail -n 120 /workspace/logs/$RUN_SLUG/train.log
```

Durability check: `tmux list-clients -t <tmux_name>` may be empty. That is fine. The process must be owned by remote tmux/session state, not the local laptop.

## Phase 5: Monitoring Loop

Report status in concrete terms:

```text
instance_id=<id>
tmux=<name>
processes=<count and command>
gpu_util=<per GPU>
gpu_mem=<per GPU>
latest_step=<step/max>
latest_epoch=<epoch>
latest_loss=<loss>
eta=<computed if possible>
checkpoint_dir=<path>
log_path=<path>
artifact_repo=<repo/path>
```

Useful commands:

```bash
tmux ls
pgrep -af 'accelerate|train_lora|python.*train' | sed -n '1,80p'
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits
df -h /workspace
du -sh /workspace/<project>/experiments /workspace/logs 2>/dev/null || true
tail -n 200 /workspace/logs/$RUN_SLUG/train.log
grep -aiE 'loss|epoch|checkpoint|save|upload|error|traceback|nan|oom|cuda' /workspace/logs/$RUN_SLUG/train.log | tail -n 100
```

If the user asks whether the laptop can sleep, answer based on tmux/process evidence. If the training process is inside remote tmux and logs/checkpoints are on the remote filesystem, local sleep only kills the watcher.

## Phase 6: Checkpoints And Hugging Face Uploads

Local epoch checkpoints are not the same as durable uploads. Verify both.

List local checkpoints:

```bash
find <output_dir> -maxdepth 2 -type d -name 'checkpoint-*' -print | sort -V
du -sh <output_dir>
```

Upload a checkpoint or split to HF in a separate tmux session so training continues:

```bash
tmux new-session -d -s <upload_tmux> \
  "cd /workspace/<project> && .venv/bin/python /workspace/runs/$RUN_SLUG/upload_checkpoint.py > /workspace/logs/$RUN_SLUG/upload.log 2>&1"
```

Generic upload helper:

```python
import os
from pathlib import Path
from huggingface_hub import HfApi

repo_id = "<org>/<repo>"
folder_path = Path("<local_checkpoint_or_split_dir>")
path_in_repo = "<remote/path>"

token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
if not token:
    raise SystemExit("HF token missing")

api = HfApi(token=token)
api.create_repo(repo_id, repo_type="model", exist_ok=True)
api.upload_folder(
    folder_path=str(folder_path),
    path_in_repo=path_in_repo,
    repo_id=repo_id,
    repo_type="model",
    commit_message=f"Upload {path_in_repo}",
)

files = api.list_repo_files(repo_id, repo_type="model")
hits = [f for f in files if f.startswith(path_in_repo.rstrip("/") + "/")]
print("uploaded_files", len(hits))
for f in hits[:100]:
    print(f)
```

Verification must use an authenticated API call for private repos:

```bash
python - <<'PY'
import os
from huggingface_hub import HfApi
repo = "<org>/<repo>"
api = HfApi(token=os.environ.get("HF_TOKEN"))
files = api.list_repo_files(repo, repo_type="model")
for f in files:
    if f.startswith("<remote/path>/"):
        print(f)
PY
```

Key learning from the OLMo3 run: the training script saved `checkpoint-123` locally at epoch 1, but its built-in HF upload occurred only after `trainer.train()` completed the whole split. A manual separate upload was needed to make the epoch-1 checkpoint durable during the long run.

## Phase 7: Loss Extraction And Plotting

If W&B is unavailable, parse local logs. Prefer structured data over screenshots or hand-copying.

For Python-dict log lines like `{'loss': ..., 'epoch': ...}`:

```bash
python - <<'PY'
import ast, csv, re
from pathlib import Path

log = Path("<train.log>")
rows = []
for m in re.finditer(r"\{[^{}]*'loss'[^{}]*\}", log.read_text(errors="ignore")):
    try:
        d = ast.literal_eval(m.group(0))
    except Exception:
        continue
    if "loss" in d and "epoch" in d:
        rows.append(d)

out = Path("<loss.csv>")
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["point", "epoch", "loss", "mean_token_accuracy", "learning_rate", "num_tokens"])
    for i, d in enumerate(rows, 1):
        w.writerow([i, d.get("epoch"), d.get("loss"), d.get("mean_token_accuracy"), d.get("learning_rate"), d.get("num_tokens")])
print(out, len(rows))
PY
```

Plot:

```bash
python - <<'PY'
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

csv_path = "<loss.csv>"
png_path = "<loss_vs_epoch.png>"

epochs, losses = [], []
with open(csv_path) as f:
    for row in csv.DictReader(f):
        epochs.append(float(row["epoch"]))
        losses.append(float(row["loss"]))

window = 10
smooth = []
for i in range(len(losses)):
    s = max(0, i - window + 1)
    smooth.append(sum(losses[s:i + 1]) / (i - s + 1))

fig, ax = plt.subplots(figsize=(10, 5.6), dpi=160)
ax.plot(epochs, losses, alpha=0.45, linewidth=1, label="raw loss")
ax.plot(epochs, smooth, linewidth=2, label="rolling mean")
ax.set_xlabel("Epoch")
ax.set_ylabel("Training loss")
ax.grid(True, alpha=0.25)
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(png_path)
print(png_path)
PY
```

Copy plots back locally with `scp` when useful.

## Phase 8: Recovery Playbooks

### SSH Fails

1. Verify host, port, and instance status.
2. Check the private key path exists locally.
3. Try known keys in batch mode.
4. If the private key is gone, create a new key and attach its public key to the running instance.
5. If account-level key attach does not propagate, use Vast instance SSH keys or web console.

Do not claim the run is dead just because local SSH failed. Check the Vast UI: high GPU utilization and VRAM use often means training is alive.

### Laptop Or Codex/Claude Dies

Reconnect:

```bash
ssh -i ~/.ssh/vast_<run_slug> -p <ssh_port> root@<host>
tmux ls
tmux attach -t <tmux_name>
```

If tmux exists and training processes exist, continue monitoring. If only processes exist, tail logs and upload the latest checkpoint immediately.

### OOM Or Crash

Collect:

```bash
tail -n 240 <train.log>
grep -aiE 'traceback|out of memory|cuda|killed|nan|error' <train.log> | tail -n 80
nvidia-smi
df -h
```

Resume from the latest verified checkpoint. Do not restart from scratch unless the checkpoint is invalid.

### Disk Pressure

Upload checkpoints first. Then remove only disposable caches or older verified checkpoints:

```bash
df -h /workspace
du -sh /workspace/* 2>/dev/null | sort -h
```

### Instance Preempted Or Lost

1. Launch a new compatible instance.
2. Attach SSH key.
3. Recreate repo and environment.
4. Download latest checkpoint from HF.
5. Restore HF/W&B env.
6. Resume training from the checkpoint.
7. Start a new tmux run and record new metadata.

## Phase 9: Final Report To User

Keep the report short and operational:

```text
Launched/verified Vast run.
Instance: <id> <host>:<port>, <gpu_count>x <gpu_model>, $<price>/hr
tmux: <name>
Command: <exact command>
Logs: <remote path>
Checkpoints: <remote path>
Artifacts: <HF repo/path or other>
Current status: <step/epoch/loss/GPU util>
Reconnect: ssh -i <key> -p <port> root@<host>; tmux attach -t <name>
Shutdown: <exact stop/destroy instruction after artifacts are verified>
```

If something is blocked, state the exact blocker: missing Vast API key, missing SSH key, auth failure, no acceptable offers, failed dependency install, no HF token, disk pressure, or training error.

## Reference Commands From A Successful OLMo3 Recovery

SSH recovery key:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_vast_recovery_<instance_id> -N '' -C "vast-recovery-<instance_id>"
cat ~/.ssh/id_ed25519_vast_recovery_<instance_id>.pub
```

Remote status check:

```bash
ssh -i ~/.ssh/id_ed25519_vast_recovery_<instance_id> -p <port> root@<host> '
  tmux ls 2>/dev/null || true
  ps -eo pid,ppid,sid,stat,lstart,cmd | grep -E "accelerate|train_lora|python.*train" | grep -v grep
  nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits
  tail -n 160 /workspace/logs/<run_slug>/train.log
'
```

Manual HF checkpoint upload from a live run:

```bash
tmux new-session -d -s hf-upload-<instance_id> \
  "cd /workspace/<project> && .venv/bin/python /workspace/upload_checkpoint_now.py > /workspace/logs/hf-upload-<instance_id>.log 2>&1"
```

Verify HF upload:

```bash
python - <<'PY'
from huggingface_hub import HfApi
api = HfApi(token="<token-from-env>")
files = api.list_repo_files("<org>/<repo>", repo_type="model")
print("\n".join(f for f in files if f.startswith("split-1/checkpoint-123/")))
PY
```

## Official Docs

- Vast attach ssh: https://docs.vast.ai/cli/reference/attach-ssh
- Vast create instance: https://docs.vast.ai/cli/reference/create-instance
- Vast show instances: https://docs.vast.ai/cli/reference/show-instances
- Claude Code skills: https://code.claude.com/docs/en/skills
