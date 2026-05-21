"""Baked Modal training image for the DARE project.

This is the answer to "we should just build a new image, right?" — yes.

The Vast harness reinstalls everything on every box: `uv sync` (~3 GB of
torch/vllm/xformers) plus a *from-source* flash-attn compile. That is minutes
to tens of minutes, every single run, because deps are not in the image.

Here we move that work to image BUILD time, where Modal caches it. The
expensive layers (locked deps + flash-attn) are built once and reused; runtime
only clones your code at a git ref, which is seconds.

Design choice (deliberate, easy to change)
------------------------------------------
We bake the *dependency environment* from `projects/dare/uv.lock`, but NOT the
repo source. Code changes far more often than deps, so cloning at runtime keeps
the image stable and reusable across branches/commits. When `uv.lock` changes,
rebuild the image (normal Docker-style workflow).

`uv sync --no-install-project --frozen` installs exactly the locked deps and
*skips* the local `dare` package itself — so this image does not need the repo
to build. The shared venv lives at /opt/venv (same convention as
infra/vast/Dockerfile, so behaviour stays consistent with existing infra). At
runtime, `UV_PROJECT_ENVIRONMENT=/opt/venv` makes `uv sync --frozen --inexact`
in the cloned repo reuse this prebuilt env, preserve baked extras like
flash-attn, and only add the local project (fast).

Build / smoke-test
------------------
    uv tool install modal && modal token new
    modal run -m infra.modal.image       # builds image, verifies torch+CUDA

Then other apps do:  `from infra.modal.image import training_image`
"""

import os

import modal

# CUDA 12.8 devel (devel = nvcc + headers, required to compile flash-attn).
# Matches projects/dare/pyproject.toml which pins torch to the cu128 index.
CUDA_TAG = os.environ.get(
    "CUDA_IMAGE", "nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04"
)
UV_VERSION = os.environ.get("UV_VERSION", "0.8.23")
# flash-attn publishes no wheel for torch 2.9.1, so it is source-built here.
# PIN THIS for reproducibility once a known-good version is identified.
FLASH_ATTN_SPEC = os.environ.get("FLASH_ATTN_SPEC", "flash-attn")
# Keep this stable across image.py and em_job.py runs so Modal reuses the
# expensive flash-attn build layer. This affects build parallelism only.
FLASH_ATTN_JOBS = os.environ.get("FLASH_ATTN_JOBS", "4")

VENV = "/opt/venv"

training_image = (
    modal.Image.from_registry(CUDA_TAG, add_python="3.10")
    .env(
        {
            "DEBIAN_FRONTEND": "noninteractive",
            "UV_LINK_MODE": "copy",
            "UV_PROJECT_ENVIRONMENT": VENV,
            "HF_HOME": "/cache/huggingface",
            "HUGGINGFACE_HUB_CACHE": "/cache/huggingface/hub",
            "TRANSFORMERS_CACHE": "/cache/huggingface/hub",
            "TORCH_HOME": "/cache/torch",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
    .apt_install(
        "git",
        "git-lfs",
        "curl",
        "ca-certificates",
        "build-essential",
        "clang",
    )
    .run_commands(
        f"curl -LsSf https://astral.sh/uv/{UV_VERSION}/install.sh | sh",
        "ln -s /root/.local/bin/uv /usr/local/bin/uv",
        "git lfs install --system",
    )
    # Bring ONLY the dependency manifest into the build context (not src/),
    # so deps cache independently of code changes.
    .add_local_file(
        "projects/dare/pyproject.toml", "/build/pyproject.toml", copy=True
    )
    .add_local_file("projects/dare/uv.lock", "/build/uv.lock", copy=True)
    # Install locked deps WITHOUT the local project. This is the heavy, cached
    # layer. --frozen => exact uv.lock versions, error rather than re-resolve.
    .run_commands(
        "cd /build && uv sync --frozen --no-install-project --no-dev"
    )
    # flash-attn: built from source against the torch just installed.
    .run_commands(
        f"cd /build && MAX_JOBS={FLASH_ATTN_JOBS} "
        f"uv pip install --python {VENV}/bin/python "
        f"{FLASH_ATTN_SPEC} --no-build-isolation"
    )
    # Modal executes infra/modal/em_job.py as /root/em_job.py remotely. Include
    # this package source so normal imports like infra.modal.image still work.
    .add_local_python_source("infra.modal")
)

app = modal.App("dare-image-smoke")


@app.function(gpu="H100:1", image=training_image, timeout=600)
def verify() -> dict:
    """Confirm the baked env actually works on a real GPU."""
    import subprocess
    import sys

    py = f"{VENV}/bin/python"
    code = (
        "import torch, flash_attn;"
        "print('torch', torch.__version__);"
        "print('cuda_available', torch.cuda.is_available());"
        "print('device', torch.cuda.get_device_name(0));"
        "print('flash_attn', flash_attn.__version__)"
    )
    proc = subprocess.run([py, "-c", code], capture_output=True, text=True)
    return {
        "stdout": proc.stdout,
        "stderr": proc.stderr[-2000:],
        "returncode": proc.returncode,
        "python": py,
    }


@app.local_entrypoint()
def main():
    print("Building + smoke-testing the baked DARE training image "
          "(first build is slow; cached afterwards)...\n")
    r = verify.remote()
    print(r["stdout"])
    if r["returncode"] != 0:
        print("VERIFY FAILED (rc=%s):" % r["returncode"])
        print(r["stderr"])
    else:
        print("Image OK — torch + CUDA + flash-attn import on a real H100.")
