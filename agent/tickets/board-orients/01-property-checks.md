---
status: review
priority: 1
size: S
---

# Property checks for the board

## Brief

The board's executable properties written as tests before any slice builds them, each failing until the slice that makes it hold lifts it. Reviewing it means reading the checks against the spec's Properties.

Slice of `spec.md`: its Properties and Testing Decisions.

## What to build

The spec's executable Properties as checks at their three seams, each an expected failure naming the ticket that lifts it (`/mx:testing`), so every later slice finds its oracle in place when its worktree is cut. The checks live beside the board's existing tests, since this repo has no properties directory; that is a deliberate deviation from `/mx:to-tickets`. Where a seam's function does not exist yet, this ticket lands its interface as a stub transcribed from the spec's Decisions, so the suite collects.

- **The loader seam**: which tickets are in needs me; a ticket's open questions read from its file, less those a `Ruled` line answers; the sessions listed for a ticket; a render with each optional source absent (GitHub, the model, transcripts, the review-page server); no GitHub request and no model call on a render that finds nothing changed.
- **The layout seam**: the demo tracker, built by `agent/prototypes/board-orients/demo-tracker/build.sh`, promoted into the test fixtures with its tickets moved to the spec's ticket file (the H1 as name, `## Questions` with `Ruled` lines), rendered, and checked with `render-lint` at window widths from 900px up and zoom from 80% to 200%, in both schemes.
- **The schedule seam**: whether a tracker change pings the briefing session, waits out the debounce, or retires the session and starts a fresh one, as a pure function of the cache file's state, the change's time and the clock.

The slice that lifts each: needs me and ruled questions → 03; no overlap → 02; a listed session has a transcript, and a render without transcripts → 05; no request on an unchanged render, and a render without GitHub → 07; no model call on an unchanged render, a render without the model, and pings and retirement → 09. A render without the review-page server already holds and carries no annotation.

## Acceptance criteria

- [ ] Every executable Property in the spec has a check at its seam, collected by `make test`, failing as an expected failure that names its lifting ticket.
- [ ] A property that already holds passes with no annotation.
- [ ] The demo tracker is a fixture the layout checks build on their own, with nothing read from `/var/tmp`.
- [ ] Demo: the diff is the demo, and the closing comment carries the `make test` output with the expected failures listed by ticket.
