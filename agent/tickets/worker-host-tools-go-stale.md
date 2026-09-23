---
status: proposed
---

# A worker host keeps the `job` it was first given

Cut from the figures-and-demos whole-feature review (ticket 06). `dispatch-ctl init` fetches `job` into `~/.local/bin` only when `command -v job` finds none (`dispatch-ctl:178`), so a host installed once keeps that copy for good. agent@pc was set up before `job stage` landed in the dotfiles on 2026-09-18, and every landing dispatched there since has printed "the `job` here has no staged mode; nothing staged" while the mode existed on the orchestrator's side.

The failure reads as a missing feature rather than a stale tool: the review that cut this ticket reported the staged mode as unbuilt and put it to the user as a call only they could close, which is the reading `dispatch`'s own message invites. That is the cost, and it is principle 10's: a state the machinery can be in with no reading of its own.

## What to build

`dispatch-ctl init` refreshes the copy it finds rather than skipping it, or records the version it fetched and refetches when the orchestrator's differs. Which of the two is the open part: `job` is one file with no version string today, so the cheap form is to fetch unconditionally, and the question is whether anything else a host gets from `init` cannot take that.

Whatever the mechanism, a host whose tool is older than the feature asking for it says so. `dispatch: the job here has no staged mode` is true and useless; `dispatch: this host's job predates the staged mode; dispatch-ctl init refreshes it` is the same line with the next step in it.

## Acceptance criteria

- [ ] A host holding a `job` older than the orchestrator's ends `dispatch-ctl init` with the current one.
- [ ] A staging that fails on an old tool names the tool and what refreshes it, not the missing mode alone.
- [ ] Demo: `agent/show/worker-host-tools-go-stale/demo`, executable, no arguments: a toy host with an old `job` on PATH, `init` run against it, and the staging that failed before it succeeding after.
