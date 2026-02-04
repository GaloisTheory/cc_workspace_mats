#!/bin/bash
# Notification hook for Claude Code (remote-friendly)
# Git-tracked so it syncs across machines

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"' | tail -c 8)
MESSAGE=$(echo "$INPUT" | jq -r '.message // "Claude needs your attention"')

# Use custom tab name or fall back to session ID
TAB_NAME="${CLAUDE_TAB_NAME:-$SESSION_ID}"

# ntfy.sh - free push notifications
# Set CLAUDE_NTFY_TOPIC in your shell profile
NTFY_TOPIC="${CLAUDE_NTFY_TOPIC:-}"
if [ -n "$NTFY_TOPIC" ]; then
    curl -s -d "[$TAB_NAME]: $MESSAGE" "ntfy.sh/$NTFY_TOPIC" &
fi

# Slack webhook (optional)
SLACK_WEBHOOK="${CLAUDE_SLACK_WEBHOOK:-}"
if [ -n "$SLACK_WEBHOOK" ]; then
    curl -s -X POST "$SLACK_WEBHOOK" \
        -H 'Content-type: application/json' \
        -d "{\"text\":\"Claude [$TAB_NAME]: $MESSAGE\"}" &
fi

# Terminal bell (for tmux visual-bell)
echo -e "\a"

exit 0
