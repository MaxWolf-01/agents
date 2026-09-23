---
status: done
blocked-by: [03]
priority: 1
size: M
diff: [230f345f96621b5fec35c48e4353d262ee4504ee..75d3fc6c77c86acbac762ffdd3df5952ccc1da97]
---

# The workflow writes what the board reads

## Brief

The skills teach the new ticket file: every filed ticket gets a priority, a size, a short name and a brief; a worker's questions go into `## Questions`; an answer is recorded as a `Ruled` line; the `needs-human.md` queues retire and their entries move onto tickets.

Slice of `spec.md`, building on the Decisions under "The ticket file" and "Where the workflow changes".

## What to build

An agent following the skills writes tickets the board can read, with no step left to memory:

- The tracker conventions define `priority`, `size`, the H1 as the short name, `## Brief`, `## Questions` with its `Ruled` line, and needs me; the queue file is gone from them.
- `/mx:to-tickets` and `/mx:grilling` give every ticket they file a priority, a size, a short H1 and a brief.
- `/mx:dispatch` and the worker contract send a worker's questions to the ticket's `## Questions` instead of an "I need from you" list, and have the session relaying the user's answer write the `Ruled` line; a question with no ticket to hang on is filed as a proposed ticket.
- `/mx:orient` and every other skill that names the queue follow.
- The board stops reading `needs-human.md`.
- One pass over this repo's tracker: every `needs-human.md` entry moves onto its ticket's questions or becomes a proposed ticket, and every live ticket gets a priority, a size and a brief.

`claude/CLAUDE.md` and the worker contract carry copies of the same blocks (the repo's `CLAUDE.md` says so); an edit to one is checked against the other.

## Acceptance criteria

- [x] Property, reviewed: a question on the board always belongs to a ticket.
- [ ] No `needs-human.md` remains in this repo's tracker, and no skill tells an agent to write one.
- [ ] Every live ticket in this repo's tracker carries a priority, a size and a brief.
- [x] Demo: the diff is the demo; the closing comment lists each migrated queue entry and where it went.

The two unticked ones are half met, and their other half is on master: no skill names the queue and
the board no longer reads one, while `agent/tickets/needs-human.md` and the standalone tickets stay
as they are on this branch (A1). The comment's listing is what finishes them.

## Questions

- [D1] **Two tickets in `review` still hold their calls in the old shape.** `02-rows` and
  `03-questions-and-needs-me` carry `I need from you` blocks under `## Comments`, which the board
  cannot read, so the two rows you are about to rule on show in needs me with no questions under
  them. Their calls reached you in chat already. The board reads a build's questions from its own
  ticket branch, which is not mine to write on, so moving them is a resume of those two workers, or
  nothing.
- [D2] **The feature debrief leaves the durable channel.** It was one queue entry; as built,
  dispatch reports it in chat, every call in it lands on a ticket as a question, and the merge
  commit body keeps what was left. The alternative the spec's own rule suggests is a proposed
  `debrief` ticket per feature, which keeps the whole account on the board.
- [D3] **A standalone ticket that forgets `status:` now disappears from the board in silence**,
  where before it rendered as `open`. A tracker root holds a README and notes, so the rule has to
  skip something; saying "n files at the root declare no status" on the page would name the typo
  and fire on every README.
- [D4] **The priorities and sizes in the listing are my reading of what you have said**, not yours.
  They are the field you are least likely to want an agent guessing at, and the cheapest to correct
  now, before they sort your board.
- [D5] **A decision ticket's subject moves from `## Question` to `## Questions`.** One heading, and
  the board shows what the ticket asks under its row; the cost is a one-line edit on each of the
  five decision tickets on master that use the old heading.

## Comments

The skills now write the ticket file the board reads: the tracker conventions gained a "The ticket
file" section (priority and size in frontmatter, the H1 as the short name, `## Brief`, `## Questions`
with its `Ruled` line), `/mx:to-tickets` and `/mx:grilling` fill those fields at filing, the worker
contract sends a worker's calls to `## Questions`, dispatch records an answer as a `Ruled` line and
files what a ruling leaves open, and the board no longer reads `needs-human.md`. The glossary
settles the word "mark" as ticket 02 asked. On branch `ticket/board-orients/10-workflow`, not
merged. The tracker pass is a listing below rather than an edit: master's queue and standalone
tickets are not this branch's (A1).

**Demo**

Two legs, from a checkout on this branch.

*The board with no queue in it.*

    $ repo=$PWD
    $ uv run mx/skills/tracker/demo_tracker.py /tmp/board-demo
    /tmp/board-demo/agent/tickets
    $ cd /tmp/board-demo && $repo/mx/bin/board agent/tickets --no-watch --no-open
    /tmp/board-demo/agent/board.html

