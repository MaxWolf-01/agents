---
name: dispatch
description: Work a feature's ticket DAG in parallel — one orchestrator fans independent frontier tickets out to parallel worker agents and integrates them on the feature branch until the feature ships. Use when a ticketed feature has independent frontier tickets, the user says "dispatch" or wants tickets worked in parallel, or when another skill routes parallel frontier work here.
---

# Dispatch

You are the **single orchestrator** of one feature's ticket DAG: compute the frontier, fan a **wave** of workers out, integrate tickets as they **land**, repeat until no open tickets remain. `/mx:implement` works one ticket; dispatch orchestrates N implements. You are the sole claim-writer, the only holder of the feature branch, and the only judge of done.

Dispatch runs downstream of `/mx:to-tickets` — the `blocked-by` DAG is what makes independence explicit and human-approved. An unticketed task with two or more independent parts routes through to-tickets first.

With a wave size of one, the same loop runs **serially** — the orchestrator role (frontier bookkeeping, integration, status, QA hand-offs) is worth keeping even without parallelism, and serial is the right mode for surface-heavy waves (see the coherence test below).

## Setup (once)

1. Fetch the spec and every ticket per `/mx:tracker`.
2. **The feature branch is the feature's integration branch, held in its own worktree** — cut both from the repo's integration branch (`git worktree add ../<repo>-<feature> -b <feature>`); the checkout you were invoked in never switches branches. Ticket branches cut from the feature branch and merge back into it; the repo's integration branch sees the feature only as one `--no-ff` merge when the spec ships.
3. **One dispatcher per feature — and check the neighbours.** Other dispatchers may run concurrently on other features. Before the first wave, scan `agent/tasks/` for other features' open and claimed tickets. A cross-feature `blocked-by` edge touching this feature is a hard serialize signal — mechanical, grep for qualified references. Beyond that, judge: where another feature's design space or file surface overlaps this one's, warn the user and let them decide whether to serialize — small merge conflicts at integration are fine, a shared design space is not (that's one feature wearing two names).
4. **Pick the worker host.** Workers belong on a machine that stays awake — a laptop that suspends kills every worker on it, mid-ticket. `$MX_WORKER_HOST` names that machine where the environment sets one; confirm it with the user, reachability included (`ssh -o ConnectTimeout=3 <host> true`), and run workers here when it doesn't. A remote host needs four things, checked once: `claude` authenticated there, the repo's bare clone and its remote in place (Mechanics), the project's setup target green there, and the `mx` plugin installed and updated — `ssh <host> claude plugin marketplace update MaxWolf-01`, then `ssh <host> claude plugin update mx@MaxWolf-01`, **once here, before the first wave**. Updating per worker races on the plugin cache; updating per wave mutates it under running workers, which load their skills lazily. One version per dispatch run. Anything missing → name it and run local. Record the answer as `worker-host:` frontmatter in the feature's `needs-human.md` — the board reads it from there.
5. **Read the host's capability record.** `ssh <host> cat HOST.md`, where the host publishes one: its toolchain, and what it cannot do at all. Report those limits to the user alongside the reachability check, and plan around them — a ticket needing a capability the host lacks belongs on a local wave, not in a worker's blocker. `isolated: true` in that record's frontmatter means the host is itself the boundary around a worker, rather than the permission classifier: spawn workers there with `--permission-mode bypassPermissions` (tick step 4). No record, no claims — default permission mode, and no capability assumed that you haven't verified.
6. Run the tick loop under `/loop` with no interval (self-paced). Worker exits drive the ticks, not a fixed cadence (tick step 5).

## The tick

### 1. Integrate what landed

Open the tick with the **state probe** (Mechanics): it decides who exited.

For each worker that has exited, bring its ticket branch into your checkout — a local worker shares your `.git` and is already there; a remote one needs `git fetch <host> ticket/<feature>/<NN>-<slug>:ticket/<feature>/<NN>-<slug>` — then read the ticket's frontmatter **from that branch**: the `done` flip lands on the ticket branch, so your feature-branch checkout still shows `claimed` until the merge:

