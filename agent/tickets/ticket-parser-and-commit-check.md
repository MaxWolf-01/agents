---
status: proposed
parent: ticket-file-contract
priority: 1
size: M
---

# The ticket parser, and the commit check that runs it

Child ticket of `ticket-file-contract`, building on its Decisions: one parser on PATH (you, r1), the flat layout with slugs as ids and `parent:` (you, r1 and r2), the pre-commit check (you, r3) installed per repo (you, r4), and its Properties P1 to P4 (my call, r2).

## Brief

One script in the tracker skill reads ticket files in the new model, and nothing else does: every script the parent ticket lists moves onto it in the sibling ticket `scripts-read-tickets-through-parser`, and the skills name it in `skills-and-glossary-speak-one-ticket-kind`, so this ticket fixes the interface both build on.

What its callers need from it:

- a check over given files or the staged ones, reporting `file:line: message` and exiting non-zero on any refusal (the commit check, and every reader before it trusts a file);
- one frontmatter field of one ticket, for shell scripts (`status` above all, read today by four scripts four ways);
- the whole tracker as data, every ticket with its frontmatter, sections, properties, acceptance criteria and assumptions (the board, `property-coverage`);
- a ticket's context: its body, then every ancestor's body, assembled one way (the worker's brief, the review's `--spec` file);
- the Assumptions bullets whole, however the writer wrapped them (`dispatch review`'s notes, where board-orients 10 lost every line past the first).

The interface's shape is yours: fewer subcommands and fewer flags are better, and `--help` states it. Record it as an assumption so the user rules on it from the review page.

The pre-commit hook ships beside the parser: it runs the check over the staged files under `agent/tickets/` and blocks the commit with the parser's output. Install it in this repo; the other installs belong to the sibling tickets.

## Acceptance criteria

- [ ] `ticket-file-contract#P1`, `#P2` and `#P3` hold as checks over generated ticket files at the parser's command line, in this repo's properties directory.
- [ ] `ticket-file-contract#P4`: a ticket's context is its body followed by its ancestors' bodies, nearest first or top-down (your call, recorded), and a missing ancestor is refused like any dangling reference.
- [ ] Every construct in the parent ticket's "What reads a ticket today" table that survives the new model has its one reading here, and the constructs the new model drops (the spec's `draft | confirmed`, `type`, the NN numbering, `feature/NN` references) are refused with a line saying what replaced them.
- [ ] The fixture corpus includes real ticket files from this tracker, converted to the new layout by hand: board-orients 10's wrapped Assumptions read whole.
- [ ] A commit in this repo that stages a ticket file the parser refuses is blocked, and the message names the file and line.

## Comments