Open it. Needs me holds seven rows, every one a ticket; the queue row that sat among them is gone,
and its entry now reads as `D2` under `Retire the QIF exporter`, the ticket whose decision it was
blocking, so the group's button says `copy all 11 questions` where it said 10. The `saved-views`
pill still carries its dot, which now comes from its tickets rather than from a queue file.

Then leave a queue file behind, the way master's will be on merge day, and render again:

    $ printf '# Needs human\n\n- rule on the exporter :: ask the three users\n' > /tmp/board-demo/agent/tickets/needs-human.md
    $ cd /tmp/board-demo && $repo/mx/bin/board agent/tickets --no-watch --no-open

Reload: no row for it, nothing of its text on the page. Markdown at the tracker root is a ticket
when it declares a status, and nothing else there is one.

*The skills, as an agent meets them.*

    $ grep -rn "needs-human" mx/skills/

prints two lines, both in the test that proves the leftover file is ignored. `git diff 1e95ca3..HEAD
-- mx/skills/tracker/MARKDOWN.md` is the new ticket file, and `mx/skills/dispatch/worker-prompt.md`
is where a worker's calls now go. This ticket's own `## Questions` above is that contract used on
itself: it is what the board will show under this row.

**I need from you**

The five calls are on this ticket's `## Questions`, which is where this ticket moves them, and the
board shows them under its row. In short: `[D1]` two `review` tickets still hold their calls in the
old shape; `[D2]` the feature debrief now goes to chat rather than a file; `[D3]` a ticket that
forgets `status:` vanishes from the board in silence; `[D4]` the priorities and sizes in the listing
below are my reading, not yours; `[D5]` a decision ticket's subject moves to `## Questions`.

**Details, if you want them**