- **Not `done`** → the worker stopped early, its in-pane retries already spent (Mechanics). `/tmp/<channel>.status` says how it ended — attempts, exit code, ticket status, session id — and `/tmp/<channel>.log` says why, in the worker's own words: the chunk it was on, and the line it wrote on the way out. Scrollback is the fallback when that log is silent; where neither explains it, report the cause as unknown rather than guessing one. A permission denial or a spent usage limit is a first-class resumable event: clear the blocker — add the allowlist entry it needed, wait out the reset — and resume.
- **`done`** → the flip alone proves nothing. Merge the ticket branch into the feature branch — capturing its merge-base first, for the review page (Mechanics) — and run the project's verification there:
  - Clean merge, green → the ticket has **landed**: keep `status: done`, remove its worktree, kill its session — then append the merged range to the ticket's `diff:` frontmatter, render its review page (Mechanics), and **announce it to the user**: the ticket is demoable now (tracer bullet), so name what works and how to exercise it, straight from the ticket's "What to build" and acceptance criteria. QA runs per landed slice, concurrent with the remaining waves.
  - Conflict, or red after merge → abort the merge and send the conflict to the most-informed agent: resume the worker with "the feature branch moved — rebase onto it, resolve, re-verify, flip done again". Ticket branches are private; rebasing them is safe.
- **Session unrecoverable** (wedged, context-exhausted, gone) → no special machinery: reset the ticket to `open`, delete its worktree and branch — ticket + spec carry everything a fresh worker needs, by construction.

Where a ticket's done-check is human (UI verification), "green" means whatever automated checks exist; the human pass happens in the QA lane below.

**Punts get filed, never buried.** When a worker's closing comment punts a cross-cutting concern, defers to a ticket that hasn't started, names friction it hit (a tooling gap, a missing feedback loop, a slow suite), or leaves an `Assumptions` block with a taste call in it — that call is yours, not the worker's: fix what you can fix between waves, and for the rest, file it — a new ticket with blocking edges, or an entry on the feature's **needs-human queue** (decisions only the user can make; entry criterion "needs the human", never "is cheap to review"). A gap noted in a comment has an audience of zero; announce punts and queue growth in every status report.

The tick's first half is complete when every exited worker is landed, resumed, or reset.

### 2. Re-evaluate the frontier

Re-read the ticket files: the frontier is open + unblocked + unclaimed (`/mx:tracker`). Landing tickets unblocks new ones — and the human QAs landed slices concurrently, filing findings as new tickets with blocking edges; the frontier absorbs those the same as the originals.

### 3. Plan the wave

Assess parallel-safety now, against the code as it stands — file overlap between two tickets depends on the current tree, so this judgment lives at dispatch time, not in to-tickets. Estimate which files each frontier ticket will touch; spawn together only tickets whose edits stay disjoint, and hold the rest for a later wave. When in doubt, serialize the doubtful pair.

File overlap is the mechanical test; **coherence** is the deeper one. Tickets that share one *surface* — one UI, one document, one API façade — produce locally-passing, globally-incoherent work when built in isolation, even where their files barely overlap: give a shared surface to one serial worker. Parallelism is for tickets separated by real seams. Repeated conflicts on one hub file are this warning arriving as a merge statistic — treat it as a structure signal, not a scheduling problem.

### 4. Claim and spawn

For each ticket in the wave:

1. Set `status: claimed` and commit on the feature branch (you are the sole claim-writer).
2. Cut its worktree + branch from the feature branch's current tip — a newly-unblocked ticket needs its blockers' landed code.
3. Run the project's setup target in the worktree — `make install`, or whatever the project documents; `nix develop -c make install` where a `flake.nix` exists. A project with no setup target gets a ticket, not an improvised venv: the target is what makes a worktree reproducible on any host, and every human on the project reads the same line.
4. Launch the worker in its tmux session (Mechanics) with the host's permission mode (setup step 5) and an explicit implementer model — Opus by default, Sonnet by your judgment for a small or trivial ticket, never Fable unless the user names it explicitly for this run, and never simply inherited from the orchestrator's own model; the judgment calls (wave planning, merges, verification) stay with you.

### 5. Stop or sleep

**Status is a render, not prose.** Keep chat output to a line or two per tick. The standing status view is the tracker board, rendered by `dashboard.py` beside this skill (`--help` for usage): `uv run <skill-dir>/dashboard.py agent/tasks` renders the whole tracker — every feature and standalone task on one page, cross-feature edges included, cycleable frontier/full/lanes views — to `~/Downloads/dispatch-dashboard/<project>.html` and opens the first render in the browser (the open tab then refreshes itself). Any agent that changes tracker state re-renders; concurrent dispatchers share the one board. Rerun after each integration; never hand-write status prose that can go stale.

