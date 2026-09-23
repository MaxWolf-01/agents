---
status: done
parent: board-orients
priority: 1
size: S
diff: [faf6f0f3366724e2e75d03f2919d939948ed97f9..6268bad46c4d370ce0dbcaa426af2e09216da496]
---

# Property checks for the board

## Brief

The board's executable properties written as tests before any slice builds them, each failing until the slice that makes it hold lifts it. Reviewing it means reading the checks against the spec's Properties.

Slice of the parent ticket: its Properties and Testing Decisions.

## What to build

The spec's executable Properties as checks at their three seams, each an expected failure naming the ticket that lifts it (`/mx:testing`), so every later slice finds its oracle in place when its worktree is cut. The checks live beside the board's existing tests, since this repo has no properties directory; that is a deliberate deviation from `/mx:to-tickets`. Where a seam's function does not exist yet, this ticket lands its interface as a stub transcribed from the spec's Decisions, so the suite collects.

- **The loader seam**: which tickets are in needs me; a ticket's open questions read from its file, less those a `Ruled` line answers; the sessions listed for a ticket; a render with each optional source absent (GitHub, the model, transcripts, the review-page server); no GitHub request and no model call on a render that finds nothing changed.
- **The layout seam**: the demo tracker, built by `agent/prototypes/board-orients/demo-tracker/build.sh`, promoted into the test fixtures with its tickets moved to the spec's ticket file (the H1 as name, `## Questions` with `Ruled` lines), rendered, and checked with `render-lint` at window widths from 900px up and zoom from 80% to 200%, in both schemes.
- **The schedule seam**: whether a tracker change pings the briefing session, waits out the debounce, or retires the session and starts a fresh one, as a pure function of the cache file's state, the change's time and the clock.

The slice that lifts each: needs me and ruled questions → 03; no overlap → 02; a listed session has a transcript, and a render without transcripts → 05; no request on an unchanged render, and a render without GitHub → 07; no model call on an unchanged render, a render without the model, and pings and retirement → 09. A render without the review-page server already holds and carries no annotation.

## Acceptance criteria

- [x] Every executable Property in the spec has a check at its seam, collected by `make test`, failing as an expected failure that names its lifting ticket.
- [x] A property that already holds passes with no annotation.
- [x] The demo tracker is a fixture the layout checks build on their own, with nothing read from `/var/tmp`.
- [x] Demo: the diff is the demo, and the closing comment carries the `make test` output with the expected failures listed by ticket.

## Comments

Eleven checks at the spec's three seams, ten of them expected failures naming the slice that lifts them, on branch `ticket/board-orients/01-property-checks`, not merged.

**Demo**

The diff is the demo; the suite is how you read it.

    make test

    mx/skills/tracker/test_board.py ...............................xxxxxxx.x
    x
    mx/skills/tracker/test_board_layout.py x
    mx/skills/tracker/test_briefing.py x..
    105 passed, 11 xfailed in 38.08s

`uv run --with pytest --with hypothesis --with tyro --with pyyaml --with markdown pytest mx/skills/tracker -rxX` lists each expected failure with the ticket that lifts it:

| lifted by | check |
| --- | --- |
| 02-rows | nothing on the board overlaps or escapes its box at any width in either scheme |
| 03-questions-and-needs-me | a ticket is in needs me exactly when it waits on a ruling, an answer or a design session |
| 03-questions-and-needs-me | a question a ruled line answers is never open |
| 03-questions-and-needs-me | the needs-me group holds exactly the tickets that wait on the user |
| 05-sessions | every session listed on a ticket has a transcript on this machine |
| 05-sessions | the board renders with no transcripts and says the absence once |
| 07-github-state | the board renders without GitHub and says the absence once |
| 07-github-state | a render that finds nothing changed makes no GitHub request |
| 09-briefing | the board renders without the model and says the absence once |
| 09-briefing | a render that finds nothing changed makes no model call |
| 09-briefing | the briefing session is pinged once a window and never past its idle hour or ping cap |

