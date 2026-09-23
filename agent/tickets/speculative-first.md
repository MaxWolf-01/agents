---
status: open
type: grilling
blocked-by: [ticket-file-contract]
priority: 2
size: M
---

# Build first, grill when it is foggy

## Brief

The user wants the agent to answer an intent with a build more often than with questions. When the user voices a want or an idea and the agent already has a good idea of how to do it, the agent implements it speculatively and shows the result ("this is what I cooked"); the user rules on the artifact, and iteration or a grilling starts from there. Grilling up front is for intents too foggy to build from. Today `/mx:grilling` fires on any intent that is not fully mechanical, and the user answers questions that did not need their answer; speculative builds, already allowed by the tracker's `proposed` status and the review page's ruling, are underused.

What stays: nothing merges into the integration branch, and nothing ship-shaped happens, before the user has reviewed it. The questions that do reach the user are the ones only they can decide, or an artifact that teaches them the implementation.

Filed on the user's request on 2026-09-23, split out of [One contract for tickets and specs](ticket-file-contract.md) to keep that rewrite's scope to the data model. It blocks on that rewrite because it edits the same skills (grilling, orient) in the vocabulary that rewrite settles.

## Question

1. **The gate between building and grilling.** What the agent checks before it builds instead of asking: whether it can state the intent, its properties and a first shape without a question only the user can answer, or something else. Options sketched by the agent, frame unconfirmed.
2. **The first render.** What the speculative build shows the user: the built thing with its demo, a prototype, or a figure of the shape before any code, depending on the intent.
3. **What still gets asked.** Which questions interrupt the build (taste on a user-visible surface, an interface others depend on, a hard-to-reverse decision), and which become anchored assumptions ruled on from the review page.

## Acceptance criteria

- [ ] The decision is recorded, and `/mx:grilling`'s trigger and `/mx:orient`'s flow say it. Options outside the lists above count.
- [ ] A worked example: one intent taken each way (built first, grilled first) shows where the gate falls.

## Comments
