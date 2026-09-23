---
status: proposed
blocked-by: [04]
---

# The skills and the output style put a session's answers on its page

Slice of `spec.md`, building on its Decisions under The session page (only questions ask, the chat reply), Producing the pages (no HTML from the agent, every artifact by a subagent or fork, review inside `/mx:show`), and The spec page (it replaces diffview for specs).

## What to build

What an agent reads so that the pages get used. `/mx:show` becomes the one home for how a session delivers an answer on its page: when a session gets a page, how a turn record and the session record are written, that every artifact is built by a subagent or a fork, and that an artifact's prose is reviewed as part of its build. `/mx:grilling` delivers a round through the session page, opens the spec page instead of a diffview page on the spec, and stops re-listing unconfirmed calls in the reply. The output style's chat reply, in a session that has a page, is one line and the page's link. Every other skill or README line that still tells an agent to open a spec on diffview, or describes the chat-reply review, is brought along. Starts after `figures-and-demos` has merged, since that feature rewrites `/mx:show` and `/mx:grilling`.

## Acceptance criteria

- [ ] The chat reply of a session that has a page is one line and the page's link (spec, Properties).
- [ ] The main session writes no HTML (spec, Properties).
- [ ] The turn record's shape has one home, in `/mx:show`, and no other file restates it.
- [ ] No skill, README line or output style still sends a spec to diffview or describes the chat-reply review.
- [ ] Demo: a driven session with the plugin from this branch, before and after: the same grilling question answered in the terminal, and answered on a session page with its record, its artifact built by a subagent, and a one-line reply.
