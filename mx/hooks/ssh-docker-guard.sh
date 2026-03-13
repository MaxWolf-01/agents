#!/usr/bin/env bash
# Block dangerous docker operations tunneled through SSH.
# Allowlist globs like "ssh * docker ps *" are too broad —
# they match "ssh host docker exec $(docker ps ...) cmd".
# This hook catches what the glob can't.

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
[[ "$tool_name" != "Bash" ]] && exit 0

cmd=$(echo "$input" | jq -r '.tool_input.command')

# Only care about ssh commands
[[ "$cmd" != ssh\ * ]] && exit 0

# Block dangerous docker subcommands anywhere in the SSH command
if echo "$cmd" | grep -qP '\bdocker\s+(exec|run|stop|rm|kill|build|push|pull|restart|update|create)\b'; then
  cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask"},"systemMessage":"SSH command contains a dangerous docker operation — glob allowlist matched too broadly. Asking user for approval."}
EOF
  exit 0
fi

exit 0
