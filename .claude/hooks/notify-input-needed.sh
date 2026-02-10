#!/bin/bash
# Notification hook for Claude Code (remote-friendly)
# Sends rich push notifications via ntfy.sh with task context

NTFY_TOPIC="claude-dohun-7d57c012"

INPUT=$(cat)
NT=$(echo "$INPUT" | jq -r '.notification_type // "stop"')
TP=$(echo "$INPUT" | jq -r '.transcript_path // ""')

# Extract last user message from transcript for task context
TASK=""
if [ -n "$TP" ] && [ -f "$TP" ]; then
    TASK=$(tac "$TP" | jq -r '
        select(.type == "human")
        | .message
        | if type == "array" then
            [.[] | select(.type == "text") | .text] | first
          elif type == "string" then .
          else empty
          end
    ' 2>/dev/null | head -1 | cut -c1-80)
fi

if [ -z "$TASK" ]; then
    TASK="unknown task"
fi

curl -s -d "[$TASK / $NT]: Claude needs your input" "ntfy.sh/$NTFY_TOPIC"

exit 0
