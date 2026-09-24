---
status: open
priority: 2
size: XL
---

# Session page: a session's answers on one page, the chat reply a link to it

## Brief

A session whose answers need more than a line gets one session page, re-rendered as each turn ends: its title, brief and resume command, the questions waiting on the user, then the turns newest first with their artefacts linked. The chat reply becomes one line and the page's link. A spec gets a spec page of its own, the design rendered with its figures inside it, which replaces diffview as the place a spec is read.

Grilled from the session-page rounds; round 3 is drawn at `agent/show/session-page/round-3/pages.html`. The build starts once `board-orients` has merged.

## Problem Statement

Every answer an agent gives lands in the terminal, and the terminal renders prose, code and diffs as text and nothing else. A figure, a before/after pair side by side or a rendered page cannot show there, so the agent describes what it would have shown, or builds an artifact that opens in a tab of its own and leaves its link in the chat, where it scrolls away with the next turn. A returning user cannot find what a session produced, and with a dozen sessions open cannot tell which pane holds which work.

The reply also restates what the artifact shows, so the user reads the same thing twice, and the user reads only the last message of a turn anyway. A line asking them to acknowledge calls that need no decision costs attention and asks for nothing.

The spec has the same problem one level up. It is read on diffview as a markdown diff, where its figures do not show and the design reads as source; the user has never reviewed a spec there, and specs have gone under-reviewed because of it.

## Solution

A session whose answers need more than a line gets one **session page**, opened once in the browser and re-rendered as each turn ends. It is a container: at the top the session's title, a short brief, the command that resumes it, and the questions waiting on the user; below, the turns newest first, each with its headline, the user's message, a short details block and links to the artifacts it produced, older turns collapsed. Artifacts are pages of their own and open in a new tab. The chat reply is one line and the page's link.

A feature's spec gets a **spec page**: the spec rendered in the house style with its figures inside it and the current round's changes marked. It replaces diffview as the place a spec is read.

Neither page is written by hand. The agent writes plain text files, a turn record shaped like a ticket and the spec as it is today; a renderer turns them into the pages as the turn ends, and every artifact is built by a subagent or a fork.

How the pages fit together, and one turn in order: [pages.html](../show/session-page/round-3/pages.html).

## User stories

1. As the user, I want a turn's artifacts linked from the turn and opening in a new tab, so that each artifact gets the whole window and the session page stays a list I can scan.
2. As the user in the terminal, I want the reply to be one line and the page's link, so that I read the answer once, on the page, after the turn has ended.
3. As the user, I want the questions waiting on me always at the top of the session page, so that I never scroll to find them.
4. As the user, I want only real questions asked, with every call I need not rule on kept out of the reply and out of the top, so that I am never asked to acknowledge something that needs no decision.
5. As the user returning to a session, I want its title, a brief of what it is about, and the turns newest first with the older ones collapsed, so that I know where it stands before reading any turn.
6. As the user, I want my own message with each turn, whole, one click away, so that a turn read later says what it answered.
7. As the user, I want one short details block per turn rather than many folds to open, so that reading a turn takes one look.
8. As the user, I want every part of both pages reachable by keyboard, on the keys diffview uses for the same moves, so that my muscle memory carries over.
9. As the user, I want one key to copy the session's resume command, one to open the spec page, and one per link to open it, so that I never reach for the mouse to act on a turn.
10. As the user with a dozen sessions open, I want the page to carry its session's resume command, so that I can close panes freely.
11. As the user on the board, I want each session listed on a ticket to link its session page, and a feature's row to link its spec page, so that I reach a session's work and a feature's design from the work.
12. As the user asking a quick question, I want no page to appear, so that a one-line answer stays a one-line answer.
13. As the user judging a grilling round, I want the spec as a rendered page with its figures inside and this round's changes marked, so that I review the design itself and not its markdown source.
14. As the user in a grilling, debugging or planning session, I want to decide in front of visuals, so that a round, a hypothesis or a plan is judged as a render.
15. As the agent, I want a turn to be a file shaped like the ticket files I already write, so that no markup of its own has to be taught to every session.
16. As the agent, I want to write no HTML at any step, and hand every artifact to a subagent or a fork, so that render loops never fill the session's context.
17. As the agent, I want a turn record that does not parse sent back to me with the reason, so that a broken record never renders as half a turn.
18. As the agent ending a turn with its answer in the chat and no turn record, I want to be sent back to move it onto the page, so that the terminal never carries the answer by accident.
19. As a later session, I want session pages outside git, so that conversation residue is never read as a tracked artifact.

