# Session page renderer, prototype

`render.py` turns a session directory into its session page and a spec into its spec page. It is the one fixed renderer of the spec's Decisions, run on this session's own records in `sample/`, so both pages can be judged as renders.

## Running it

From the worktree root, with nothing installed beyond `uv`:

```
agent/prototypes/session-page/render.py session agent/prototypes/session-page/sample -o agent/show/session-page/round-3/session.html
agent/prototypes/session-page/render.py spec agent/tickets/session-page/spec.md --base 185d279 -o agent/show/session-page/round-3/spec.html
```

`--help` on either subcommand lists the flags. Each page looks for the other beside itself (`spec.html`, `session.html`). A record that does not parse prints `file:line: reason`, exits 1 and writes no page; that line is what the Stop hook would send back.

## What building it hit

### Keys

- **diffview binds `1` to `4`.** They switch its image views (`setImageView` in `diffview.html`). The Keys decision calls `1` to `9` keys diffview leaves free `(my call, r3)`, and a Property says a key either page binds does what diffview's does. Read strictly, `1` to `4` break that Property. Image views apply only to an image diff, which a session page never shows. Either the Property is worded "for a move both pages have", or link opening moves to other keys.
- **diffview's top is `gg`.** A first `g` arms and a second within half a second goes to the top. Both pages copy this, so their key lists show `g g` where the spec says `g`.
- **Next change on the spec page is `d`, previous is `D`.** `d` is free in diffview, whose `Ctrl-d` moves between directories. `D` deletes a focused comment in diffview; the spec page has no comments, so the two collide only if it gets them. `o` and Enter show what the focused change was.
- **The user's message has no key of its own.** Tab reaches its toggle and Enter opens it; `o` opens and closes the turn.
- **With no turn focused, `1` to `9` open the newest turn's links.** The spec does not say which turn they act on then.

### The record shape

- **`NN.you.md` loses the boundaries between queued messages.** The sample joins them with runs of blank lines, and dictation leaves blank lines inside a single message as well. The renderer splits on three or more blank lines, which gives turn 3 the four parts the round-2 mock showed and turn 4 seven. The transcript has the boundaries, so a reader of the transcript needs no such rule.
- **`answered` holds an option letter; real answers are often more.** The round-2 spec records Q2 as (a), read from the user's "today versus proposed" and marked unconfirmed as a reading. The renderer takes any string. A letter naming an option marks that option, and anything else shows as a free answer. The spec does not say what an answer is.
- **A turn's question and a ticket's question clear in different ways.** A turn's question clears through a later turn's frontmatter. A `board-orients` ticket's question clears through a `Ruled <date>:` sub-item under it. The item shape is shared and the clearing is not. The two meet where the Fog section files a session's open questions as decision tickets.
- **Links relative to `turns/` tie a record to where its directory sits.** The sample's `../../../../show/...` climbs four levels from `agent/prototypes/session-page/sample/turns/`. From `agent/sessions/<id>/turns/` the same target is three levels up. Links written from the repository root (`agent/show/...`) would survive the move.
- **Provenance marks are code spans in this spec and plain text in `board-orients`.** This spec writes `` `(you, r1)` ``; the board-orients spec writes `(you, r1)`. The renderer recognises only the code-span form, so the board-orients spec's marks render as running text. The spec does not say how a mark is written.

### What the spec leaves unsaid

- **Where the rendered pages live.** `agent/sessions/<session-id>/` holds the records. The spec names neither the session page's file nor the spec page's, nor whether a spec page is tracked. The pages link each other, so the renderer needs both paths. `session.md`'s `spec:` names the spec's markdown, not its page; the renderer shows it in the spec button's tooltip.
- **Which round a spec page shows.** The renderer has the base commit and no round number, so the page says "changes since 185d279 · 2026-09-23", the commit subject on hover.

### The spec diff

- **Sequence matching alone reads this round as mostly new and removed.** Round 3 regrouped the Decisions under `###` headings and rewrote many of them. The renderer pairs an edited block with its old version first by a shared bold lead (`**Layout.**`), then by overlap of rarer words, each word weighted by how few blocks use it. Unweighted, unrelated user stories scored 0.3 to 0.4 against each other, since each opens "As the user, I want". A block that stayed in place needs a weighted overlap of 0.33, a block that moved 0.5. The last render counted 34 new, 29 edited and 13 removed blocks.
- **A split block shows as one edited and one new.** Round 2's Layout decision became Layout and Keys; Layout is marked edited, Keys new.
- **The Testing Decisions oracle holds.** A toy spec with one figure and one changed decision rendered one edited block, one new paragraph with its figure in place, and every other block unmarked.

### Figures

- **An HTML figure is an iframe at a fixed height**, 72% of the window and resizable, because a page opened from `file://` cannot measure a frame's content. The frame gets the spec page's `?theme=` and follows the toggle. At the column's width a full page shows its narrow layout; "open in its own tab" shows the whole.
- **A figure is a link into `agent/show/<the spec's directory name>/`.** A spec outside `agent/tickets/<slug>/` needs `--show-dir`.

### Calls the prototype made

- A turn shows the user's message, then what the turn settled ("your answers Q4 a, Q6 a · Q5 replaced by Q7"), its details, its numbered links, and last the questions it asked, each with its answer. Details before links is the spec's Layout order.
- An open question shows only at the top, which names the turn that asked it; its turn does not repeat it.
- The meta line under the title says when the page was rendered, since the page is right only after a manual reload and a stale tab should show it.
- The user's message renders as plain text with its line breaks kept, not as markdown.
