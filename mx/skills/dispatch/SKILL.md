---
name: dispatch
description: "Work a feature's ticket DAG in parallel: one orchestrator fans independent frontier tickets out to parallel worker agents and integrates them on the feature branch until the feature ships. Use when a ticketed feature has independent frontier tickets, the user says \"dispatch\" or wants tickets worked in parallel, or when another skill routes parallel frontier work here."
---

# Dispatch

You are the **single orchestrator** of one feature's ticket DAG: compute the frontier, fan a **wave** of workers out, integrate tickets as they **land**, repeat until no open tickets remain. `/mx:implement` works one ticket; dispatch orchestrates N implements. You are the sole claim-writer, the only holder of the feature branch, and the only judge of done.

Dispatch runs downstream of `/mx:to-tickets`: the `blocked-by` DAG is what makes independence explicit and human-approved. An unticketed task with two or more independent parts routes through to-tickets first.

With a wave size of one, the same loop runs **serially**: the orchestrator role (frontier bookkeeping, integration, status, QA hand-offs) is worth keeping even without parallelism, and serial is the right mode for surface-heavy waves (see the coherence test below).

## Setup (once)

1. Fetch the spec and every ticket per `/mx:tracker`.
2. **The feature branch is the feature's integration branch, held in its own worktree.** Cut both from the repo's integration branch (`git worktree add ../<repo>-<feature> -b <feature>`); the checkout you were invoked in never switches branches. Ticket branches cut from the feature branch and merge back into it; the repo's integration branch sees the feature only as one `--no-ff` merge when the spec ships.
3. **One dispatcher per feature, and check the neighbours.** Other dispatchers may run concurrently on other features. Before the first wave, scan `agent/tasks/` for other features' open and claimed tickets. A cross-feature `blocked-by` edge touching this feature is a hard serialize signal: mechanical, grep for qualified references. Beyond that, judge: where another feature's design space or file surface overlaps this one's, warn the user and let them decide whether to serialize; small merge conflicts at integration are fine, a shared design space is not (that's one feature wearing two names).
4. **Pick the worker host.** Workers belong on a machine that stays awake; a laptop that suspends kills every worker on it, mid-ticket. `worker-hosts` lists the candidates with their state where the environment provides such a command. Report that list to the user and pick one; the machine you are on may be among them, and is where workers run when nothing else is reachable. A remote host needs `claude` authenticated there with the `mx` plugin installed; `dispatch setup` (Mechanics) does the rest once per feature and prints the plugin version this run's workers start on. Anything missing → name it and run local. Record the answer as `worker-host:` frontmatter in the feature's `needs-human.md`; the board reads it from there.
5. **Read the host's capability record.** `worker-hosts <name>`: the host publishes its toolchain and what it cannot do at all, and the command falls back to a checked-in copy when the host is down. Report those limits to the user alongside the reachability check, and plan around them: a ticket needing a capability the host lacks belongs on a local wave, not in a worker's blocker. `isolated: true` in that record's frontmatter means the host is itself the boundary around a worker, rather than the permission classifier: spawn workers there with `--permission-mode bypassPermissions` (tick step 4). No record, no claims: default permission mode, and no capability assumed that you haven't verified.
6. Run the tick loop under `/loop` with no interval (self-paced). Worker exits drive the ticks, not a fixed cadence (tick step 5).

## The tick

### 1. Integrate what landed

Open the tick with the **state probe** (Mechanics): it decides who exited.

For each worker that has exited, bring its ticket branch into your checkout (a local worker shares your `.git` and is already there; a remote one needs `git fetch <remote> ticket/<feature>/<NN>-<slug>:ticket/<feature>/<NN>-<slug>`, on the remote `dispatch setup` printed), then read the ticket's frontmatter **from that branch**: the `done` flip lands on the ticket branch, so your feature-branch checkout still shows `claimed` until the merge:

