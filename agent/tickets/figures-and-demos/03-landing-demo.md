---
status: review
blocked-by: [01]
---

# A landing stages the demo file in a tmux session on the user's machine

Slice of `spec.md`, building on Solution (you, r4, r8), Decisions "The demo is one file named `demo`" (you, r4, r5), "The landing stages the demo in a tmux session" (you, r8), "Loose work demos the same way" (you, r4), "The rows" (agent's call, r2 to r5), "A heavy artefact goes to a fresh agent with a brief" (you, r4). The staged mode of `job` this leans on lands in dotfiles before this ticket starts (Decisions, "The staged mode of `job` lives in dotfiles"); a worker cannot add it.

## What to build

A worker closing a ticket writes the demo file in the ticket's show directory, runs it, and pastes the command and that run's output into the closing comment's Demo line, the medium per the table; a heavy demo goes to a fresh agent with a brief. The orchestrator landing the ticket adds the ticket branch's worktree beside the feature's, named after the ticket, and stages the demo through `job`: one detached tmux session named after the ticket, its working directory in that worktree, the demo's path typed and Enter not sent; the landing message names the session. The user runs it when they choose, and the demo opens what it produces. The ruling kills the session and removes the worktree, whichever way it goes. A demo that is missing or does not run under the worker's own hand goes back to the worker before the ruling, as a missed acceptance criterion does. A session landing loose work writes the same file under the branch's show directory, stages it the same way, and its landing message carries the same Demo line. The worker contract, the dispatch scripts and tick, orient's landing and loose steps, and the landing message shape in the output style say this in one sentence each and point at `/mx:show` for the medium; the worktree and the staging are steps of the `dispatch` script, since nothing in them is judgment.

The landing as a sequence, drawn for this spec: `agent/show/figures-and-demos/landing.svg`.

## Acceptance criteria

- [ ] The worker contract's Demo line names the file, its place, no arguments, and that the output is pasted from a run, and points at `/mx:show` for the medium.
- [ ] `dispatch` adds the ticket worktree and stages the demo session at a landing, and removes both at the ruling; the skill's tick says so in a sentence and the script's `--help` carries the mechanics.
- [ ] The landing message names the session the demo waits in; the output style's landing shape and orient's loose-work step name `agent/show/<branch>/demo` and the same staging.
- [ ] Property, reviewed: every landing, whatever its size, has one demo file, and the demo's output in the comment or message is pasted from a run of that file under the command that ran it.
- [ ] Property, reviewed: a demo file takes no arguments and runs from its branch on any host where the project is installed.
- [ ] Demo: `agent/show/figures-and-demos/03-landing-demo/demo`, executable, no arguments: a toy landing driven end to end with a stub in place of the harness (the precedent is `agent/show/host-per-spawn/demo.sh` in git history, deleted by ticket 04's sweep: `git log --diff-filter=D -- agent/show/host-per-spawn` finds it), the stub worker writing a demo file, the landing step adding the worktree and staging the session, and the session's pane captured with the command typed; where that is out of reach, a driven closing comment from a print-mode worker, and the comment says so.
