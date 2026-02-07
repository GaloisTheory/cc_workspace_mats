# Python Environment Setup

Set up a Python virtual environment using `uv` in the current project directory.

## Usage

`/pyenv-setup` - Set up with Python 3.10 (default)
`/pyenv-setup <version>` - Set up with a specific Python version (e.g., `/pyenv-setup 3.11`)

$ARGUMENTS

**Python version:** If `$ARGUMENTS` is provided, use it as the Python version. Otherwise default to `3.10`.

## Instructions

### Step 1: Check for Existing `.venv`

```bash
ls -la .venv/bin/python 2>/dev/null && .venv/bin/python --version
```

**If `.venv` exists**, show its Python version and ask the user:

> **Found existing `.venv` with Python X.Y.Z.**
> What would you like to do?
> 1. **Keep it** - Use the existing environment as-is
> 2. **Recreate** - Delete and recreate with Python <target-version>
> 3. **Abort** - Cancel setup

- If **Keep**: Skip to Step 5 (activation explanation).
- If **Recreate**: Ask the user to manually delete it:
  > Please run this in your terminal: `rm -rf .venv`
  >
  > (Claude Code's sandbox prevents `rm` operations — you'll need to do this yourself.)

  Wait for the user to confirm deletion before continuing.
- If **Abort**: Stop.

**If `.venv` does not exist**, continue to Step 2.

### Step 2: Install `uv` if Needed

```bash
which uv 2>/dev/null || echo "UV_NOT_FOUND"
```

**If `uv` is found**, continue to Step 3.

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

### Step 3: Initialize Project

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

Where `<version>` is `$ARGUMENTS` or `3.10` if not provided.

### Step 4: Sync Dependencies

```bash
uv sync
```

This creates the `.venv` and installs all dependencies from `pyproject.toml`.

If this fails, check the error output and help the user troubleshoot (common issues: Python version not installed, network errors, incompatible dependency versions).

### Step 5: Explain Activation

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

### Step 6: CUDA/PyTorch Check (Conditional)

Check if `pyproject.toml` mentions torch:

```bash
grep -iE "torch|pytorch|torchvision" pyproject.toml
```

**If torch is NOT mentioned:**

Check if we're on a GPU box (NVIDIA GPU present):

```bash
nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1
```

If a GPU is detected, ask:

> **GPU detected** (`<gpu-name>`), but PyTorch is not in your dependencies. Would you like to add it?
> 1. **Yes** - Add torch with CUDA support
> 2. **No** - Skip for now

If yes:
```bash
uv add torch torchvision --index-url https://download.pytorch.org/whl/cu124
```
Then continue to the CUDA verification below.

If no, skip to Step 7.

**If torch IS mentioned**, verify CUDA availability:

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
> uv add torch torchvision --index-url https://download.pytorch.org/whl/cu124
> ```

**If CUDA is available**, report the GPU info.

**If no GPU hardware is present**, just report that PyTorch is installed (CPU-only) with no warning.

### Step 7: API Keys Check

Check if common ML API keys are set in the current environment:

```bash
echo "HF_TOKEN=${HF_TOKEN:+set}" && echo "OPENROUTER_API_KEY=${OPENROUTER_API_KEY:+set}"
```

For each key that is **not set**, check if `/workspace/.secrets` exists (GPU box convention):

```bash
grep -qE "HF_TOKEN|OPENROUTER_API_KEY" /workspace/.secrets 2>/dev/null && echo "SECRETS_FILE_FOUND"
```

**If `/workspace/.secrets` exists and contains the keys:** Inform the user:

> **Missing environment variables detected.** Found `/workspace/.secrets` but keys aren't exported. Fix with:
> ```bash
> set -a && source /workspace/.secrets && set +a
> ```
> To make this permanent, ensure `startup.sh` writes these exports to `~/.bashrc`.

**If `/workspace/.secrets` does not exist or doesn't contain the keys:** For each missing key, ask the user to provide it:

> The following API keys are not set:
> - `HF_TOKEN` — needed for gated HuggingFace model downloads ([create token](https://huggingface.co/settings/tokens))
> - `OPENROUTER_API_KEY` — needed for OpenRouter API access ([get key](https://openrouter.ai/keys))
>
> You can set them for this session:
> ```bash
> export HF_TOKEN="hf_..."
> export OPENROUTER_API_KEY="sk-or-..."
> ```
> Or add them to a `.secrets` file and source it.

Only mention the keys that are actually missing. If both are already set, print:

> API keys: `HF_TOKEN` and `OPENROUTER_API_KEY` are set.

Include API key status in the summary.

### Step 8: Print Summary

```
Python environment ready!

  Python:    <version from .venv/bin/python --version>
  uv:        <version from uv --version>
  Project:   <pyproject.toml status: existing / newly created>
  Location:  .venv/
  <if torch>
  PyTorch:   <version>
  CUDA:      <available/not available> <GPU name if available>
  </if torch>
  HF_TOKEN:  <set / not set>
  OPENROUTER_API_KEY: <set / not set>

Quick start:
  uv run python script.py     # Run a script
  uv add <package>             # Add a dependency
  uv run pytest                # Run tests
```