- **Not `done`** → the worker stopped early, its in-pane retries already spent (Mechanics). `dispatch-ctl log <NN>-<slug>` shows how it ended (attempts, exit code, ticket status, session id) and why, in the worker's own words: the chunk it was on, and the line it wrote on the way out. Scrollback is the fallback when that log is silent; where neither explains it, report the cause as unknown rather than guessing one. A permission denial or a spent usage limit is a first-class resumable event: clear the blocker (add the allowlist entry it needed, wait out the reset) and resume.
- **`done`** → the flip alone proves nothing. Merge the ticket branch into the feature branch with `--no-ff` and run the project's verification there:
  - Clean merge, green → the ticket has **landed**: keep `status: done`, `dispatch-ctl cleanup <NN>-<slug>` on the host, `dispatch review <NN>-<slug>` here (Mechanics), and **announce it to the user**: the ticket is demoable now (tracer bullet), so name what works and how to exercise it, straight from the ticket's "What to build" and acceptance criteria. QA runs per landed slice, concurrent with the remaining waves.
  - Conflict, or red after merge → abort the merge and send the conflict to the most-informed agent: resume the worker with "the feature branch moved: rebase onto it, resolve, re-verify, flip done again". Ticket branches are private; rebasing them is safe.
- **Session unrecoverable** (wedged, context-exhausted, gone) → no special machinery: reset the ticket to `open` and `dispatch-ctl cleanup` it; ticket + spec carry everything a fresh worker needs, by construction.

Where a ticket's done-check is human (UI verification), "green" means whatever automated checks exist; the human pass happens in the QA lane below.

**Punts get filed, never buried.** When a worker's closing comment punts a cross-cutting concern, defers to a ticket that hasn't started, names friction it hit (a tooling gap, a missing feedback loop, a slow suite), or leaves an `Assumptions` block with a taste call in it, that call is yours, not the worker's: fix what you can fix between waves, and for the rest, file it as a new ticket with blocking edges, or as an entry on the feature's **needs-human queue** (decisions only the user can make; entry criterion "needs the human", never "is cheap to review"). A gap noted in a comment has an audience of zero; announce punts and queue growth in every status report.

The tick's first half is complete when every exited worker is landed, resumed, or reset.

### 2. Re-evaluate the frontier

Re-read the ticket files: the frontier is open + unblocked + unclaimed (`/mx:tracker`). Landing tickets unblocks new ones, and the human QAs landed slices concurrently, filing findings as new tickets with blocking edges; the frontier absorbs those the same as the originals.

### 3. Plan the wave

Assess parallel-safety now, against the code as it stands: file overlap between two tickets depends on the current tree, so this judgment lives at dispatch time, not in to-tickets. Estimate which files each frontier ticket will touch; spawn together only tickets whose edits stay disjoint, and hold the rest for a later wave. When in doubt, serialize the doubtful pair.

File overlap is the mechanical test; **coherence** is the deeper one. Tickets that share one *surface* (one UI, one document, one API façade) produce locally-passing, globally-incoherent work when built in isolation, even where their files barely overlap: give a shared surface to one serial worker. Parallelism is for tickets separated by real seams. Repeated conflicts on one hub file are this warning arriving as a merge statistic: treat it as a structure signal, not a scheduling problem.

### 4. Claim and spawn

For each ticket in the wave:

1. Set `status: claimed` and commit on the feature branch (you are the sole claim-writer); push the feature branch to a remote host, so the ticket cuts from its current tip: a newly-unblocked ticket needs its blockers' landed code.
2. Write the worker prompt to `prompt-<NN>.md` in the scratch dir.
3. `dispatch-ctl spawn <NN>-<slug> <implementer>` (Mechanics) with the host's permission mode (setup step 5): it cuts the ticket's worktree and branch, runs the project's setup target there (`make install`; `nix develop -c make install` where a `flake.nix` exists) and starts the worker. A project with no setup target fails the spawn and gets a ticket, not an improvised venv: the target is what makes a worktree reproducible on any host, and every human on the project reads the same line. The implementer is an explicit model: Opus by default, Sonnet by your judgment for a small or trivial ticket, never Fable unless the user names it explicitly for this run, and never simply inherited from the orchestrator's own model; the judgment calls (wave planning, merges, verification) stay with you.

### 5. Stop or sleep

**Status is a render, not prose.** Keep chat output to a line or two per tick. The standing status view is the tracker board, rendered by `dashboard.py` beside this skill (`--help` for usage): `uv run <skill-dir>/dashboard.py agent/tasks` renders the whole tracker (every feature and standalone task on one page, cross-feature edges included, cycleable frontier/full/lanes views) to `~/Downloads/dispatch-dashboard/<project>.html` and opens the first render in the browser (the open tab then refreshes itself). Any agent that changes tracker state re-renders; concurrent dispatchers share the one board. `dispatch review` re-renders it after each landing; rerun it yourself after any other change to tracker state, and never hand-write status prose that can go stale.

