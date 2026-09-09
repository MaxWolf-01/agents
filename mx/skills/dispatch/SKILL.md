---
name: dispatch
description: "Work a feature's tickets: one orchestrator hands each frontier ticket to a worker agent in its own worktree, one at a time or in parallel waves, and integrates them on the feature branch until the feature ships. Use whenever a feature has tickets to work, when the user says \"dispatch\", or when another skill routes ticketed work here."
---

# Dispatch

You are the **single orchestrator** of one feature's ticket DAG: compute the frontier, fan a **wave** of workers out, integrate tickets as they **land**, repeat until no open tickets remain. `/mx:implement` works one ticket; dispatch orchestrates N implements. You are the sole claim-writer, the only holder of the feature branch, and the only judge of done.

Dispatch runs downstream of `/mx:to-tickets` and is the one way tickets are worked, at any size: a feature with tickets is dispatched, a feature without them is built by the session that grilled it. The `blocked-by` DAG is what makes independence explicit and human-approved.

With a wave size of one the same loop runs **serially**, the common case: the orchestrator role (frontier bookkeeping, the pre-merge read, integration, status, QA hand-offs) is what a two-ticket feature gets from dispatch, and serial is the right mode for surface-heavy waves (see the coherence test below).

Two scripts beside this skill carry the mechanics, and each one's `--help` is its reference. `bash <skill-dir>/dispatch` (`dispatch` from here on) runs here, in the feature worktree, and is the one command you type for the worker host: `dispatch ctl <args>` runs `dispatch-ctl` there (this machine or one over ssh, as `setup` recorded), which owns the ticket worktrees, branches, sessions and run state on the host. History stays here: commits, merges, pushes and fetches are yours. `run-worker.sh` is the in-pane runner and the only file that names a harness; a different one (`codex exec`, a container) is a sibling runner passed via `DISPATCH_RUNNER`.

## Setup (once)

1. Fetch the spec and every ticket per `/mx:tracker`.
2. **The feature branch is the feature's integration branch, held in its own worktree.** Cut both from the repo's integration branch (`git worktree add ../<repo>-<feature> -b <feature>`); the checkout you were invoked in never switches branches. Ticket branches cut from the feature branch and merge back into it; the repo's integration branch sees the feature only as one `--no-ff` merge when the spec ships.
3. **One orchestrator per feature, and check the neighbours.** Other orchestrators may run concurrently on other features. Before the first wave, scan `agent/tickets/` for other features' open and claimed tickets. A cross-feature `blocked-by` edge touching this feature is a hard serialize signal: mechanical, grep for qualified references. Beyond that, judge: where another feature's design space or file surface overlaps this one's, warn the user and let them decide whether to serialize; small merge conflicts at integration are fine, a shared design space is not (that's one feature wearing two names).
4. **Pick the worker host.** Workers belong on a machine that stays awake; a laptop that suspends kills every worker on it. `worker-hosts` lists the candidates with their live state, and `worker-hosts <user@host>` prints one's capability record (its toolchain, and what it cannot do at all); the machine you are on is a candidate too, and where workers run when nothing else is reachable. Report the list and the chosen host's limits to the user, and plan around them: a ticket needing a capability the host lacks belongs on a local wave, not in a worker's blocker. `isolated: true` in the record means the host is itself the boundary around a worker: spawn there with `DISPATCH_PERMISSION_MODE=bypassPermissions`. No record, no claims: default permission mode, and no capability assumed that you haven't verified.
5. `dispatch setup <host> <repo> [setup-command]` from the feature worktree. A remote host needs `claude` authenticated there with the `mx` plugin installed; anything missing → name it and run local.
6. Run the tick loop under `/loop` with no interval (self-paced). Worker exits drive the ticks, not a fixed cadence (tick step 5).

## The tick

### 1. Integrate what landed

Open the tick with `dispatch ctl probe`: it decides who exited.

For each worker that has exited, `dispatch fetch <NN-slug>` brings its ticket branch here; then read the ticket's frontmatter **from that branch**: the `done` flip lands on the ticket branch, so your feature-branch checkout still shows `claimed` until the merge:

- **Not `done`** → the worker stopped early, its in-pane retries already spent. `dispatch ctl log <NN-slug>` shows how it ended and why, in the worker's own words: the chunk it was on, and the line it wrote on the way out. Scrollback is the fallback when that log is silent (Observe, below); where neither explains it, report the cause as unknown rather than guessing one. A permission denial or a spent usage limit is a first-class resumable event: clear the blocker (add the allowlist entry it needed, wait out the reset) and resume.
- **`done`** → the flip alone proves nothing. Read the ticket branch's diff against the ticket and the spec first: you hold the whole feature where the worker held one ticket, so a detail its brief missed is yours to catch; what you find goes back to the worker as guidance on resume, or becomes a ticket. One finding in that read is not a judgement call: a change under the project's properties directory (`tests/properties/`), in any ticket but the one that builds them, goes back to the worker unmerged, whatever it looks like, since a slice that edits a property passes by weakening what the property was there to hold. Then merge the ticket branch into the feature branch with `--no-ff` and run the project's verification there:
  - Clean merge, green → the ticket has **landed**: keep `status: done`, `dispatch ctl cleanup <NN-slug>`, `git branch -d` the ticket branch here, `dispatch review <NN-slug>`, and **announce it to the user**: the ticket is demoable now (tracer bullet), so name what works and how to exercise it, straight from the ticket's "What to build" and acceptance criteria. QA runs per landed slice, concurrent with the remaining waves.
  - Conflict, or red after merge → abort the merge and send the conflict to the most-informed agent: resume the worker with "the feature branch moved: rebase onto it, resolve, re-verify, flip done again". Ticket branches are private; rebasing them is safe.
- **Session unrecoverable** (`gone` in the probe, wedged, context-exhausted) → no special machinery: reset the ticket to `open` and `dispatch ctl cleanup <NN-slug>`; ticket + spec carry everything a fresh worker needs, by construction.

Where a ticket's done-check is human (UI verification), "green" means whatever automated checks exist; the human pass happens in the QA lane below.

**Punts get filed, never buried.** When a worker's closing comment punts a cross-cutting concern, defers to a ticket that hasn't started, names friction it hit (a tooling gap, a missing feedback loop, a slow suite), or leaves an `Assumptions` block with a taste call in it, that call is yours, not the worker's: fix what you can fix between waves, and for the rest, file it as a new ticket with blocking edges, or as an entry on the feature's **needs-human queue** (decisions only the user can make; entry criterion "needs the human", never "is cheap to review"). A gap noted in a comment has an audience of zero; announce punts and queue growth in every status report.

The tick's first half is complete when every exited worker is landed, resumed, or reset.

### 2. Re-evaluate the frontier

Re-read the ticket files: the frontier is open + unblocked + unclaimed (`/mx:tracker`). A decision ticket on it (one carrying a `type`; a build ticket has none, per `/mx:tracker`) is never a worker's, and `spawn` refuses it. Claim it, so it leaves the frontier, and route it by the type's value: `research` → a background `/mx:research` agent, whose findings you record as the ticket's answer; the human-in-the-loop types → an entry on `needs-human.md` carrying the question. Landing tickets unblocks new ones, and the human QAs landed slices concurrently, filing findings as new tickets with blocking edges; the frontier absorbs those the same as the originals.

### 3. Plan the wave

Assess parallel-safety now, against the code as it stands: file overlap between two tickets depends on the current tree, so this judgment lives at dispatch time, not in to-tickets. Estimate which files each frontier ticket will touch; spawn together only tickets whose edits stay disjoint, and hold the rest for a later wave. When in doubt, serialize the doubtful pair.

File overlap is the mechanical test; **coherence** is the deeper one. Tickets that share one *surface* (one UI, one document, one API façade) produce locally-passing, globally-incoherent work when built in isolation, even where their files barely overlap: give a shared surface to one serial worker. Parallelism is for tickets separated by real seams. Repeated conflicts on one hub file are this warning arriving as a merge statistic: treat it as a structure signal, not a scheduling problem.

