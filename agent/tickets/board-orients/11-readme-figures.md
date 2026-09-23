---
status: review
blocked-by: [09, 10]
priority: 3
size: XS
---

# The README shows the board as it is

## Brief

The README's two board screenshots and their alt text show the board before this feature: a needs-human queue, a debrief as a queue entry, no priority, time or questions on a row. Once the last board slice has landed, re-render them from the README's fixture tracker and rewrite the alt text to match.

Filed on the user's review comment on 10 (C1, 2026-09-23): a stale figure gets updated, and one pass after the other slices is cheaper and more accurate than one per slice.

## Questions

- [D1] **The board's two screenshots now ship in both colour schemes, as five of the README's six other figures do.** They shipped the night board alone, which hid the day scheme this feature spent a decision on; `<picture>` now carries a day render and a night one and the reader's own setting picks. The cost is two more tracked PNGs and about 1.3 MB on the payload every machine installs with the plugin, since the shots also grew at the wider viewport. One scheme, at half the bytes, is the other answer; `review-page.png` is the one figure still on it.
- [D2] **`ticket-state-figure-review` retires when this lands.** Its work is in this branch, because this ticket's brief says to take it together and the figure is edited once: `review` is in the chain, the queue card is a ticket's own questions, and both PNGs are re-rendered. It keeps `status: proposed` with its criteria ticked and a comment pointing here, since it has no branch of its own for anyone to merge, so accepting this build is the ruling on it and the orchestrator can `git rm` it in the same landing.

## What to build

`mx/assets/board-overview.png` and `mx/assets/board-feature.png` rendered again from the board fixture tracker the README's caption names, in the board this feature built. The fixture tickets carry what the new rows show: priority, size, a brief, and at least one open question. The alt text in `mx/README.md` describes what the new screenshots show. The ticket-state figure's labels for the retired needs-human queue go the same way, together with `ticket-state-figure-review` where it is still open.

## Acceptance criteria

- [x] Both screenshots show the needs-me group with questions under a row, and rows with their marks.
- [x] No figure or alt text in the README names the needs-human queue.
- [x] Demo: the README's board section before and after, side by side.

## Comments

