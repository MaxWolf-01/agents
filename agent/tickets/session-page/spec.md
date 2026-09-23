---
status: draft
---

# Session page: a session's answers on one page, the chat reply as its index

## Problem Statement

Every answer an agent gives lands in the terminal, and the terminal renders prose, code and diffs as text and nothing else. A figure, a before/after pair side by side, a rendered page or an embedded demo cannot show there, so the agent describes what it would have shown, or builds an artifact that opens in a tab of its own and leaves its link in the chat. The link scrolls away with the next turn. A returning user cannot find what a session produced, and with a dozen sessions open cannot tell which pane holds which work.

The reply also restates what the artifact already shows, so the user reads the same thing twice, and the user reads only the last message of a turn anyway: a long reply is where they stop reading. A line asking them to acknowledge calls that need no decision ("9 calls of mine wait on the page") costs attention and asks for nothing.

## Solution

A session whose answers need more than a few lines gets one page, opened once in the browser, that re-renders as the session goes. What needs the user sits at the top; below it the turns run newest first, each carrying its full answer with its artifacts inline, older turns collapsed. The chat reply becomes the page's index: one line on what happened, the link, and each question on one line, answerable from the terminal. The page carries the command that resumes its session, and the board lists every session that touched a ticket, each opening its page. `(you, r1)`

One turn reaching the page, in order: [round-2/index.html](../../show/session-page/round-2/index.html), section "how a turn reaches the page". `(figure, r2)`

## User Stories

1. As the user reading a turn, I want its figures, before/after pairs and rendered pages inline on one page, so that I see what the agent means instead of reading a description of it.
2. As the user in the terminal, I want the reply to be one line, the page's link and the questions, so that I can answer without opening the browser and open it when I want the why.
3. As the user, I want the questions waiting on me always at the top of the page, so that I never scroll to find them.
4. As the user, I want only real questions at the top and in the chat, and every call I need not rule on kept in the detail, so that I am never asked to acknowledge something that needs no decision.
5. As the user returning to a session, I want the turns newest first with the older ones collapsed, so that the latest state is what I see first and the history is one keystroke away.
6. As the user, I want every part of the page reachable by keyboard, on the keys diffview uses for the same moves, so that my muscle memory carries over.
7. As the user reading a turn later, I want my message collapsed above the answer it got, so that the turn says what it answered.
8. As the user, I want the spec's review page and any other whole page linked as a button that opens its own tab, so that the browser does the window management.
9. As the user with a dozen sessions open, I want the page to carry its session's resume command, copyable, so that I can close panes freely.
10. As the user on the board, I want every session that touched a ticket listed on that ticket, each opening its session page and offering its resume command, so that I reach a session's work from the work.
11. As the user asking a quick question, I want no page to appear, so that a one-line answer stays a one-line answer.
12. As the user in a grilling, debugging or planning session, I want the round's figures and questions on the page and the spec's delta on diffview, so that I decide in front of visuals and neither surface repeats the other.
13. As the agent, I want to write a turn's answer as markdown with its figures embedded by path, so that a turn costs what a chat reply costs today and no HTML is written per turn.
14. As the agent, I want a small fixed set of blocks (a figure, an embedded page, a before/after pair, a question) and raw HTML where they fall short, so that a turn can show anything while the layout stays the same from turn to turn.
15. As the agent ending a turn with a long reply and no page body, I want to be sent back to move it onto the page, so that the terminal never carries the body by accident.
16. As the agent, I want the turn's body reviewed for prose tells as the turn ends, so that the review the chat reply had follows the content onto the page.
17. As a later session, I want session pages outside git, so that conversation residue is never read as a tracked artifact.

## Properties

- The top of the page holds open questions and nothing else; a question answered in a later turn leaves it.
- A turn's body file is the only source of its section, and the page is regenerated from the bodies alone.
- A session that never needed a page writes nothing under `agent/sessions/`.
- A key the page binds does what the same key does in diffview wherever diffview binds it.
- The chat reply of a session that has a page carries no body: the line, the link and the questions.

## Decisions

