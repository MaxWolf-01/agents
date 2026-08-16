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
2. **The feature branch is the integration branch.** Check it out in the main checkout and hold it: ticket branches cut from it and merge back into it; main sees the feature only as one squashed PR when the spec ships.
3. **Pick the worker host.** Workers belong on a machine that stays awake — a laptop that suspends kills every worker on it, mid-ticket. `$MX_WORKER_HOST` names that machine where the environment sets one; confirm it with the user, reachability included (`ssh -o ConnectTimeout=3 <host> true`), and run workers here when it doesn't. A remote host needs four things, checked once: `claude` authenticated there, the `mx` plugin installed, the repo's bare clone and its remote in place (Mechanics), and the project's setup target green there. Anything missing → name it and run local. The answer rides on `dashboard.py --worker-host` from the first render on.
4. Run the tick loop under `/loop` with no interval (self-paced). Worker exits drive the ticks, not a fixed cadence (step 5).

## The tick

### 1. Integrate what landed

Open the tick with the **state probe** (Mechanics): it decides who exited.

For each worker that has exited, bring its ticket branch into your checkout — a local worker shares your `.git` and is already there; a remote one needs `git fetch <host> ticket/<NN>-<slug>:ticket/<NN>-<slug>` — then read the ticket's frontmatter **from that branch**: the `done` flip lands on the ticket branch, so your feature-branch checkout still shows `claimed` until the merge:

- **Not `done`** → the worker stopped early. Diagnose from its scrollback. A permission denial or a spent usage limit is a first-class resumable event: clear the blocker — add the allowlist entry it needed, wait out the reset — and resume with "continue".
- **`done`** → the flip alone proves nothing. Merge the ticket branch into the feature branch and run the project's verification there:
  - Clean merge, green → the ticket has **landed**: keep `status: done`, remove its worktree, kill its session — and **announce it to the user**: the ticket is demoable now (tracer bullet), so name what works and how to exercise it, straight from the ticket's "What to build" and acceptance criteria. QA runs per landed slice, concurrent with the remaining waves.
  - Conflict, or red after merge → abort the merge and send the conflict to the most-informed agent: resume the worker with "the feature branch moved — rebase onto it, resolve, re-verify, flip done again". Ticket branches are private; rebasing them is safe.
- **Session unrecoverable** (wedged, context-exhausted, gone) → no special machinery: reset the ticket to `open`, delete its worktree and branch — ticket + spec carry everything a fresh worker needs, by construction.

Where a ticket's done-check is human (UI verification), "green" means whatever automated checks exist; the human pass happens in the QA lane below.

**Punts get filed, never buried.** When a worker's closing comment punts a cross-cutting concern, defers to a ticket that hasn't started, or leaves an `Assumptions` block with a taste call in it — file it: a new ticket with blocking edges, or an entry on the feature's **needs-human queue** (decisions only the user can make; entry criterion "needs the human", never "is cheap to review"). A gap noted in a comment has an audience of zero; announce punts and queue growth in every status report.

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
4. Launch the worker in its tmux session (Mechanics) with `--permission-mode auto` and the implementer model settled with the user at setup — Opus by default, Fable when the tickets warrant it (per the users directive -- heavily depends on current plan limits which you can't know and shouldn't guess), never lower; the judgment calls (wave planning, merges, verification) stay with you.

### 5. Stop or sleep

**Status is a render, not prose.** Keep chat output to a line or two per tick. The standing status view is `dashboard.py` beside this skill (`--help` for usage): `uv run <skill-dir>/dashboard.py agent/tasks/<feature>` deterministically renders tracker state — three cycleable overviews of the ticket DAG (frontier graph by default), an expandable ticket table, the needs-human queue, recent commits — to `~/Downloads` and opens the first render in the browser (the open tab then refreshes itself). Rerun after each integration, passing current `--needs-human` entries; never hand-write status prose that can go stale. An entry is `summary :: markdown detail` — the detail is what lets the human act without a chat round-trip: the decision's context and options, or the paste-ready kickoff prompt of a session only they can start (HITL prototypes).

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
- **Worktree**: local — `git worktree add ../<repo>-<NN>-<slug> -b ticket/<NN>-<slug>`, run from the feature-branch checkout; worktrees live as its siblings, one branch per worktree, the checkout itself holding the feature branch. Remote — `git push <host> <feature-branch>` so the tip exists there, then `ssh <host> git -C repos/dispatch/<repo>.git worktree add ../<repo>-<NN>-<slug> -b ticket/<NN>-<slug> <feature-branch>`.
- **Spawn**: write the worker prompt to `/tmp/dispatch-<feature>-<NN>.md` (multi-line text never survives quoting through send-keys — pass it via stdin), `scp` it to the worker host when remote, then create the session with a shell so it survives worker exit and send the command, trailed by a signal on a channel named for the session:
  ```
  tmux new-session -d -s dispatch-<feature>-<NN> -c <worktree-path>
  tmux send-keys -t dispatch-<feature>-<NN> -l 'CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 claude -p --permission-mode auto --model <implementer> < /tmp/dispatch-<feature>-<NN>.md; tmux wait-for -S dispatch-<feature>-<NN>'
  tmux send-keys -t dispatch-<feature>-<NN> Enter
  ```
  Print mode kills its own subagents after 600s unless that ceiling is lifted with `=0`, which silently truncates the code review closing `/mx:implement` — every worker runs one, so every spawn and resume carries the variable.
- **Watcher**: right after spawning, arm one — a `run_in_background` Bash call of `tmux wait-for dispatch-<feature>-<NN>`, which blocks until that trailing signal fires. Background tasks are harness-tracked, so the watcher's own exit re-invokes you seconds after the worker finishes; you never poll for exits. A signal that fires with no waiter armed is remembered, so arming is race-free, and each worker run (including each resume) needs its own watcher. It exits with the worker; nothing to clean up.
  A remote watcher rides its ssh connection and dies with it: a suspended laptop leaves the far-end `tmux wait-for` orphaned, and the signal it eventually catches is delivered to nobody and remembered for nobody. Arm it with `-o ServerAliveInterval=15 -o ServerAliveCountMax=2` so a dead connection collapses in ~30s, and re-arm whenever the probe says the worker is still running.
- **State probe**: `tmux list-panes -a -F '#{session_name}:#{pane_current_command}'` names every session and what it is running; a shell name means that worker has exited. One call covers the whole wave, and it is the sole authority on who is done — a watcher only decides how fast you hear about it. The format string stays space-free so it survives an unquoted `ssh <host> …`.
- **Resume**: same send-keys shape with `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 claude -p --continue "<guidance>"; tmux wait-for -S dispatch-<feature>-<NN>` — the worktree cwd locates the worker's conversation — then arm a fresh watcher.
  `--continue` restores that whole conversation, so the worker holds its own commits, edits, and stopping point in far more detail than your reading of its scrollback gives you — and it can read anything in the repo, the feature branch included, for itself. What it lacks is a reason to look. So guidance is an instruction to act on something that shifted while it was stopped ("the feature branch moved — rebase onto it"), and `"continue"` is the entire message whenever nothing did. Recapping the worker's own state to it overwrites better knowledge with worse.
- **Observe**: `tmux capture-pane -p -J -t <session> -S -100`; the human can attach any time — `tmux attach -t <session>`, or `ssh <host> -t tmux attach -t <session>`.
- **Cleanup after landing**: `git worktree remove <path>`, `git branch -d ticket/<NN>-<slug>`, `tmux kill-session -t <session>` — on the worker host, plus the ticket branch you fetched into your own checkout.
