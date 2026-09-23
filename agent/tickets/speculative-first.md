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

The fog decides how far a build runs ahead of the user. An intent the agent cannot yet state, with many ways to go, is grilled before anything is built. An intent with one sensible way to build it is built without waiting; its details are judged in the finished artifact, with its demo, where the larger context makes them easier to judge.

The user added, on 2026-09-23: speculation today stops at the leaves, so a parent ticket's children are each put to the user one at a time. A speculative build could instead run up to and through the next parent ticket's close-out, and the user reviews that parent ticket whole with its children (what a feature was): accept or reject it whole, or criticise single parts. Nothing is lost when a whole subtree is rejected but tokens; the work goes back to an earlier point in the tree, or to the tickets, and starts over. Per-leaf review stays where a wrong detail in one child makes everything downstream much harder to fix.

Filed on the user's request on 2026-09-23, split out of [One contract for tickets and specs](ticket-file-contract.md) to keep that rewrite's scope to the data model. It blocks on that rewrite because it edits the same skills (grilling, orient) in the vocabulary that rewrite settles.

## Question

1. **The gate between building and grilling.** What the agent checks before it builds instead of asking: whether it can state the intent, its properties and a first shape without a question only the user can answer, or something else. Options sketched by the agent, frame unconfirmed.
2. **The first render.** What the speculative build shows the user: the built thing with its demo, a prototype, or a figure of the shape before any code, depending on the intent.
3. **Where the user reviews.** Each leaf, or the first parent ticket above the leaves, whole; and what makes a subtree need per-leaf review. Today's rules that change with it: a ticket in `review` unblocks nothing, and speculation goes one level deep (`/mx:dispatch`).
4. **What still gets asked.** Which questions interrupt the build (taste on a user-visible surface, an interface others depend on, a hard-to-reverse decision), and which become anchored assumptions ruled on from the review page.

## Acceptance criteria

- [ ] The decision is recorded, and `/mx:grilling`'s trigger and `/mx:orient`'s flow say it. Options outside the lists above count.
- [ ] A worked example: one intent taken each way (built first, grilled first) shows where the gate falls.

## Comments
