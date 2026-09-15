#!/usr/bin/env bash
# The host chosen per spawn, driven end to end on one machine: two tickets of a
# feature and one standalone ticket, each spawning on the host named at that
# spawn, each later command following the ticket to it, and a host staged again
# once the branch's worker prompt has moved past the copy it holds.
#
# Usage: bash demo.sh [work-dir]
#
# Everything it makes is inside the work dir, plus the scratch dirs a spawn puts
# under ~/.local/state/dispatch (named after the toy repo, removed at the end).
# `claude` is stood in for by a stub runner, the DISPATCH_RUNNER seam: it makes
# one commit, flips the ticket to done and writes the status line a real worker's
# runner writes, so what runs here is dispatch and dispatch-ctl themselves.
set -eu

dispatch_skill=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../mx/skills/dispatch" && pwd)
work=${1:-$(mktemp -d /tmp/host-per-spawn.XXXX)}
skill=$work/skill
dispatch="bash $skill/dispatch"

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
# Each step's claim, as something that can fail: under `set -e` a false inside an
# `&&` list is exempt from errexit, so a claim written that way never fails the run.
ok() { printf '   \033[32mok\033[0m %s\n' "$1"; }
not() { ! "$@"; }
check() { # <claim> <command...>
    claim=$1; shift
    "$@" || { printf '   \033[31mFAIL\033[0m %s\n' "$claim" >&2; exit 1; }
    ok "$claim"
}

step "the plugin's dispatch, with a stub in place of the harness, in $skill"
mkdir -p "$skill"
cp "$dispatch_skill"/{dispatch,dispatch-ctl,worker-prompt.md} "$skill/"
cat > "$skill/run-worker.sh" <<'STUB'
#!/usr/bin/env bash
# Stands in for run-worker.sh: no harness, one commit, and the same
# log-then-status contract the real runner owes dispatch-ctl.
set -u
message=$1 ticket=$2 model=$3 run_id=$4
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
printf '%s stub: started %s on %s (%s)\n' "$(date -u +%FT%TZ)" "$ticket" "$model" "$run_id" >> "$here/$run_id.log"
printf 'built by %s\n' "$run_id" >> built.txt
sed -i '0,/^status:/s/^status:.*/status: done/' "$ticket"
git add -A
git -c user.email=stub@toy -c user.name=stub commit -q -m "stub: $(basename "$ticket")"
printf '%s stub: committed, %s is done\n' "$(date -u +%FT%TZ)" "$ticket" >> "$here/$run_id.log"
printf 'attempts=1 exit=0 status=done session=stub-%s\n' "$run_id" > "$here/$run_id.status"
STUB

step "a toy repo: one feature of three tickets, one standalone ticket"
mkdir -p "$work/lamp/agent/tickets/lamp-ui"
cd "$work/lamp"
git init -q -b main .
git config user.email toy@toy
git config user.name toy
printf -- '---\nstatus: confirmed\n---\n\n# Lamp UI\n' > agent/tickets/lamp-ui/spec.md
for t in 01-warm-preset 02-cool-preset 03-usage-line; do
    printf -- '---\nstatus: open\n---\n\n# %s\n' "$t" > "agent/tickets/lamp-ui/$t.md"
done
printf -- '---\nstatus: open\n---\n\n# Tidy the readme\n' > agent/tickets/tidy-readme.md
git add -A
git commit -q -m "toy tracker"
git worktree add -q "$work/lamp-lamp-ui" -b lamp-ui

spawn() { # <ticket> <host> [dispatch ctl options...]
    ticket=$1 host=$2; shift 2
    $dispatch claim "$ticket" > /dev/null
    dir=agent/tickets/$(git branch --show-current)
    [ -d "$dir" ] || dir=agent/tickets
    echo "Work the ticket at $dir/$ticket.md." | $dispatch prompt "$ticket"
    $dispatch ctl --host "$host" "$@" spawn "$ticket" sonnet
    $dispatch wait "$ticket"
}

cd "$work/lamp-lamp-ui"
step "01 on local: the first spawn on a host stages it and pushes what it cuts from"
spawn 01-warm-preset local --setup-cmd true

step "02 on local: staged already, so the spawn is the spawn"
spawn 02-cool-preset local > "$work/spawn-02.log" 2>&1
cat "$work/spawn-02.log"
# The ticket message is copied on every spawn; the scripts and `init` are what a
# host already staged does not pay again.
check "no copy of the scripts, no init" not grep -qE \
    '^\+ ((cp|scp).*(dispatch-ctl|run-worker\.sh|worker-prompt\.md)|bash .*dispatch-ctl init)' "$work/spawn-02.log"

step "the branch's worker prompt moves on; 03 finds an older copy staged and stages again"
staged=$HOME/.local/state/dispatch/lamp-lamp-ui
before=$(stat -c %i "$staged/run-worker.sh")
printf '\nA clause the branch added after this host was staged.\n' >> "$skill/worker-prompt.md"
spawn 03-usage-line local
check "the host holds the branch's prompt, byte for byte" diff -q "$skill/worker-prompt.md" "$staged/worker-prompt.md"
# A worker still running reads its runner by name: a re-stage that wrote through
# those bytes would make its shell resume at its old offset in the new file.
check "the re-staged runner is a new file, not the old one rewritten" \
    [ "$before" != "$(stat -c %i "$staged/run-worker.sh")" ]

step "each run recorded its host, under the common git dir"
cat "$work/lamp/.git/dispatch/runs"

step "probe: every host this branch has run on, each line behind its host"
$dispatch ctl probe

step "fetch and cleanup follow each ticket to its own host"
for t in 01-warm-preset 02-cool-preset 03-usage-line; do
    $dispatch fetch "$t"
    $dispatch ctl cleanup "$t"
done
git -C "$work/lamp" branch --list 'ticket/*'
check "a cleaned-up run is forgotten, so nothing follows a ticket to a host it has left" \
    not grep -q 'lamp-ui' "$work/lamp/.git/dispatch/runs"

step "a standalone ticket dispatches from the integration branch, into its own scratch dir"
cd "$work/lamp"
spawn tidy-readme local --setup-cmd true
cat "$work/lamp/.git/dispatch/runs"
ls -d "$HOME/.local/state/dispatch/lamp-lamp-ui" "$HOME/.local/state/dispatch/lamp-main"
$dispatch fetch tidy-readme
check "the standalone ticket was built on its own branch" \
    git -C "$work/lamp" merge-base --is-ancestor main ticket/main/tidy-readme
$dispatch ctl cleanup tidy-readme

step "a ticket recorded on another machine: the command goes there, and only there"
printf 'main\t04\tagent@nowhere.invalid\n' >> "$work/lamp/.git/dispatch/runs"
timeout 30 $dispatch ctl log 04 || echo "(no such machine, which is the point: it was addressed, not guessed)"

step "done; removing the scratch dirs this demo made"
rm -rf "$HOME/.local/state/dispatch/lamp-lamp-ui" "$HOME/.local/state/dispatch/lamp-main"
echo "the toy repo is still at $work"
