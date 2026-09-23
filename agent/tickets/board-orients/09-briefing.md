---
status: claimed
blocked-by: [08]
priority: 2
size: M
---

# The board briefing

## Brief

A model session explores the repo once and writes the briefing: where things stand and the next picks, marking what can run in parallel. Tracker changes are sent to that same session, debounced, and it retires after an idle hour or a ping cap.

Slice of `spec.md`, building on the Decisions under "The board briefing".

## Questions

- [D1] **The board asks GitHub once every five minutes for as long as it is watched.** The watcher now re-renders when the cached answer has run out, so a pull request that merges while the tracker sits still shows as merged within the window instead of waiting for someone to touch a ticket (07's D3, which you have not ruled on). It costs one GraphQL query and one render, 0.3 s here, every five minutes per watched board that names any `gh` reference; a tracker naming none is untouched, and the page's stamp is unchanged when the answer is, so the open tab does not reload for it. A quiet tracker asked nothing at all before.
- [D2] **The briefing runs on whatever model this machine's `claude` is set to, with no effort flag.** On opus, two runs of the demo put a first exploration at $0.35 and $0.54 and the ping after it at $0.30 and $0.54: what it costs is the exploring, not the rereading, since the hour-long prompt cache carries the session's own context between pings and not the repo it reads each time. A board watching a tracker that changes every window pays that once a window, so a working day with the board open is dollars rather than cents. Pinning it to sonnet, or to a low effort, is one constant.
- [D3] **A board started on a quiet tracker writes its first briefing straight away.** The spec hangs every briefing on a tracker change, which would leave the board you open after a week away showing the deterministic count for ever: the tracker has not changed precisely because you were away. So the watcher's own start counts as a change where no briefing has ever been written; one already written is left standing however old, with the time it was written beside it.
- [D4] **The session retires on an hour idle or twenty pings, and nothing reads its context.** The spec names the session's context as a third limit; the cache file cannot say it and `claude -p` does not report it. Twenty pings is at least an hour and three quarters of a tracker changing every window, and Claude Code compacts a session that outgrows its window rather than failing. A real context limit means reading the session's transcript, which is machinery this does not have.

## What to build

The first run is a fresh `claude -p` session on a short prompt of its own, never the user's system prompt, given the tracker's state as the board computes it and free to explore the repo from there. It writes a few sentences on where things stand and three next picks with a reason each, marking picks that can run in parallel as one wave for dispatch. The board's watcher sends each tracker change, debounced by five to ten minutes, to the same session with `--resume` as a short note of what changed, and the session decides whether and how to rewrite the briefing. The session retires after an idle hour or a cap on pings or context, whichever comes first, and the next change starts a fresh one. A cache file beside the board holds the briefing, the time it was written, and the session's id, start, last activity and ping count; the board shows the time written. With no model available, or before the first briefing, the board writes the deterministic sentence and ordering the spec names.

The prompt cache's lifetime on the plan in use (five minutes by default, an hour where the longer cache applies) is confirmed before the idle limit is set, and the closing comment says which it found.

## Acceptance criteria

- [x] The pings-and-retirement, no-model-call-on-an-unchanged-render and render-without-the-model checks from 01 pass and their annotations are gone.
- [x] The briefing shows the time it was written, and the fallback shows when no briefing exists.
- [x] Demo: the demo tracker's first briefing written, a change pinged into the same session and the briefing it rewrote, and the cache file after both.

## Comments

The side column opens with the board briefing: where things stand and three next picks, written by
a `claude -p` session that is given the tracker as the board computes it and explores the repo from
there, with the time it was written beside it. The board's watcher sends that session what changed,
at most once a five-minute window, and retires it after an hour idle or twenty pings; until a
briefing has been written the column holds the board's own count of what waits and the frontier by
what accepting it unlocks. On branch `ticket/board-orients/09-briefing`, not merged. My calls for
you are this ticket's `## Questions`.

The spec asked this slice to confirm the prompt cache's lifetime on the plan in use before setting
the idle limit. A `claude -p` run on this machine reports its input under
`cache_creation.ephemeral_1h_input_tokens` and nothing under the five-minute one, so it is the
hour-long cache, and the idle limit is the hour the spec's other branch names. The demo prints that
reading on each of its two runs.

**Demo**

    agent/show/board-orients/09-briefing/demo

builds the demo tracker, renders its board with no briefing, then makes the two calls the watcher
makes: a fresh session on the tracker's state, and a `--resume` ping on the note a change makes. It
prints what each run was given, what it answered, what it cost and how much of that came back from
the prompt cache, and the cache file after each. It runs the model twice on this machine's own
login, about a minute and a dollar. Run here, with the tracker's own state cut where the demo
already cuts it:

    /tmp/board-briefing-demo/board.html

    The board with no briefing written yet: /tmp/board-briefing-demo/board.html

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    what the column holds meanwhile
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    Two builds to rule on, eleven questions wanting a word and two design sessions wait on you. One ticket is being worked on.

    ## next
    - **Map columns once per bank**: now · accepting it unblocks one · 1 h of yours
    - **The flaky upload test**: now · 15 min of yours
    - **Retire the QIF exporter**: now · 1 h of yours

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    what a fresh session is given (board.briefing_state)
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    The tracker of board-briefing-demo as the board reads it.

    One line per ticket: reference, status, what it asks of you, priority, your time on it, its name,
    its file. Under it, where the ticket has them: the brief, what it waits on, its open questions.


      [ ... one line per ticket, its brief, what it waits on, its open questions ... ]

    …

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the briefing it wrote, having explored /tmp/board-briefing-demo · $0.539 · 129867 tokens read from the prompt cache, 37529 written to the hour-long cache and 0 to the five-minute one
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    csv-import/01 is in, and 03 is claimed and running. The thing holding the feature is 02's review: its demo and diff are already sitting in `agent/show` (first import asks for the columns, second asks nothing), both acceptance boxes still unticked, and its three questions — mapping per bank or per file, comma decimals, where `mappings.toml` lives — are what you're actually ruling on. 04 waits on 02, and 05, export-to-xlsx and saved-views/02 all wait on 04. flaky-upload-test reads as two questions on the board, but D2 was ruled Monday; only retry-or-fake-clock is left.

    ## next

    - Rule csv-import/02 and four tickets come unstuck; the demo runs in a minute.
    - flaky-upload-test is half-answered already, so 15 minutes closes a p1.
    - retire-legacy-exporter's D2 is a question for three users, and replies take days, so send it today.

    All three can run at the same time: send the QIF question first, then rule the review and the test while answers come back.

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the cache file beside the board
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    {
     "text": "csv-import/01 is in, and 03 is claimed and running. The thing holding the feature is 02's review: its demo and diff are already sitting in `agent/show` (first import asks for the columns, second asks nothing), both acceptance boxes still unticked, and its three questions \u2014 mapping per bank or per file, comma decimals, where `mappings.toml` lives \u2014 are what you're actually ruling on. 04 waits on 02, and 05, export-to-xlsx and saved-views/02 all wait on 04. flaky-upload-test reads as two questions on the board, but D2 was ruled Monday; only retry-or-fake-clock is left.\n\n## next\n\n- Rule csv-import/02 and four tickets come unstuck; the demo runs in a minute.\n- flaky-upload-test is half-answered already, so 15 minutes closes a p1.\n- retire-legacy-exporter's D2 is a question for three users, and replies take days, so send it today.\n\nAll three can run at the same time: send the QIF question first, then rule the review and the test while answers come back.",
     "written": "2026-09-23T13:07:30.399577+00:00",
     "session": "5ec96e3f-5fd0-4471-b859-d4564bfeaf48",
     "started": "2026-09-23T13:07:30.399577+00:00",
     "last_activity": "2026-09-23T13:07:30.399577+00:00",
     "pings": 0
    }

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    what the watcher tells that same session, a window after the change
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    changed: agent/tickets/csv-import/02-map-columns.md
    the repo has moved on: 1c66c9a csv-import: 02 accepted is its last commit

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    what it made of the change, in the session it already explored in · $0.543 · 125068 tokens read from the prompt cache, 43392 written to the hour-long cache and 0 to the five-minute one
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    csv-import/02 is accepted, so the keystone is gone and 04 is the frontier: one transaction per import, an hour of work, with 05, export-to-xlsx and saved-views/02 all queued behind it. 02 landed with both acceptance boxes still unticked, and the second one, "a mapping that fails halfway writes nothing," is really 04's property, so 04 is where it gets proven — check that before you hand it off. speed-up-tests is now the only review still sitting on you. flaky-upload-test reads as two questions on the board, but D2 was ruled Monday; only retry-or-fake-clock is left.

    ## next

    - csv-import/04 is newly unblocked and three tickets wait on it; it can go to a worker.
    - flaky-upload-test is half-answered already, so 15 minutes closes a p1.
    - retire-legacy-exporter's D2 is a question for three users, and replies take days, so send it today.

    The first can run at the same time as the other two: dispatch 04, send the QIF question, then rule the test while both are out.

    ────────────────────────────────────────────────────────────────────────────────────────────────────
    the cache file after both
    ────────────────────────────────────────────────────────────────────────────────────────────────────
    {
     "text": "csv-import/02 is accepted, so the keystone is gone and 04 is the frontier: one transaction per import, an hour of work, with 05, export-to-xlsx and saved-views/02 all queued behind it. 02 landed with both acceptance boxes still unticked, and the second one, \"a mapping that fails halfway writes nothing,\" is really 04's property, so 04 is where it gets proven \u2014 check that before you hand it off. speed-up-tests is now the only review still sitting on you. flaky-upload-test reads as two questions on the board, but D2 was ruled Monday; only retry-or-fake-clock is left.\n\n## next\n\n- csv-import/04 is newly unblocked and three tickets wait on it; it can go to a worker.\n- flaky-upload-test is half-answered already, so 15 minutes closes a p1.\n- retire-legacy-exporter's D2 is a question for three users, and replies take days, so send it today.\n\nThe first can run at the same time as the other two: dispatch 04, send the QIF question, then rule the test while both are out.",
     "written": "2026-09-23T13:08:28.693743+00:00",
     "session": "5ec96e3f-5fd0-4471-b859-d4564bfeaf48",
     "started": "2026-09-23T13:07:30.399577+00:00",
     "last_activity": "2026-09-23T13:08:28.693743+00:00",
     "pings": 1
    }
    /tmp/board-briefing-demo/board.html

    The same board with the briefing at the head of its side column: /tmp/board-briefing-demo/board.html
    Watch it keep itself current: CLAUDE_CONFIG_DIR=/tmp/board-briefing-demo/claude uv run /home/agent/repos/dispatch/agents-board-orients-09-briefing/mx/skills/tracker/board.py /tmp/board-briefing-demo/agent/tickets

The board it leaves behind is the one to open; the last line it prints is the command that watches
that tracker, which is where the ping happens on the clock rather than on demand.

**The figure**

    agent/show/board-orients/09-briefing/figure.py    # writes figure.html beside it

`agent/show/board-orients/09-briefing/figure.html` is the before and the after: three panels, each
a screenshot of the board's side column, with a numbered badge sitting where each note points,
placed from the box the browser measured for that element. The `before` panel runs the board as
`f977938` had it, read out of git, so it is what the board did rather than an account of it; the
other two are the column now, with the board's own count and with a briefing a session really wrote
on that tracker, kept in `briefing.json` beside the figure so it costs no model run and says the
same words every time. Both schemes are captured and the day/night switch picks one. It is
committed, so opening it needs no build.

**Details, if you want them**

- [D5] Assumptions
  - A1 `mx/skills/tracker/briefing.py:36`: the session's own prompt is `--system-prompt`, with settings that leave the user's memory files out and tools that read; the machine's own permissions still stand under those, so the three tools that write are named as denied rather than left unmentioned.
  - A2 `mx/skills/tracker/briefing.py:26`: twenty pings retires a session, where the spec says a cap and gives no number (D4).
  - A3 `mx/skills/tracker/briefing.py:116`: retirement reads the clock and the ping count, and nothing reads the session's context, which the spec names as its third limit (D4).
  - A4 `mx/skills/tracker/board.py:303`: the watcher's own start is a change where no briefing has ever been written, so a tracker quiet since the last one still gets a first briefing (D3).
  - A5 `mx/skills/tracker/board.py:306`: a watched board re-renders when GitHub's cached answer has run out, which is 07's D3 and this ticket's D1, and the orchestrator's recommendation rather than the spec's (D1).
  - A6 `mx/skills/tracker/board.py:386`: a run's clock is read before it starts, so the session's last activity is what a change arriving mid-exploration is read as untold against; the time the column shows is the run's start rather than its answer, which is a minute out and never a change dropped.
  - A7 `mx/skills/tracker/board.py:1873`: the session's markdown goes onto the page as a ticket's own does, which is the first model-written text the board renders; a local page rendering a local model's answer is the reason, and escaping it would take the emphasis with it.
  - A8 `mx/skills/tracker/test_board.py:1861`: five checks beyond the seams the Testing Decisions names, all of them at seams this slice created: what a fresh session is given, what a change tells it, the board's own count, one pass of the watcher, and the watcher's own briefing schedule with `claude` stubbed as the Decisions asks. The Decisions wants a sentence for them when this lands.
  - A9 `mx/skills/tracker/board.py:119`: two boards watching one tracker each keep their own briefing schedule, so each pays for every briefing and each resumes the same session; the `--help` says one watcher per board rather than a claim file guarding it, since the cost is two runs and a ping count, not a broken page.
- [D6] Findings, from `/mx:code-review` over `f977938..3da2a2f`, four axes, reports in `agent/reviews/f977938..3da2a2f/`
  - Fixed in ec1b806, the three that cost money or lose work: a watched board exploring the repo again every idle hour for a change the session answered hours ago, since `on_change` read retirement before "this change already reached it" and the watcher's `changed_at` is never cleared, which is roughly $6 a night on an untouched tracker (correctness 1, spec c1); the GitHub clock re-rendering every two seconds once a tracker stops naming any reference, since the answer it reads never moves again and the stamp never changes, so nothing on screen says the board is spinning (correctness 2); and a run that answered nothing having already consumed the account of what moved, so the retry pinged the session with "something under the tracker was touched without changing" (correctness 3, spec c3).
  - Fixed in the same commit, what the reader sees: the board's own count saying "One build to rule on wait on you" (standards 2) and counting no design session where the row under it is tagged one, because its buckets were exclusive where the row's mark is not (spec c5); a tracker with nothing open showing a bare `## next`; the briefing's hover words, the first tooltip on the page inside a box that scrolls, cut off at its last two lines, now the `title` the column's own buttons already use (tests D6, standards 10); the shown time carrying no year (spec c8); the `--help` saying the board's own count is what a machine without `claude` shows even when a briefing stands (spec c8).
  - Fixed in the same commit, the machinery: the session given `--system-prompt` and still the user's memory files, now run with the settings that leave them out and with the three writing tools denied (spec c6); a model that is installed and cannot answer saying so only on the console, now on the page in its own words as GitHub's absence is (standards 4, correctness's own note); `BRIEFING_TIP` spelling out the two windows whose home is the schedule (standards 3); the tracker load written out three times, one copy without the rule that hides an absorbed standalone ticket (standards 7); `now` naming the module's clock and a dict of paths in one function (standards 8); `Briefer.showing`, the watcher's render bookkeeping living on the session object (standards 9); `Briefer.tick` walking the tracker a second time in the same pass (standards 9); `quiet` returning a value it is typed not to have and `absences`' new parameter named for a datetime (standards 10); `import json` out of order and the em dashes in what the board writes and in the checks that read it back (standards 1); the demo's copy of the loader and its inline dependency on the fixture's feature list (standards 7, 10); the figure's two notes claiming what the render does not show, the wave line among them, now a recorded run that has one (spec c4, standards 6); `MARKDOWN.md` restating the fallback (standards 11); and `test_briefing.py`'s own dependencies, which had never let it run the way its docstring says (pre-existing, found by three of the four axes).
  - Covered by the same commit's checks, from the tests axis's list of what no check could tell from its absence: one pass of the watcher (`look`), so the two re-render triggers are driven rather than described; the watcher's own schedule with `claude` stubbed, which is the stub the Testing Decisions named and nothing had built, including that a fresh run passes `--system-prompt` and a ping `--resume`; `content_stamp`'s briefing term, which is the whole live path; both halves of the model absence; the clock that arms the GitHub re-render; a worked-example line of what the session is handed, brief included, and the standalone block; a change that moves the repo as well as the files; the board's own count laid out in a browser, which the diff had stopped measuring; and that the briefing is set as prose, which is the shape of the bug 3da2a2f fixed by eye.
  - Declined, with the reason in the assumption it stands on: the run's clock read before the run rather than after (correctness, smaller things) → A6; two watchers on one board (correctness 4, spec c7, now said in the `--help`) → A9; the model's markdown rendered unescaped (tests D8, standards 10) → A7; the five seams the Testing Decisions does not name (tests B4, spec a2) → A8. Not reproduced: a change arriving while the session explores being swallowed (spec c2, tests C3): the run's clock is read before the subprocess, so such a change reads as untold and is pinged out a window later; the watcher check drives exactly that sequence. Left alone: `github.asked_at` repeating four lines of `github.read`'s guard (standards 10), and the parameter clump `render_page`, `content_stamp` and `absences` share (standards 10), which is the board's own shape and grows by a member per slice rather than by this one.
- [D7] Friction
  - `CLAUDE_CONFIG_DIR` is the board's transcripts and `claude`'s own login at once. Every demo and figure of this feature points it at the fixture's config directory, so the sessions on the fixture's commits can be named; a briefing run under that same variable is a `claude` with no login. It answered `Not logged in`, the watcher wrote nothing, the board sat on its own count, and nothing on screen said why, and the run that found it was a six-minute end-to-end check spent on a fixture path. The demo sets `board.TRANSCRIPTS` instead, and a failed run now says what it said on the watcher's own output, which is the part that was missing. What would have saved the time is the board reading transcripts from a setting of its own rather than from the variable that also carries the credentials.
  - The briefing block took `.brief`, the class a row's ticket brief already wears, and inherited its `nowrap` and its ellipsis: the briefing ran off the side column at every width, in both schemes. The layout check stayed green, because text a box clips rather than spills is what that mark does by design and the check filters `clipped` findings out; the first screenshot of the figure showed it at a glance. The page's CSS is one stylesheet in one string with no scoping, so a grep for a class name before adding it is the whole defence. The mechanical answer is a check that reads a new element's computed style against what it was written to be, `white-space` here; the review round added one, and the same round found the tooltip beside it cut off by the column's own scrolling.
  - The five-minute debounce is the feedback loop as well as the design: verifying that a change reaches the session takes six minutes per attempt, and two attempts went to a race with the board's own startup and to the login above. `job` made them affordable, since each one ran unattended in tmux. What would have made them cheap is the windows being readable from the environment, which `on_change`'s purity already allows and nothing asked for.
  - What a run costs is in `claude -p`'s JSON and nowhere else: `first` and `ping` keep the briefing and the session id and drop the usage. The spec's Decision rests on that cost ("a ping inside the cache's lifetime rereads the session's context at the cached price"), so the demo wraps `briefing.ask` to print it. Nothing the board itself writes says what its briefing cost, and the cache file is where it would go.
