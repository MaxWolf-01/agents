---
status: claimed
blocked-by: [13]
priority: 2
size: XS
---

# The briefing's cadence and model, as ruled

## Brief

The briefing is rewritten when a ticket's status has changed, after five minutes with no further change, and at most once every ten minutes. It runs on Opus 5.5 at medium effort. Today any edit under the tracker counts as a change, and the model is whatever this machine's `claude` defaults to.

Ruled by the user on 2026-09-23, on 09's D2 and its cadence, after 09 merged.

## What to build

The watcher pings the briefing session only when a ticket's status has changed since the last briefing, a new ticket and a retired one included. A text edit to a ticket does not count. The ping waits for five minutes with no further status change, and never comes sooner than ten minutes after the last briefing was written. Every `claude -p` run of the briefing passes `--model claude-opus-5-5 --effort medium`. It runs without the user's output style, which shapes replies for a human at a terminal (ruled 2026-09-23 for every noninteractive run; `"outputStyle": "default"` in its settings does it, as for dispatch workers). The schedule's property check follows the new rule.

## Acceptance criteria

- [ ] A ticket's status change reaches the session after five quiet minutes, and no sooner than ten minutes after the last briefing.
- [ ] An edit that changes no ticket's status sends no ping.
- [ ] The briefing session runs on Opus 5.5 at medium effort.
- [ ] A captured first request of the briefing carries no output style (`~/Downloads/show/review-launcher-calls/proto/capture.py` records one).
- [ ] Demo: a status change, a text edit, and a second status change inside ten minutes, with the pings each one produced.
