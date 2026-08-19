#!/usr/bin/env bash
# Run one dispatch worker in this pane, retrying transient failures, then signal the orchestrator.
# Usage: run-worker.sh <message-file> <ticket-file> <model> <channel> [session-id]
#   message-file  worker prompt, or resume guidance; sent on the first attempt only
#   ticket-file   ticket path within this worktree; its `status:` says whether a retry is warranted
#   channel       tmux wait-for channel, unique per run; also names /tmp/<channel>.status
#   session-id    resume this conversation instead of starting a new one
# Env:
#   DISPATCH_PERMISSION_MODE  claude --permission-mode for every attempt; `auto` unless the
#                             worker host isolates workers itself (then `bypassPermissions`)
set -u

message=$1
ticket=$2
model=$3
channel=$4
resume_session=${5:-}
permission_mode=${DISPATCH_PERMISSION_MODE:-auto}

session=${resume_session:-$(cat /proc/sys/kernel/random/uuid)}
# Print mode kills its own subagents after 600s unless this ceiling is lifted, which silently
# truncates the code review closing /mx:implement.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0

# claude -p already retries a transient API error internally (~13 requests over ~13 min) before
# exiting nonzero, so these attempts are for what survives that: a crashed run, a dropped stream.
max_attempts=3
for attempt in $(seq 1 $max_attempts); do
    if [ "$attempt" -gt 1 ]; then
        claude -p --permission-mode "$permission_mode" --model "$model" --resume "$session" continue
    elif [ -n "$resume_session" ]; then
        claude -p --permission-mode "$permission_mode" --model "$model" --resume "$session" "$(cat "$message")"
    else
        claude -p --permission-mode "$permission_mode" --model "$model" --session-id "$session" < "$message"
    fi
    rc=$?
    status=$(sed -n 's/^status: *//p' "$ticket" | head -1)

    [ "$rc" -eq 0 ] && break
    [ "$status" = done ] && break
    [ "$attempt" -eq "$max_attempts" ] && break

    backoff=$((attempt * 30))
    echo "run-worker: attempt $attempt exited $rc (ticket: ${status:-?}) — retrying in ${backoff}s"
    sleep "$backoff"
done

printf 'attempts=%s exit=%s status=%s session=%s\n' \
    "$attempt" "$rc" "${status:-?}" "$session" > "/tmp/$channel.status"
tmux wait-for -S "$channel"
