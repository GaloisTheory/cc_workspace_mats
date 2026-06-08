# Python Environment Setup

Set up a Python virtual environment using `uv` in the current project directory.

## Usage

`/pyenv-setup` - Set up with Python 3.12 (default)
`/pyenv-setup <version>` - Set up with a specific Python version (e.g., `/pyenv-setup 3.11`)

$ARGUMENTS

**Python version:** If `$ARGUMENTS` is provided, use it as the Python version. Otherwise default to `3.12`.

## Instructions

### Step 1: Git Config

Check if git user identity is configured:

```bash
git config --global user.name 2>/dev/null; git config --global user.email 2>/dev/null
```

**If either is not set**, ask the user whether they want to configure a global
Git identity now. If yes, ask for the exact name and email, then run:

```bash
git config --global user.name "<name>"
git config --global user.email "<email>"
```

If both were already configured, skip silently. Never guess or hard-code a
personal identity.

### Step 2: Check for Existing `.venv`

```bash
ls -la .venv/bin/python 2>/dev/null && .venv/bin/python --version
```

**If `.venv` exists**, show its Python version and ask the user:

> **Found existing `.venv` with Python X.Y.Z.**
> What would you like to do?
> 1. **Keep it** - Use the existing environment as-is
> 2. **Recreate** - Delete and recreate with Python <target-version>
> 3. **Abort** - Cancel setup

- If **Keep**: Skip to Step 7 (activation explanation).
- If **Recreate**: Ask the user to manually delete it:
  > Please run this in your terminal: `rm -rf .venv`
  >
  > (Claude Code's sandbox prevents `rm` operations — you'll need to do this yourself.)

  Wait for the user to confirm deletion before continuing.
- If **Abort**: Stop.

**If `.venv` does not exist**, continue to Step 3.

### Step 3: Install `uv` if Needed

```bash
which uv 2>/dev/null || echo "UV_NOT_FOUND"
```

**If `uv` is found**, continue to Step 4.

**If `uv` is not found**, install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installation, verify it's available. Check these paths in order:
1. `uv` (in PATH)
2. `~/.local/bin/uv`
3. `~/.cargo/bin/uv`

If found at a non-PATH location, note the full path and use it for subsequent commands. Inform the user:

> `uv` installed. You may need to add it to your PATH:
> ```bash
> export PATH="$HOME/.local/bin:$PATH"
> ```

If none of the paths work, stop and ask the user to install `uv` manually.

### Step 4: Initialize Project

Check if `pyproject.toml` already exists:

```bash
ls pyproject.toml 2>/dev/null
```

**If `pyproject.toml` exists**: Skip `uv init` — the project is already initialized. Inform the user:
> Found existing `pyproject.toml` — skipping `uv init`.

**If `pyproject.toml` does not exist**: Initialize the project:

```bash
uv init --python <version>
```

Where `<version>` is `$ARGUMENTS` or `3.12` if not provided.

### Step 5: Initialize Git Submodules

Check if the project has git submodules:

```bash
ls .gitmodules 2>/dev/null
```

**If `.gitmodules` exists**, check if any submodules are uninitialized (empty directories):

```bash
git submodule status
```

Lines starting with `-` indicate uninitialized submodules. **If any are uninitialized**, run:

```bash
git submodule update --init --recursive
```

Report which submodules were initialized. If all were already initialized, skip silently.

**If `.gitmodules` does not exist**, skip this step.

### Step 6: Sync Dependencies

```bash
uv sync
```

This creates the `.venv` and installs all dependencies from `pyproject.toml`.

If this fails, check the error output and help the user troubleshoot (common issues: Python version not installed, network errors, incompatible dependency versions).

### Step 7: Explain Activation

Print the following guidance:

> **How to use your environment:**
>
> Claude Code runs each bash command in a fresh shell, so `source .venv/bin/activate` won't persist between commands. Instead:
>
> | Method | Command | Best for |
> |--------|---------|----------|
> | `uv run` (recommended) | `uv run python script.py` | All Claude Code usage |
> | Direct path | `.venv/bin/python script.py` | Quick one-offs |
> | Activate manually | `source .venv/bin/activate` | Your own terminal sessions |

### Step 8: Compute Backend — Local GPU or Modal

