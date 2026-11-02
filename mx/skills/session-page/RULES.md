# The session page

A session the user reads answers on its **session page**: one page per session, rendered from plain-text records each time a turn ends, with what waits on the user at its top (the questions to decide, the to-dos, the artifacts to look at) and the turns below, newest first. Every session the user sits at has one from its first turn that ends on a reply. A turn that delivers something (an answer, an artifact, a question, a to-do, a landing) writes it there as a turn record and ends without a chat message of its own: the Stop hook's message stands in the terminal in its place, with the record's headline, a link to the page, and the questions and to-dos waiting on the user. A turn that only reports where it stands (working on X, waiting on a worker or a run), naming nothing for the user to do, ends on a line or two in the chat, which the page shows as a chat turn. A session outside a project with an agent repo (`session-page` refuses) answers in the chat, and so does one nobody reads live, a dispatched worker or a print-mode run, whose artifacts are its report.

The records sit in the directory `session-page` prints, the same from every worktree and project the session works in; its second line is the path the next turn record goes to and whether `session.md` is written yet. They live outside every checkout while the session runs, and are copied into the agent repo and committed there as it ends. A write to one is checked as it lands: a record that does not parse comes back with the reader's error, and the turn's record gets a light review of its prose once it parses, whose findings come back while the turn still runs. As the turn ends the page renders from the records, and the turn is sent back instead when a record does not parse or was written other than with the Write tool. A turn that writes no record and ends on a reply gets one from the Stop hook, whatever the reply's length: the reply as it stood, as a chat turn, which the page shows among the turns by its time and without a number. The session's first such reply is what creates its directory and its page.

A turn that delivers something, in order:

1. **Its artifacts**, each built by a subagent or a fork (`/mx:show`, Who builds it), since the session writes no HTML. The turn waits for them, so every link its record carries points at a page that exists.
2. **The session record**, with the first turn record: `session.md`, its H1 alone, one that names the session's subject the way an email subject line does (the area of the project and the things worked on, by name). Until it exists, the page takes the title Claude Code keeps for the session. The H1 is rewritten when the session's scope moves, and a turn that rewrites it has it reviewed with its record.
3. **The turn record**, below, written with the Write tool, since the page pairs the record with the user's message by that call. Revise it where a finding holds, and end the turn once it is final. Everything the user needs is in the record, so nothing follows it in the chat: what waits on them stays at the page's top until a later record clears it, a call under Questions, a thing to do under To do, an artifact under Links.

A question still open when the session ends leaves the page for a ticket, since every question on the board belongs to a ticket: a grilling's as the child tickets `/mx:grilling` files, any other as one of the questions of the ticket it concerns (`/mx:tracker`), or a proposed ticket where no ticket holds it. A question is tagged where it lives: `Qn` on the session page, `Dn` in a ticket.

## The turn record

`turns/NN.md`, at the path `session-page`'s second line gives, shaped like a ticket file and written once: a later turn never edits it, and a question clears through the frontmatter of the turn that received its answer.

```markdown
---
date: 2026-09-28
answered:
  Q3: a
  Q4: keep both, the user's own words where the answer was neither option
  A2: done
superseded:
  Q5: Q7
---

# The turn's headline: what it answers, in one line

## Questions

- [Q7] **The decision, as a question** the part of the design it would change
  - (a) The option recommended *my pick*
    - Gives: what taking it gets the user
    - Costs: what taking it gives up
  - (b) The other option
  - Why: the argument for the pick
- [two-main-checkouts-synced-by-git D5]

## To do

- [A3] **What the user does, outside the session** what it unblocks, and where its material is ([text](#t07))

## Links

- [What the artifact shows](agent/show/<slug>/figure.html): why to open it

## Details

A few lines of plain markdown: what the reader needs beyond the headline and the links.
```

- The **headline** is what the hub shows under the session's title as its status, and the first line of the Stop hook's message in the terminal, so it is the line read most often without the page. Where a skill fixes how a headline opens (`/mx:wrap` opens on its verdict), that opening is part of the record's shape.
- `date` is the day the turn ends. `answered` maps each question whose answer this turn received to the option's letter, or to the user's own words where the answer was neither option, and each to-do the user reported on to what they said (`done`, `dismissed`, their words); `superseded` maps a question or to-do to the one that replaced it. A question or to-do named in either table leaves the top of the page.
- **Questions** holds only the calls the user must make, which *What the user decides* below sets out. A question that passes names what they asked for and the change you would make to it, with at least two options you would defend and your pick marked. Tags run `Q1`, `Q2`, … across the whole session. An option's `Gives:` and `Costs:` sub-items are the columns of the table the page lays its options out in; an option leaves out the one it has nothing for. What a question leans on beyond its detail line (a draft it asks about, a list, a table) goes in Details, and the question links it with `[text](#tNN)`. A call the user need not make is a line of Details, or a call mark in the ticket it shapes, and nothing asks the user to acknowledge it. A ticket's question is put to the user as its bare handle: the page reads its words from the ticket and clears it once the ticket records the ruling. A **blind** question carries one sub-item, `- Blind: <path of its test page>`, in place of options and a Why: the page (`blind-test`) holds the options and your pick, if you made one, until the user reveals them, and the answer the user pastes back clears it.
- **To do** holds what the user has to do outside the session for the work to go on: a review, a message to post, a command only they can run. Tags run `A1`, `A2`, … across the whole session. A to-do waits at the top until a later record clears it, so a turn lists one once, and a to-do that changed gets a new tag and supersedes the old.
- **Links** are the artifacts this turn made or moved, each a path and a note on why to open it. The path is from the repo root; `show/<file>` for one in the session's own `show/`; absolute for one in another repo. A link to a file that does not exist comes back as the record is written. As the turn ends, the Stop hook hands every one but a ticket file to `claude-browser`, which puts it on the hub.
- **Details** says what the reader needs beyond the headline and the links, and never retells what an artifact shows.
- Anything the record points at is a link. A path on this machine written as code opens the file; `[text](#t07)` opens turn 07 and `[text](#q3)` shows question Q3, so a question at the top links the turn whose Details it leans on. A tag naming something outside the page is qualified by its home (`<ticket> P3`, `retro F1`, `review <range> S13`, another session's `<first 8 of its id> Q3`), which the page links.
- The user works through what waits on the page and sends it as one message, a line per item: `Q7: a`, an option's letter, or their words where they picked none; `A3: done` or `A3: dismissed`; `<ticket> D5: their words`, a ruling for its ticket (`/mx:tracker`); `<artifact path>: their note`. A line may end on a note after a comma, and their own words follow the lines. The next record clears what the lines settled.
- A section with nothing in it is left out. The user's own message is read from the transcript, so the record never quotes it.

## What the user decides

The user decides what gets built: its purpose, its scope, its constraints, the trade-offs between them, and its architecture, the shape other work is built on (where data lives, which machine does what, what talks to what, how a part learns that something happened). Ask them before you change what they asked for (adding to it, cutting from it, replacing one of their rulings, assuming what it is for), and before a build rests on an architecture call they have not made. The rest is yours: how it is built inside that shape, the order of the work, a hand-off to another session, a fact a check settles, and any call one commit undoes that changes nothing they see. Make it, name it in a line where they read, and never put it to them as a question, or ask whether to go ahead with what they already asked for.