- [D6] The tracker pass, for master. This branch owns `agent/tickets/board-orients/`, whose ten
  tickets already carry a priority, a size and a brief, so nothing there needed migrating.
  `agent/tickets/needs-human.md`, the standalone tickets and `agent/tickets/session-page/` live on
  master and change there daily, so migrating them here would conflict with all of it and show
  branch copies on the board. What each one gets, to apply on master when the feature merges:
  - The three queue entries. **D32**, may a Tests reviewer make its own checkout and run the tests
    there, becomes a `## Questions` item on `review-launcher.md`, whose amend it says it rides along
    with, tagged from that file's own sequence. **D33**, `job` has no staged mode and a landing
    depends on it, becomes a proposed ticket, `job-staged-mode.md`, p2, XS: "The figures-and-demos
    landing stages its demo in a tmux session with Enter left to you, and `job stage` never landed
    in the dotfiles, so every landing prints 'nothing staged'. The work is outside every worktree,
    so it is yours to do or to hand to a session in a dotfiles worktree." **D9**, release mx after
    figures-and-demos merges, becomes a proposed ticket, `release-mx.md`, p1, XS: "The installed
    plugin is v0.1.69 while master carries unreleased skill edits, so every worker host runs an
    older contract than the skills state. One `make release-patch` and a push after
    figures-and-demos and board-orients land covers everything in flight."
  - The standalone tickets. Three already carry all three fields: `board-renders-on-worker-hosts`
    (p4, XS), `render-lint-html-overlap` (p2, S), `runner-resumes-early-stops` (p2, XS). The rest,
    as priority, size and brief:
    - `best-of-n` — p4, L. Several workers build one ticket and one result lands, synthesised by an
      agent rather than picked by you. Open: when a ticket gets variants, who synthesises from what
      evidence, and what becomes of the losers.
    - `comment-density-ceiling` — p3, M. Comment density keeps arriving above what you call
      reasonable, because a rule read while generating washes out and this one is a count a script
      can make. Settles what is counted, where the ceiling sits and which rung enforces it.
    - `dispatch-comments` — p3, XS. About half of the two dispatch scripts is comment, much of it
      workflow prose whose home is the skills. A pass that leaves each comment saying what the code
      beside it does.
    - `dispatch-scripts-under-test` — p2, S. `make test` reaches none of the 400 lines of dispatch
      scripts, and the one driver checks the shipped runner against a copy of itself. Three rungs of
      coverage, cheapest first, stopping where the next costs more than it returns.
    - `dispatch-shown` — p2, M. The dispatch machinery as one artefact: the states a ticket passes
      through with the one writer of each, and every command both roles type for one ticket from
      claim to retirement. You read it to see what is doubled before a pass that simplifies it.
    - `loose-work-review-page` — p3, S. The workflow states that loose work is gated by a review
      page, and nothing in the plugin renders one: the only instruction lives in your own config.
      Either `dispatch review` gains a branch mode or the docs name diffview as the dependency.
    - `mutmut-upstream-issues` — p4, XS. Five mutation-tooling defects the harden script works
      around; three are filed upstream, the skipped decorated functions and the unbudgeted setup
      time are not. Each fix that lands deletes a workaround.
    - `one-flow-open-rulings` — p2, S. Four small calls left open when one-flow shipped: which prose
      rules the chat hook applies, whether the question-word ban returns, whether proposed tickets
      still read wrong on the board, and whether rule 14 binds agent-facing prose.
    - `one-tracker-per-user` — p3, L. One workspace repo holding every project's tracker, with
      research and show artefacts committed, as your work setup already runs. The cost to weigh is
      that a feature's tickets would stop moving with its code.
    - `render-check` — p3, XS. A committed figure can drift from the HTML it was rendered from, and
      did: the README shipped a PNG one edit stale. `--check` re-renders every figure and fails on a
      stale one, inside `make check`.
    - `retro-semi-automated` — p5, M. Retros do not happen. A way to run them with little attention,
      reading indexed sessions rather than one live conversation, with upstream's seven categories as
      the checklist. Rough intent, so it wants a grilling before it is built.
    - `review-launcher` — p2, S. The code-review skill carries four reviewer briefs word for word and
      the mechanics around them, and every caller copies that boilerplate by hand. A script takes the
      mechanics; the skill keeps the judgment.
    - `reviewer-ablation` — p4 (already set), M. The turn-record prose reviewer ships on one model at
      one effort with nothing measured. One command runs the matrix over labelled texts and reports
      validity, recall, cost and time, so a new model can be re-measured.
    - `show-grid-words` — p3, S. The ways an explanation can show a thing, as words you and an agent
      both ask with: the level (concept, code, output) against the form (as it is, how it changed).
      They land in `/mx:show` and the glossary.
    - `skill-driver` — p3, S. A skill's wording is observable only by driving a session against it,
      and three demos each carry their own copy of that harness. One script runs a prompt against two
      versions of a skill and diffs what they produce.
    - `skills-holistic-pass` — p2, L. The skills, the worker contract, the output style and the
      scripts' help texts have grown feature by feature, and reviewing one diff at a time glosses
      over what only a read of the whole shows: what is doubled, what could be a pointer, what sits
      in the wrong file.
    - `svg-guide-vs-figure-set` — p3, XS. The SVG guide rules out three things every committed figure
      does. One of the two is wrong, and the way to tell is looking at the renders rather than the
      text.
    - `ticket-state-figure-review` — p3, XS. The README's ticket-state figure draws `done` as the
      worker's flip, the reading the review status retired, and its alt text lists four statuses
      where the tracker has five. Its three labels for the needs-human queue go the same way, since
      this feature retired it.
  - The `session-page` feature's tickets, none of which carries the new fields yet:
    - `01-properties` — p2, S. The session page's executable properties as checks at their three
      seams, before the code behind them exists, so each later slice lands against a check it did not
      write.
    - `02-session-renderer` — p2, M. A session directory and its transcript render into the session
      page: the title, brief and resume command, the open questions under them, then the turns newest
      first with each user message whole behind one click.
    - `03-spec-page` — p2, M. A spec renders into its own page: its figures shown in place, its
      provenance marks as tags, and every block the round changed marked where it sits. It replaces
      diffview for specs.
    - `04-stop-hook` — p2, S. One hook renders the pages as each turn ends, and sends the agent back
      when its record does not parse or its answer went to the chat instead of the page.
    - `05-turn-review` — p3, S. A turn record's prose gets a light review against the writing
      catalogue before the page renders, and the chat-reply reviewer it replaces retires.
    - `06-skills-teach-it` — p2, S. What an agent reads so that the pages get used: `/mx:show`
      becomes the one home for how a session delivers an answer, grilling delivers its rounds on the
      page, and the chat reply becomes one line and a link.
    - `07-board-links` — p3, XS. The board links each listed session's page and each feature's spec
      page, where one has been rendered.
  - Two more edits ride along on master: the five decision tickets using `## Question` take
    `## Questions` (D5), and `agent/show/mx-readme-figures/demo/build.py` stops writing a queue file
    into the figure demo, whose tickets also want the new fields before the board screenshots are
    shot again.