- **Two features.** The grid's words (prose, concept figure, concept diff, code listing, code diff, output, output diff) land in `/mx:show` as a change of their own once `figures-and-demos` merges; this spec is the page. `(you, r1)`
- **One page per session**, linking into the work's artifacts rather than per feature or ticket: a session's turns belong to it, and a session often spans several tickets or none. `(you, r1)`
- **The chat reply is the index**: one line, the link, one line per question. `(you, r1: read from your "today versus proposed" and your strike of the calls line; unconfirmed as a reading)`
- **Only questions ask.** A call that needs the user is a question with a number; every other call is detail, on the page and as a mark in the spec, and no line asks the user to acknowledge it. This moves `/mx:grilling`'s end-of-round re-listing of unconfirmed calls out of the reply: the marks stay, the nagging goes. `(you, r1)`
- **Layout.** Top-down: the open questions, then the turns newest first, older ones collapsed, each with the user's message collapsed above the answer. Every part keyboard-reachable, on diffview's keys where a move has one (`j`/`k` between items, `o`/Enter to open one, `O` for all, `g`/`G` to the ends, `?` for the key list, `y` to copy). `(you, r1; the user's message per turn is my call)`
- **Markdown bodies, a fixed but flexible renderer.** The agent writes `turns/NN.md`; a renderer turns every body into the page in the house style. `(you, r1)` The interface: plain markdown; `![caption](path)` inlines an SVG so it takes the scheme, shows an image, or frames an HTML page; a `before` fence followed by an `after` fence renders as a pair side by side; a link alone on its line renders as a button that opens its own tab; the turn's questions section is lifted to the top while open; raw HTML passes through with the house classes available. `(my call, r2)` Whether a model lays the page out instead: `(open → Q4)`
- **One Stop hook replaces `chat_review.py`.** As a turn ends it renders the page from the bodies, sends the agent back when the reply is long and the turn wrote no body, and reviews the new body's prose with the catalogue `chat_review.py` uses today. `(my call, r2)` Whether a hook reviews at all: `(open → Q5)`
- **Rendering happens in the hook, not in a watcher.** A pure function over the bodies runs in milliseconds, so no background process per session exists to start, find or stop. How the open tab learns to reload (a served page, as diffview's are, or polling) is an interchangeable part behind that seam; left undecided, the page is still right on a manual reload. `(my call, r2)`
- **Created lazily** by the first turn whose answer needs more than the index; a `qq` never gets a page. `(you, r1)`
- **Where it lives.** `agent/sessions/<session-id>/`, ignored through the global git ignore list in dotfiles (`nix/home/common.nix`, beside `agent/handoffs`). `(you, r1)` Keyed by the session id, which the hook receives, with the session's title as the page title. `(my call, r2)`
- **Whole pages open in their own tab**, the spec's review page included; the page has no tabs of its own. Your skilltree ruling of 2026-08-15 decides it: no reinventing window management. `(my call, r2)`
- **Artifacts are inline.** An SVG, an image, an HTML page in a frame, a before/after pair all sit in the turn that produced them. `(you, r1)`
- **The board**, per ticket: every session that touched it, its title opening the session page and a copy button beside it for the resume command. Two controls, since opening a page should never overwrite the clipboard. Built after `board-orients` merges; recording which sessions touched a ticket is [A ticket records the sessions that touched it](../ticket-sessions.md). `(you, r1: wait for board-orients; two controls my call, r2)`
- **The user replies in the terminal.** `(you, r1)`
- **Reverses a call of `figures-and-demos`**, which put "rendering the grilling round as a page" out of scope as duplicating diffview. The diff shows the code that finally ships; a round, a debugging session or a planning session decides in front of visuals, which diffview does not carry. `(you, r1)`
- **Claude Docs is not the page.** The claude.ai living-docs connector does this as a hosted product; it would send repo content to claude.ai, tie the page to one harness, and show no local file. `(my call, r1)`

## Testing Decisions

Two seams. The renderer, bodies in and a page out, with worked examples as the oracle: a body per block and the section it must produce. The Stop hook at its input, the hook's JSON and the session's directory in and its decision out (render, send back, review findings), with the cases in the Decisions as the oracle; `chat_review.py`'s tests are the prior art. The first two Properties and the lazy-creation Property are executable at those seams; the key Property and the reply-shape Property are reviewed.

## Out of Scope

- The grid's words: their own change, above. `(you, r1)`
- Replying on the page. `(you, r1)`

## Fog

- How the page's open questions relate to the needs-human queue and the board's needs-me section, both being redesigned in `board-orients`; the queue may dissolve into the page.

