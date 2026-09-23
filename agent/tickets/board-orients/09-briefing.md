---
status: review
blocked-by: [08]
priority: 2
size: M
---

# The board briefing

## Brief

A model session explores the repo once and writes the briefing: where things stand and the next picks, marking what can run in parallel. Tracker changes are sent to that same session, debounced, and it retires after an idle hour or a ping cap.

Slice of `spec.md`, building on the Decisions under "The board briefing".

## What to build

The first run is a fresh `claude -p` session on a short prompt of its own, never the user's system prompt, given the tracker's state as the board computes it and free to explore the repo from there. It writes a few sentences on where things stand and three next picks with a reason each, marking picks that can run in parallel as one wave for dispatch. The board's watcher sends each tracker change, debounced by five to ten minutes, to the same session with `--resume` as a short note of what changed, and the session decides whether and how to rewrite the briefing. The session retires after an idle hour or a cap on pings or context, whichever comes first, and the next change starts a fresh one. A cache file beside the board holds the briefing, the time it was written, and the session's id, start, last activity and ping count; the board shows the time written. With no model available, or before the first briefing, the board writes the deterministic sentence and ordering the spec names.

The prompt cache's lifetime on the plan in use (five minutes by default, an hour where the longer cache applies) is confirmed before the idle limit is set, and the closing comment says which it found.

## Acceptance criteria

- [ ] The pings-and-retirement, no-model-call-on-an-unchanged-render and render-without-the-model checks from 01 pass and their annotations are gone.
- [ ] The briefing shows the time it was written, and the fallback shows when no briefing exists.
- [ ] Demo: the demo tracker's first briefing written, a change pinged into the same session and the briefing it rewrote, and the cache file after both.
