---
status: proposed
parent: ticket-file-contract
priority: 1
size: L
---

# The tracker command, and the commit check that runs it

## Brief

One `tracker` command does every mechanical thing to ticket files, reads and writes, and a pre-commit hook runs its check so a malformed ticket is refused the moment it is committed. The two sibling tickets build on its interface: the scripts call it, the skills name it.

Child ticket of `ticket-file-contract`, building on its Decisions: the `tracker` command owning every mechanical operation (you, r6), the flat layout with slugs as ids and `parent:` (you, r1 and r2), the pre-commit check (you, r3) installed per repo (you, r4) and running the command's own check (you, r6), and its Properties P1 to P4 and P6 (you, r5 and r6). The operations and a sketch of the interface are drawn at `agent/show/ticket-file-contract/tracker-cli.html`; the sketch is yours to redesign.

## What to build

`tracker` lives in the tracker skill and is on PATH through `mx/bin/`, as `board` is. It is the only code that reads or writes ticket files; `board`, `dispatch` and the other scripts move onto it in `scripts-go-through-tracker-command`.

Reads its callers need:

- a check over given files or the staged ones, reporting `file:line: message` and exiting non-zero on any refusal;
- one frontmatter field of one ticket, for shell scripts (`status` above all, read today by four scripts four ways);
- the whole tracker as data: every ticket with its frontmatter, sections, questions, properties, acceptance criteria and assumptions (the board, `property-coverage`);
- a ticket's context: its body, then every ancestor's body, assembled one way (the worker's brief; the review's `--spec` file);
- the frontier: the unclaimed, unblocked tickets that are open or proposed and do not need the user, with what holds the rest back;
- the Assumptions bullets whole, however the writer wrapped them (`dispatch review`'s notes, where board-orients 10 lost every line past the first).

Writes, each refusing what the tracker's rules forbid and saying which rule:

- filing a ticket: its frontmatter and skeleton, with the body left for the agent to write;
- status changes along the transitions `/mx:tracker` defines (Ticket state), e.g. `done` only for a ticket whose branch has merged, and a ticket in `review` unblocking nothing;
- recording the user's answer to a `## Questions` item (the `Ruled <date>:` line);
- retiring a ticket and its descendants, together with what the tracker retires with them (show directories, prototypes, research notes), printing each step it runs and leaving the commit to the caller.

The ticket body stays prose the agent writes in the file; the check is what holds it to the format.

`--help` states the function: the subcommands, their flags, their arguments and what each returns or refuses. The flow they sit in (when to file, what a status means, how to cut child tickets) is the tracker skill's, and the two never say the same thing (you, r6). Fewer subcommands and flags are better. Record the interface as an assumption so the user rules on it from the review page.

The pre-commit hook is a few lines that run `tracker`'s check over the staged files under `agent/tickets/`; the check has one home, in the command. Install it in this repo; the other installs belong to the sibling tickets.

## Acceptance criteria

- [ ] `ticket-file-contract#P1`, `#P2` and `#P3` hold as checks over generated ticket files at `tracker`'s command line, in this repo's properties directory.
- [ ] `ticket-file-contract#P4`: a ticket's context is its body with its ancestors' bodies, in one order you choose and record, and a missing ancestor is refused like any dangling reference.
- [ ] `ticket-file-contract#P6`: retiring deletes nothing that git history or `~/logs` does not keep, beyond renders whose generating source is tracked; a run over a fixture tracker shows each file's route.
- [ ] Every status transition the tracker skill defines is accepted, and each one it forbids is refused with the rule named.
- [ ] Every construct in the parent ticket's "What reads a ticket today" table that survives the new model has its one reading here, and the constructs the new model drops (the spec's `draft | confirmed`, `type`, NN numbering, `feature/NN` references) are refused with a line saying what replaced them.
- [ ] The fixture corpus includes real ticket files from this tracker, converted to the new layout by hand: board-orients 10's wrapped Assumptions read whole.
- [ ] A commit in this repo that stages a ticket file `tracker` refuses is blocked, and the message names the file and line.

## Comments
