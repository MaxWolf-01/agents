---
status: review
parent: ticket-file-contract
blocked-by: [tracker-command-and-commit-check]
priority: 1
size: L
---

# Every script goes through the tracker command, and the live tracker is converted

Child ticket of `ticket-file-contract`, building on its Decisions: one kind of ticket with a parent ticket and slugs as ids (you, r1 and r2), ticket files on the parent ticket's branch (you, r2), close-out at every parent ticket (you, r2), properties read through the ancestry (you, r2), the review reading the ticket plus its ancestry (you, r1), no decision tickets and one field for tickets that need the user (you, r3), the tracker converted by a worker rather than a script (you, r2), and shipped work left for the parent ticket's final cleanup (you, r5).

## Brief

This ticket builds on master after board-orients has merged, which reworked the board, the tracker and dispatch (its queue file among them); read what it landed before the list below, which was written against the master before it, and treat any item it already settled as settled.

The scripts that read or write ticket files move onto the `tracker` command from `tracker-command-and-commit-check` and onto the new model, and the live tracker is converted in the same branch, so no commit has scripts and tracker disagreeing.

- `board.py`: one ticket kind in place of the Feature and Standalone classes; the parent-ticket tree shown where the feature grouping was; the slug as a row's id; the spec-status chip and the absorbed-standalone filter gone; the worktree override generalised to "the branch a parent ticket is built on". It renders nested lists the way the writers write them (CommonMark's three-space nesting; the parent ticket's incident).
- `dispatch`, `dispatch-ctl`, `run-worker.sh`: the feature-or-standalone case detection goes; a ticket branch `ticket/<slug>` is cut from the branch dispatch runs on, which is the parent ticket's; every status read and write goes through `tracker`; `spawn` refuses a ticket that needs the user, in place of refusing a `type`; `notes_of` takes `tracker`'s Assumptions; a review page lives at `agent/diffviews/<slug>.html`; the fuzz run and the close-out helpers take a parent ticket where they took a feature. `dispatch-ctl` wires the commit check into the repo it stages on a worker host.
- `property_coverage.py`: every executable property has a check; a citation `<slug>#P<n>` resolves or is refused.
- code-review's `review`: `--spec` takes `tracker`'s context for a ticket; nothing in it keys on a `spec.md`.
- The conversion, with judgment: each feature's `spec.md` becomes a top-level ticket named after the feature, its `NN-slug.md` tickets become child tickets with descriptive slugs, and every `blocked-by` and cross-reference is rewritten to slugs. A feature that has shipped with every ticket done is left as it is: the parent ticket's final cleanup commit retires it. Tickets filed on master in the old format after this branch was cut are converted when this ticket's parent merges.

## Acceptance criteria

- [x] No script under `mx/` reads or writes a ticket file itself: every read and write goes through `tracker` (`ticket-file-contract#P2`).
- [x] The board renders the converted tracker: parent tickets with their children, the dependency graph by slug, the review pages linked; a before and after of the board is the demo.
- [x] `dispatch` runs one ticket end to end on a throwaway repo in the new layout: claim, spawn, the `review` flip read from the ticket branch, the review page, the landing.
- [x] `ticket-file-contract#P4`: the worker's brief and the review's `--spec` come from the same context assembly.
- [x] `ticket-file-contract#P5`, reviewed: no script branches on a kind of ticket beyond having child tickets and needing the user.
- [x] Every file under `agent/tickets/` passes `tracker`'s check. Every flat ticket does; the seven under `agent/tickets/figures-and-demos/` cannot, and another session has retired them on master, which this branch takes at the merge (D2).

## Testing seams