The feature's queue lives in `agent/tasks/<feature>/needs-human.md`: optional `worker-host:` frontmatter, then one `- summary :: markdown detail` bullet per pending entry. The detail is what lets the human act without a chat round-trip: the decision's context and options, or the paste-ready kickoff prompt of a session only they can start (HITL prototypes). Delete an entry when it's answered — the answer lands in code or tickets, never in the file.

Frontier empty and everything landed → run the full suite once more on the feature branch, report the feature PR-ready to the user, and stop the loop.

Otherwise the watchers are your wake signal: a worker's exit re-invokes you within seconds of it happening, so the scheduled wakeup is a long fallback heartbeat (1200s+), never a poll. It exists for what a watcher can't catch — a worker wedged short of exiting, a dead watcher, a human who interrupted the pane.

## Worker contract

The worker prompt carries exactly this contract, concretized per ticket:

```
Load /mx:implement and work the ticket at agent/tasks/<feature>/<NN>-<slug>.md.
You own only this ticket and this worktree; the feature branch and other tickets belong to the orchestrator.
Your final act, once the implementation is committed and verified: set `status: done` in the ticket's frontmatter and commit.
```

The `done` flip as the *last* act is the done signal you read on exit; a worker that exits without it gets resumed.

## Mechanics

The spawn layer is deliberately thin — a tmux window running a CLI — so it stays swappable (`codex exec`, a container) without touching the rest.

Every command below runs **on the worker host**: as written when that's this machine, prefixed with `ssh <host>` when it's another. One command per ssh call, never a chain — a chained remote command that starts the tmux server inherits the connection's stdout and holds it open until the call times out.

- **Remote setup (once per repo)**: `ssh <host> git clone --bare <github-url> repos/dispatch/<repo>.git`, then here `git remote add <host> <host>:repos/dispatch/<repo>.git`. Bare on purpose — nothing is checked out there, so you can push any branch to it, and worktrees hang off it as siblings. Ticket-branch churn stays off GitHub, where branch pushes would fire CI.
- **Worktree**: local — `git worktree add ../<repo>-<feature>-<NN>-<slug> -b ticket/<feature>/<NN>-<slug>`, run from the feature-branch worktree; ticket worktrees live as its siblings, one branch per worktree. Ticket branches and worktree paths are feature-namespaced because the worker host's bare repo and the sibling directory are shared — two features' `01-setup` must not collide. Remote — `git push <host> <feature-branch>` so the tip exists there, then `ssh <host> git -C repos/dispatch/<repo>.git worktree add ../<repo>-<feature>-<NN>-<slug> -b ticket/<feature>/<NN>-<slug> <feature-branch>`.
- **Spawn**: write the worker prompt to `/tmp/dispatch-<feature>-<NN>.md` (multi-line text never survives quoting through send-keys — pass it as a file), `scp` it, `run-worker.sh` and `worker-prompt.md` (both beside this skill, and the script reads the prompt from its own directory) to `/tmp` on the worker host when remote — `<run-worker-path>` below is whichever copy the pane can reach — then create the session with a shell so it survives worker exit and send the command:
  ```
  tmux new-session -d -s dispatch-<feature>-<NN> -c <worktree-path>
  tmux send-keys -t dispatch-<feature>-<NN> -l 'DISPATCH_PERMISSION_MODE=<mode> bash <run-worker-path> /tmp/dispatch-<feature>-<NN>.md <ticket-path> <implementer> dispatch-<feature>-<NN>-<run-id>'
  tmux send-keys -t dispatch-<feature>-<NN> Enter
  ```
  `run-worker.sh` owns what happens inside the pane: it runs the worker, retries a failed run up to three times with backoff by resuming the same conversation, writes `/tmp/<channel>.status`, and only then fires the channel. `DISPATCH_PERMISSION_MODE` is the mode every attempt runs with, the script's own retries included. A transient API error costs a backoff instead of an orchestrator round-trip, so the exits you hear about are the ones that need judgment.
  `<run-id>` is anything unique to this run (`$(date +%s)`). tmux remembers a signal fired with no waiter armed, so a channel reused across runs can hand you a stale exit the instant you arm the next watcher.
  **Confirm the launch**: `tmux list-panes -t dispatch-<feature>-<NN> -F '#{pane_current_command}'` must read `claude`. A send-keys that landed in the wrong pane, or a command that died on its first line, leaves a shell sitting in the session and a watcher that waits forever.