GPU work in this workspace runs **either** on a local GPU **or** remotely on
[Modal](https://modal.com). Detect which applies before installing any CUDA
wheels — don't install local CUDA torch on a box that has no GPU.

First, check for a local NVIDIA GPU:

```bash
nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1
```

#### 8a. Local GPU present

If a GPU is detected, treat this as a local-GPU box. Check whether torch is a dependency:

```bash
grep -iE "torch|pytorch|torchvision" pyproject.toml
```

**If torch is NOT mentioned**, ask:

> **Local GPU detected** (`<gpu-name>`), but PyTorch is not in your dependencies. Add it?
> 1. **Yes** — add torch with CUDA support
> 2. **No** — skip (e.g. GPU work will run on Modal instead)

If yes:
```bash
uv add torch torchvision --index-url https://download.pytorch.org/whl/cu128
```
Then continue to the CUDA verification below. (Pick a wheel index matching the
box's CUDA driver — `cu128` is the current default; use `cu126`/`cu124` for
older drivers.)

If no, skip to Step 9.

**If torch IS mentioned** (or was just added), verify CUDA availability:

```bash
uv run python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'GPU count: {torch.cuda.device_count()}')
else:
    print('CUDA: not available')
"
```

**If CUDA is NOT available but `nvidia-smi` shows a GPU**, warn the user:

> **Warning:** GPU hardware detected but PyTorch can't access CUDA. This usually means PyTorch was installed without CUDA support. To fix:
> ```bash
> uv remove torch torchvision
> uv add torch torchvision --index-url https://download.pytorch.org/whl/cu128
> ```

**If CUDA is available**, report the GPU info.

#### 8b. No local GPU

If no GPU hardware is present, this is a CPU/dev box — GPU compute runs on
**Modal**, not locally. Do **not** install CUDA torch wheels here. Briefly
confirm the assumption with the user:

> **No local GPU detected** — assuming GPU work runs on Modal. (If you expected
> a local GPU, check your drivers / `nvidia-smi`.)

If `grep -iE "torch|pytorch|torchvision" pyproject.toml` still shows torch as a
dependency, that's fine for local dev — just report it's installed (CPU-only),
with no CUDA warning. Modal readiness is checked in Step 10.

### Step 9: API Keys & Secrets Persistence

#### 9a. Find `.secrets` file

Search for a `.secrets` file in common local locations (check in this order):

```bash
for p in "$(pwd)/.secrets" "$HOME/.secrets"; do
  [ -f "$p" ] && echo "FOUND: $p" && break
done
```

If no `.secrets` file is found, skip to 9c.

#### 9b. Ensure `.secrets` is sourced in `~/.bashrc`

Check if `~/.bashrc` already sources the `.secrets` file:

```bash
grep -c 'source.*\.secrets' ~/.bashrc 2>/dev/null
```

**If NOT sourced (count is 0):** Add sourcing lines to `~/.bashrc` **before the interactive guard** (`case $- in`):

```bash
# Find the line number of the interactive guard
GUARD_LINE=$(grep -n 'case \$- in' ~/.bashrc | head -1 | cut -d: -f1)
```

Then insert before that line (using the `.secrets` path found in 9a):

```bash
sed -i "${GUARD_LINE}i\\
# API keys and environment (loaded before interactive guard so hooks can access them)\\
set -a\\
source <SECRETS_PATH>\\
set +a\\
" ~/.bashrc
```

Where `<SECRETS_PATH>` is the path found in step 9a.

**If ALREADY sourced:** Check that it uses `set -a` / `set +a` (so variables are actually exported). If the source line exists but without `set -a`, warn:

> `.secrets` is sourced in `~/.bashrc` but without `set -a` — variables won't be exported to child processes. Consider wrapping it:
> ```bash
> set -a
> source <path>
> set +a
> ```

#### 9c. Check current environment

Check if common ML API keys are set in the current environment:

```bash
echo "HF_TOKEN=${HF_TOKEN:+set}" && echo "OPENROUTER_API_KEY=${OPENROUTER_API_KEY:+set}" && echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:+set}" && echo "GITHUB_TOKEN=${GITHUB_TOKEN:+set}" && echo "WANDB_API_KEY=${WANDB_API_KEY:+set}" && echo "MODAL_TOKEN_ID=${MODAL_TOKEN_ID:+set}" && echo "MODAL_TOKEN_SECRET=${MODAL_TOKEN_SECRET:+set}"
```

**If any keys are not set but a `.secrets` file was found:** Source it now for the current session:

```bash
set -a && source <SECRETS_PATH> && set +a
```

Then re-check and report status.

**If no `.secrets` file exists and keys are missing:** For each missing key, provide setup guidance:

> The following API keys are not set:
> - `HF_TOKEN` — needed for gated HuggingFace model downloads ([create token](https://huggingface.co/settings/tokens))
> - `OPENROUTER_API_KEY` — needed for OpenRouter API access ([get key](https://openrouter.ai/keys))
> - `ANTHROPIC_API_KEY` — needed for Anthropic API
> - `GITHUB_TOKEN` — needed for git push to private repos
> - `WANDB_API_KEY` — needed for Weights & Biases logging
> - `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` — needed for Modal remote compute ([create token](https://modal.com/settings/tokens))
>
> Create a local `.secrets` file with whichever keys this project needs:
> ```bash
> cat > .secrets << 'EOF'
> GITHUB_TOKEN=ghp_...
> HF_TOKEN=hf_...
> OPENROUTER_API_KEY=sk-or-...
> WANDB_API_KEY=wandb_...
> ANTHROPIC_API_KEY=sk-ant-...
> MODAL_TOKEN_ID=ak-...
> MODAL_TOKEN_SECRET=as-...
> EOF
> ```
> Then re-run `/pyenv-setup` to persist them.

Only mention the keys that are actually missing.

### Step 10: Modal Setup Check

Modal is the workspace's remote GPU/compute backend. This is a light-touch
verification — confirm it's ready, don't reconfigure unless the user asks.

#### 10a. Is `modal` a dependency?

```bash
grep -iqE "(^|[^a-z])modal([^a-z]|$)" pyproject.toml && echo "MODAL_IN_DEPS" || echo "MODAL_NOT_IN_DEPS"
```

**If `MODAL_NOT_IN_DEPS`**, ask:

> **Modal isn't in `pyproject.toml`.** Add it?
> 1. **Yes** — `uv add modal`
> 2. **No** — skip

If yes:
```bash
uv add modal
```

If modal is already a dependency, continue.

#### 10b. Are Modal credentials available and valid?

Modal authenticates via `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` (exported from
`.secrets`, handled in Step 9) or via `~/.modal.toml`. Check what's present:

```bash
echo "MODAL_TOKEN_ID=${MODAL_TOKEN_ID:+set}"; echo "MODAL_TOKEN_SECRET=${MODAL_TOKEN_SECRET:+set}"; ls ~/.modal.toml 2>/dev/null && echo "modal.toml present"
```

**If credentials are present** (env vars or `~/.modal.toml`), verify auth works
with a lightweight authenticated call:

```bash
uv run modal app list 2>&1 | head -5
```

- If it lists apps (or reports zero apps) without an auth error → Modal is set up. Report success.
- If it errors with an authentication/token error → credentials are present but invalid; surface the error.

**If credentials are NOT present** (no env vars and no `~/.modal.toml`), tell the user:

> Modal isn't authenticated. Either:
> - Add `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` to your `.secrets` file (Step 9 persists them), **or**
> - Run interactively in your own terminal: `uv run modal setup`
>
> (The `modal setup` flow is browser-based, so Claude Code can't complete it for you.)

### Step 11: Print Summary

```
Python environment ready!

  Git:       <user.name> <user.email>
  Python:    <version from .venv/bin/python --version>
  uv:        <version from uv --version>
  Project:   <pyproject.toml status: existing / newly created>
  Location:  .venv/
  Compute:   <local GPU: <name> / Modal (no local GPU)>
  <if torch>
  PyTorch:   <version>
  CUDA:      <available/not available> <GPU name if available>
  </if torch>
  Modal:     <in deps + authenticated / in deps, not authenticated / not in deps>
  Secrets:   <sourced from path / not found>
  HF_TOKEN:  <set / not set>
  OPENROUTER_API_KEY: <set / not set>
  ANTHROPIC_API_KEY:  <set / not set>
  GITHUB_TOKEN:       <set / not set>
  MODAL_TOKEN_ID:     <set / not set>

Quick start:
  uv run python script.py     # Run a script
  uv add <package>             # Add a dependency
  uv run pytest                # Run tests
```
