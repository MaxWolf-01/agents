---
status: open
needs-user: true
priority: 4
size: L
---

# Best-of-N: several workers build one ticket, one result is chosen

## Brief

Several workers build one ticket and one result lands, synthesised by an agent rather than picked by you. Open: when a ticket gets variants, who synthesises from what evidence, and what becomes of the losers.

## Questions

Filed from the one-flow grilling (round 1, Q3; sharpened in round 2): the flow should stay open to spending compute for quality, several workers building the same ticket and one result landing. Grill after one-flow ships, against its unit (one ticket, one worker, one branch, one review page), which is the seam this plugs into at spawn and at landing.

Two rulings already given in the one-flow grilling, round 2:

- **The result is synthesised by an agent, not chosen by the user.** N branches feeding the user N review pages would multiply the review load the mechanism exists to cut. What lands is one branch, enriched by the variants; the user sees one review page. Wanting to see several concrete designs is the prototype path, not this one.
- **Diversity is the failure mode to design against.** N workers given the same ticket tend to converge, and then the variants are a waste of tokens. How to raise the odds of genuinely different implementations (different framings in the prompt, different models, different constraints, a research note per variant) is the first thing to decide.

Still to decide:

- When a ticket gets N variants: a per-ticket knob, a class of ticket by default, or the orchestrator's call at claim time.
- Who synthesises and from what evidence: the N diffs, the N closing comments, the tests each variant passes.
- What happens to the losers: kept as primary sources like prototypes, or deleted with the verdict recorded in the ticket.
- What dispatch needs: N branches per ticket at spawn, one synthesis worker, one landing.

Options sketched by agent 2026-09-14, frame unconfirmed.