- **Watcher**: right after spawning, arm one — a `run_in_background` Bash call of `tmux wait-for dispatch-<feature>-<NN>-<run-id>`, which blocks until `run-worker.sh` fires that channel. Background tasks are harness-tracked, so the watcher's own exit re-invokes you seconds after the worker finishes; you never poll for exits. A signal that fires with no waiter armed is remembered, so arming is race-free. Every run — spawn or resume — gets its own channel and its own watcher. It exits with the worker; nothing to clean up.
  A remote watcher rides its ssh connection and dies with it: a suspended laptop leaves the far-end `tmux wait-for` orphaned, and the signal it eventually catches is delivered to nobody and remembered for nobody. Arm it with `-o ServerAliveInterval=15 -o ServerAliveCountMax=2` so a dead connection collapses in ~30s, and re-arm whenever the probe says the worker is still running.
- **State probe**: `tmux list-panes -a -F '#{session_name}:#{pane_current_command}'` names every session and what it is running; a shell name means that worker has exited. Filter to this feature's `dispatch-<feature>-` prefix — other dispatchers' sessions share the tmux server. One call covers the whole wave, and it is the sole authority on who is done — a watcher only decides how fast you hear about it. The format string stays space-free so it survives an unquoted `ssh <host> …`.
- **Resume**: the pane already retried what was transient, so a resume you run by hand either carries guidance or restarts a worker whose attempts are spent. Write the guidance to `/tmp/dispatch-<feature>-<NN>-resume.md` and re-run the script with the session id from the status file and a fresh channel, then confirm the launch and arm a new watcher:
  ```
  tmux send-keys -t dispatch-<feature>-<NN> -l 'DISPATCH_PERMISSION_MODE=<mode> bash <run-worker-path> /tmp/dispatch-<feature>-<NN>-resume.md <ticket-path> <implementer> dispatch-<feature>-<NN>-<run-id> <session-id>'
  tmux send-keys -t dispatch-<feature>-<NN> Enter
  ```
  Resume by session id, never `--continue`: `--continue` means "the most recent conversation in this directory", which stops being the worker's the moment anything else runs `claude` in that worktree — you attaching to try something, or a retry that started fresh.
  A resume restores the worker's whole conversation, so the worker holds its own commits, edits, and stopping point in far more detail than your reading of its scrollback gives you — and it can read anything in the repo, the feature branch included, for itself. What it lacks is a reason to look. So guidance is an instruction to act on something that shifted while it was stopped ("the feature branch moved — rebase onto it"), and a file holding just `continue` is the entire message whenever nothing did. Recapping the worker's own state to it overwrites better knowledge with worse.
- **Observe**: `tmux capture-pane -p -J -t <session> -S -100`; the human can attach any time — `tmux attach -t <session>`, or `ssh <host> -t tmux attach -t <session>`.
- **After an orchestrator restart** (your session crashed, or a new one took over): watchers are background tasks of *your* session and die with it, while the workers keep running unobserved. Run the state probe; for each session still running `claude`, read the channel off its launch command (`tmux capture-pane -p -t <session> -S -200 | grep run-worker`) and arm a watcher on that channel — a new channel would never fire. Sessions already back at a shell have their exits waiting in `/tmp/dispatch-<feature>-<NN>-*.status`. Nothing else needs reconstructing: claims live in ticket frontmatter, work on ticket branches.
- **Review page**: the human's diff surface for a landed ticket, linked from the board automatically. Append `<merge-base-sha>..<ticket-tip-sha>` to the ticket's `diff:` frontmatter first — SHAs, because cleanup deletes the branch while its commits survive. Read that merge-base **before** merging: afterwards the ticket tip is an ancestor of the feature branch, so `git merge-base` returns the tip itself and the range comes out empty. Then render every range the ticket lists in one page:
  ```
  diffview '<repo>@<range>' ['<repo>@<range>' …] --notes agent/diffviews/<feature>/<NN>-<slug>.notes.json -o agent/diffviews/<feature>/<NN>-<slug>.html
  ```
  The notes file is a pure projection of the ticket — two scans, no state of its own: assumption bullets become `notes` (`A3` → `"id": 3`), `Addressed:` lines become `resolved`. Rewrite it whole on every render; the user's own comments and overrides live in a state file beside the page that rendering never touches. `agent/diffviews/` is gitignored, so render here, never on the worker host.
- **Cleanup after landing**: `git worktree remove <path>`, `git branch -d ticket/<feature>/<NN>-<slug>`, `tmux kill-session -t <session>` — on the worker host, plus the ticket branch you fetched into your own checkout.
