---
status: proposed
blocked-by: [01]
---

# A session directory renders into its session page

Slice of `spec.md`, building on its Decisions under The session page (a container of links, the layout, the keys, only questions ask) and The turn record (fields in a ticket's shape, records written once, the session record, the user's message read from the transcript), and on its Floors.

## What to build

A command that takes a session directory and its transcript and writes the session page: the session's title, brief and resume command at the top, the open questions under them, then the turns newest first, the newest open and the older ones collapsed, each with its headline, the user's message whole behind one click, its details block and its links, which open in a new tab. The records are parsed as the spec shapes them, and a record that does not parse is refused with its file, line and reason, and no page is written. The user's messages come from the transcript: their own messages and the ones queued mid-turn. Links in a record are paths from the repo root. The page wears the house style in both schemes and is driven by the spec's keys.

## Acceptance criteria

- [ ] The session renderer's two properties from 01 pass, their expected failures lifted.
- [ ] The prototype at `agent/prototypes/session-page/` is the quality floor: match it or consciously beat it; its incidental slop is not the target; name deviations in the closing comment.
- [ ] A move either page shares with diffview is on diffview's key (spec, Properties).
- [ ] `render-lint` reports nothing fatal in either scheme at the default width and at 900px.
- [ ] Demo: this session's sample rendered from the fixture transcript, the page opened, and a record broken on purpose refused with its line.
