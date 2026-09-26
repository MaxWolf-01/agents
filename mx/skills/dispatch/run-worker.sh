#!/usr/bin/env bash
# Run one dispatch worker in this pane, retrying transient failures, then leave a status line.
# Usage: run-worker.sh <message-file> <slug> <model> <run> [session-id]
#   message-file  the ticket message, or resume guidance; sent on the first attempt only
#   slug          the ticket this worker holds: its report is agent/show/<slug>/report.md,
#                 committed in the agent repo this pane's worktree holds at `agent`
#   run           id of this run, unique; names <run>.{status,log} beside this script
#   session-id    resume this conversation instead of starting a new one
# TERM (from `dispatch-ctl stop`) ends the run: the status line then reads `exit=stopped`.
# Env:
#   DISPATCH_PERMISSION_MODE  claude --permission-mode for every attempt; `auto` unless the
#                             worker host isolates workers itself (then `bypassPermissions`)
set -u

message=$1
slug=$2
model=$3
run_id=$4
resume_session=${5:-}
permission_mode=${DISPATCH_PERMISSION_MODE:-auto}

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
prompt_file=$here/worker-prompt.md
if [ ! -f "$prompt_file" ]; then
    # Without it the worker would run on no instructions at all, and silently.
    printf 'attempts=0 exit=1 report=no session=- error=%s\n' \
        "no worker-prompt.md beside run-worker.sh" | tee "$here/$run_id.status" >&2
    exit 1
fi

# By id, never --continue: --continue means the newest conversation in this
# directory, which stops being this worker's the moment anything else runs
# claude here (someone attaching to try something).
session=${resume_session:-$(cat /proc/sys/kernel/random/uuid)}
# Print mode kills its own subagents after 600s unless this ceiling is lifted, which silently
# truncates the code review that closes a worker's contract.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0
# Where the worker records what it is doing and why it stopped. Unset outside dispatch, which is
# what makes the instruction to write it conditional rather than a path every session must know.
export DISPATCH_WORKLOG="$here/$run_id.log"
# What the worker has to say about the ticket: its closing comment and the questions its build
# raised, committed in the agent repo, which is a repo of its own at
# `agent` inside this worktree. The orchestrator fetches that branch and imports the report into
# the ticket; this round's report being committed is what says the worker finished.
#
# This round's, not any: a resumed round starts with the round before it already committed there,
# so what the run is measured against is the blob that was there when it started. A crash before
# the worker writes anything then reads as the unfinished run it is.
was_reported=$(git -C agent rev-parse -q --verify "HEAD:show/$slug/report.md" 2> /dev/null)
reported() { [ "$(git -C agent rev-parse -q --verify "HEAD:show/$slug/report.md" 2> /dev/null)" != "$was_reported" ]; }
# The models this round's turns of the session transcript answered in, comma-separated: <model> is
# an alias the host's claude resolves, so what ran is read off the run, not the command line. `-`
# is a round no model answered, `?` one whose transcript or `jq` is missing. This round's, as with
# the report: a resumed session's transcript opens with the rounds before it. `<synthetic>` marks
# messages claude wrote itself (an API error).
transcript() { cat "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/projects/*/"$session".jsonl 2> /dev/null; }
transcript_before=$(transcript | wc -l)
models() {
    local found
    command -v jq > /dev/null && transcript > /dev/null || { echo '?'; return; }
    found=$(transcript | tail -n "+$((transcript_before + 1))" |
        jq -r 'select(.type == "assistant") | .message.model // empty' |
        grep -vx '<synthetic>' | sort -u | paste -sd,)
    echo "${found:--}"
}
# Opened with one line from the runner, so a log holding only that line says the worker wrote
# nothing after starting, where a missing file would say it was never told about the log.
claude_version=$(claude --version 2> /dev/null | cut -d' ' -f1)
printf '%s runner: started %s on %s with claude %s (%s)\n' "$(date -u +%FT%TZ)" "$slug" "$model" \
    "${claude_version:-?}" "$run_id" >> "$DISPATCH_WORKLOG"
# Said once, here: without that repo the worker has nowhere to commit a report, so every attempt
# would end in `report=no` with nothing saying why.
git -C agent rev-parse --git-dir > /dev/null 2>&1 ||
    printf '%s runner: no agent repo at %s/agent, so no report of this run can be committed\n' \
        "$(date -u +%FT%TZ)" "$PWD" >> "$DISPATCH_WORKLOG"

# The user CLAUDE.md and output style are written for a human at a terminal: they tell their
# reader to ask and how to shape a reply, for a conversation this worker is not in.
# worker-prompt.md replaces them. On an isolated worker host neither is set, and both lines are
# inert.
settings=$(cat <<EOF
{
  "claudeMdExcludes": ["${CLAUDE_CONFIG_DIR:-$HOME/.claude}/CLAUDE.md"],
  "outputStyle": "default",
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

# `dispatch-ctl stop` sends TERM to this process group: claude dies with it and returns, then
# this runs, and the loop below ends the run instead of retrying it. The status line says
# `exit=stopped` and carries the session id, which is what a later resume needs.
stopped=
trap 'stopped=1' TERM

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
    [ -n "$stopped" ] && break
    [ "$rc" -eq 0 ] && break
    # The report is the worker's finished signal, so a crash after it is a crash with the work done.
    reported && break
    [ "$attempt" -eq "$max_attempts" ] && break

    backoff=$((attempt * 30))
    echo "run-worker: attempt $attempt exited $rc (no report yet); retrying in ${backoff}s"
    sleep "$backoff"
    # A TERM that lands here ends the sleep, and must end the run too.
    [ -n "$stopped" ] && break
done

[ -n "$stopped" ] && rc=stopped
# Last act: the orchestrator's wait returns on this file, and reads off it whether the worker left
# a report to import.
printf 'attempts=%s exit=%s report=%s session=%s models=%s\n' \
    "$attempt" "$rc" "$(reported && echo yes || echo no)" "$session" "$(models)" > "$here/$run_id.status"
