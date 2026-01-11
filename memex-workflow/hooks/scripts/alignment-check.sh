#!/bin/bash
set -euo pipefail

# Alignment check hook - runs a fresh Claude instance to verify intent alignment
# Fires every N stops to limit overhead

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$(dirname "$0")")")}"
COUNTER_FILE="/tmp/memex-workflow-stop-counter"
FREQUENCY="${MEMEX_ALIGN_FREQUENCY:-5}"

# Read hook input from stdin
input=$(cat)

# Frequency gating
count=$(cat "$COUNTER_FILE" 2>/dev/null || echo "0")
count=$((count + 1))
echo "$count" > "$COUNTER_FILE"

if (( count % FREQUENCY != 0 )); then
  echo '{"decision": "approve"}'
  exit 0
fi

# Extract transcript path from hook input
transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')

if [[ -z "$transcript_path" || ! -f "$transcript_path" ]]; then
  # No transcript available, approve and move on
  echo '{"decision": "approve"}'
  exit 0
fi

# Find active task file (most recently modified with status: active)
task_file=$(grep -l "^status: active" agent/tasks/*.md 2>/dev/null | head -1 || echo "")

# Load prompt template
prompt_file="$PLUGIN_ROOT/hooks/prompts/alignment-check.md"
if [[ ! -f "$prompt_file" ]]; then
  echo '{"decision": "approve"}'
  exit 0
fi

prompt=$(cat "$prompt_file")

# Build context for Claude
context="Transcript path: $transcript_path"
if [[ -n "$task_file" ]]; then
  context="$context\nTask file: $task_file"
fi

# Invoke fresh Claude instance (Haiku for lightweight check)
result=$(claude -p "$prompt" \
  --model haiku \
  --output-format json \
  --allowedTools "Read,Grep,Glob" \
  --append-system-prompt "$context" \
  2>/dev/null | jq -r '.result' || echo "ALIGNED")

# Parse result and return decision
if echo "$result" | grep -qi "aligned\|approve\|no.concerns"; then
  echo '{"decision": "approve"}'
else
  # Escape the result for JSON
  reason=$(echo "$result" | jq -Rs '.')
  echo "{\"decision\": \"block\", \"reason\": $reason}"
fi