The README's board section shows the board this feature built: the needs-me group with a question
under each row, what every row asks of you beside your time on it and its priority, an opened
ticket as blocks, and the briefing over the graph preview in the column beside the rows. Its
fixture tracker is migrated to the ticket file the feature decided, its two `needs-human.md` queues
gone; the ticket-state figure gains `review` and loses the queue card, which is also the work of
[The README's ticket-state figure shows the review state](../ticket-state-figure-review.md); and
the one-flow and full-cycle figures lose their last mentions of the retired queue. On branch
`ticket/board-orients/11-readme-figures`, not merged. My calls for you are this ticket's
`## Questions`.

**Demo**

    /home/agent/repos/dispatch/agents-board-orients-11-readme-figures/agent/show/board-orients/11-readme-figures/demo

rebuilds the four screenshots the README embeds, from the demo repo up: it lays down the fixture
tracker, runs `board` against it, shoots both schemes of both states, puts them in `out/` beside
itself, and says where to look on each. It leaves the board it shot open to drive, since the marks
it describes explain themselves on hover and a picture cannot. Run here:

    $ docs/figures/board-fixture/build.py

    no diffview on PATH: skipping review-page.png, and the board's review links stay bare
    board-overview-light.png
    board-feature-light.png
    board-overview.png
    board-feature.png
    repo: /var/tmp/mx-demo/ledger

    The four renders, beside the copies the README embeds:

      board-overview-light.png      2880x1576 fresh,  2880x1576 in mx/assets
      board-overview.png            2880x1576 fresh,  2880x1576 in mx/assets
      board-feature-light.png       2880x2722 fresh,  2880x2722 in mx/assets
      board-feature.png             2880x2722 fresh,  2880x2722 in mx/assets

    The overview shot, top to bottom
      needs me       three tickets, and nothing else on the board is in this group: a build waiting on
                     your ruling (to rule on), a prototype decision (prototype), and a slice stopped on
                     a question (your answer). Under each row sits its own [D1] question with a copy
                     button, and the group header carries "copy all 3 questions".
      a row's marks  what it asks of you, then the name with its brief under it, then your time on it
                     (15 min, 1 h) and its priority (p1 now, p3 soon). Hover any of them on the live
                     board below: each says in words what it means and who sets it.
      the column     the briefing at the head of it: where things stand, then three picks with a
                     reason each, written by a model that read this tracker's repo. Under it a preview
                     of the whole tracker's dependency graph, which "full" opens over the board at
                     full size and "window" opens beside it.

    The feature shot
      csv-import is hidden by its chip, and saved-views 03 is opened: a ticket reads as blocks now,
      its question with the detail under it, what to build, and the acceptance criteria as a checklist.

    What the fixture tracker had to gain for any of that to show: a priority and a size in frontmatter,
    a `## Brief` under the H1, and a `## Questions` item on the three tickets that wait on you. Its two
    `needs-human.md` queues are gone, their entries moved onto the tickets they belong to. The briefing
    is one a session really wrote on this tracker, kept in `briefing.json` beside `build.py`, so the
    shot costs no model run and says the same thing every time.

    the board those shots are of   /var/tmp/mx-demo/ledger/agent/board.html
    the tracker it rendered        /var/tmp/mx-demo/ledger/agent/tickets
    the four renders               /home/agent/repos/dispatch/agents-board-orients-11-readme-figures/agent/show/board-orients/11-readme-figures/out
    the README's before and after  /home/agent/repos/dispatch/agents-board-orients-11-readme-figures/agent/show/board-orients/11-readme-figures/figure.html

    No display here, so nothing was opened: the board and the figure are the two to open.

The before and after, master's README board section and this branch's, each rendered from its own
markdown with the screenshots that version points at and its alt text under each, with numbered
notes and a before / after switch:
`/home/agent/repos/dispatch/agents-board-orients-11-readme-figures/agent/show/board-orients/11-readme-figures/figure.html`.
Its second half is the same comparison for the ticket-state figure, in both schemes, which is the
demo the absorbed ticket asks for.

**Details, if you want them**

- [D3] Assumptions
  - A1 `docs/figures/board-fixture/tracker/flaky-upload-test.md:2`: five of the eleven fixture tickets change status, past the priority, size, brief and question the ticket asked for, so the needs-me group holds the three kinds the spec names (a build to rule on, a prototype decision, a ticket stopped on a question) and the frontier is not empty; each new status is one the tracker conventions allow for a ticket already ruled.
  - A2 `docs/figures/board-fixture/briefing.json:1`: the briefing in the shot is one run of the real briefing session against this fixture, recorded by `brief.py` beside it and planted in the cache before the render, rather than a model run per build; without it the column falls back to the board's own count and the README's prose beside it is false.
  - A3 `docs/figures/board-fixture/build.py:29`: the shots move from 1280x900 to 1440x1400, past the board's own 1400px breakpoint so the graph panel sits beside the rows as the caption says, and tall enough that the side column does not scroll its graph out of the shot.
  - A4 `mx/README.md:45`: both board screenshots ship in both schemes behind `<picture>`, which the ticket did not ask for (D1).
  - A5 `docs/figures/board-fixture/build.py:114`: `build.py` skips the review-page shot where `diffview` is not installed, and deletes the stale PNG rather than leaving it, so the board shots build on a host that has no dotfiles; the printed line is the only thing that says the run produced three artefacts rather than four.
  - A6 `docs/figures/ticket-state.html:32`: the `review` chip wears the accent that means waiting on you, so the figure carries two accent chips where it carried one; `proposed` and `review` are the two states that wait on a ruling, which is what the legend says.
  - A7 `agent/tickets/ticket-state-figure-review.md:2`: that ticket keeps `status: proposed` with its criteria ticked rather than flipping to `review`, since `review` is read off a ticket's own branch and its work is on this one (D2).
  - A8 `agent/show/board-orients/11-readme-figures/figure.html:1`: the before and after are stacked with a switch that puts one in the other's place, where the acceptance criterion says side by side; two 1400px-wide README sections at half width each are unreadable, and flipping in place is the comparison the show conventions offer instead.
  - A9 `agent/show/board-orients/11-readme-figures/figure.py:110`: the figure inlines ten README renders, resampled to the width a panel draws them at and re-encoded, and is 1.15 MB, about twice 07, 08 and 09 together; it is committed so it opens on any machine without a build, which is what the inlining is for.
  - A10 `docs/figures/board-fixture/build.py:143`: the fixture's ticket in review carries the branch it sits on and a demo beside it, so the row that says "to rule on" offers something to run, but no review page: rendering one needs `diffview` (A5), so that link is bare where the demo tracker's other one is not.
  - A11 `agent/show/board-orients/11-readme-figures/figure.py:96`: `figure.py` takes `--before`, which the one comparison this ticket asks for never needs, because 07, 08 and 09's figures all take it and a figure whose baseline is unreachable is worth less than the flag costs (spec b3, declined).
  - A12 `agent/show/board-orients/11-readme-figures/figure.py:188`: the page reads `?theme=` as well as carrying a switch, kept from the three sibling figures, which is how a shot of the page pins a scheme (spec b4, declined).
  - A13 `mx/README.md:87`: the Artefacts table's Ticket row still gives the lifecycle without `review`. The same row reads the same way in `orient/SKILL.md`, so the two are one copy and moving one leaves the other wrong; `skills-holistic-pass.md` is where that pass lives (spec a4, declined).
- [D4] Findings, from `/mx:code-review` over `3449557..7580057`, three axes, reports in `agent/reviews/3449557..7580057/`
  - Fixed in d16e9a7, the three that made the README say what its own pictures deny: the prose calling the briefing model-written beside a shot bylined "the board's own", since `build.py` renders with `--no-watch` and no session ever ran (correctness 2, standards F1, spec c1 and c2); the feature shot's alt text losing the needs-me group entirely and calling the opened row a blocked slice where the board renders it in needs me (spec c3); and the ticket-state figure advertising wave lanes, which left the board in `514dbb8`, in the one panel whose job is to list what the page shows (correctness 1).
  - Fixed in the same commit, the figure's own layout: two accent arrows four pixels apart at the `review` chip, reading as one line from a ticket's open questions into `review`, which is not the model and which the SVG guide's twelve-pixel rule forbids (standards F2, spec c4); middle dots inside the new panel's label (standards H2); the two em dashes the README's board paragraph introduced, the only two in the file (standards H1); the `NEEDS ME` label against the board zone's hairline.
  - Fixed in the same commit, what the absorbed ticket asked for and the figure dropped: the orchestrator's flip of the feature branch's copy, now on the claimed-to-review transition beside the worker's last act (spec a2), and `review` also holding a decision ticket's agent-written answer (spec a3).
  - Fixed in the same commit, the pipeline: `build.py` now fails where the board rendered without an optional source, since those notes sit inside the shot's own clip band and a host missing `claude` or its transcripts would bake one into the README (correctness 4); it deletes `review-page.png` where it skipped it, so gone reads as not shot rather than as fresh (correctness 5); the demo opens nothing on a Wayland session (standards C1); the demo's hardcoded copy of the fixture repo's path, now imported from `build.py` (standards S1); its byte-compare against `mx/assets`, which printed a failure word and then a paragraph saying the failure word meant nothing (standards S2); and `figure.py` encoding the same render twice where a README figure ships one PNG for both schemes (standards S3).
  - Fixed in the same commit, the worked example: the fixture's row in review offering nothing to rule on, now carrying its branch and a demo (standards C2, A10); the same clause in a brief and in what-to-build on `06`, and a what-to-build repeating its own acceptance criterion and its frontmatter on `flaky-upload-test` (correctness 6, standards S4 and S5, spec c5); provenance in a different section on two fixture tickets; the README's Artefacts table describing the pre-feature board (correctness 3, spec a4, the Board row only).
  - Declined, with the reason in the assumption it stands on: `--before` on `figure.py` (spec b3) → A11; the unused-looking `?theme=` parameter (spec b4) → A12; the Ticket row's lifecycle (spec a4) → A13; the stacked rather than side-by-side comparison (spec a1) → A8, now with a switch; `build.py`'s diffview skip (spec b1, correctness 5) → A5; the five fixture status changes (spec b2) → A1; the figure's weight against its siblings (standards S3, the part resampling does not reach) → A9.
- [D5] Friction
  - `diffview` is not on this host and is not a project dependency: it comes from the dotfiles. `build.py` shoots the README's review-page figure with it, so a third of the pipeline cannot run here at all, and the first run of it died on `diffview: command not found` with nothing built. The build now skips that shot and says so, which is the honest reading, but `mx/assets/review-page.png` is the one figure in the README nobody on a worker host can re-render. Naming a figure pipeline's host requirements where a worker reads them, or installing `diffview` from the project's own setup, would have saved the detour.
  - The copy from `docs/figures/*.png` into `mx/assets/` is still by hand, which [Renders go stale with nothing to catch it](../render-check.md) already records. Over this build I made it seven times, twice nearly shipping a pair where one scheme was fresh and the other was not; the demo's size column exists because I wanted a reading of it. An `--install` on `render.py`, which that ticket names, is the fix.
  - The board's own screenshots need a briefing, and a briefing needs a model run, which a reproducible build script cannot have. `brief.py` records one run and `build.py` plants it, which is 09's figure promoted; nothing checks that the record still describes the fixture once the fixture moves, so the next tracker change to the fixture can quietly make the README's column stale again.
  - Finding the right clip for the overview took four rebuild-and-look rounds, because what the shot contains depends on the viewport height through the side column's `max-height` and on the briefing's own length, neither of which is visible from the script. The reading that fixed it was a screenshot, every time. A `band()` that clips to a set of elements rather than one is what came out of it.
