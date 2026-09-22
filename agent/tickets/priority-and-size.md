---
status: open
type: grilling
---

# Tickets carry a priority and a size, and the board orders by them

## Question

Asked for by the user in chat, 2026-09-22. The board shows a ticket's state and its blocking edges, and nothing about how much it matters or what it costs, so picking what to grill, rule on or dispatch next means opening tickets. The user's reference, the scale used at work:

- **Priority**: P1 critical (business critical, sprint blocker), P2 very important, P3 important, P4 normal, P5 low or future.
- **Size**: XS under two hours, S half a day, M one to two days, L several days, XL has to be split (an epic, or a concept).

What these fields would act on, read from the tracker skill and `board.py` on 2026-09-22:

- The frontier's one ordering rule is "first by number wins" (MARKDOWN.md, Ticket state). Standalone tickets have slugs, not numbers, so the board lists them alphabetically; this repo has twenty-odd, and their order says nothing. Within a feature, the `blocked-by` edges and the numbering already say what comes first.
- XL already has a home: work too big for one ticket is a feature with a spec, cut by `/mx:to-tickets`, whose sizing is two-sided (a slice too small pays an agent start).
- A build ticket's hours are a worker's, spent unattended. The user's hours go to grilling decision tickets and to ruling on builds.

To decide, options sketched by agent 2026-09-22, frame unconfirmed:

1. **What each field is for.** Priority: the order within each group on the board, what the orchestrator dispatches next, or both. Size: whether it measures the build's effort (the work scale above) or the user's time the ticket will take (a grilling's length, a review and its QA), and whether it drives picking what fits the time at hand or flagging a ticket to split.
2. **Where they live.** On every ticket; on standalone tickets and features only, since a feature's own tickets are ordered by their edges; or priority on the feature and size on the ticket.
3. **The scales.** Five priority levels or fewer, and whether one person working with agents has a use for "critical"; size as letters or as hours.
4. **Who sets them.** Priority is a ruling, so a value an agent sets stays marked until the user confirms it (`/mx:tracker`, Provenance); size may be the agent's estimate.
5. **What the board does with them.** A badge per row, the order within each group, a filter.

Resolved when the decision is recorded here, the build is filed as a ticket blocked on this one, and the terms are in `CONTEXT.md` through `/mx:domain-modelling`. Options outside this list count.
