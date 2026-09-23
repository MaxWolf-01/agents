# Session page and spec page: answer

## The question

What a session page and a spec page look like, and what an agent writes so that a renderer can produce them, judged on this session's own content rather than on a sketch.

## What was tried

- Round 2: a session page built by hand, with artifacts framed inside it and turn bodies written in a markdown dialect (`before`/`after` fences, a link alone on a line becoming a button). `agent/show/session-page/round-2/index.html`.
- Round 3: `render.py`, a fixed renderer over ticket-shaped turn records and the spec's markdown, run on `sample/` (this session, max's messages copied verbatim from the transcript). Its outputs are `agent/show/session-page/round-3/session.html` and `spec.html`, with `pages.html` beside them showing how the pages fit together.

## Verdicts, max's, 2026-09-23

- **A turn is fields in a ticket's shape, never a markup of its own.** A dialect has to be taught to every session that writes a turn, whereas the ticket's shape (frontmatter, a heading, fixed sections) is already written by all of them. Max: "we definitely don't want to invent some DSL".
- **The session page holds links, and artifacts open in their own tab.** Each artifact keeps the full freedom `/mx:show` gives it and gets the whole window; framing round 1 inside the page was the wrong call.
- **One details block per turn.** Max: "I don't want to click 10 details thingies".
- **The user's own message is shown whole, one click away.** A turn read later then says what it answered, and the page becomes a view of the session worth keeping.
- **`y` copies the resume command and `S` opens the spec page.** Max was missing keys in round 1; every move sits on the keyboard, on diffview's key wherever diffview already has that move.
- **The spec page replaces diffview for specs.** Max never reviewed a spec as a diffview markdown diff, and specs went under-reviewed for it. On the spec page the figures sit inside the spec and this round's changes are marked.
- **The chat reply is one line and the link.** The page is read once the turn has ended.
- **No line asks the user to acknowledge a call.** A call either needs a decision and is a numbered question, or it is detail. Max, on "9 calls of mine wait on the page": "either I need to decide or I don't".

## Floor

Max, 2026-09-23: "this prototype definitely is the floor for the real implementation", with nothing in it to criticise. The floor covers both pages as `render.py` produces them from `sample/`: the layout, the keys, the turn record's shape, the open questions at the top, the spec page's in-place change marks and embedded figure. The real implementation matches it or consciously beats it; the prototype's incidental choices (fallback heuristics, the sample's message splitting) are not part of the floor.

Regenerate both pages from the worktree root:

```
agent/prototypes/session-page/render.py session agent/prototypes/session-page/sample -o agent/show/session-page/round-3/session.html
agent/prototypes/session-page/render.py spec agent/tickets/session-page/spec.md --base 185d279 -o agent/show/session-page/round-3/spec.html
```

`NOTES.md` beside this file has what building the renderer ran into.
