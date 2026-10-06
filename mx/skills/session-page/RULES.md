# The session page

A session the user reads answers on its **session page**: one page per session, rendered from plain-text records each time a turn ends, with the questions waiting on the user at its top and the turns below, newest first. Every session the user sits at has one from its first turn that ends on a reply. A turn that delivers something (an answer, an artifact, a question, a landing) writes it there as a turn record and ends on a chat recap, with the Stop hook's line under it: the questions waiting on the user and a link to the page. A turn that only reports where it stands (working on X, waiting on a worker or a run) ends on a line or two in the chat, which the page shows as a chat turn. A session outside a project with an agent repo (`session-page` refuses) answers in the chat, and so does one nobody reads live, a dispatched worker or a print-mode run, whose artifacts are its report.

The records sit in the directory `session-page` prints, outside git and the same from every worktree of the project. A write to one is checked as it lands: a record that does not parse comes back with the reader's error, and the turn's record gets a light review of its prose once it parses, whose findings come back while the turn still runs. As the turn ends the page renders from the records, and the turn is sent back instead when a record does not parse or was written other than with the Write tool. A turn that writes no record and ends on a reply gets one from the Stop hook, whatever the reply's length: the reply as it stood, as a chat turn, which the page shows among the turns by its time and without a number. The session's first such reply is what creates its directory and its page.

A turn that delivers something, in order:

1. **Its artifacts**, each built by a subagent or a fork (`/mx:show`, Who builds it), since the session writes no HTML. The turn waits for them, so every link its record carries points at a page that exists.
2. **The session record**, with the first turn record: `session.md`, with frontmatter `session` (the id) and `repo` (the directory the session was started in, which the page's resume command changes into), an H1 that names the session's subject the way an email subject line does (the area of the project and the things worked on, by name), and a `## Brief` of a few sentences. Until it exists, the page takes the title Claude Code keeps for the session and shows no brief. Both are rewritten when the session's scope moves, and a turn that rewrites them has them reviewed with its record.
3. **The turn record**, below, written with the Write tool, since the page pairs the record with the user's message by that call. Revise it where a finding holds.
4. **The chat recap**, the turn's last message, once the record is final: what waits on the user, as action items, one plain line each that reads on its own, each open question named by what it decides ("Rule on Q7, what reviews a turn's prose"), or one line saying nothing does. The user reads the recap in the terminal and the page beside it, so the recap never points at the page, and the questions themselves, with their reasons, options and figures, stay on the page. It reads the same whether or not a finding or a parse error came back on the way.

A question still open when the session ends leaves the page for a ticket, since every question on the board belongs to a ticket: a grilling's as the child tickets `/mx:grilling` files, any other as one of the questions of the ticket it concerns (`/mx:tracker`), or a proposed ticket where no ticket holds it. A question is tagged where it lives: `Qn` on the session page, `Dn` in a ticket.

## The turn record

`turns/NN.md`, numbered on from the last `NN.md`, shaped like a ticket file and written once: a later turn never edits it, and a question clears through the frontmatter of the turn that received its answer.

```markdown
---
date: 2026-09-28
answered:
  Q3: a
  Q4: keep both, the user's own words where the answer was neither option
superseded:
  Q5: Q7
---

# The turn's headline: what it answers, in one line

## Questions

- [Q7] **The decision, as a question** the part of the design it would change
  - (a) The option recommended *my pick*
  - (b) The other option
  - Why: the argument for the pick, and what it costs

## Links

- [What the artifact shows](agent/show/<slug>/figure.html): why to open it

## Details

A few lines of plain markdown: what the reader needs beyond the headline and the links.
```

- `date` is the day the turn ends. `answered` maps each question whose answer this turn received to the option's letter, or to the user's own words where the answer was neither option; `superseded` maps a question to the one that replaced it. A question either one names leaves the top of the page.
- **Questions** holds only the calls the user must make, which *What the user decides* below sets out. A question that passes names what they asked for and the change you would make to it, with at least two options you would defend and your pick marked. Tags run `Q1`, `Q2`, … across the whole session. A call the user need not make is a line of Details, or a call mark in the ticket it shapes, and nothing asks the user to acknowledge it. A ticket's own question shown on the page is a line of Details citing its ticket and its `Dn`, since it clears through the ticket.
- **Links** are the artifacts this turn made or moved, each a path from the repo root (absolute for one in another repo) and a note on why to open it. As the turn ends, the Stop hook opens every one but a ticket file in the user's browser.
- **Details** says what the reader needs beyond the headline and the links, and never retells what an artifact shows.
- Anything the record points at is a link. A path on this machine written as code opens the file; `[text](#t07)` opens turn 07 and `[text](#q3)` shows question Q3, so a question at the top links the turn whose Details it leans on.
- A section with nothing in it is left out. The user's own message is read from the transcript, so the record never quotes it.

## What the user decides

The user decides what gets built: its purpose, its scope, its constraints, and the trade-offs between them; you decide how. Ask them before you change what they asked for: adding to it, cutting from it, replacing one of their rulings, or assuming what it is for. Never ask them how to build it, or whether to go ahead with what they already asked for: do it, and the landing shows them.