The feature's queue lives in `agent/tasks/<feature>/needs-human.md`: optional `worker-host:` frontmatter, then one `- summary :: markdown detail` bullet per pending entry. The detail is what lets the human act without a chat round-trip: the decision's context and options, or the paste-ready kickoff prompt of a session only they can start (HITL prototypes). Delete an entry when it's answered; the answer lands in code or tickets, never in the file.

Frontier empty and everything landed → run the full suite once more on the feature branch, report the feature PR-ready to the user, and stop the loop.

Otherwise the watchers are your wake signal: a worker's exit re-invokes you within seconds of it happening, so the scheduled wakeup is a long fallback heartbeat (1200s+), never a poll. It exists for what a watcher can't catch: a worker wedged short of exiting, a dead watcher, a human who interrupted the pane.

## Worker contract

The worker prompt carries exactly this contract, concretized per ticket:

```
Load /mx:implement and work the ticket at agent/tasks/<feature>/<NN>-<slug>.md.
You own only this ticket and this worktree; the feature branch and other tickets belong to the orchestrator.
Your final act, once the implementation is committed and verified: set `status: done` in the ticket's frontmatter and commit.
```

The `done` flip as the *last* act is the done signal you read on exit; a worker that exits without it gets resumed.

## Mechanics

The spawn layer is deliberately thin. Two scripts beside this skill split it by where they run, and each one's `--help` is its header comment: `bash <skill-dir>/dispatch` runs **here**, in the feature worktree (setup, review page); `dispatch-ctl` runs **on the worker host**, from the feature's scratch dir (worktrees and branches off the repo there, sessions, channels, state files). History stays here: commits, merges, pushes, fetches are yours. `run-worker.sh` is the in-pane runner and the only file that names a harness: a different one (`codex exec`, a container) is a sibling runner script passed via `DISPATCH_RUNNER`, and everything else stands.

`dispatch-ctl` and `tmux` commands run as written when the host is this machine, prefixed with `ssh <host>` when it's another; `dispatch setup` prints the prefix. One command per ssh call, never a chain: a chained remote command that starts the tmux server inherits the connection's stdout and holds it open until the call times out.

- **Setup (once per feature)**: `bash <skill-dir>/dispatch setup <user@host|local> <repo>` from the feature worktree, on the feature branch; `<repo>` names the bare repo on the host, shared by the project's features. It adds the git remote, puts this plugin version's `dispatch-ctl`, `run-worker.sh` and `worker-prompt.md` into `/tmp/dispatch-<repo>-<feature>/` on the host, runs `dispatch-ctl init` there (bare repo, plugin update) and pushes the feature branch. The bare repo is empty rather than a clone of the project's remote: history arrives by push from here, so the worker host never authenticates anywhere, and a private repo is no different from a public one; ticket-branch churn stays off GitHub, where branch pushes would fire CI. The scratch dir is per feature because a concurrent dispatcher may be on another plugin version and a shared path would hand your workers its copy; its name carries the repo because `/tmp` and the tmux server are global to the host. Worker prompts land in the same directory. The `manifest` dispatch-ctl keeps there is the record of every run's channel; a channel can't be reconstructed, so an orchestrator taking over reuses the directory as it stands and never clears it.
- **Spawn**:
  ```
  bash /tmp/dispatch-<repo>-<feature>/dispatch-ctl spawn <NN>-<slug> <implementer>
  ```
  with `DISPATCH_PERMISSION_MODE=<mode>` in its environment. Session name, branch, worktree and ticket path all derive from `<NN>-<slug>` on the host, feature-namespaced because the bare repo and the worktree directory are shared there. It cuts the worktree from the feature branch's pushed tip when absent and runs the setup target in it, creates the session (a shell, so it survives worker exit), sends the runner command, verifies the launch, records the run in `manifest` beside itself, and prints the channel, exiting nonzero with the failing output when any of that didn't take. It echoes every command it runs, so the transcript doubles as the by-hand recipe when something off-script needs doing.
  Inside the pane, `run-worker.sh` runs the worker, retries a failed run up to three times with backoff by resuming the same conversation, writes `/tmp/<channel>.status`, and only then fires the channel. `DISPATCH_PERMISSION_MODE` is the mode every attempt runs with, the script's own retries included. A transient API error costs a backoff instead of an orchestrator round-trip, so the exits you hear about are the ones that need judgment.
