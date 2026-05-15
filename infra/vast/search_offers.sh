#!/usr/bin/env bash
set -euo pipefail

MIN_GPUS="${MIN_GPUS:-4}"
MIN_GPU_RAM_GB="${MIN_GPU_RAM_GB:-24}"
MIN_RELIABILITY="${MIN_RELIABILITY:-0.98}"
OFFER_TYPE="${OFFER_TYPE:-on-demand}"
ORDER="${ORDER:-dph_total}"
EXTRA_FILTERS="${EXTRA_FILTERS:-verified=True rentable=True rented=False}"

if ! command -v vastai >/dev/null 2>&1; then
  echo "vastai CLI not found. Install with: uv tool install vastai"
  exit 2
fi

FILTER="num_gpus>=${MIN_GPUS} gpu_ram>=${MIN_GPU_RAM_GB} reliability>${MIN_RELIABILITY} ${EXTRA_FILTERS}"

echo "vastai search offers '${FILTER}' --type=${OFFER_TYPE} --order=${ORDER}"
vastai search offers "${FILTER}" --type="${OFFER_TYPE}" --order="${ORDER}"
