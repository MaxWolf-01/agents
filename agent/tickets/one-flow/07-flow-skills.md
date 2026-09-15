---
status: claimed
blocked-by: [06]
---

# The flow skills describe one flow

## What to build

The skills that route and gate work say what the spec's Solution says. Orient's main flow: an intent arrives in chat; grilling as deep as it needs; the brief test, stated as the spec's paragraph and not as a table, decides loose, ticket or spec; a fresh worker per ticket; the review page and the demo per landed slice; QA. The size call at the gate ("build here, or to-tickets") is gone; a feature always slices. Loose is defined as the absence of a brief, with no agent review. The standalone ticket path and the speculative build are on the map, and the user's stations (answering open questions, the demo plus review page per slice, QA, the needs-human queue) are named as the only places their attention is asked for. The demo has two parties and the map keeps them apart: the worker specifies it in its closing comment as steps a stranger can run, and the orchestrating session on the user's machine performs them and opens the result, since a worker on a host can open nothing for the user.

Grilling's gate becomes non-blocking: when the frontier is empty the session cuts the tickets and dispatches them with the agent's calls still marked; the spec is confirmed when the user ratifies on the review page or in chat; "do not act before that confirmation" is replaced by that rule. To-tickets cuts from a draft spec whose frontier is empty, publishes the tickets as `proposed`, renders the board, and names in each ticket the spec calls it builds on for the worker to carry as assumptions; its quiz no longer blocks the build. The prototype skill says a prototype is for rival shapes or something that must be seen or driven, and that a single clear design is built. Phase-boundaries and the README's flow prose follow. The README's figures are regenerated from `agent/show/one-flow/` into the plugin's assets and embedded where the old flow figures were.

## Acceptance criteria

- [ ] Orient states the brief test as the spec's paragraph; no size call remains at the gate; the standalone path, the speculative build and the user's stations are on the map.
- [ ] Grilling's gate section states the non-blocking rule and where confirmation happens; to-tickets cuts from an empty-frontier draft, publishes `proposed`, and stamps the spec calls each ticket builds on.
- [ ] The prototype skill routes a single clear design to the build.
- [ ] The README's flow prose and figures match orient.
- [ ] Property, reviewed: no step blocks on the user reading a brief; a ticket written by an agent is dispatched, not presented.
- [ ] Property, reviewed: the build never starts while the agent still has a question for the user; it never waits for the user to ratify a call.
- [ ] Assumption to carry, anchored: tickets naming the calls they build on is the agent's call from the spec.
- [ ] Demo in the closing comment: the README rendered with the new figures, opened.