## Properties

- P1 The top of the session page holds open questions and nothing else; a question a later turn answers or supersedes leaves it.
- P2 A turn's record is the only source of its section, and the session page is regenerated from the records and the transcript alone.
- P3 A session that never needed a page writes nothing under `agent/sessions/`.
- P4 A move either page shares with diffview is on diffview's key.
- P5 The chat reply of a session that has a page is one line and the page's link.
- P6 The main session writes no HTML.
- P7 The spec page shows every figure the spec links, and marks exactly what changed since the previous round's commit.
- P8 A turn record that does not parse is sent back and never rendered.

## Acceptance criteria

- [ ] Every child ticket is done, and this ticket's close-out has run over the whole output.
- [ ] `session-page#P1`, `session-page#P2`, `session-page#P3`, `session-page#P7` and `session-page#P8` hold as checks at the three seams the Testing seams name.
- [ ] `session-page#P4`, `session-page#P5` and `session-page#P6`, reviewed: the keys, the shape of the chat reply, and that the main session writes no HTML.

## Decisions

### The session page

- **One page per session**, linking into the work's artifacts, not one per feature or ticket: a session's turns belong to it, and a session often spans several tickets or none.
- **A container of links.** Artifacts are pages of their own, open in a new tab, and have the full freedom `/mx:show` gives them; nothing is framed into the session page.
- **Layout.** Top-down: the session's title, its brief and the resume command, then the open questions, then the turns newest first, the newest open and the older ones collapsed. A turn shows its headline, the user's message whole behind one click, its details block, and its links.
- **Keys**, diffview's where a move has one: `j`/`k` between blocks, `o`/Enter to open or close one, `O` for every turn, `gg`/`G` to the ends, `?` for the key list, `y` to copy the resume command. Moves diffview has no key for take their own: `S` opens the spec page, `1` to `9` the focused turn's links, and on the spec page `d`/`D` jump to the next and previous change.
- **Only questions ask.** A call that needs the user is a numbered question; every other call is detail, a mark in the draft spec, and no line asks the user to acknowledge it. `/mx:grilling`'s end-of-round re-listing of unconfirmed calls leaves the reply.
- **The chat reply** is one line and the page's link.

### The turn record

- **Fields, not a markup.** A turn is `turns/NN.md` in the shape of a ticket file: frontmatter for what the renderer reads as data (`answered`, `superseded`), an H1 that is the turn's headline, and three fixed sections, `## Questions`, `## Links`, `## Details`, any of them absent when the turn has none. A question is written as a ticket's questions are in `board-orients` (`- [Q7] **headline** detail`), with its options as sub-items and the pick marked. Details is plain markdown, short. The worked example is this session: `agent/prototypes/session-page/sample/`.
- **Records are written once and never edited.** A question clears through the frontmatter of the turn that received the answer: `answered` holds the option's letter, or the user's own words when the answer was neither option; `superseded` names the question that replaced it. A ticket's question clears through a `Ruled` line under it instead (`board-orients`), since a ticket is edited in place. Links in a record are paths from the repo root, which the renderer resolves, so a record reads the same wherever the session directory sits.
- **The session record** is `session.md` beside the turns: frontmatter with the session id, the repo and the spec's path, an H1 title and a `## Brief`. The agent writes it when the page is created and rewrites the brief when the session's scope moves.
- **The user's message is not the agent's to write.** The renderer reads it from the session's transcript: the user's own messages and the ones queued mid-turn, whole.

### The spec page

- **The spec rendered**, in the house style, from `spec.md` as it stands: the marks as small tags (written bare or in code spans), each figure the spec links shown inside it, and the changes since the previous round's commit marked in place. A link into the feature's show directory is what makes a figure; nothing else marks one. `spec.md` stays the source an agent reads and the work order a worker builds from.
- **It replaces diffview for specs.** `/mx:grilling`'s round opens the spec page instead of a diffview page on the spec.
- **In this feature, as its own slice**, since a grilling round changes both pages at once and they share a renderer.

### Producing the pages

