---
status: review
blocked-by: [01]
---

# A grilling round draws its figures, opens them first, and re-renders them as the design moves

Slice of `spec.md`, building on Solution (you, r2, r5), Decisions "Figures live in `agent/show/<feature>/`" (you, r2), "Re-render with the round" (you, r5), "The figure is opened before the round is read" (you, r5), "The figure is the decision's home" (agent's call, r5, delegated by you), "Trigger by shape, not size, on every artefact" (you, r5).

## What to build

A grilling round whose Decisions gain or move a decision of a shape the table lists produces or re-renders that figure in the same round, commits its source with the round, and opens it in the user's browser before the round's message, whose first line says it is open. The Decisions entry links the figure and carries what the figure cannot: the why and the rejected alternative. The spec format's Decisions section points at the table beside the content types it already lists, and grilling's sentence that the spec stays textual and a visual is a show artefact is replaced by the rule, not joined by it.

## Acceptance criteria

- [ ] The spec format's Decisions section points at `/mx:show`'s table where it lists schema changes, API contracts and interactions; the grilling skill's round produces, re-renders, commits and opens the figure, in that order, before the message.
- [ ] The sentence "The spec stays textual; a visual that would help a round is a `/mx:show` artefact" no longer exists in any form.
- [ ] Property, reviewed: a figure states the decision as it stands; a figure whose decision moved is re-rendered in the same round.
- [ ] Property, reviewed: a figure's source is committed; its raster render is never tracked.
- [ ] Property, reviewed: a spec with no decision of a listed shape has no figure.
- [ ] Demo: `agent/show/figures-and-demos/02-spec-figures/demo`, executable, no arguments: a driven round on a toy spec with a schema decision, showing the figure produced and the message's first line; where the plugin cannot be loaded in that session, the closest render, and the comment says so.
