---
status: claimed
blocked-by: [08]
priority: 2
size: M
---

# The board briefing

## Brief

A model session explores the repo once and writes the briefing: where things stand and the next picks, marking what can run in parallel. Tracker changes are sent to that same session, debounced, and it retires after an idle hour or a ping cap.

Slice of `spec.md`, building on the Decisions under "The board briefing".

## Questions

- [D1] **The board asks GitHub once every five minutes for as long as it is watched.** The watcher now re-renders when the cached answer has run out, so a pull request that merges while the tracker sits still shows as merged within the window instead of waiting for someone to touch a ticket (07's D3, which you have not ruled on). It costs one GraphQL query and one render, 0.3 s here, every five minutes per watched board that names any `gh` reference; a tracker naming none is untouched, and the page's stamp is unchanged when the answer is, so the open tab does not reload for it. A quiet tracker asked nothing at all before.
- [D2] **The briefing runs on whatever model this machine's `claude` is set to, with no effort flag.** On opus, two runs of the demo put a first exploration at $0.35 and $0.54 and the ping after it at $0.30 and $0.54: what it costs is the exploring, not the rereading, since the hour-long prompt cache carries the session's own context between pings and not the repo it reads each time. A board watching a tracker that changes every window pays that once a window, so a working day with the board open is dollars rather than cents. Pinning it to sonnet, or to a low effort, is one constant.
- [D3] **A board started on a quiet tracker writes its first briefing straight away.** The spec hangs every briefing on a tracker change, which would leave the board you open after a week away showing the deterministic count for ever: the tracker has not changed precisely because you were away. So the watcher's own start counts as a change where no briefing has ever been written; one already written is left standing however old, with the time it was written beside it.
- [D4] **The session retires on an hour idle or twenty pings, and nothing reads its context.** The spec names the session's context as a third limit; the cache file cannot say it and `claude -p` does not report it. Twenty pings is at least an hour and three quarters of a tracker changing every window, and Claude Code compacts a session that outgrows its window rather than failing. A real context limit means reading the session's transcript, which is machinery this does not have.

## What to build

The first run is a fresh `claude -p` session on a short prompt of its own, never the user's system prompt, given the tracker's state as the board computes it and free to explore the repo from there. It writes a few sentences on where things stand and three next picks with a reason each, marking picks that can run in parallel as one wave for dispatch. The board's watcher sends each tracker change, debounced by five to ten minutes, to the same session with `--resume` as a short note of what changed, and the session decides whether and how to rewrite the briefing. The session retires after an idle hour or a cap on pings or context, whichever comes first, and the next change starts a fresh one. A cache file beside the board holds the briefing, the time it was written, and the session's id, start, last activity and ping count; the board shows the time written. With no model available, or before the first briefing, the board writes the deterministic sentence and ordering the spec names.

The prompt cache's lifetime on the plan in use (five minutes by default, an hour where the longer cache applies) is confirmed before the idle limit is set, and the closing comment says which it found.

## Acceptance criteria

- [x] The pings-and-retirement, no-model-call-on-an-unchanged-render and render-without-the-model checks from 01 pass and their annotations are gone.
- [x] The briefing shows the time it was written, and the fallback shows when no briefing exists.
- [x] Demo: the demo tracker's first briefing written, a change pinged into the same session and the briefing it rewrote, and the cache file after both.
