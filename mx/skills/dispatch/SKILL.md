---
name: dispatch
description: "Work a feature's tickets, or a standalone ticket: one orchestrator hands each frontier ticket to a worker agent in its own worktree, one at a time or in parallel waves, and integrates them on the feature branch until the feature ships. Use whenever a feature has tickets to work, whenever a standalone ticket is filed and its build starts, when the user says \"dispatch\", or when another skill routes ticketed work here."
---

# Dispatch

You are the **single orchestrator** of one feature's ticket DAG: compute the frontier, fan a **wave** of workers out, integrate tickets as they **land**, repeat until no open tickets remain. One worker works one ticket; dispatch orchestrates N workers. You are the sole claim-writer, the only holder of the feature branch, and the only judge of done.

Dispatch runs downstream of `/mx:to-tickets` and is the one way tickets are worked, at any size: every ticket of a feature, and every standalone ticket, goes to a worker. The `blocked-by` DAG is what makes independence explicit and human-approved.

With a wave size of one the same loop runs **serially**, the common case: the orchestrator role (frontier bookkeeping, the pre-merge read, integration, status, QA hand-offs) is what a two-ticket feature gets from dispatch, and serial is the right mode for surface-heavy waves (see the coherence test below).

**A standalone ticket** (`agent/tickets/<slug>.md`, no spec, `/mx:tracker`) is dispatched by the session that filed it, as the feature case with two substitutions: the repo's integration branch stands in for the feature branch, and the tracker root for the feature directory. Everything below then reads unchanged, and the scripts make the same substitution from the branch you run them on.

Two scripts beside this skill carry the mechanics, and each one's `--help` is its reference. `dispatch` runs here, on the branch the ticket branches cut from, and is the one command you type for the worker host: `dispatch ctl <args>` runs `dispatch-ctl` there (this machine or one over ssh, as `setup` recorded), which owns the ticket worktrees, branches, sessions and run state on the host. History stays here: commits, merges, pushes and fetches are yours. `run-worker.sh` is the in-pane runner and the only file that names a harness; a different one (`codex exec`, a container) is a sibling runner passed via `DISPATCH_RUNNER`.

## Setup (once)

1. Fetch the spec and every ticket per `/mx:tracker`; a standalone ticket is the whole brief and has no spec.
2. **The feature branch is the feature's integration branch, held in its own worktree.** Cut both from the repo's integration branch (`git worktree add ../<repo>-<feature> -b <feature>`); the checkout you were invoked in never switches branches. Ticket branches cut from the feature branch and merge back into it; the repo's integration branch sees the feature only as one `--no-ff` merge when the spec ships. A standalone ticket has neither branch nor worktree to cut: you dispatch it from the checkout you are in, on the integration branch its ticket branch cuts from and merges back into at the ruling (tick step 1).
3. **One orchestrator per feature, and check the neighbours.** Other orchestrators may run concurrently on other features. Before the first wave, scan `agent/tickets/` for other features' open and claimed tickets. A cross-feature `blocked-by` edge touching this feature is a hard serialize signal: mechanical, grep for qualified references. Beyond that, judge: where another feature's design space or file surface overlaps this one's, warn the user and let them decide whether to serialize; small merge conflicts at integration are fine, a shared design space is not (that's one feature wearing two names). Sessions dispatching standalone tickets are neighbours of the same kind, each claiming its own on the integration branch, where a collision is an ordinary one-line conflict.
4. **Pick the worker host.** Workers belong on a machine that stays awake; a laptop that suspends kills every worker on it. `worker-hosts` lists the candidates with their live state, and `worker-hosts <user@host>` prints one's capability record (its toolchain, and what it cannot do at all); the machine you are on is a candidate too, and where workers run when nothing else is reachable. Report the list and the chosen host's limits to the user, and plan around them: a ticket needing a capability the host lacks belongs on a local wave, not in a worker's blocker. `isolated: true` in the record means the host is itself the boundary around a worker: spawn there with `DISPATCH_PERMISSION_MODE=bypassPermissions`. No record, no claims: default permission mode, and no capability assumed that you haven't verified.
5. `dispatch setup <host> <repo> [setup-command]` the first time the repo is dispatched. The host, the bare repo there and the setup command are recorded per repo and reused, so every later `dispatch setup` takes no arguments: it stages this branch's scratch dir on the recorded host, once per feature branch, and once per repo for standalone tickets, which all share the integration branch's. A remote host needs `claude` authenticated there with the `mx` plugin installed; anything missing → name it and run local.
6. Run the tick loop under `/loop` with no interval (self-paced). Worker exits drive the ticks, not a fixed cadence (tick step 5). A standalone ticket's loop is one ticket wide.