### 4. Claim and spawn

For each ticket in the wave:

1. Set `status: claimed`, commit on the feature branch (you are the sole claim-writer), and `dispatch push`, so the ticket cuts from the current tip: a newly-unblocked ticket needs its blockers' landed code.
2. Write the worker prompt (Worker contract) and hand it over: `dispatch prompt <NN-slug> < <file>`.
3. `dispatch ctl spawn <NN-slug> <model>` with the host's permission mode in the environment (setup step 4), then arm the watcher: `dispatch wait <NN-slug>` as a background task. The worker's model is explicit: Opus by default, Sonnet by your judgment for a small or trivial ticket, never Fable unless the user names it explicitly for this run, and never simply inherited from the orchestrator's own model; the judgment calls (wave planning, merges, verification) stay with you.

### 5. Stop or sleep

**Status is a render, not prose.** Keep chat output to a line or two per tick. The standing status view is the board (`/mx:tracker`, Board): `dispatch review` re-renders it after each landing, and the watcher you started when you fetched the tickets at setup keeps it current in between; never hand-write status prose that can go stale.

The feature's queue lives in `agent/tickets/<feature>/needs-human.md`: `worker-host:` frontmatter (setup writes it), then one `- summary :: markdown detail` bullet per pending entry. The detail is what lets the human act without a chat round-trip: the decision's context and options, or the paste-ready kickoff prompt of a session only they can start (HITL prototypes). Delete an entry when it's answered; the answer lands in code or tickets, never in the file.

Frontier empty and everything landed → run the full suite once more on the feature branch, then `make harden` once from the feature worktree, whose default range is this feature since it forked (`/mx:testing`), and report to the user: the feature is PR-ready, and harden's report is theirs to read, here or at the review session. Its findings sort like any other review-session finding, into tickets or a knowing ship. Then stop the loop. Frontier empty with open tickets left, every one a decision ticket or blocked on one → the feature waits on the human: report which questions, and stop the loop; the answers reopen it.

Otherwise the watchers are your wake signal: `dispatch wait` returns within seconds of the worker's exit, so the scheduled wakeup is a long fallback heartbeat (1200s+), never a poll. It exists for what a watcher can't catch: a worker wedged short of exiting, a human who interrupted the pane.

## Worker contract

The worker prompt carries exactly this contract, concretized per ticket:

```
Load /mx:implement and work the ticket at agent/tickets/<feature>/<NN>-<slug>.md.
You own only this ticket and this worktree; the feature branch and other tickets belong to the orchestrator.
Your final act, once the implementation is committed and verified: set `status: done` in the ticket's frontmatter and commit.
```

The `done` flip as the *last* act is the done signal you read on exit; a worker that exits without it gets resumed.

## Intervening and observing

- **Guidance**: `dispatch ctl stop <NN-slug>` when a worker needs to hear something now (the feature branch moved under it, the user changed a ruling); write the guidance with `dispatch prompt`; `dispatch ctl resume <NN-slug> <model>`; arm a watcher on it. A resume restores the worker's whole conversation, so it holds its own commits, edits and stopping point in far more detail than your reading of its scrollback gives you, and it can read anything in the repo, the feature branch included, for itself. What it lacks is a reason to look. Guidance is an instruction to act on something that shifted while it was stopped ("the feature branch moved: rebase onto it"); when nothing did, `continue` is the entire message. Recapping the worker's own state to it overwrites better knowledge with worse.
- **Observe**: `tmux capture-pane -p -J -t <session> -S -100` on the host (the probe names the session); the human attaches with `tmux attach -t <session>`, over ssh with `-t`.
- **After an orchestrator restart** (your session crashed, or a new one took over): watchers were background tasks of *your* session and died with it, while the workers kept running. `dispatch ctl probe`, then arm a watcher per `running` worker; the same two steps when a watcher fails on an unreachable host. Nothing else needs reconstructing: claims live in ticket frontmatter, work on ticket branches, runs in the host's manifest.