The parent ticket names one seam, `tracker`'s command line, for its own properties. Each script this
ticket moves is checked at the command line it already had one for (my call, from the review):
`board.py`'s loader, graph and page functions (`test_board.py`); `review`'s own command line, in a
scratch repo (`test_review.py`); `property-coverage`'s (`test_property_coverage.py`); and
`dispatch`'s, over a toy repo whose worker is a stub on the `DISPATCH_RUNNER` seam
(`test_dispatch.py`, new here, four cases; the rest of those scripts' coverage is
`dispatch-scripts-under-test`'s). `ticket-file-contract#P2`'s other half, that no script parses a
ticket file itself, has one seam and it is the source: `test_tracker.py` reads every file under `mx/`
that mentions the tracker and refuses a frontmatter, heading, question or assumption pattern of its
own.

## Questions

- [D1] **`property-coverage` now asks a question next to the one the line names.** The ticket asks for "every executable property has a check", and the dispositions that said which property is executable (`executable | reviewed | unsliced`) left the machine-read part of a ticket with the old model, so no command can tell one from another. What it checks is that every property a ticket states is cited by some acceptance criterion, anywhere in the tracker: stricter one way (a property disposed *reviewed* is a finding if no criterion cites it) and weaker the other (a citation counts whether or not a check exists). The other reading is to put a disposition back into the criterion's shape, which is what `tracker-command-and-commit-check` deliberately refused (A2).
  - Ruled 2026-09-24: accepted as built: property-coverage holds every property a ticket states to being cited by some acceptance criterion.
- [D2] **The seven files under `agent/tickets/figures-and-demos/` are now on no board and pass no check.** They are left as the ticket says, since every one of their tickets shipped, and the parent ticket's cleanup commit retires them. What was not foreseen: the flat reader globs `*.md` at the tracker root, so those tickets are invisible to the board and to `tracker` alike rather than showing as a feature with a pill. They are in git and nothing reads them; the alternative is to retire them now, one commit earlier than the parent ticket's plan (A3).
  - Ruled 2026-09-24: accepted. figures-and-demos/ is already retired on master, by another session; nothing to do here.
- [D3] **`mx/README.md` still teaches the three kinds of file**, its Artefacts table naming `agent/tickets/<feature>/spec.md` and `NN-slug.md` with the four decision types, and its flow figure drawing the same. Neither this ticket nor `skills-and-glossary-speak-one-ticket-kind` names it, and it is the file a human reads to learn the workflow, so a reader learns the model this feature replaced. It wants an owner: the prose sibling, this ticket's parent at its cleanup, or `readme-reshoot`, which already exists for the figure.
  - Ruled 2026-09-24: the prose sibling rewrote mx/README.md; the README's figures wait for readme-reshoot, later. Nothing to do here.
- [D4] **A `Ruled` line that is not a bullet of its own no longer answers its question.** The board's old reader took `  Ruled 2026-09-21: per bank.` indented under a question as a ruling; the one parser reads a lazily continued line as part of the bullet above it, so that text lands in the question's detail and the question stays open on the board. Every real ticket writes the ruling as a nested bullet and the corpus agrees, so nothing in the tracker moved, but the drift is silent: the writer sees their answer in the file and the board still asks. Either the tracker refuses a `Ruled <date>:` that is not its own bullet, or the rule stays as it is and the prose says so.
  - Ruled 2026-09-24: tracker check refuses a Ruled line that is not a bullet of its own under its question, naming the file and the line.
- [D5] **A question a build asks on its ticket branch cannot be ruled with `tracker rule`.** `rule` writes under the question in the tracker's own copy, and until the merge that copy has no `## Questions` at all: the worker's are on the branch. The board reads them from there and shows them, so the user sees the question and the command that answers it refuses. Today the ruling on a build is the accept, amend, redo or reject on its review page, so this may be a question that never needs a `Ruled` line; if it does, either `rule` learns to write the question in as it answers it, or the landing brings the branch's questions into the tracker's copy before the merge.
  - Ruled 2026-09-24: no copying. A build's questions stay on its ticket branch until the merge: on accept the orchestrator merges and then answers with tracker rule on the merged copy, on amend the answers travel in the guidance and the worker writes the Ruled lines on its own branch. dispatch review stays as it is; the prose sibling's dispatch skill says the order.

## Comments

Every script that reads or writes a ticket file goes through `tracker`, and the live tracker is converted with them, on `ticket/ticket-file-contract/scripts-go-through-tracker-command`; nothing is merged. `agent/tickets/figures-and-demos/` is the one thing left as it was, which the last acceptance criterion and D2 say.

**Demo**

```
$ /home/agent/repos/dispatch/agents-ticket-file-contract-scripts-go-through-tracker-command/agent/show/scripts-go-through-tracker-command/demo
wrote /home/agent/repos/dispatch/agents-ticket-file-contract-scripts-go-through-tracker-command/agent/show/scripts-go-through-tracker-command/out/index.html
no display here; open the file above to read it
```

It builds a toy tracker of four ticket files and drives the real scripts over it, writing the walkthrough as one page: the check and the frontier, `property-coverage` with and without the criterion that cites the property, the context one assembly hands a worker and a reviewer, `dispatch` from the claim through the spawn, the review flip, the notes and the landing, and `review --spec <slug>` for the file it hands a reviewer. Every run on the page is a real one; the worker alone is a stub on `dispatch-ctl`'s `DISPATCH_RUNNER` seam, so what runs is `dispatch` and `dispatch-ctl` themselves.

The before and after the change owes is the last panel: the same work rendered by the board of the commit this branch cut from, over a feature directory with a `spec.md` and `NN-` tickets, and by this branch's, over the flat ticket files, with four numbered notes on what moved. `out/board-before.png` and `out/board-after.png` beside the page.

**Details, if you want them**

- [D6] Assumptions
  - A1 `mx/skills/tracker/board.py:171`: the board imports the tracker's parser rather than spawning the command. It is the same parser, which is what `ticket-file-contract#P2` asks for, and a render reads several tracker roots several times a second while watching; the scripts that are not its neighbours (`property-coverage`, `review`, the dispatch three) call the command.
  - A2 `mx/skills/to-tickets/property_coverage.py:92`: what "every executable property has a check" became, with no disposition left to read (D1).
  - A3 `agent/tickets/figures-and-demos/spec.md:1`: left as it is, and now invisible to every reader (D2).
  - A4 `mx/skills/dispatch/dispatch:109`: a ticket branch is `ticket/<slug>`, its worktree `<repo>-<slug>`, its pane `dispatch-<repo>-<slug>`, and the commit-message prefix a feature branch added is gone. The slug is unique across the tracker, so nothing needs the base branch in its name to stay apart; the scratch directory keeps it, since two dispatchers on two branches may be on two plugin versions.
  - A5 `mx/skills/dispatch/dispatch:277`: a spawn sends the orchestrator's message with `tracker context <slug>` under it, and keeps what it sent beside the message; a resume sends the message alone, the context being in the conversation it resumes. This is the worker half of `ticket-file-contract#P4`, and the ticket left where the assembly is joined to the message to me.
  - A6 `mx/skills/dispatch/dispatch-ctl:190`: the commit check is installed only in a bare repo, which is the one a worker host stages; a local orchestrator passes its own checkout, whose hooks are the user's (`tracker-command-and-commit-check` D1).
  - A7 `mx/skills/tracker/board.py:804`: a worktree whose tracker no reader can read leaves the render the main checkout's and prints the refusal whole. The main checkout is the tracker; a branch is a source a render can do without, as GitHub and the page server are. A refusal in the main checkout's own tracker ends the render, naming the file and the line.
  - A8 `mx/skills/tracker/board.py:1678`: a row keeps two name columns where it had the feature and the number: the tree, which is the top-level ticket its ancestry runs to and the pill that hides it, and its own slug, which is the row's id and what a click copies the path of. A top-level ticket with children shows its slug in both, which is what it is.
  - A9 `mx/skills/tracker/board.py:195`: what a row asks is four words where it was seven, `with you` standing for every ticket carrying `needs-user`. The three that came from a decision ticket's type go with the field.
  - A10 `mx/skills/tracker/demo_tracker.py:24`: the demo tracker writes its fixture ticket files itself rather than through `tracker new`. It is a fixture builder, and half its value is writing shapes a reader refuses; the check over it is `tracker check`, which the board's own loader runs on every render of it.
  - A11 `mx/skills/show/SKILL.md:35`: `/mx:show`'s show-directory rule is changed here, to `agent/show/<slug>/` for every ticket, because `dispatch` stages a demo from that path and the board reads a ticket's artefacts there. It is prose in a skill neither this ticket nor its prose sibling names, so if that sibling touched the same lines the orchestrator resolves it; `mx/skills/grilling/SKILL.md` and `mx/skills/orient/SKILL.md` carry the old path too and are the sibling's.
  - A12 `mx/skills/tracker/board.py:949`: the renderer nests a list at three spaces, which is what the ticket asks for and what the incident was. CommonMark nests at the parent's content column, which is two for a `- ` marker, and this repo's own assumptions are written that way: those still render flat. Two would fix both and would also make a two-space-indented line after a blank one an indented code block, which is why it is three.
  - A13 `agent/tickets/mutmut-upstream-issues.md:3`: the one `type: legwork` ticket became `needs-user: true`, since filing upstream issues needs GitHub credentials no worker host has. Every `type: grilling` became the same; nothing else carried a type.
  - A14 `agent/tickets/dispatch-shown.md:1`: the two `blocked-by: [figures-and-demos/06]` edges are dropped rather than rewritten to a slug, since 06 is done and dropping the edges onto what leaves is exactly what `tracker retire` does.
  - A15 `agent/tickets/session-page.md:1`: the converted spec keeps its own sections (Problem statement, Solution, User stories, Floors, Around it) and gains a `## Brief`, which is what a row shows and what a spec had no room for. Its properties are numbered so they can be cited, and its acceptance criteria are new: they cite all eight.
  - A16 `mx/skills/tracker/tracker.py:614`: `tracker hook` takes the repository to install into, since the one a worker host stages is bare and nothing is ever checked out of it to run the installer from.
  - A17 `mx/skills/dispatch/dispatch:248`: `dispatch claim` refuses a ticket already claimed, in the script rather than in the tracker. `tracker set` takes a write to the status a ticket already has, idempotently, which is what `dispatch review` relies on; a claim is the one caller for which that is not a no-op but a ticket in somebody else's hands.
  - A18 `agent/tickets/scripts-go-through-tracker-command.md:34`: the Testing seams section is written from the review's read, not from the ticket, which carried none. The seam the parent ticket names is `tracker`'s command line; each script this ticket moves is checked at the command line it already had a seam for.
- [D7] Findings, from `/mx:code-review` over `09734b4..12374bb`, four axes, reports in `agent/reviews/09734b4..12374bb/`
  - Fixed in `ad35c5a`, correctness: a `tracker` refusal swallowed by a pipeline whose tail is `jq`, in `dispatch review`'s notes and in `dispatch-ctl spawn`'s needs-user guard, which wrote an empty notes file and handed a worker an unreadable ticket; the review page of a ticket read from a worktree looked up in the main checkout, where `dispatch review` never wrote one; the board's first render raising a traceback where every other refusal names a file and a line; `/mx:show` still sending a demo to `agent/show/<feature>/NN-<slug>/`, which no script looks in.
  - Fixed in `ad35c5a`, spec and standards: the board throwing away the refusals of a ticket read from its own branch, and with them its second parser of the sections, the brief and the questions; `--help` saying `--spec <path>` and crediting the tracker with a refusal dispatch makes; the tree column's words naming a parent where it holds the top-level ticket; the lone tickets' pill last in the bar and first in the graph; the `ftag`, `num` and `featnav` marks named for what they held before; a second copy of the status vocabulary; three derivations of a tree's tickets; `uv` and `jq` unchecked on a worker host that now needs both; `run-worker.sh` folding every tracker failure into one `?`; the demo page without the house tokens or a scheme toggle, and its before board falling back to `HEAD~6` where the branch it names is absent; a title-case heading and two references to a section this branch renamed.
  - Fixed in `ad35c5a`, tests: nine of the ten mutations the Tests axis's run named now fail a check (the three-space nesting, a blocker the board cannot see, a tree deeper than one level read from its worktree, the stamp on every mark a row shows, the worktree's review page, the lone tickets' graph and their pill order, the findings' order, two properties under one id, and `review`'s re-run line); the layout check that pans the whole-tracker graph, which went red when the slugs made its nodes narrow enough to fit, narrows the window instead of leaning on the fixture; a GitHub-absence check that rendered an empty board; and a check that asserted the board reads a question shape the tracker refuses.
  - Filed, not fixed: nothing. `dispatch-scripts-under-test` already carries the rest of the dispatch scripts' coverage; the four cases this ticket's own move made are `mx/skills/dispatch/test_dispatch.py`.
  - Declined: the reading `property-coverage` took (A2), the seven files left under `figures-and-demos` (A3), the fixture builder writing ticket files itself (A10), and two-space nesting (A12).
- [D8] Friction
  - The four-axis review took 19 minutes against a 2,200-line diff and was worth every one: the two swallowed refusals were the parent ticket's own incident reproduced in the code that was meant to end it, and nothing in my own driving of the demo could have shown them, since the demo's tickets are all readable. The Tests axis's mutation run found nine more.
  - Three of this ticket's scripts had no checks at all before it (`dispatch`, `dispatch-ctl`, `run-worker.sh`), so 483 changed lines of them landed on a demo transcript and a reviewer's reading. `test_dispatch.py` is four cases and took twenty minutes; the shape (a toy repo, a stub on the runner seam, the script as a subprocess) was already in the landing demo of `figures-and-demos`, unrun by anything.
  - The board's tests are the largest file in the repo and were written against the old model end to end: about half this ticket's wall clock went into them rather than into the board. A fixture named for the model it tests (`FEAT`, `01-second.md`, `standalone-`) is what made it a rewrite rather than a rename.
  - `tracker check` refuses a ticket with no priority or size, and half the board's fixtures were written without them, which is right and was a hundred small edits. Worth knowing for the next ticket that touches a fixture tracker.

Your rulings of 2026-09-24 are written under their questions. D1, D2 and D3 needed nothing built; D4 and D5 are the round, with the change to light mode beside them, and nothing is merged.

`tracker check` refuses a `Ruled <date>:` line that is no bullet of its own under its question, naming the file and the line (D4). A line merely indented under a bullet continues that bullet, so such a ruling lands in the question's detail: the writer sees their answer in the file and every reader still shows the question as open, which is `ticket-file-contract#P1`. The refusal fires on both shapes, the lazily continued line and the indented one after a blank; a `- Ruled <date>:` bullet and a `Ruled out:` line carrying no date are untouched.

`review --light` takes `--spec`, and its one reviewer judges the diff against what was asked for as well: the light brief gains a fourth part, so a small ticketed diff is no longer reviewed with no view of its ticket. With no `--spec` the brief says there is none and tells the reviewer to invent no requirement.

D5 needed no code: `dispatch review` stays as it is.

**Demo**

```
$ /home/agent/repos/dispatch/agents-ticket-file-contract-scripts-go-through-tracker-command/agent/show/scripts-go-through-tracker-command/demo
wrote /home/agent/repos/dispatch/agents-ticket-file-contract-scripts-go-through-tracker-command/agent/show/scripts-go-through-tracker-command/out/index.html
no display here; open the file above to read it
```

The same page, with a panel each for the round: "a ruling its writer did not bullet" is the check refusing one, and the `review --spec` panel now runs light mode over the same slug and prints the part its brief gained. The board's before and after is unchanged, at `out/board-before.png` and `out/board-after.png` beside the page.

**Details, if you want them**

- [D9] Assumptions, continuing the block above
  - A19 `mx/skills/tracker/tracker.py:1042`: the refusal fires on a line that matches a ruling whole, `Ruled <date>:`, and on nothing else. A continuation that merely opens with the word Ruled is prose a writer meant as detail, which is the shape `- [D3] **Ruled out is not a ruling.**` was written in, so refusing every such line would refuse the ticket that explains the rule.
  - A20 `mx/skills/code-review/briefs/asked.md:1`: what light mode gains with a spec is a part of its own, composed as the other parts are, rather than a paragraph the script writes or a second copy of the Spec axis's brief. The brief a reviewer read is the record of what bound it, so the words stay in `briefs/` where every other reviewer's do.
  - A21 `mx/skills/code-review/SKILL.md:71`: light mode's own prose is brought along here, since it said the trade was right "exactly where there is no spec" and the script now says otherwise. It is a SKILL.md, which `skills-and-glossary-speak-one-ticket-kind` owns; your ruling came from that ticket's review, so if it made the same edit the orchestrator takes either.
- [D10] The round
  - The suite is 354 passing, `make check` clean, `tracker check` clean over every flat ticket, `property-coverage` 14 of 14. Four checks cover the new refusal: the two shapes that are refused, and the two that are not.
  - Nothing else moved: the first round's findings stand as `ad35c5a` left them, and its assumptions A1 to A18 are as built.
