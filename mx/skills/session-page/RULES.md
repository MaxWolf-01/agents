# The session page

A session the user reads answers on its **session page**: one page per session, rendered from plain-text records each time a turn ends: the turns, newest first, beside the session's tasks (what waits on the user, what is in flight, what comes next, drawn from its plan) and its timeline. Every session the user sits at has one from its first turn that ends on a reply. A turn that delivers something (an answer, an artifact, a question, a to-do, a landing) writes it there as a turn record and ends without a chat message of its own: the Stop hook's message stands in the terminal in its place, with the record's headline, a link to the page, and the questions and to-dos waiting on the user. A turn that only reports where it stands (working on X, waiting on a worker or a run), naming nothing for the user to do, ends on a line or two in the chat, which the page shows as a chat turn. A session outside a project with an agent repo (`session-page` refuses) answers in the chat, and so does one nobody reads live, a dispatched worker or a print-mode run, whose artifacts are its report.

The records sit in the directory `session-page` prints, the same from every worktree and project the session works in; its second line is the path the next turn record goes to and whether `session.md` is written yet. They live outside every checkout while the session runs, and are copied into the agent repo and committed there as it ends. A write to one is checked as it lands: a record that does not parse comes back with the reader's error, and the turn's record gets a light review of its prose once it parses, whose findings come back while the turn still runs. As the turn ends the page renders from the records, and the turn is sent back instead when a record does not parse or was written other than with the Write tool. A turn that writes no record and ends on a reply gets one from the Stop hook, whatever the reply's length: the reply as it stood, as a chat turn, which the page shows among the turns by its time and without a number. The session's first such reply is what creates its directory and its page.

A turn that delivers something, in order:

1. **Its artifacts**, each built by a subagent or a fork (`/mx:show`, Who builds it), since the session writes no HTML. The turn waits for them, so every link its record carries points at a page that exists.
2. **The session record**, with the first turn record: `session.md`, its H1 alone, one that names the session's subject the way an email subject line does (the area of the project and the things worked on, by name). Until it exists, the page takes the title Claude Code keeps for the session. The H1 is rewritten when the session's scope moves, and a turn that rewrites it has it reviewed with its record.
3. **The turn record**, below, written with the Write tool, since the page pairs the record with the user's message by that call. Revise it where a finding holds, and end the turn once it is final. Everything the user needs is in the record, so nothing follows it in the chat: what waits on them stays in the page's tasks until it clears, a call under Questions, a thing to do under To do, an artifact under Links.

A question still open when the session ends leaves the page for a ticket, since every question on the board belongs to a ticket: a grilling's as the child tickets `/mx:grilling` files, any other as one of the questions of the ticket it concerns (`/mx:tracker`), or a proposed ticket where no ticket holds it.

Everything put to the user is a session `Qn`, a worker's or a ticket's question too: the `Qn` is written for what the user knows now, and a `- Ticket: <slug> D3` sub-item names the ticket it was asked for. A ticket's `Dn`s are its audit log and specification, read by agents. When the user answers such a `Qn`, record the answer on its ticket (`/mx:tracker`, Questions: `tracker rule`); the `Qn` clears with the answer, or once the ticket records the ruling.

## The turn record

`turns/NN.md`, at the path `session-page`'s second line gives, shaped like a ticket file and written once: a later turn never edits it, and a question clears through the user's answer line, or the frontmatter of the turn that received an answer in other words.

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
  - (a) One option
    - Leads to: what deciding it this way sets going
    - Gives: what taking it gets the user
    - Costs: what taking it gives up
  - (b) The other option
  - Recap: what the question leans on, whole
    - a list, a table or a quoted draft, indented under it
  - [The render of each option](agent/show/<slug>/options.html): what to compare
- [Q8] **A worker's question, as the user would ask it** the part of the design it would change
  - Ticket: two-main-checkouts-synced-by-git D5
  - (a) One option
  - (b) The other option

## To do

- [A3] **What the user does, outside the session** what it unblocks
  - Recap: what they need to do it, whole
  - [Its material](agent/show/<slug>/review.html): what to look at there

## Links

- [What the artifact shows](agent/show/<slug>/figure.html): why to open it

## Details