The property that already holds, unannotated, is the render with no review-page server. To see the fixture the layout and session checks build:

    uv run mx/skills/tracker/demo_tracker.py /tmp/demo && (cd /tmp/demo && board agent/tickets --no-watch --no-open)

prints `/tmp/demo/agent/board.html`: the ledger tracker with two features, two builds waiting on a ruling with their questions on their ticket branches, a ruled question, a needs-human queue, review pages, and four sessions on its commits.

To see a check turn green, implement one seam and watch its annotation become a failure: `mx/skills/tracker/board.py:592` `needs_me` is four lines.

**I need from you**

- [D1] **A done ticket with an open question is in needs me, by the Property read literally.** The board's groups are otherwise one per ticket, and done is folded away, so 03 will have to put it somewhere. Either the Property wants "a ticket that is not done", or the needs-me group wins over done.
- [D2] **The no-overlap Property is executable only as far as render-lint reaches.** It measures text against its own box and SVG text against other SVG text; two HTML marks overlapping each other, and text a box clips rather than spills, are outside it. The spec disposes the Property as executable; either that reading stands with the limit written into the spec's Testing Decisions, or teaching render-lint HTML-to-HTML overlap is a ticket of its own, against `mx/skills/show/render_lint.py`, which every `/mx:show` artefact would gain from.
- [D3] **The review-page server's absence is not said on the page**, and no slice owns saying it. This ticket dispositions that property as already holding (the render works and the pages link as files), which is what I built; if "says each absence once" is meant to cover all four sources, 02 owns the page and should carry a fourth note.
- [D4] **The demo tracker now exists twice**: the prototype's `build.sh`, which renders the prototype and teaches the rejected `name:` field, and the promoted `demo_tracker.py`. They drift from here. Retiring the prototype's copy with ticket 10 would end that; keeping it as the prototype's primary source is the alternative.
- [D5] **Hypothesis is now a dependency of `make test`.** Three of the checks are rule-shaped and generated inputs discriminate there; if the repo would rather not carry it, they can be written as worked examples at some loss.

**Details, if you want them**

- [D6] Assumptions
  - A1 `mx/skills/tracker/test_board.py:572`: the Property's "a build in review" is read as any ticket at status review, since the Decisions fold the whole "needs my review" group into needs me.
  - A2 `mx/skills/tracker/test_board.py:574`: "a design or prototype decision" is read as the `grilling` and `prototype` types, the two the user sits for; "nobody has claimed" as open or proposed, since a blocked or done ticket is not the user's to sit for.
  - A3 `mx/skills/tracker/board.py:592`: the needs-me rule is a pure function of the four things a ticket file says, rather than a method on a row, so 02's choice of where priority lives does not gate 03.
  - A4 `mx/skills/tracker/board.py:635`: an absence is said through `absence_note`, marked `data-absent="<source>"`. Implemented rather than stubbed: "said once" is only checkable against a marked note, and without one the check would have to pin the page's wording.
  - A5 `mx/skills/tracker/test_board_layout.py:65`: the layout check requires the page to pin its scheme from `?theme=`, the house style's switch. Without it both runs measure the same scheme, and the check would pass today saying nothing.
  - A6 `mx/skills/tracker/test_board_layout.py:43`: browser zoom scales the layout, so a window of W pixels at zoom Z is measured as W/Z CSS pixels; the widths are that quotient over the four windows and four zooms, fourteen browser runs once the check goes green.
  - A7 `mx/skills/tracker/briefing.py:20`: `PING_CAP = 20`, a number the spec does not give; 09 confirms it. `DEBOUNCE` is the low end of the spec's five to ten minutes.
  - A8 `mx/skills/tracker/briefing.py:55`: the schedule answers with one of three verbs, "ping", "wait" or "fresh", and the caller applies it; the cache file is a dataclass with the six fields the spec names.
  - A9 `mx/skills/tracker/demo_tracker.py:538`: the fixture's transcripts carry `ai-title`, which is what all 1505 title records on this host carry, with one session also carrying a `/rename` name so the precedence has an example. No session here has ever been renamed, so that record's shape is the prototype's reading, not something I could verify.
  - A10 `Makefile:17`: Hypothesis added to the test command (D5).
  - A11 `mx/skills/tracker/conftest.py:1`: the checks share a `conftest.py` rather than a second suite; the loader properties sit in `test_board.py` as the spec's Testing Decisions names it, the layout and schedule seams in files of their own.
