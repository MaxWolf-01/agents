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

(you, r5 and r6)

- P1 Text a writer put in a machine-read part of a ticket is read whole or refused with its file and line, never dropped.
- P2 Every machine-read construct has one parser, in the `tracker` command, and every script reads and writes tickets through that command.
- P3 A reference (`parent`, `blocked-by`, `<slug>#P<n>`) that names no ticket or property is refused with its file and line.
- P4 Wherever a worker or a reviewer is given a ticket's context, it is the ticket's body plus every ancestor's body, assembled by one function. The correctness and standards reviewers are given none on purpose: they judge the diff against the code alone.
- P5 No skill, script or glossary entry distinguishes tickets by kind beyond whether a ticket has child tickets and whether it needs the user in the loop.
- P6 Retiring never loses anything irrecoverably: a tracked file leaves by `git rm`, so history keeps it; an untracked file is moved out of the repo to `~/logs`, unless it is a render whose generating source is tracked, which alone may be deleted. Deleting anything else takes the user saying so.
- P7 A worker never writes a ticket file; everything a worker produces reaches the ticket through the session that orchestrates it. (you, r7)
- P8 Nothing the workflow produces is committed to the code repo: its history holds code alone. (you, r8)

## Decisions

**Data model**

- One kind of file: the ticket, flat at `agent/tickets/<slug>.md`, with an optional `parent: <slug>`. The hierarchy goes as deep and as wide as the work needs. (you, r1)
- The slug is the ticket's id; `parent` and `blocked-by` name slugs, one reference form. A slug is descriptive enough to recognise the ticket from it alone, in the spirit of `/mx:session-name`'s names; agents say the slug to the user rather than a number. No short hash beside it until practice asks for one. A rename is a string replace of the unique slug across the tracker, read over as a diff; a script for it only once renames recur. (you, r2)
- `agent/` is always its own git repo, at `<code repo>/agent/`, and the code repo ignores it: tickets, their claim, review and done commits, show directories, prototypes and research notes are all committed there, and the code repo's history holds code alone. Every tool finds it at `<the code repo's main checkout>/agent/`, with no setting. (you, r8; amended 2026-09-25, was: the tracker is the code repo's own `agent/tickets/` or one another repo names with `git config mx.tracker`, show directories on code branches)
- A ticket file is committed in the agent repo's own checkout, on the branch it has out, and never on a work branch; ticket commits need no branch or merge of their own. (you, r7 and r8; amended 2026-09-24, was: committed on its parent ticket's branch)
- Only the orchestrator and the sessions working with the user write ticket files, always through `tracker`. A worker is handed its ticket's context and gets both repos on its host, each on a `ticket/<slug>` branch: it commits code in the code repo, and its demo, figures and report (its closing comment, questions and assumptions) under `agent/show/<slug>/` in the agent repo, never touching `agent/tickets/`. The committed report is the finished signal; `dispatch review` reads it off the agent branch and brings it into the ticket. (you, r7 and r8; amended 2026-09-25, was: the report a file outside the worktree)
- A review page shows both ranges, a landing merges both branches, and a ticket's `diff:` records both, named `code` and `agent`, the only two repos a ticket has. (you, r8)
- One agent repo serving several code repos (the same `agent/` linked into each) is out of scope; it would need each ticket to name its code repo again, and `one-tracker-per-user` is where it is weighed. (you, r8)
- This repo's `agent/` is split out with its history by `git filter-repo --subdirectory-filter agent` once this ticket's work is on master, as part of its close-out; a dry run on a fresh clone of master on 2026-09-25 kept every commit touching `agent/` (606, trailers intact) and every file, with retired files still found by `git log --diff-filter=D`. (you, r8)
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

**The tracker command**

- One `tracker` command in the tracker skill, on PATH, owns every mechanical operation on ticket files, reads and writes: the check, a field, the whole tracker as data, a ticket's context, the frontier, filing, status changes along the tracker's transitions, recording a ruling, retiring. Every script that touches tickets goes through it: `board.py`, `property_coverage.py`, `dispatch` (`notes_of`, its status reads and writes), `dispatch-ctl`, `run-worker.sh`. The ticket body stays prose the agent writes. (you, r1 and r6)
- `tracker --help` states the function (subcommands, flags, arguments, what each returns or refuses); the tracker skill states the concepts and the flow; neither repeats the other. The skill can embed the `--help` output so it loads with the skill. The skill shrinks to at least half its size. (you, r6)
- Retiring runs the tracker's recipe and prints each step it ran; the commit stays with the caller. (you, r6)
- A mismatch is refused at commit, by a git pre-commit hook that runs `tracker`'s own check over the staged ticket files, and again by every reader, each naming the file and line. Since the hook fires on every commit, no skill has to tell an agent to run the check. (you, r3 and r6) The hook is installed where ticket files are written, the agent repo on the user's machine, and `/mx:project-setup` wires it; a worker host gets none, since nothing there writes a ticket. (you, r4 and r8; amended 2026-09-25, was: dispatch also wires it into the repo it stages on a worker host)

**The build**

- Three child tickets: the `tracker` command and its tests first; then, in parallel, the scripts moved onto the parser and the new model, and the prose (tracker, grilling, to-tickets, orient, dispatch, code-review, the worker contract, the glossary) in one worker. This ticket's own close-out review is the pass over the whole output. (you, r2)
- The live tracker is converted by the scripts ticket's worker, with judgment, not by a migration script: each feature's `spec.md` becomes a top-level ticket and its `NN-slug.md` tickets its child tickets. (you, r2)
- The last step of this ticket's close-out is one cleanup commit that brings the whole tracker in order: work that shipped without being retired (`figures-and-demos`, for one) is retired, stale tickets are closed or rewritten. (you, r5)
- The build starts from master once board-orients has merged, and the child tickets were written against the master before it: each worker reads what board-orients landed first (it removed the needs-human queue files, for one). (you, r2)

## Testing seams

`tracker`'s command line is the one seam. P1 to P4 and P6 are executable there, as checks over generated ticket files and fixture trackers, built by `tracker-command-and-commit-check`. P5 is reviewed: by each child ticket's review and by this ticket's close-out. (my call, r3)

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

Rulings of 2026-09-24 on the two sibling builds, relayed in chat:

- `property-coverage` holds every property a ticket states to being cited by some acceptance criterion in the tracker, since the executable-or-reviewed disposition is no longer machine-read: accepted.
- A `Ruled <date>:` line written as a continuation of a question rather than a bullet of its own is refused by `tracker check`, since read as the question's detail it would leave the question open with nothing saying why: left to the orchestrator, who takes the refusal.
- `/mx:to-tickets` becomes `mx/skills/tracker/SLICING.md`: accepted.
- The release that ships this is a major version. Other repos' trackers are converted by the user, on demand; no ticket per repo.
- Open, drawn at `agent/show/ticket-file-contract/open-points.html`: where a build's questions get their answers, light review and the ticket's context, the tracker skill's size, the README figures.
