---
status: claimed
priority: 1
size: L
---

# One kind of ticket, read by one parser

## Brief

The tracker has three kinds of file, a feature's `spec.md`, a feature's `NN-slug.md` ticket and a standalone `<slug>.md` ticket, and every stage of the workflow branches on which one it holds: the tracker's layout and retire rules, grilling's absorb step, dispatch's case detection, code-review's spec lookup, the board's two classes, orient's ticket-or-spec step. Each branch is more prose, more tokens and more edge cases, and deciding whether work gets a spec is one more branch. At the same time, agents write ticket files by following prose in the skills while several scripts parse them with their own regexes, and a writer's drift from a reader's expectation drops text silently (The incident, below).

This ticket replaces the three kinds with one: a ticket, which can have child tickets. A ticket file has one format and one parser every script calls, so a mismatch fails loudly where the text was written.

Filed on the user's request on 2026-09-23, at priority 1. Grilled from the architecture review of that day (`~/Downloads/show/architecture-review-2026-09-23/`); round 2 is drawn at `agent/show/ticket-file-contract/index.html`.

## Properties

(you, r5; P2's reach open → Q6)

- P1 Text a writer put in a machine-read part of a ticket is read whole or refused with its file and line, never dropped.
- P2 Every machine-read construct has one parser, and every script reads tickets through it.
- P3 A reference (`parent`, `blocked-by`, `<slug>#P<n>`) that names no ticket or property is refused with its file and line.
- P4 Wherever a worker or a reviewer is given a ticket's context, it is the ticket's body plus every ancestor's body, assembled by one function. The correctness and standards reviewers are given none on purpose: they judge the diff against the code alone.
- P5 No skill, script or glossary entry distinguishes tickets by kind beyond whether a ticket has child tickets and whether it needs the user in the loop.

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

- Sections: Brief (the intent and why, as a technical stakeholder writes it) always; Properties when the ticket has any, as short always/never sentences; Acceptance criteria; Decisions where a call needs its mark; User stories, Testing seams, Out of scope and Fog only when they have content; Comments. (you, r2)
- There is no decision ticket. A ticket whose deliverable is an answer is a ticket like any other: its acceptance criteria say what is decided, and the answer lands in the parent ticket's Decisions (its own, for a top-level ticket), the reasoning in its Comments. The four types (research, prototype, grilling, legwork) go. One frontmatter field says a ticket needs the user in the loop (a grilling, work only the user can do), and dispatch keeps that ticket from a worker; every other ticket, research and prototypes included, goes to a worker and is ruled on its review page. (you, r3)
- Research lands in the ticket that asked for it: the gist, the sources, the answers its criteria asked for. Extra detail too long for the ticket goes to `agent/research/`, only when there is some; what the user has to see or understand is a `/mx:show` artifact. `/mx:research` is trimmed to that. (you, r3 and r4)
- `/mx:to-tickets` is overhauled, possibly into a companion file of the tracker skill read when a ticket is split into child tickets. (you, r4; where it lands is the prose worker's call)

**The parser**

- One parser, a script in the tracker skill on PATH, called by every script that reads tickets: `board.py`, `property_coverage.py`, `dispatch` (`notes_of`, the `^status:` reads), `dispatch-ctl`, `run-worker.sh`. (you, r1)
- A mismatch is refused at commit, by a git pre-commit hook that runs the parser over the staged ticket files, and again by every reader, each naming the file and line. (you, r3) The hook is installed per repo: `/mx:project-setup` wires it, and dispatch wires it into the repo it stages on a worker host. (you, r4)

**The build**

- Three child tickets: the parser and its tests first; then, in parallel, the scripts moved onto the parser and the new model, and the prose (tracker, grilling, to-tickets, orient, dispatch, code-review, the worker contract, the glossary) in one worker. This ticket's own close-out review is the pass over the whole output. (you, r2)
- The live tracker is converted by the scripts ticket's worker, with judgment, not by a migration script: each feature's `spec.md` becomes a top-level ticket and its `NN-slug.md` tickets its child tickets. (you, r2)
- The last step of this ticket's close-out is one cleanup commit that brings the whole tracker in order: work that shipped without being retired (`figures-and-demos`, for one) is retired, stale tickets are closed or rewritten. (you, r5)
- The build starts from master once board-orients has merged, and the child tickets were written against the master before it: each worker reads what board-orients landed first (it removed the needs-human queue files, for one). (you, r2)

## Open questions

- **Q6: how far the parser reaches.** Whether it only reads and checks ticket files, or becomes a `tracker` command every mechanical tracker operation goes through (filing, status changes, rulings, the frontier, retiring), with the tracker skill keeping only the judgment. Drawn at `agent/show/ticket-file-contract/tracker-cli.html`.

## Testing seams

The parser's command line is the one seam. P1 to P3 are executable there, as checks over generated ticket files, built by the parser's own ticket. P4 is executable at the same seam once the context assembly exists. P5 is reviewed: by each child ticket's review and by this ticket's close-out. (my call, r3)

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

- [x] Every question the grilling raised is decided and recorded above.
- [ ] Every construct in the table above has an owner: read through the parser, merged, or dropped.
- [ ] The three child tickets are filed with `parent: ticket-file-contract`.
- [ ] This ticket's close-out review has run over the whole output.

## Comments
