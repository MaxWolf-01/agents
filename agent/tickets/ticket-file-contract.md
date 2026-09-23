---
status: claimed
type: grilling
priority: 1
size: L
---

# One kind of ticket, read by one parser

## Brief

The tracker has three kinds of file, a feature's `spec.md`, a feature's `NN-slug.md` ticket and a standalone `<slug>.md` ticket, and every stage of the workflow branches on which one it holds: the tracker's layout and retire rules, grilling's absorb step, dispatch's case detection, code-review's spec lookup, the board's two classes, orient's ticket-or-spec step. Each branch is more prose, more tokens and more edge cases, and deciding whether work gets a spec is one more branch. At the same time, agents write ticket files by following prose in the skills while several scripts parse them with their own regexes, and a writer's drift from a reader's expectation drops text silently (The incident, below).

This ticket replaces the three kinds with one: a ticket, which can have child tickets. A ticket file has one format and one parser every script calls, so a mismatch fails loudly where the text was written.

Filed on the user's request on 2026-09-23, at priority 1. Grilled from the architecture review of that day (`~/Downloads/show/architecture-review-2026-09-23/`); round 2 is drawn at `agent/show/ticket-file-contract/index.html`.

## Properties

(my call, r2; unconfirmed)

- P1 Text a writer put in a machine-read part of a ticket is read whole or refused with its file and line, never dropped.
- P2 Every machine-read construct has one parser, and every script reads tickets through it.
- P3 A reference (`parent`, `blocked-by`, `<slug>#P<n>`) that names no ticket or property is refused with its file and line.
- P4 A ticket's context is its body plus every ancestor's body, assembled one way for the worker and the reviewer alike.
- P5 No skill, script or glossary entry distinguishes tickets by kind beyond whether a ticket has child tickets (open → Q4 on whether it also distinguishes tickets that need the user).

## Decisions

**Data model**

- One kind of file: the ticket, flat at `agent/tickets/<slug>.md`, with an optional `parent: <slug>`. The hierarchy goes as deep and as wide as the work needs. (you, r1)
- The slug is the ticket's id; `parent` and `blocked-by` name slugs, one reference form. A slug is descriptive enough to recognise the ticket from it alone, in the spirit of `/mx:session-name`'s names; agents say the slug to the user rather than a number. No short hash beside it until practice asks for one. A rename is a string replace of the unique slug across the tracker, read over as a diff; a script for it only once renames recur. (you, r2)
- A ticket file is committed on its parent ticket's branch; a top-level ticket's on the integration branch. (you, r2)
- No `draft | confirmed` state. The marks stay on each call as the record of who decided it; making them searchable waits until it is needed. (you, r1)
- The glossary loses **Feature**, **Spec**, **Standalone ticket** and **Gate**, and gains **Parent ticket** (with child ticket): the ticket another ticket is part of. A child ticket reads the parent ticket's body as its context, cuts its branch from the parent ticket's, and the parent ticket is done once every child ticket is done and its own close-out is ruled. (you, r2; the term "parent ticket" over bare "parent", since a graph has parents too)

**Parent tickets**

