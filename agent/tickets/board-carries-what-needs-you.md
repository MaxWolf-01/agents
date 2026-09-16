---
status: open
type: grilling
---

# The board's needs-human section: everything that needs the user, managed from there

## Question

Ruled worth doing by the user during the one-flow dispatch (2026-09-15). Today the calls only the user can make arrive in chat, per landing, as tagged "I need from you" lists; each new landing restates them or they scroll away, and the user cannot tell what is still current. The board's needs-human section is where they belong, so a returning user reads one page: the rulings waiting on them with their options, the proposals agents filed (workflow and tooling improvements, what the debrief sorts today), the landings waiting to be driven.

Two more from the user, same day: every entry carries a tag (`D123`, unique across the board, the way landing messages tag their calls) so a ruling can name it from anywhere; and the board may take the ruling itself, an input box per entry and an X to dismiss, so the user never has to find the session that filed it. That makes the section a served page with state, as diffview already is for comments, against a read-only render that stays simple; the trade is part of the grilling. Not the diffview notes: a note per call, asking the user to dismiss things that never needed them, is the load this exists to cut.

Also to consider, from the user: whether tags should encode the round they came from (`A1, A2` in one message, `B1, B2` in the next) rather than one running sequence; the letters show where a call came from, the sequence is simpler.

To decide, in a grilling with the board rendered: what an entry is (a ruling with its options, a landing to QA, a proposal to accept or reject), where entries come from (the closing comment's "I need from you" list, the queue file, proposed tickets), how an entry clears (a ruling on the review page, a word in chat, a ticket flip, the board's own input), and how the board shows a slice that is built and waiting for a ruling.

## Comments

**2026-09-16** The last question, how the board shows a slice built and waiting for a ruling, is answered by the `review` status ([A `review` status: a build waiting for the user's ruling has its own state and its own group on the board](review-status.md)): such a slice sits in the board's needs-my-review group with its review page linked. Left for this grilling: the entries the page itself takes (tags, an input per entry, dismissal), and where the landings to drive and the proposals to rule on come from.