- **One fixed renderer** turns the records into the session page and the spec into the spec page.
- **The agent writes no HTML, and every artifact is built by a subagent or a fork** through `/mx:show`, which keeps the render loops out of the session's context. A small figure now costs a spawn.
- **The main session waits for a turn's artifacts** before it writes the record, so every link in the record points at a page that exists.
- **The Stop hook** validates the turn record and sends back one that does not parse, sends the agent back when it answered in the chat and wrote no record (in a session that has a page, a reply longer than three lines with no record written this turn), and renders both pages. Rendering is a pure function over the files and runs in milliseconds, so no process runs between turns. How an open tab learns to reload (a served page as diffview's are, or polling) is an interchangeable part behind that seam; left undecided, the page is right on a manual reload.
- **Review.** An artifact's prose is reviewed inside `/mx:show` as it is built, so its rules have one home and every artifact gets them. `chat_review.py`'s hook on the chat reply goes, since the reply is one line. The turn record's own prose gets a light review as the turn ends: Opus 5.5 at medium effort, against the catalogue's rules for chat, seeing what the reader of the page has seen (the session's earlier turn records and the user's messages, no tool calls), and handing at most three findings back to the agent, which revises the record before the page renders.
- **The reviewer's harness**, from the chat-review audit of 2026-09-22, whose data travels with [Ablate the prose reviewer](reviewer-ablation.md): its own system prompt instead of Claude Code's persona, which otherwise answers the text instead of reviewing it; the record fenced in tags; the answer bound to a JSON schema; a finding dropped when its quote is not a substring of the record; and the turn record's shape given to it, with the structure that shape requires exempt by name. On a page a revision costs only the review's seconds, since a revised record re-renders and is not reprinted.
- **Created lazily** by the first turn whose answer needs more than a line; a `qq` never gets a page.
- **Where it lives.** `agent/sessions/<session-id>/`, ignored through the global git ignore list in dotfiles (`nix/home/common.nix`, beside `agent/handoffs`). Keyed by the session id, which the hook receives. The session page is `index.html` in that directory; the spec page is `spec.html` beside its `spec.md`, untracked like the board, since both regenerate from their sources.

### Floors

- **The prototype at `agent/prototypes/session-page/` is the quality floor** for both pages: their layout, their keys, the turn record's shape. `agent/show/session-page/round-3/pages.html` shows how the pages fit together and one turn in order.

### Around it

- **The build starts once `board-orients` has merged**: that feature rebuilds the board this one links into, and settles the ticket file's shape the turn record copies.
- **The board**, after `board-orients` merges: its spec lists a ticket's sessions from `Session:` commit trailers with a resume copy button; this feature links each listed session to its session page and each feature's row to its spec page.
- **The user replies in the terminal.**
- **Questions and the board.** A session's open questions live on its session page. One the session ends with still open becomes a decision ticket, as `/mx:grilling` already has it, and the board shows it there, since in `board-orients` every question on the board belongs to a ticket.
- **Reverses a call of `figures-and-demos`**, which put "rendering the grilling round as a page" out of scope as duplicating diffview. The diff shows the code that finally ships; a round, a debugging session or a planning session decides in front of visuals.
- **Claude Docs is not the page.** The claude.ai living-docs connector does this as a hosted product; it would send repo content to claude.ai, tie the pages to one harness, and show no local file.

## Testing seams

Three seams. The session renderer: a session directory and a transcript in, the page out; the oracle is the worked example in `agent/prototypes/session-page/sample/` and the Properties. The spec renderer: a spec, its figures and a base commit in, the page out; the oracle is a spec with one figure and one changed section. The Stop hook at its input: the hook's JSON and the session directory in, its decision out (render, send back with a reason); `chat_review.py`'s tests are the prior art, and the reviewer is stubbed there as they stub it. P1, P2, P3, P7 and P8 are executable at those seams; P4, P5 and P6 are reviewed.

## Out of scope

- The grid's words: [The grid's words in /mx:show](show-grid-words.md), their own change once `figures-and-demos` merges.
- Tuning the prose reviewer (model, effort, prompt, context) against labelled data: [Ablate the prose reviewer](reviewer-ablation.md).
- Replying on the page.
- An agent review of a spec before its gate: not decided; its own decision ticket if it is wanted.

## Fog

None.