- Close-out runs at every parent ticket when its last child ticket is done: the full suite and leftover expected failures, the review one level up (the parent ticket reviewed against its own body, with every child's work in), harden, the debrief, the fuzz run. It is today's feature close-out; most trees are one or two levels deep. (you, r2)
- Properties are stated once, on the ticket they hold for, and every descendant reads them through its ancestry. `/mx:to-tickets` stops stamping properties onto child tickets; `property-coverage` shrinks to "every executable property has a check". A property is cited as `<slug>#P<n>`. (you, r2)
- A review reads the ticket plus its ancestry as one assembled file; light or full is decided by the diff's size and whether it touches a contract others depend on. (you, r1)

**Ticket body**

- Sections: Brief (the intent and why, as a technical stakeholder writes it) always; Properties when the ticket has any, as short always/never sentences; Acceptance criteria; Decisions where a call needs its mark; User stories, Testing seams, Out of scope and Fog only when they have content; Comments. (you, r2) Whether a ticket whose deliverable is an answer keeps its own Question and Answer sections: open → Q4.

**The parser**

- One parser, a script in the tracker skill on PATH, called by every script that reads tickets: `board.py`, `property_coverage.py`, `dispatch` (`notes_of`, the `^status:` reads), `dispatch-ctl`, `run-worker.sh`. (you, r1) When it refuses: open → Q5.

**The build**

- Three child tickets: the parser and its tests first; then, in parallel, the scripts moved onto the parser and the new model, and the prose (tracker, grilling, to-tickets, orient, dispatch, code-review, the worker contract, the glossary) in one worker. This ticket's own close-out review is the pass over the whole output. (you, r2)
- The live tracker is converted by the scripts ticket's worker, with judgment, not by a migration script: each feature's `spec.md` becomes a top-level ticket and its `NN-slug.md` tickets its child tickets. A shipped feature whose tickets are all done is retired instead of converted. (you, r2; the retire rule my call)
- The build starts from master once board-orients has merged. (you, r2)

## Open questions

- **Q4: whether a ticket whose deliverable is an answer stays its own kind.** Today a decision ticket carries a `type` (research, prototype, grilling, legwork), a Question section and an Answer section, and dispatch routes it by type instead of spawning a worker. Options sketched by the agent, frame unconfirmed:
  - (a) Every ticket is Brief plus Acceptance criteria. "Decided, and recorded in the parent ticket's Decisions" is a criterion like any other. The one fact dispatch needs is whether the ticket needs the user in the loop (a grilling, hands-on legwork), a single frontmatter field; research and prototypes go to a worker like any build and are ruled on their review page.
  - (b) Keep the decision ticket and its four types.
- **Q5: what refuses a mismatch, and when.** Options sketched by the agent, frame unconfirmed:
  - (a) An mx plugin hook that runs the parser on every ticket file an agent writes, plus every reader refusing with file and line.
  - (b) A git pre-commit hook on `agent/tickets/**`, plus the readers.
  - (c) The readers alone.

## The incident

`dispatch review` builds a review page's notes from the ticket's `Assumptions` bullets (`notes_of` in `mx/skills/dispatch/dispatch`), one line at a time. board-orients 10's worker wrapped its bullets at about 100 columns, as the Markdown renders fine that way, so every note on its page ends mid-sentence: "a relayed question carries two numberings, the ticket's and". 02 and 04 wrap the same way. `notes_of` already refuses a bullet that doesn't match its pattern, but a continuation line isn't a bullet, so nothing refused it.

The board shows the same kind of drift in how it renders Markdown. `board.py` uses Python-Markdown, which nests a list only under four spaces of indent, where GitHub and CommonMark take three. So a Question list whose options are indented three renders on the board as flat numbered items. The writer followed one Markdown and the reader implements another.

## What reads a ticket today

As of board-orients' chain (tickets 01 to 10) plus master:

| construct | written by (the rule) | read by |
| --- | --- | --- |
| frontmatter: `status`, `type`, `blocked-by`, `diff`, `gh`, `priority`, `size` | `/mx:tracker` MARKDOWN.md | `board.py` (YAML); `dispatch`, `dispatch-ctl`, `run-worker.sh` (each an `awk`/`sed` match on `^status:`; `run-worker.sh` takes the first `status:` line anywhere in the file) |
| H1 as the short name, `## Brief` | MARKDOWN.md, `/mx:to-tickets` | `board.py` |
| `## Questions`: `- [Dn] **headline** detail` with `Ruled <date>:` under it | MARKDOWN.md, worker contract, `/mx:dispatch` | `board.py` |
| `Assumptions`: ``- A<n> `path:line`: text``; `Addressed: C1, C4` | worker contract (`worker-prompt.md`) | `dispatch` (`notes_of`, jq) |
| `## Acceptance criteria` checklist, `Property P<n>, <disposition>:` | `/mx:to-tickets` | `board.py` (04), `property-coverage` |
| spec `## Properties`: `- P<n> …` | `/mx:grilling` SPEC-FORMAT | `property-coverage` |
| spec frontmatter `status: draft \| confirmed` | SPEC-FORMAT | `board.py` |
| spec marks (`(you, r5)`, `(my call, r8; unconfirmed)`), the Testing Decisions' dispositions | SPEC-FORMAT, `/mx:grilling` | agents only: the Spec reviewer, `/mx:to-tickets`, workers anchoring assumptions to a mark |

## Acceptance criteria

- [ ] Q4 and Q5 are decided and recorded above; options outside the lists count.
- [ ] Every construct in the table above has an owner: read through the parser, merged, or dropped.
- [ ] The three child tickets are filed with `parent: ticket-file-contract`.
- [ ] This ticket's close-out review has run over the whole output.

## Comments
