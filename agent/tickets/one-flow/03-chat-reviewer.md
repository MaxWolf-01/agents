---
status: claimed
blocked-by: [01]
---

# The chat reviewer ships with the mx plugin

## What to build

Every session with the mx plugin gets a Stop hook that has a small model read the turn's final message against the chat-scoped rules of the prose catalogue and, when it finds tells, returns them as hook feedback so the turn continues with a corrected reply. The hook is a command hook in the plugin's own hooks file; its script lives in the plugin and reads the catalogue file, selecting the rules tagged `chat` or `both`; there is no second rules file. The prototype at `agent/prototypes/chat-review-hook/` is the working reference: its `chat-review` script, its `ANSWER.md` (measurements and findings), and its `try` driver. Keep what the prototype found: the nested model call runs with no settings, plugins, hooks or MCP servers and with thinking off, since thinking turns a five-second review into two minutes; it fails open; it logs every decision as one JSON line; it returns early on its own re-entry.

Two conditions make it return early without calling a model: an environment variable that turns it off, and a session nobody reads (a dispatched worker, marked by the worker environment dispatch sets; an unattended session, if the harness marks one). The prototype's rules copy is retired once the hook reads the catalogue; the prototype directory stays as the primary source of the measurements.

## Acceptance criteria

- [ ] The plugin's hooks file registers the Stop hook; a session started with the plugin runs it with no per-machine setup.
- [ ] The script reads the chat-scoped rules from the catalogue file of ticket 01; no rules text lives in the script or the hooks file.
- [ ] Off switch by environment variable; early return in a dispatched worker's session.
- [ ] Property, reviewed: a chat reply the user reads has been checked against the chat-scoped rules, and the check never runs more than once per turn.
- [ ] Demo in the closing comment: the `try` driver (or its successor) run against the shipped hook, showing the draft, the feedback line and the rewrite, with the review's latency from the log.
