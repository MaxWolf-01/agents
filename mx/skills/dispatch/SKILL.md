---
name: dispatch
description: Work a feature's ticket DAG in parallel — one orchestrator fans independent frontier tickets out to parallel worker agents and integrates them on the feature branch until the feature ships. Use when a ticketed feature has independent frontier tickets, the user says "dispatch" or wants tickets worked in parallel, or when another skill routes parallel frontier work here.
---

# Dispatch

You are the **single orchestrator** of one feature's ticket DAG: compute the frontier, fan a **wave** of workers out, integrate tickets as they **land**, repeat until no open tickets remain. `implement` works one ticket; dispatch orchestrates N implements. You are the sole claim-writer, the only holder of the feature branch, and the only judge of done.

Dispatch runs downstream of `/mx:to-tickets` — the `blocked-by` DAG is what makes independence explicit and human-approved. An unticketed task with two or more independent parts routes through to-tickets first.

## Setup (once)

1. Fetch the spec and every ticket per the `tracker` skill.
2. **The feature branch is the integration branch.** Check it out in the main checkout and hold it: ticket branches cut from it and merge back into it; main sees the feature only as one squashed PR when the spec ships.
3. Run the tick loop under `/loop` with no interval (self-paced). Workers run in tmux between ticks — external state the harness can't watch — so size each wakeup to what the current wave is actually doing.

## The tick

### 1. Integrate what landed

For each spawned worker whose `claude -p` has exited (see Mechanics), read the ticket's frontmatter **from the worker's worktree** — the `done` flip lands on the ticket branch, so your feature-branch checkout still shows `claimed` until the merge:

- **Not `done`** → the worker stopped early. Diagnose from its scrollback. A permission denial is a first-class resumable event: add the allowlist entry it needed, or resume with guidance; otherwise resume with "continue".
- **`done`** → the flip alone proves nothing. Merge the ticket branch into the feature branch and run the project's verification there:
  - Clean merge, green → the ticket has **landed**: keep `status: done`, remove its worktree, kill its session — and **announce it to the user**: the ticket is demoable now (tracer bullet), so name what works and how to exercise it, straight from the ticket's "What to build" and acceptance criteria. QA runs per landed slice, concurrent with the remaining waves.
  - Conflict, or red after merge → abort the merge and send the conflict to the most-informed agent: resume the worker with "the feature branch moved — rebase onto it, resolve, re-verify, flip done again". Ticket branches are private; rebasing them is safe.
- **Session unrecoverable** (wedged, context-exhausted, gone) → no special machinery: reset the ticket to `open`, delete its worktree and branch — ticket + spec carry everything a fresh worker needs, by construction.

Where a ticket's done-check is human (UI verification), "green" means whatever automated checks exist; the human pass happens in the QA lane below.

The tick's first half is complete when every exited worker is landed, resumed, or reset.

### 2. Re-evaluate the frontier

Re-read the ticket files: the frontier is open + unblocked + unclaimed (`tracker`). Landing tickets unblocks new ones — and the human QAs landed slices concurrently, filing findings as new tickets with blocking edges; the frontier absorbs those the same as the originals.

### 3. Plan the wave

Assess parallel-safety now, against the code as it stands — file overlap between two tickets depends on the current tree, so this judgment lives at dispatch time, not in to-tickets. Estimate which files each frontier ticket will touch; spawn together only tickets whose edits stay disjoint, and hold the rest for a later wave. When in doubt, serialize the doubtful pair.

### 4. Claim and spawn

For each ticket in the wave:

1. Set `status: claimed` and commit on the feature branch (you are the sole claim-writer).
2. Cut its worktree + branch from the feature branch's current tip — a newly-unblocked ticket needs its blockers' landed code.
3. Set up per-worktree environment where the project needs one (venv, node_modules — project-specific).
4. Launch the worker in its tmux session (Mechanics) with `--permission-mode auto` and the implementer model — typically one tier below the orchestrator (e.g. Opus implements while Fable orchestrates); the judgment calls (wave planning, merges, verification) stay on the strongest model, with you.

### 5. Stop or sleep

Open or claimed tickets remain → schedule the next wakeup and end the tick. Frontier empty and everything landed → run the full suite once more on the feature branch, report the feature PR-ready to the user, and stop the loop.

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

- **Worktree**: `git worktree add ../<repo>-<NN>-<slug> -b ticket/<NN>-<slug>`, run from the feature-branch checkout; worktrees live as its siblings, one branch per worktree, the checkout itself holding the feature branch.
- **Spawn**: write the worker prompt to `/tmp/dispatch-<feature>-<NN>.md` (multi-line text never survives quoting through send-keys — pass it via stdin), then create the session with a shell so it survives worker exit and send the command:
  ```
  tmux new-session -d -s dispatch-<feature>-<NN> -c <worktree-path>
  tmux send-keys -t dispatch-<feature>-<NN> -l 'claude -p --permission-mode auto --model <implementer> < /tmp/dispatch-<feature>-<NN>.md'
  tmux send-keys -t dispatch-<feature>-<NN> Enter
  ```
- **Exit check**: `tmux list-panes -t dispatch-<feature>-<NN> -F '#{pane_current_command}'` prints the shell's name once the worker has exited.
- **Resume**: same send-keys shape with `claude -p --continue "<guidance>"` — the worktree cwd locates the worker's conversation.
- **Observe**: `tmux capture-pane -p -J -t <session> -S -100`; the human can `tmux attach -t <session>` any time.
- **Cleanup after landing**: `git worktree remove <path>`, `git branch -d ticket/<NN>-<slug>`, `tmux kill-session -t <session>`.