## The tick

### 1. Integrate what landed

Open the tick with `dispatch ctl probe`: it decides who exited.

For each worker that has exited, `dispatch fetch <NN-slug>` brings its ticket branch here; then read the ticket's frontmatter **from that branch**: the `done` flip lands on the ticket branch, so your feature-branch checkout still shows `claimed` until the merge:

- **Not `done`** → the worker stopped early, its in-pane retries already spent. `dispatch ctl log <NN-slug>` shows how it ended and why, in the worker's own words: the chunk it was on, and the line it wrote on the way out. Scrollback is the fallback when that log is silent (Observe, below); where neither explains it, report the cause as unknown rather than guessing one. A permission denial or a spent usage limit is a first-class resumable event: clear the blocker (add the allowlist entry it needed, wait out the reset) and resume.
- **`done`** → the flip alone proves nothing. Read the ticket branch's diff against the ticket and the spec first: you hold the whole feature where the worker held one ticket, so a detail its brief missed is yours to catch; what you find goes back to the worker as guidance on resume, or becomes a proposed ticket (`/mx:tracker`). Two findings in that read are not judgement calls. A change under the project's properties directory (`tests/properties/`), in any ticket but the one that builds them, goes back to the worker unmerged, since a slice that edits a property passes by weakening what the property was there to hold; the one edit that merges is the deletion of the expected failures naming this ticket (`/mx:testing`), and a diff that is anything beyond those deletions goes back whole. And an expected failure in the ticket branch's tree that still names this ticket goes back the same way, whatever the suite says, since the slice has not made its property hold: grep the properties directory for the ticket's number, because one the worker never touched is absent from its diff. Then merge the ticket branch into the feature branch with `--no-ff` and run the project's verification there:
  - **Standalone and still `proposed`** → its branch stays unmerged: with no feature branch to hold the build, the ticket branch is the container the user rules on. The worker's own verification stands while it sits there, and an integration branch that moved since the claim goes back to the worker to rebase onto, as a conflict would. `dispatch review <slug>` renders its page from the unmerged branch; queue the ruling (step 5) and stop there. The ruling lands it: **accept** → merge `--no-ff`, re-verify, `dispatch review <slug>` again for the range, `dispatch ctl cleanup <slug>`; **reject** → `git rm` the ticket and `dispatch ctl cleanup <slug>`, reason in the commit (`/mx:tracker`).
  - Clean merge, green → the ticket has **landed**: keep `status: done`, `dispatch review <NN-slug>` (it needs the ticket branch, so it runs before anything deletes one), then `dispatch ctl cleanup <NN-slug>` and `git branch -d` the ticket branch here, and **announce it to the user**: relay the worker's closing comment as it stands, and open the demo it names beside the review page. QA runs per landed slice, concurrent with the remaining waves.
  - Conflict, or red after merge → abort the merge and send the conflict to the most-informed agent: resume the worker with "the feature branch moved: rebase onto it, resolve, re-verify, flip done again". Ticket branches are private; rebasing them is safe.
- **Session unrecoverable** (`gone` in the probe, wedged, context-exhausted) → no special machinery: reset the ticket to `open` and `dispatch ctl cleanup <NN-slug>`; ticket + spec carry everything a fresh worker needs, by construction.

Where a ticket's done-check is human (UI verification), "green" means whatever automated checks exist; the human pass happens in the QA lane below.