- [D7] Findings, from `/mx:code-review` over `faf6f0f..e4cae0f`, four axes, reports in `agent/reviews/faf6f0f..e4cae0f/`
  - Fixed in fde7abc: the transcript fixture's invented format and project-directory slug (correctness 5, standards 1, spec C4, tests F1); two properties entering below the seam the Testing Decisions names (spec C1, tests F7); `TRANSCRIPTS` ignoring `$CLAUDE_CONFIG_DIR` (correctness 4, standards 2); `uv run test_briefing.py` dying on a missing tyro (correctness 1, standards 3, spec C8); real `diffview --serve` processes on a machine that has diffview (correctness 2, standards 9, spec C5, tests F8); the gh check counting processes and lines rather than queries (spec C6, tests F12); the schedule property asserting the constants against themselves (tests F3); `needs_me` sampled rather than enumerated, and its readings unrecorded (correctness 6, standards 6); the question generator unable to produce the spec's own questions (standards 8, tests F6); the weak `detail` assertion (tests F5); `PING_CAP` unmarked (correctness 7, standards 5); "the properties are the oracle" inverting the glossary (standards 4); the widths not derivable from the sentence explaining them (standards 18); the precondition's message overstating what it checks (standards 19); `Briefing`'s field list written three times and its parameter named for the wrong concept (standards 10, 12); `rm -rf` through the shell (correctness 7); the docstring's miscounts and its history in `--help` (standards 16).
  - Declined, with the reason in the assumption it stands on: the review-page server's absence (correctness 3, standards 20, tests F9) → D3; render-lint's reach (tests F2, spec C3) → D2; the cache file's round trip being its own oracle (tests F4) → it is a round trip, which is an oracle; the model-call check having no positive leg (standards 15, tests F13) → the spec puts the ping in the watcher, so a render that called the model would be the bug; `needs_me`'s check transcribing the rule (standards 7) → the rule is the spec's sentence, which is the oracle available; the three verbs having no named home (standards 11) → the test's literal set is the oracle, the docstring the interface; `path_with` naming one of its two jobs (standards 14); the two demo trackers (correctness 7, standards 17) → D4; the Testing Decisions' per-slice checks (frontmatter, the H1 as name, the Brief, GitHub state from a stubbed query, the briefing fallback) having no checks here → they are named in 02, 03, 07 and 09's own criteria, not in this ticket's Properties.
- [D8] Friction
  - The spec's own disposition of two properties was unbuildable as written, and I only found out by running them: a pure render-lint check and a pure "no model call" check both pass on today's board, so an expected failure on either would have gone red at once. Both needed a second assertion to have teeth (A5, and the cached briefing showing on the page). A spec that dispositions a property as executable is worth one run against the current code before the ticket is cut: `make test` with the property written and no annotation says immediately whether it is red today.
  - Hypothesis prints ``git apply .hypothesis/patches/...`` after every run while an expected failure stands, which reads as an action the suite wants taken and is not one. It will be on every worker's `make test` output until 03, 05, 07 and 09 land. No switch turns it off.
  - `board` cannot render on a dispatch worker host: the main checkout there is the bare repo the worktrees hang off (`/home/agent/repos/dispatch/agents.git`), and `tracker_roots` reads the tracker from the main checkout, so it stops with `no tracker at .../agents.git/agent/tickets`. Nobody opens a board on that host, so it cost me only the render the tracker conventions ask for after a ticket change; it would cost a worker that wanted to look at the tracker it is working from.
  - `harden` runs the suite through `uv run --with mutmut --with coverage --with pytest-cov`, which does not carry this repo's test dependencies; hypothesis is now one more. I did not run it (it is the orchestrator's, per feature), so I do not know whether it already works here.
