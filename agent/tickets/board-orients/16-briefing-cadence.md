---
status: review
blocked-by: [13]
priority: 2
size: XS
---

# The briefing's cadence and model, as ruled

## Brief

The briefing is rewritten when a ticket's status has changed, after five minutes with no further change, and at most once every ten minutes. It runs on Opus 5.5 at medium effort. Today any edit under the tracker counts as a change, and the model is whatever this machine's `claude` defaults to.

Ruled by the user on 2026-09-23, on 09's D2 and its cadence, after 09 merged.

## Questions

- [D1] **The ten-minute floor is measured from the session's last run, not from the time the last briefing was written.** The two come apart when a ping answers `unchanged`: the run costs what a run costs and writes no new text, and measuring from the run pushes the next rewrite out by ten minutes from there. Measuring from `written`, which is what this ticket says, would let a tracker that keeps moving pay a run on every pass once ten minutes have passed since the last rewrite, which is the cost the ruling caps. I built the conservative one; the ticket's letter is the other.
- [D2] **A tracker whose statuses move oftener than every five minutes never gets its briefing rewritten.** The quiet window restarts on each status change, so a dispatch wave landing a ticket every four minutes leaves the column showing the briefing from before the wave, for as long as the wave runs. That is the rule as ruled ("waits for five minutes with no further status change"), and a wave moves in bursts rather than steadily, so it may never bite; what is gone is any bound on how stale the column can be, since the idle hour retires a session rather than writing a briefing. A ceiling ("ping anyway once the briefing is half an hour old") is the alternative, and it is one more window to hold in your head.

## What to build

The watcher pings the briefing session only when a ticket's status has changed since the last briefing, a new ticket and a retired one included. A text edit to a ticket does not count. The ping waits for five minutes with no further status change, and never comes sooner than ten minutes after the last briefing was written. Every `claude -p` run of the briefing passes `--model claude-opus-5-5 --effort medium`. It runs without the user's output style, which shapes replies for a human at a terminal (ruled 2026-09-23 for every noninteractive run; `"outputStyle": "default"` in its settings does it, as for dispatch workers). The schedule's property check follows the new rule.

## Acceptance criteria

- [x] A ticket's status change reaches the session after five quiet minutes, and no sooner than ten minutes after the last briefing.
- [x] An edit that changes no ticket's status sends no ping.
- [x] The briefing session runs on Opus 5.5 at medium effort.
- [x] A captured first request of the briefing carries no output style (`~/Downloads/show/review-launcher-calls/proto/capture.py` records one).
- [x] Demo: a status change, a text edit, and a second status change inside ten minutes, with the pings each one produced.

## Comments

The watcher pings the briefing session only on a ticket's status moving, five minutes after the last
one to move and no sooner than ten minutes after the session's last run, and every run of it passes
`--model claude-opus-5-5 --effort medium` with the stock output style. A ticket filed or retired is a
status appearing or going; prose rewritten is a render and nothing else. On branch
`ticket/board-orients/16-briefing-cadence`, not merged. My calls for you are this ticket's
`## Questions`.

**Demo**

    /home/agent/repos/dispatch/agents-board-orients-16-briefing-cadence/agent/show/board-orients/16-briefing-cadence/demo