**Punts get filed, never buried.** A worker's closing comment punts a cross-cutting concern, defers to a ticket that hasn't started, names friction it hit (a tooling gap, a missing feedback loop, a slow suite), or leaves an `Assumptions` block with a taste call in it. Every such line is yours to sort, and the sort has four outcomes: fixable now → fix it between waves, in a commit naming what it answers; action-shaped but not now → a **proposed ticket** (`/mx:tracker` says what it carries), with blocking edges where a ticket waits on it, and dispatched in this loop like any other ticket; a question only the user can answer → an entry on the **needs-human queue** (entry criterion "needs the human", never "is cheap to review"); nothing statable → left, and named as left in the debrief (step 5). A landed proposal's **ruling** is the user's, and the queue is where it waits: one entry per landed proposal, naming the ticket and its review page, is what the debrief counts and what an orchestrator that restarts reads. Speculation goes one level deep: a proposal cut from the build of a proposal whose ruling is still on the queue is filed and left unclaimed, its provenance line naming that proposal, so any orchestrator reads the hold from the ticket file. What the depth counts is an agent's own reading; a breakdown's slices are `proposed` too (`/mx:to-tickets`) and a proposal cut from one of those builds is at the first level, since the design under it is the user's. Friction with the workflow itself (a skill that misled, a dispatch script that broke) is a proposed ticket like any other, its body saying the fix lives in the plugin. A gap noted in a comment has an audience of zero; announce proposals and queue growth in every status report.

The tick's first half is complete when every exited worker is landed, resumed, or reset.

### 2. Re-evaluate the frontier

Re-read the ticket files: the frontier is unclaimed + unblocked + open or proposed (`/mx:tracker`), minus the proposals held for a ruling (step 1). A decision ticket on it (one carrying a `type`; a build ticket has none, per `/mx:tracker`) is never a worker's, and `spawn` refuses it. `dispatch claim` it, so it leaves the frontier, and route it by the type's value: `research` → a background `/mx:research` agent, whose findings you record as the ticket's answer; the human-in-the-loop types → an entry on `needs-human.md` carrying the question. Landing tickets unblocks new ones, and the human QAs landed slices concurrently, filing findings as new tickets with blocking edges; the frontier absorbs those the same as the originals.

### 3. Plan the wave

Assess parallel-safety now, against the code as it stands: file overlap between two tickets depends on the current tree, so this judgment lives at dispatch time, not in to-tickets. Estimate which files each frontier ticket will touch; spawn together only tickets whose edits stay disjoint, and hold the rest for a later wave. When in doubt, serialize the doubtful pair.

File overlap is the mechanical test; **coherence** is the deeper one. Tickets that share one *surface* (one UI, one document, one API façade) produce locally-passing, globally-incoherent work when built in isolation, even where their files barely overlap: give a shared surface to one serial worker. Parallelism is for tickets separated by real seams. Repeated conflicts on one hub file are this warning arriving as a merge statistic: treat it as a structure signal, not a scheduling problem.

### 4. Claim and spawn

For each ticket in the wave:

1. `dispatch claim <NN-slug>`: it flips the status, commits on the feature branch (you are the sole claim-writer) and pushes, so the ticket cuts from the current tip, since a newly-unblocked ticket needs its blockers' landed code.
2. Write the ticket message (Worker contract) and hand it over: `dispatch prompt <NN-slug> < <file>`.
3. `dispatch ctl spawn <NN-slug> <model>` with the host's permission mode in the environment (setup step 4), then arm the watcher: `dispatch wait <NN-slug>` as a background task. The worker's model is explicit: Opus by default, Sonnet by your judgment for a small or trivial ticket, never Fable unless the user names it explicitly for this run, and never simply inherited from the orchestrator's own model; the judgment calls (wave planning, merges, verification) stay with you.

### 5. Stop or sleep

**Status is a render, not prose.** Keep chat output to a line or two per tick. The standing status view is the board (`/mx:tracker`, Board): `dispatch review` re-renders it after each landing, and the human's own `board` keeps the tab current in between; never hand-write status prose that can go stale.

The queue lives in the `needs-human.md` beside the tickets, `agent/tickets/<feature>/` for a feature and the tracker root for standalone ones: `worker-host:` frontmatter (setup writes it), then one `- summary :: markdown detail` bullet per pending entry, the detail continuing on indented lines when it needs more than one. The detail is what lets the human act without a chat round-trip: the decision's context and options, or the paste-ready kickoff prompt of a session only they can start (HITL prototypes). Delete an entry when it's answered; the answer lands in code or tickets, never in the file.

A standalone ticket has no feature to close out: the loop ends when it lands, or when its ruling is on the queue and its branch waits for the answer.

Frontier empty and everything landed → close the feature out, in order:

1. Run the full suite once more on the feature branch, and grep the properties directory for expected failures (`/mx:testing`): one left names a ticket that never lifted it, and goes back to that ticket's worker before anything else.
2. The **whole-feature review**: a full `/mx:code-review` of the feature branch against the repo's integration branch with the spec as the spec axis, since no slice was reviewed against the whole and that is where incoherence between them shows. It runs as one more ticket, filed `open` (the flow's own step, not a proposal) under the feature's next number, its body naming the range and the spec, then claimed and spawned like any other; its worker reviews, fixes and aggregates under the same rule as any review, and you integrate its branch as usual. That ticket on disk is the record the pass ran.
3. `make harden ARGS="--integration-branch <the repo's integration branch>"` once from the feature worktree, so the range is this feature since it forked rather than everything the integration branch is ahead of the default branch by (`/mx:testing`). **The report is yours to read, not the user's**, and every line of it takes the sort of step 1: fixable now is a survivor a test can pin or an uncovered line a test can reach; a proposed ticket is a survivor whose fix is a design change, an unmeasured change, an uncovered line that wants restructuring. Those proposals go round the loop like any other, their own proposals held one level down, and the close-out resumes at the debrief when the frontier empties again; 1 to 3 run once per feature.
4. The feature's **debrief**, as one needs-human entry, summary `debrief`, detail in three parts: the commits that fixed, the proposed tickets by number with their review pages, and what was left with its reason. That entry is what the user reads besides the diff, which already carries the proposed ticket files; the raw report stays with you, and the chat report is a pointer to the entry. The rulings land the accepted tickets and delete the rejected with their builds (`/mx:tracker`); the feature's merge commit body records them.
5. Start the feature's fuzz run on the worker host, `dispatch ctl fuzz start`, and tell the user its session name and how to attach. It runs until you or they stop it (`dispatch ctl fuzz stop`), which retiring the feature includes; so does ruling every proposed ticket (`/mx:tracker`, Retire). Then stop the loop.

Frontier empty with tickets left, every one a decision ticket, a proposal held for a ruling, or blocked on one of those → the feature waits on the human: report which questions and rulings, and stop the loop; the answers reopen it.

Otherwise the watchers are your wake signal: `dispatch wait` returns within seconds of the worker's exit, so the scheduled wakeup is a long fallback heartbeat (1200s+), never a poll. It exists for what a watcher can't catch: a worker wedged short of exiting, a human who interrupted the pane.

## Worker contract

The contract itself is [`worker-prompt.md`](worker-prompt.md), which the runner appends to every worker's system prompt. What you write is the ticket, and nothing else about the dispatch: a worker's obligations are the same whatever spawned it. A standalone ticket's path is `agent/tickets/<slug>.md`.

```
Work the ticket at agent/tickets/<feature>/<NN>-<slug>.md.
You own only this ticket and this worktree; the branch it was cut from and other tickets belong to the orchestrator.
Your final act, once the implementation is committed and verified: set `status: done` in the ticket's frontmatter and commit.
```

The `done` flip as the *last* act is the done signal you read on exit; a worker that exits without it gets resumed.

## Intervening and observing

- **Guidance**: `dispatch ctl stop <NN-slug>` when a worker needs to hear something now (the feature branch moved under it, the user changed a ruling); write the guidance with `dispatch prompt`; `dispatch ctl resume <NN-slug> <model>`; arm a watcher on it. A resume restores the worker's whole conversation, so it holds its own commits, edits and stopping point in far more detail than your reading of its scrollback gives you, and it can read anything in the repo, the feature branch included, for itself. What it lacks is a reason to look. Guidance is an instruction to act on something that shifted while it was stopped ("the feature branch moved: rebase onto it"); when nothing did, `continue` is the entire message. Recapping the worker's own state to it overwrites better knowledge with worse.
- **Observe**: `tmux capture-pane -p -J -t <session> -S -100` on the host (the probe names the session); the human attaches with `tmux attach -t <session>`, over ssh with `-t`.
- **After an orchestrator restart** (your session crashed, or a new one took over): watchers were background tasks of *your* session and died with it, while the workers kept running. `dispatch ctl probe`, then arm a watcher per `running` worker; the same two steps when a watcher fails on an unreachable host. Nothing else needs reconstructing: claims live in ticket frontmatter, work on ticket branches, runs in the host's manifest.
