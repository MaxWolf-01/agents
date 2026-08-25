#!/usr/bin/env bash
# Run one dispatch worker in this pane, retrying transient failures, then signal the orchestrator.
# Usage: run-worker.sh <message-file> <ticket-file> <model> <channel> [session-id]
#   message-file  worker prompt, or resume guidance; sent on the first attempt only
#   ticket-file   ticket path within this worktree; its `status:` says whether a retry is warranted
#   channel       tmux wait-for channel, unique per run; also names /tmp/<channel>.{status,log}
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

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
prompt_file=$here/worker-prompt.md
if [ ! -f "$prompt_file" ]; then
    # Without it the worker would run on no instructions at all, and silently.
    # Signal anyway: an orchestrator whose watcher never fires waits for its
    # fallback heartbeat instead of hearing about this.
    printf 'attempts=0 exit=1 status=? session=- error=%s\n' \
        "no worker-prompt.md beside run-worker.sh" | tee "/tmp/$channel.status" >&2
    tmux wait-for -S "$channel"
    exit 1
fi

session=${resume_session:-$(cat /proc/sys/kernel/random/uuid)}
# Print mode kills its own subagents after 600s unless this ceiling is lifted, which silently
# truncates the code review closing /mx:implement.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0
# Where the worker records what it is doing and why it stopped. Unset outside dispatch, which is
# what makes the instruction to write it conditional rather than a path every session must know.
export DISPATCH_WORKLOG="/tmp/$channel.log"
# Created here, never truncated: a resume keeps the earlier run's lines, and a file that
# exists but is empty says the worker wrote nothing, where a missing one would leave the
# orchestrator unable to tell that from a worklog it never got told about.
touch "$DISPATCH_WORKLOG"

# The user CLAUDE.md is written for a human at a terminal: it tells its reader to ask, and
# describes a conversation this worker is not in. worker-prompt.md replaces it. On an isolated
# worker host that path holds nothing anyway, and the exclusion is inert.
settings=$(cat <<EOF
{
  "claudeMdExcludes": ["$HOME/.claude/CLAUDE.md"],
  "autoMemoryEnabled": false
}
EOF
)

common=(
    -p
    --permission-mode "$permission_mode"
    --model "$model"
    --settings "$settings"
    --append-system-prompt "$(cat "$prompt_file")"
)

# claude -p already retries a transient API error internally (~13 requests over ~13 min) before
# exiting nonzero, so these attempts are for what survives that: a crashed run, a dropped stream.
max_attempts=3
for attempt in $(seq 1 $max_attempts); do
    if [ "$attempt" -gt 1 ]; then
        claude "${common[@]}" --resume "$session" continue
    elif [ -n "$resume_session" ]; then
        claude "${common[@]}" --resume "$session" "$(cat "$message")"
    else
        claude "${common[@]}" --session-id "$session" < "$message"
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