- [D7] Assumptions
  - A1 `agent/tickets/needs-human.md:1`: master's queue file and its standalone tickets are listed
    rather than migrated, on the orchestrator's ruling of 2026-09-23, so two acceptance criteria are
    half met here and the listing is what finishes them on master.
  - A2 `mx/skills/tracker/board.py:424`: a markdown file at the tracker root with no `status` is
    skipped without a word, since a tracker root holds a README and notes and a note on the page
    would fire on those every render (D3).
  - A3 `agent/tickets/board-orients/02-rows.md:225`: the calls in 02's and 03's closing comments
    stay where their workers wrote them; the board reads a build's questions from its own ticket
    branch, which is not mine to write on (D1).
  - A4 `mx/README.md:25`: the alt text keeps naming the queue because the PNG beside it still draws
    one, and the board screenshots are a ticket behind besides; the figure's three labels join
    `ticket-state-figure-review` in the listing (D4).
  - A5 `mx/skills/dispatch/SKILL.md:82`: the debrief is reported in chat, its calls landing on
    tickets as questions and its leftovers in the merge commit body, rather than becoming a ticket
    of its own (D2).
  - A6 `mx/skills/dispatch/SKILL.md:34`: a relayed question carries two numberings, the ticket's and
    the relaying session's, as that sentence already said before this ticket.
  - A7 `mx/skills/grilling/SKILL.md:57`: "mark" stays bare where the sentence around it is about the
    spec; only to-tickets' template, whose line rides into a row, says "spec mark".
  - A8 `mx/skills/to-tickets/SKILL.md:72`: the provenance line stays inside `## Brief`, as all ten
    board-orients tickets have it, so it reads on the row after the brief's own sentences.
  - A9 `mx/skills/tracker/MARKDOWN.md:44`: a decision ticket states what it asks under `## Questions`,
    which is the demo tracker's shape and what puts it under the row; to-tickets' template follows
    (D5).
  - A10 `mx/skills/dispatch/SKILL.md:51`: a HITL decision ticket is not claimed off the frontier,
    since claiming it would drop it out of needs me; the ask written on it is what takes it off the
    frontier a worker could take.
  - A11 `mx/skills/tracker/board.py:1172`: the feature chip keeps its dot, now read from the
    needs-me group, and loses the "N need me" count, which named the same ticket its status count
    already had.
  - A12 `mx/skills/tracker/demo_tracker.py:315`: the demo tracker's own queue entry is migrated the
    way this ticket migrates the real ones, onto the ticket whose decision it was blocking, so the
    fixture shows the change rather than losing it.
- [D8] Findings, from `/mx:code-review` over `1e95ca3..0b9b9da`, four axes, reports in
  `agent/reviews/1e95ca3..0b9b9da/`
  - Fixed in `a847393`: dispatch's two exits both guarded by an empty frontier while an unclaimed
    HITL ticket sat on it, so a feature whose last item was a design session could never close out,
    and legwork having no station at all (correctness 1, spec a3); two rules for "is this a ticket"
    in one function, one of which dropped a typo'd status silently (correctness 4, standards 1, spec
    c2); the feature chip counting a `review` ticket twice (spec c3, standards); the conventions
    claiming a decision ticket states its subject under `## Question` while the demo tracker states
    it under `## Questions` (spec c4); a question's detail collapsing to one line under an
    instruction to put a paste-ready prompt in it (standards 2); the Row mark entry carrying
    mechanism and banning the word the code uses, and Spec mark defending nothing (standards 3 and
    4, spec a4); the new root-ticket check passing under the rule it replaced (tests 1, spec c5) and
    the chip dot having no input that told it from the review count (tests 2); `rows_in`'s filter
    with nothing left to filter (tests 3); to-tickets restating the conventions' mechanics, the
    debrief's doubled clause and its ambiguous "step 1", the `?` baked into the question template,
    and the docstring's wrap (spec notes).
  - Declined, with the reason in the assumption it stands on: the repo's own queue leaving the board
    with nothing moved (correctness 3, standards, spec a1, tests) -> A1 and the listing; a ticket
    that forgets `status:` vanishing in silence (spec c1) -> A2 and D3; 02's and 03's calls in the
    old shape (spec a1) -> A3 and D1; the README's alt texts and the figure demo's queue file (spec
    a2, correctness 2) -> A4 and D4; the debrief in chat (spec b) -> A5 and D2; a relayed question's
    two numberings (standards) -> A6; "mark" left bare in grilling (spec a4) -> A7.
- [D9] Friction
  - `board` still cannot render this repo's own tracker on a worker host, where the main checkout is
    the bare repo the worktrees hang off (01, 02 and 03 hit it too; it is now the proposed
    `board-renders-on-worker-hosts`). Every demo here is on the demo tracker, which is its own repo,
    so this cost me only the render the conventions ask for after a ticket change.
  - The listing is thirty tickets' worth of priority, size and brief, written by reading each file
    and landing in a comment rather than in the files, because the files are master's. Applying it
    is thirty hand edits transcribed from prose. A `ticket-meta <file> --priority 2 --size S` that
    wrote frontmatter, or a listing in a format such a script reads, would have made it one command
    and taken the transcription errors out.
  - The contract I run under and the one this ticket writes disagree by design: my prompt says the
    calls go in an "I need from you" list, and the shape this ticket lands puts them on the ticket.
    Both are in the comment above as a result. Every worker spawned before the release runs the old
    contract, so the two shapes coexist until `make release-patch` and a push, which is the D9 queue
    entry now standing as the proposed `release-mx` ticket.
