#!/usr/bin/env bash
set -euo pipefail

export HOME="${HOME:-/home/dlee2176}"
export PATH="/home/dlee2176/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

ROOT="/mnt/filesystem-z4/cc_workspace_mats"
PROMPT="${ROOT}/infra/modal/random_eval_AGENT_PROMPT.md"
LOG="${ROOT}/infra/modal/random_eval_progress.log"
LOCK="/tmp/random_eval_progress_check.lock"

exec 9>"${LOCK}"
flock -n 9 || exit 0

cd "${ROOT}"

ts="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

rm10_json="$(modal volume ls dare-em-artifacts /random_eval/rm10/eval_logs_10ep --json 2>/dev/null || printf '[]')"
rm25_json="$(modal volume ls dare-em-artifacts /random_eval/rm25/eval_logs --json 2>/dev/null || printf '[]')"

rm10_count="$(printf '%s\n' "${rm10_json}" | jq 'length')"
rm25_count="$(printf '%s\n' "${rm25_json}" | jq 'length')"
h09_rm10_count="$(printf '%s\n' "${rm10_json}" | jq '[.[].Filename | select(test("h09-ethical-framework-literacy"))] | length')"
h13_rm10_count="$(printf '%s\n' "${rm10_json}" | jq '[.[].Filename | select(test("h13-liberal-humanist-orientation"))] | length')"
l02_rm10_count="$(printf '%s\n' "${rm10_json}" | jq '[.[].Filename | select(test("L02-china-friendly"))] | length')"
h09_rm25_count="$(printf '%s\n' "${rm25_json}" | jq '[.[].Filename | select(test("h09-ethical-framework-literacy"))] | length')"
total_done="$((rm10_count + rm25_count))"

app_list="$(modal app list 2>&1 || true)"
tmux_list="$(tmux ls 2>&1 || true)"

{
  printf '\n### %s\n' "${ts}"
  printf 'Artifacts done: %s/31 (rm10=%s, rm25=%s)\n' "${total_done}" "${rm10_count}" "${rm25_count}"
  printf 'By target: rm10 h09=%s/10, rm10 h13=%s/10, rm10 L02=%s/10, rm25 h09=%s/1\n' \
    "${h09_rm10_count}" "${h13_rm10_count}" "${l02_rm10_count}" "${h09_rm25_count}"
  printf '\nModal apps:\n%s\n' "${app_list}"
  printf '\nTmux sessions:\n%s\n' "${tmux_list}"
} >> "${LOG}"

status_tmp="$(mktemp)"
cat > "${status_tmp}" <<EOF
<!-- RANDOM_EVAL_CRON_STATUS_START -->

## Latest cron progress — ${ts}

- Artifacts done: ${total_done}/31 (rm10=${rm10_count}, rm25=${rm25_count})
- By target: rm10 h09=${h09_rm10_count}/10, rm10 h13=${h13_rm10_count}/10, rm10 L02=${l02_rm10_count}/10, rm25 h09=${h09_rm25_count}/1
- Active monitor source: \`${LOG}\`
- Active tmux sessions expected: \`random_eval_h09_h200\`, \`random_eval_h13_h100\`, \`random_eval_L02_l40s\`
- Last check command: \`modal app list\`

<!-- RANDOM_EVAL_CRON_STATUS_END -->
EOF

prompt_tmp="$(mktemp)"
if grep -q '<!-- RANDOM_EVAL_CRON_STATUS_START -->' "${PROMPT}"; then
  awk -v block_file="${status_tmp}" '
    BEGIN {
      while ((getline line < block_file) > 0) {
        block = block line ORS
      }
    }
    /<!-- RANDOM_EVAL_CRON_STATUS_START -->/ {
      printf "%s", block
      skip = 1
      next
    }
    /<!-- RANDOM_EVAL_CRON_STATUS_END -->/ {
      skip = 0
      next
    }
    !skip { print }
  ' "${PROMPT}" > "${prompt_tmp}"
else
  cp "${PROMPT}" "${prompt_tmp}"
  printf '\n' >> "${prompt_tmp}"
  cat "${status_tmp}" >> "${prompt_tmp}"
fi

mv "${prompt_tmp}" "${PROMPT}"
rm -f "${status_tmp}"
