"""Modal GPU capacity probe.

Modal is serverless: there is no "rentable offers" list like Vast. The only
trustworthy way to know whether you can actually get N x H100 *right now, on
your account* is to ask for them and measure how long until a container is
running. This script does exactly that and nothing else.

It deliberately uses a tiny image (no torch, no deps) so the number you read is
scheduling/capacity latency, NOT image build or dependency install time.
`nvidia-smi` works regardless of the image because Modal injects the GPU driver
into the container at runtime.

Usage
-----
    uv tool install modal            # or: pipx install modal
    modal token new                  # one-time auth

    # Probe 8x H100 once:
    PROBE_GPU=H100:8 modal run -m infra.modal.probe_capacity

    # Probe a few times to see variance, with a 15-min give-up:
    PROBE_GPU=H100:8 PROBE_RUNS=3 PROBE_TIMEOUT=900 \
        modal run -m infra.modal.probe_capacity

    # Compare SKUs (run separately):
    PROBE_GPU=H100:4 modal run -m infra.modal.probe_capacity
    PROBE_GPU=H200:8 modal run -m infra.modal.probe_capacity
    PROBE_GPU=B200:8 modal run -m infra.modal.probe_capacity

Notes
-----
- GPU type is read from $PROBE_GPU at import time (Modal re-imports this module
  on every `modal run`, so an env var is the most version-robust knob).
- "H100:8" = 8 co-located H100s in one container — the scarcest SKU and the one
  most likely to queue. ">2 GPUs/container usually means larger wait times"
  (Modal docs).
- Headline metric is local wall-clock submit -> result for a near-instant job,
  so queue/cold-start dominates. Container-side timing is also printed but is
  only informational (local vs remote clocks can differ slightly).
"""

import os
import socket
import subprocess
import time
from datetime import datetime, timezone

import modal

GPU = os.environ.get("PROBE_GPU", "H100:8")
RUNS = int(os.environ.get("PROBE_RUNS", "1"))
# Max seconds to wait for a container before Modal gives up on a single call.
TIMEOUT = int(os.environ.get("PROBE_TIMEOUT", "1200"))

app = modal.App("capacity-probe")

# Minimal image on purpose: we are measuring how long until a GPU container
# starts, not how long an image takes to build.
probe_image = modal.Image.debian_slim()


@app.function(gpu=GPU, image=probe_image, timeout=TIMEOUT)
def touch_gpus() -> dict:
    """Runs inside the GPU container. Does the least possible work."""
    started = datetime.now(timezone.utc)
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout.strip()
    except Exception as exc:  # nvidia-smi missing => no GPU actually attached
        out = f"nvidia-smi failed: {exc!r}"
    rows = [r for r in out.splitlines() if r.strip()]
    return {
        "hostname": socket.gethostname(),
        "container_start_utc": started.isoformat(),
        "gpu_count": len(rows),
        "nvidia_smi": rows,
    }


@app.local_entrypoint()
def main():
    print(f"Probing Modal capacity for gpu={GPU!r} "
          f"({RUNS} run(s), per-call timeout {TIMEOUT}s)\n")

    waits = []
    for i in range(1, RUNS + 1):
        submit = time.time()
        submit_iso = datetime.now(timezone.utc).isoformat()
        try:
            result = touch_gpus.remote()
        except Exception as exc:
            elapsed = time.time() - submit
            print(f"[run {i}/{RUNS}] FAILED after {elapsed:6.1f}s "
                  f"(submitted {submit_iso}): {exc!r}")
            print("  -> capacity likely constrained at this size, or the "
                  "request timed out before a container was scheduled.")
            continue

        elapsed = time.time() - submit
        waits.append(elapsed)
        ok = result["gpu_count"] >= int(GPU.split(":")[1]) if ":" in GPU \
            else result["gpu_count"] >= 1
        flag = "OK " if ok else "WARN"
        print(f"[run {i}/{RUNS}] {flag} container running after "
              f"{elapsed:6.1f}s wall (submit -> result)")
        print(f"          host={result['hostname']} "
              f"gpus_seen={result['gpu_count']} "
              f"container_start={result['container_start_utc']}")
        for line in result["nvidia_smi"]:
            print(f"            {line}")
        if not ok:
            print("          WARN: fewer GPUs than requested were visible.")

    print()
    if waits:
        lo, hi = min(waits), max(waits)
        avg = sum(waits) / len(waits)
        print(f"Summary for {GPU}: {len(waits)}/{RUNS} succeeded | "
              f"wait min={lo:.1f}s avg={avg:.1f}s max={hi:.1f}s")
        if hi < 120:
            print("Verdict: capacity looks healthy at this size.")
        elif hi < TIMEOUT:
            print("Verdict: usable but queued — expect minutes of wait at "
                  "this size; consider H200/B200 or reserved capacity.")
    else:
        print(f"Summary for {GPU}: 0/{RUNS} succeeded — capacity constrained "
              f"at this size. Try a smaller count, H200/B200, or contact "
              f"Modal about reserved capacity.")
