---
status: proposed
blocked-by: [01]
---

# A landing's demo is the file the orchestrator runs on the user's machine

Slice of `spec.md`, building on Solution (you, r4), Decisions "The demo is one file named `demo`" (you, r4, r5), "Loose work demos the same way" (you, r4), "The rows" (agent's call, r2 to r5), "A heavy artefact goes to a fresh agent with a brief" (you, r4).

## What to build

A worker closing a ticket writes the demo file in the ticket's show directory, runs it, and pastes the command and that run's output into the closing comment's Demo line, the medium per the table; a heavy demo goes to a fresh agent with a brief. The orchestrator landing the ticket runs the same file on the user's machine, opens what it produced beside the review page, and treats a demo that is missing or does not run as it treats a missed acceptance criterion: back to the worker before the ruling. A session landing loose work writes the same file under the branch's show directory and its landing message carries the same Demo line. The worker contract, the dispatch tick, orient's landing and loose steps, and the landing message shape in the output style all say this in one sentence each and point at `/mx:show` for the medium; none restates the table.

The landing as a sequence, drawn for this spec: `agent/show/figures-and-demos/landing.svg`.

## Acceptance criteria

- [ ] The worker contract's Demo line names the file, its place, no arguments, and that the output is pasted from a run, and points at `/mx:show` for the medium.
- [ ] Dispatch's landing step runs the demo file on the orchestrator's machine and opens what it produced beside the review page; a missing or failing demo goes back to the worker before the ruling.
- [ ] The output style's landing shape and orient's loose-work step name `agent/show/<branch>/demo`.
- [ ] Property, reviewed: every landing, whatever its size, has one demo file, and the demo's output in the comment or message is pasted from a run of that file under the command that ran it.
- [ ] Property, reviewed: a demo file takes no arguments and runs from its branch on any host where the project is installed.
- [ ] Demo: `agent/show/figures-and-demos/03-landing-demo/demo`, executable, no arguments: a toy landing driven end to end with a stub in place of the harness (the precedent is `git show a2cfd9f:agent/show/host-per-spawn/demo.sh`, retired with one-flow), the stub worker writing a demo file and the landing step running it and printing what it produced; where that is out of reach, a driven closing comment from a print-mode worker, and the comment says so.