drives a watched board over twenty minutes of the demo tracker on a clock it holds, with the model
stubbed, and then captures what a real run of the briefing sends to the API, against a recorder on
localhost with an output style planted where yours would be read from. It spends no tokens and takes
about a minute. The run:


    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the tracker under the board
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    /home/agent/repos/dispatch/agents-board-orients-16-briefing-cadence/agent/show/board-orients/16-briefing-cadence/out/tracker/agent/tickets
    the board it renders: /home/agent/repos/dispatch/agents-board-orients-16-briefing-cadence/agent/show/board-orients/16-briefing-cadence/out/tracker/agent/board.html

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the windows the watcher holds to (mx/skills/tracker/briefing.py)
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    a ping waits 5 minutes after the last status to move, and no run of the session
    is started sooner than 10 minutes after the one before it; it retires after 1 h idle or 20 pings

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the clock: what each pass of the watcher did
    ────────────────────────────────────────────────────────────────────────────────────────────────────
     min  what happened to the tracker                the page  the session
       0                                                        explored the repo, wrote the briefing
       1                                              rendered  
       2  csv-import/02 accepted: review to done      rendered  told a status moved
       3                                                        waiting: the tracker is still moving
       4  csv-import/04's brief reworded              rendered  waiting: the tracker is still moving
       5                                                        waiting: the tracker is still moving
       6                                                        waiting: the tracker is still moving
       7                                                        waiting: the last briefing is not ten minutes old
       8                                                        waiting: the last briefing is not ten minutes old
       9                                                        waiting: the last briefing is not ten minutes old
      10                                                        pinged, and it rewrote the briefing
      11  csv-import/04 claimed                       rendered  told a status moved
      12                                                        waiting: the tracker is still moving
      13                                                        waiting: the tracker is still moving
      14                                                        waiting: the tracker is still moving
      15                                                        waiting: the tracker is still moving
      16                                                        waiting: the last briefing is not ten minutes old
      17                                                        waiting: the last briefing is not ten minutes old
      18                                                        waiting: the last briefing is not ten minutes old
      19                                                        waiting: the last briefing is not ten minutes old
      20                                                        pinged, and it rewrote the briefing

    Minute 1 is the briefing written at 0 reaching the page: the watcher re-renders on the cache
    file beside it as well as on the tracker. Minutes 3 to 9 and 12 to 19 are the two windows: the
    tracker has to go five minutes without a status moving, and the last run of the session has to
    be ten minutes back. Minute 4 is the one the rule is for: prose is a render and nothing else.

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    what the watcher launched, as it ran it (the stub recorded its own arguments)
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    --system-prompt <the briefing's own prompt, 785 characters> -p <the tracker as the board reads it, 9634 characters> --model claude-opus-5-5 --effort medium --output-format json --allowedTools Read,Glob,Grep,Bash(git log:*),Bash(git show:*),Bash(git diff:*) --disallowedTools Write,Edit,NotebookEdit --settings {"autoMemoryEnabled": false, "claudeMdExcludes": ["/home/agent/.claude/CLAUDE.md"], "outputStyle": "default"}

    --resume 5ec96e3f-demo -p <the note of what changed, 398 characters> --model claude-opus-5-5 --effort medium --output-format json --allowedTools Read,Glob,Grep,Bash(git log:*),Bash(git show:*),Bash(git diff:*) --disallowedTools Write,Edit,NotebookEdit --settings {"autoMemoryEnabled": false, "claudeMdExcludes": ["/home/agent/.claude/CLAUDE.md"], "outputStyle": "default"}

    [ the third launch is the second again, on the note minute 20's change made ]

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    what each ping told the session, in the words it was told them in
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    changed: agent/tickets/csv-import/02-map-columns.md, agent/tickets/csv-import/04-commit-import.md

    changed: agent/tickets/csv-import/04-commit-import.md

    The note names every file that moved since the session was last told, the reworded brief
    among them; what decides whether a ping goes at all is the status.

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the cache file beside the board
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    {
     "text": "csv-import/04 is claimed and running; speed-up-tests is the only review left on you.",
     "written": "2026-09-23T09:20:00+02:00",
     "session": "5ec96e3f-demo",
     "started": "2026-09-23T09:00:00+02:00",
     "last_activity": "2026-09-23T09:20:00+02:00",
     "pings": 2
    }

    The board this left behind, with the last briefing at the head of its side column: /home/agent/repos/dispatch/agents-board-orients-16-briefing-cadence/agent/show/board-orients/16-briefing-cadence/out/tracker/agent/board.html

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the launch: the request a real run sends, captured
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    An output style is planted in /home/agent/repos/dispatch/agents-board-orients-16-briefing-cadence/agent/show/board-orients/16-briefing-cadence/out/config,
    where the user's own would be read from, and three runs go to a recorder on localhost: the
    briefing as the board launches it, the same with its settings emptied, and a bare run of
    the model, which is what this machine gives a launch that says nothing about either.
    A run names its own session in a request of its own, which carries no tools; the one read
    here is the agent's, which carries them.


    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the briefing, as the board launches it: claude-opus-5-5, effort medium
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the planted output style is nowhere in the request (91 KB, 3 system blocks, 23 tools)

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the briefing, with its settings emptied: claude-opus-5-5, effort medium
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the planted output style is nowhere in the request (91 KB, 3 system blocks, 23 tools)

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    a bare run of the model on this machine: claude-opus-5-5, effort medium
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the planted output style is in the request (100 KB, 3 system blocks, 24 tools)

    Read across the three: what this machine would put in a run is in the third and in neither
    of the briefing's, because the briefing replaces the system prompt the style is written into.
    Its settings say so as well ('default'), which is what holds if a launch ever appends its
    prompt rather than replacing it.

    The three requests as they went: /home/agent/repos/dispatch/agents-board-orients-16-briefing-cadence/agent/show/board-orients/16-briefing-cadence/out/*.json

The figure beside it is the before and the after:

    /home/agent/repos/dispatch/agents-board-orients-16-briefing-cadence/agent/show/board-orients/16-briefing-cadence/figure.html

the same forty minutes driven through the schedule as this branch was cut from it, read out of git,
and through the ruled one: eight runs of the model against three, with the closing comment a worker
writes drawing the difference.

The demo captures the launch with a recorder of its own rather than
`~/Downloads/show/review-launcher-calls/proto/capture.py`, which is on your machine and not on this
host; it also captures a bare run of the model beside the briefing's two, since "the style is
nowhere in the request" says nothing without a run that has it.

**I need from you**

This ticket's `## Questions`: D1 and D2 above.

**Details, if you want them**

- [D3] Assumptions
  - A1 `mx/skills/tracker/briefing.py:121`: the ten-minute floor is read off the session's last run rather than the time the last briefing was written, which is D1.
  - A2 `mx/skills/tracker/board.py:410`: a pass that moves no status leaves the quiet window where it stands, and statuses back at what the session was last told clear it, which is my reading of "changed since the last briefing".
  - A3 `mx/skills/tracker/board.py:282`: the watcher's first pass reads the tracker once more for its baseline instead of taking the render `main` did, so the baseline and the file snapshot it is measured against are read in one pass; it costs one load per watcher start (declined finding).
  - A4 `mx/skills/tracker/briefing.py:153`: `"outputStyle": "default"` is belt and braces. The demo's capture shows the style is already out of the request because the run replaces the system prompt it is written into; the setting is what holds if a launch ever appends its prompt instead.
  - A5 `agent/tickets/board-orients/spec.md:117`: the confirmed spec's Decision and Property are amended in place with dated marks as 13's amendment was, its Testing Decisions gains the launch seam, and a Decision records the model, the effort and the output style.
  - A6 `agent/tickets/unattended-launch.md:22`: that ticket's table of call sites had the briefing inheriting your output style, which this branch makes untrue, so its row is rewritten. It is another ticket's file, and an open grilling.
  - A7 `agent/show/board-orients/09-briefing/demo:109`: 09's landed demo called a constant this branch deletes and its figure quoted the hover words this branch rewrites, so both are fixed and the figure re-rendered from its own script.
  - A8 `mx/skills/tracker/test_briefing.py:42`: the drawn runs' gaps are narrowed to eighteen minutes over up to eighty ticks, since wider ones retire every session on the idle hour and leave the ping cap with no witness.
  - A9 `mx/skills/tracker/board.py:263`: `render` answers with the statuses it drew, which is how the watcher gets them without loading the tracker twice per change.
- [D4] Findings, from `/mx:code-review` over `298cff2..3d5ff52`, four axes, reports in `agent/reviews/298cff2..3d5ff52/`
  - Fixed in 1657a2f, the two that cost a run of the model: the ten-minute floor sat below the retirement test, so a session past its ping cap explored the repo again five minutes after the last briefing (correctness F1, spec C3); and the watcher compared each render against the pass before it rather than against what the session was last told, so a ticket claimed and unclaimed inside a window bought a ping (spec C1).
  - Fixed in the same commit, what no check could tell from its absence: the model and the effort asserted against themselves rather than against the literals the spec decides (tests A1), the ping cap unreachable in the drawn runs, at fifteen of twenty (tests C2), the retry of a run that answered nothing (tests D1), the hover words the user reads (tests D2), the watcher's pass never driven over a feature ticket, a ticket retired, or a status put back (tests A2, B2, spec A3), and the opening baseline no check could see (tests B3). The tautology and three of the mutations are killed by the new checks; the ping-cap one needed a worked example, which the drawn runs alone still do not reach reliably.
  - Fixed in the same commit, the prose: the spec's Testing Decisions still named the retired window and no seam for the launch (spec A2, standards H1, tests B1), the amended Decision and Property timed the quiet window off any edit rather than off a status (correctness F2, standards J2), 09's demo called `briefing.DEBOUNCE` (standards H1), `github.py` justified its five minutes by a window that no longer exists (correctness F5), the hover tip broke mid-clause and said "20 of those" (standards J6, spec D2's note), the ping cap's prose restated a number the check did not pin (correctness F3, standards J8), a confirmed spec carried a ruling receipt (standards H3), tickets were named by bare id (standards H4), the launch table said more than the diff shows (spec C5), `statuses` described itself as the group a row is shown under (spec C4), "a window" named two windows (standards J1), and three `--` dashes (standards H2).
  - Fixed in the same commit, the artefacts: the figure's `exec` of a string where its three siblings load a file (standards J15), its `object`-typed module, branch-named alias, three parallel dicts and repeated event lookup (J14, J20, J16, J21), its off-grid coordinates and hand-placed legend (J18), its scheme script below the body where a screenshot can catch the wrong one (J19), and "rewritten" where the schedule knows only runs (J17); the demo's dead parameter, hand-rolled context manager, free-port race, shadowed name, duplicated heading and two-meanings-of-`told` line (J22 to J27), its missing opener (J28), and its three captures now asserted rather than only printed (tests D3).
  - Declined, with the reason in the assumption it stands on: the second load at the watcher's start (spec B1, standards J4) → A3; the floor read off the last run rather than the last briefing written (spec C2) → A1 and D1. Left alone: the watcher-side assertion that reads as the cadence gate and is stopped by `Briefer.tried` (correctness F4, standards J10, tests' own note), now reworded to say which gate it tests, since the cadence itself is checked at the schedule seam; and `Seen.statuses` using `()` where `snapshot` uses None (standards J5), which the field's own comment now explains.
  - Not a finding, and worth keeping: the demo's own recorder, which the spec axis called the largest thing nobody asked for and earned (spec B2).
- [D5] Friction
  - The layout check (`test_board_layout.py`, no-overlap) fails under `make test` and passes when its file runs alone. It failed twice on this branch and once on an archive of the merge-base, and passed on the third full run, so it is flaky under a loaded machine rather than this branch's doing; the finding it reports is a text box in the graph overlay measured at a negative x. Twenty minutes went to proving it was not mine, by unpacking the merge-base into `/tmp` and running the suite there. What would have saved it is the check saying which element it measured in the failure message, and a name for the state it is in when the whole suite runs before it.
  - The account hit its weekly usage limit mid-review: two of the four axes died with `You've hit your weekly limit` in their logs and left no report, which reads exactly like an axis that found nothing until you open the log. The re-run an hour later worked. `review` names the axis that left no report and prints the command to re-run it, which is what made it recoverable; what it cannot do is say the run died on quota rather than on the diff.
  - `claude -p` against a local recorder captures a launch for nothing: `ANTHROPIC_BASE_URL` at an HTTP server on localhost, `ANTHROPIC_API_KEY` at any string, and the recorder answering 400 so the run gives up rather than retrying for thirteen minutes. The request carries the model, the effort and every system block, so what an unattended launch really sends is readable without spending a token. `unattended-launch`'s brief points at a capture script on your machine; this is the same move in twenty lines, and it belongs in that ticket rather than in a show directory of mine.
  - A run also names its own session in a request of its own, before the agent's, and that one carries no tools. The first capture I read was that one: 4 KB, `output_config.effort` from your machine rather than the flag, and no output style, which made the briefing look like it was already doing what this ticket asks. Reading the request that carries tools is what makes the capture say anything.
  - `python3` is not on this host; `uv run python` is. A recorder started with `python3` failed silently into a log nobody reads, and the first capture attempt hung for two minutes on a `claude` retrying an unanswered port.