A few lines of plain markdown: what the reader needs beyond the headline and the links.
```

- The **headline** is what the hub shows under the session's title as its status, and the first line of the Stop hook's message in the terminal, so it is the line read most often without the page. Where a skill fixes how a headline opens (`/mx:wrap` opens on its verdict), that opening is part of the record's shape.
- `date` is the day the turn ends. `answered` maps each question whose answer this turn received in other words than its answer line to the option's letter, or to the user's own words where the answer was neither option, and each to-do the user reported on to what they said (`done`, `dismissed`, their words); `superseded` maps a question or to-do to the one that replaced it. A question or to-do named in either table leaves the tasks.
- **Questions** holds only the calls the user must make, which *What the user decides* below sets out. A question that passes names what they asked for and the change you would make to it, with at least two options you would defend, none marked as yours; where the options differ in what the user would see, the question links the render of each (`/mx:show`, What a reader can be shown) and is asked once it exists. Tags run `Q1`, `Q2`, … across the whole session. An option's `Leads to:`, `Gives:` and `Costs:` sub-items are the columns of the table the page lays its options out in; an option leaves out the one it has nothing for. Writing them is also the test of the question: one whose options lead to the same place, or cost nothing either way, is a call that is yours to make. A call the user need not make is a line of Details, or a call mark in the ticket it shapes, and nothing asks the user to acknowledge it. A **blind** question carries one sub-item, `- Blind: <path of its test page>`, in place of options: the page (`blind-test`) holds the options and your pick, if you made one, until the user reveals them, and the answer the user pastes back clears it.
- **To do** holds what the user has to do outside the session for the work to go on: a review, a message to post, a command only they can run. Tags run `A1`, `A2`, … across the whole session. A to-do waits in the tasks until it clears, so a turn lists one once, and a to-do that changed gets a new tag and supersedes the old.
- A question's or a to-do's card is all the user reads of it, so it carries everything it leans on: a `- Recap:` sub-item, whose lines indented under it are markdown (a draft it asks about, a list, a table), and the artefacts it needs as link sub-items, `- [text](path): note`, written as a Links item is. A card that sends the user to a turn instead comes back as the record is written.
- **Links** are the artifacts this turn made or moved, each a path and a note on why to open it. The path is from the repo root; `show/<file>` for one in the session's own `show/`; absolute for one in another repo. A link to a file that does not exist comes back as the record is written. As the turn ends, the Stop hook hands every one but a ticket file to `claude-browser`, which puts it on the hub.
- **Details** says what the reader needs beyond the headline and the links, and never retells what an artifact shows.
- Anything the record points at is a link. A path on this machine written as code opens the file; `[text](#t07)` opens turn 07 and `[text](#q3)` shows question Q3. A tag naming something outside the page is qualified by its home (`<ticket> P3`, `retro F1`, `review <range> S13`, another session's `<first 8 of its id> Q3`), which the page links.
- The user works through what waits on the page and sends it as one message, a line per item: `Q7: a`, an option's letter, or their words where they picked none; `A3: done` or `A3: dismissed`; `<artifact path>: seen` for an artefact they looked at, or their note on it. A line may end on a note after a comma, and their own words follow the lines. A line in that form settles its item as the message lands, whether or not a record follows; the next record's `answered:` carries an answer in other words.
- A section with nothing in it is left out. The user's own message is read from the transcript, so the record never quotes it.

## The plan

The session keeps its plan in `plan`, in the directory `session-page` prints: the session's steps, one line each, which the page's tasks column draws in the order the user should look at them. It is how the user sees where the work stands and where each open question fits, and how another agent finds out what this session is doing. Write it once the work has more than one step, and touch it when a step starts, ends or comes to wait on a question; a line a step, never a log of the work.

```
wait  Prototype the new top of the session page | waits Q12 Q13 | see agent/show/top/index.html
  next  The phone layout of it
doing Collect last week's auto-mode denials | job a local subagent
done  Merge the heavy-work line | settles Q14
```

- A line is `<state> <text>`, the state `wait` (on a question or to-do of the user's), `doing`, `next` or `done`, then fields after ` | `: `waits Q7 A3` for what holds the step up, `settles Q14` for what its going done answered, `see <path>` for an artefact to look at for it, `job <what runs it>` for work running in the background.
- A line indented two spaces under another is a step under it: a tangent off it, or a step waiting on it.
- A step that goes `done` settles every question and to-do it names, so one that something else answered (a merge on the user's review comment, a worker's result) leaves the page with no answer line: mark the step that did it done, naming the question.
- The agent works on everything the open questions do not block, and that work is a `doing` step, so the tasks show what goes on while the user decides.

## What the user decides

The user decides what gets built: its purpose, its scope, its constraints, the trade-offs between them, and its architecture, the shape other work is built on (where data lives, which machine does what, what talks to what, how a part learns that something happened). Ask them before you change what they asked for (adding to it, cutting from it, replacing one of their rulings, assuming what it is for), and before a build rests on an architecture call they have not made. The rest is yours: how it is built inside that shape, the order of the work, a hand-off to another session, a fact a check settles, and any call one commit undoes that changes nothing they see. Make it, name it in a line where they read, and never put it to them as a question, or ask whether to go ahead with what they already asked for.