- **Watcher**: right after spawning, arm one: a `run_in_background` Bash call of `tmux wait-for <channel>`, on the channel spawn printed. Background tasks are harness-tracked, so the watcher's own exit re-invokes you seconds after the worker finishes; you never poll for exits. A signal that fires with no waiter armed is remembered, so arming is race-free. Every run, spawn or resume, gets its own channel and its own watcher. It exits with the worker; nothing to clean up.
  A remote watcher rides its ssh connection and dies with it: a suspended laptop leaves the far-end `tmux wait-for` orphaned, and the signal it eventually catches is delivered to nobody and remembered for nobody. Arm it with `-o ServerAliveInterval=15 -o ServerAliveCountMax=2` so a dead connection collapses in ~30s, and re-arm whenever the probe says the worker is still running.
- **State probe**: `bash /tmp/dispatch-<repo>-<feature>/dispatch-ctl probe`: one line per worker, `running` (with the worklog's last line) or `exited` (with the status line: attempts, exit code, ticket status, session id), or `gone` (runner dead with no status file: a killed pane, a rebooted host); treat that as session-unrecoverable (tick step 1). It reads each worker's current run from the manifest, its status file, and whether the runner still has a process; writing that file is run-worker.sh's last act before firing the channel, which makes the probe the sole authority on who is done; a watcher only decides how fast you hear about it. The pane's process name answers nothing here: run-worker.sh is the pane process, so the pane reads `bash` for live and dead workers alike.
- **Resume**: the pane already retried what was transient, so a resume you run by hand either carries guidance or restarts a worker whose attempts are spent. Overwrite `prompt-<NN>.md` with the guidance (the worker holds the original in its conversation) and rerun spawn with the session id from the status file (same session name, so dispatch-ctl reuses the live pane):
  ```
  bash /tmp/dispatch-<repo>-<feature>/dispatch-ctl spawn <NN>-<slug> <implementer> <session-id>
  ```
  Then arm a watcher on the new channel. Resume by session id, never `--continue`: `--continue` means "the most recent conversation in this directory", which stops being the worker's the moment anything else runs `claude` in that worktree: you attaching to try something, or a retry that started fresh.
  A resume restores the worker's whole conversation, so the worker holds its own commits, edits, and stopping point in far more detail than your reading of its scrollback gives you, and it can read anything in the repo, the feature branch included, for itself. What it lacks is a reason to look. So guidance is an instruction to act on something that shifted while it was stopped ("the feature branch moved: rebase onto it"), and a file holding just `continue` is the entire message whenever nothing did. Recapping the worker's own state to it overwrites better knowledge with worse.
- **Observe**: `tmux capture-pane -p -J -t <session> -S -100`; the human can attach any time: `tmux attach -t <session>`, or `ssh <host> -t tmux attach -t <session>`.
- **After an orchestrator restart** (your session crashed, or a new one took over): watchers are background tasks of *your* session and die with it, while the workers keep running unobserved. Run the state probe; each `running` worker gets a watcher armed on the channel the probe shows: that channel, from the manifest, not a fresh one, which would never fire. Exited workers' status lines are already in the probe's output. Nothing else needs reconstructing: claims live in ticket frontmatter, work on ticket branches.
- **Review page**: the human's diff surface for a landed ticket, linked from the board automatically. `bash <skill-dir>/dispatch review <NN>-<slug>` once the ticket branch is fetched, before or after the merge: it appends the branch's `<merge-base-sha>..<tip-sha>` to the ticket's `diff:` frontmatter and commits that on the feature branch (SHAs, because cleanup deletes the branch while its commits survive; after the merge the base is read off the `--no-ff` merge commit), projects the ticket's assumption bullets and `Addressed:` lines into the page's notes, renders every range the ticket lists into `agent/diffviews/<feature>/<NN>-<slug>.html`, serves that directory (only a served page can save comments, and the board links the served URL whenever it finds a server) and re-renders the board. The notes file is rewritten whole on every render; the user's own comments and overrides live in a state file beside the page that rendering never touches. `agent/diffviews/` is gitignored, so this runs here, never on the worker host.
- **Cleanup after landing**: `bash /tmp/dispatch-<repo>-<feature>/dispatch-ctl cleanup <NN>-<slug>` on the worker host (session, manifest entry, worktree, branch), and `git branch -d` on the ticket branch you fetched into your own checkout.
