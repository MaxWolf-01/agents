---
status: open
type: grilling
priority: 1
size: M
---

# One contract for tickets and specs

## Brief

Agents write ticket files by following prose in the skills, and several scripts parse those files with their own regexes. When a writer's formatting drifts from what a reader expects, the reader drops the text without saying anything. The review pages of board-orients 02, 04 and 10 each lost every assumption past its first line that way. This session designs the conventions, their tests and at most a small automatic check, so that a mismatch fails loudly at the moment the text is written, and nobody has to remember to run anything. A spec is the same problem with its own format document, readers and instructions, so it is in scope, and so is whether a spec should be a kind of its own at all.

Filed on the user's request on 2026-09-23, at priority 1, after the incident below.

## The incident

`dispatch review` builds a review page's notes from the ticket's `Assumptions` bullets (`notes_of` in `mx/skills/dispatch/dispatch`), one line at a time. board-orients 10's worker wrapped its bullets at about 100 columns, as the Markdown renders fine that way, so every note on its page ends mid-sentence: "a relayed question carries two numberings, the ticket's and". 02 and 04 wrap the same way. `notes_of` already refuses a bullet that doesn't match its pattern, but a continuation line isn't a bullet, so nothing refused it.

The board shows the same kind of drift in how it renders Markdown. `board.py` uses Python-Markdown, which nests a list only under four spaces of indent, where GitHub and CommonMark take three. So this ticket's own Question list, whose options are indented three, renders on the board as thirteen flat numbered items. The writer followed one Markdown and the reader implements another.

## What reads a ticket today

As of board-orients' chain (tickets 01 to 10, unmerged) plus master:

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

Each reader carries its own reading of a rule that lives in prose elsewhere, and each writer is an agent reading that prose while generating, which is the rung PRINCIPLES.md §1 says washes out.

## Questions

1. **Where the format lives, once.** Options sketched by the agent, frame unconfirmed:
   - (a) One parser module in the tracker skill that every reader imports or calls. The format's prose shrinks to a pointer and an example, and the parser's tests are the format's spec.
   - (b) Keep separate readers, with one shared fixture corpus of real ticket files every reader's tests run against.
   - (c) Make the readers tolerant (join continuation lines, accept variations) and leave writers free.
2. **What catches a mismatch, and when, without anyone calling it.** Options sketched:
   - (a) The existing moments that already run code on a ticket refuse what they can't read, and name the line: `dispatch review`, the runner reading the `review` flip, and the board render. The worker is resumed with the refusal.
   - (b) A lint behind a git hook on `agent/tickets/**`.
   - (c) A `make check` target, which only runs if someone runs `make check`.
3. **Which constructs stay machine-read at all.** Every one in the table is a place writer and reader can disagree. Candidates to drop or merge: `Addressed:` against review comments resolved on the page, two question formats (`## Questions` and the closing comment's `[Dn]` details), the status read by four scripts four ways.
4. **Whether a spec is its own kind.** A ticket is where the facts about one piece of work live. A spec is a parallel file with a parallel lifecycle (`draft`, `confirmed` against a ticket's five statuses), its own format document, its own marks and rounds, and its own place in the directory layout, and it shares frontmatter, sections and the property ids with the tickets cut from it. Every difference is one more set of conventions, instructions and tests. Options sketched by the agent, frame unconfirmed:
   - (a) Keep the spec separate, under the same contract as tickets.
   - (b) The spec becomes a ticket with a `type` of its own (`spec`, or a decision ticket's), and a feature is that ticket plus the tickets that name it.
   - (c) A ticket can have child tickets, and a feature's spec is simply the parent's body.

   The glossary's **Feature**, **Spec**, **Gate** and **Round** entries, and the tracker's layout, move with whatever is decided here.
5. **What the contract's properties are**, stated as always/never rules the spec can dispose. For example: "text a writer put in a machine-read section is either read whole or refused with its line named, never dropped"; "one construct has one parser".

## Acceptance criteria

- [ ] The decision is recorded, with a spec or a build ticket for what gets built. Options outside the lists above count.
- [ ] Every construct in the table has an owner: kept with its one reader, merged, or dropped.
- [ ] Whether a spec stays its own kind is decided, and the glossary and the tracker's layout follow.
- [ ] Whatever checks the contract runs without an agent choosing to run it, and its failure names the file and line.
