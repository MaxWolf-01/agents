## 1.0.145

- `review` picks the commit it reviews from, and `dispatch accept` merges, checks and commits a ticket itself
  Two command sequences the skills spelled out for the agent to run by hand now live in the scripts. `review` with no fixed point reviews since the nearest of the last `Workflow-stage: review` commit, the upstream and the merge-base with the default branch, among those that leave a diff, and prints the one it took. `dispatch accept` on a ticket with no children merges each unmerged ticket branch --no-ff (code repo, and listed repos whose work is no `gh:` PR), runs each repo's check (`--verify <cmd>`, else the Makefile's check or test), and commits only once all are green; a conflict, a red check, a ticket not in review or an unlisted repo refuses with nothing merged, and the message names the resume. code-review's step 1 and dispatch's Accept shrink to pointers at them.
- A dispatched worker lists only the mx skills a worker can use
  run-worker.sh now gives each worker a per-run view of the mx install: every file linked, less the SKILL.md of each skill that mx/skills/dispatch/worker-skills does not name. A worker's skill list holds the 24 skills on that file instead of all of mx, and a skill added to mx stays off it until named there. Only SKILL.md is left out, so the hook scripts and reference files inside a hidden skill's folder (session-page's hooks, handoff's checkpoint, grilling/DESIGN.md that tracker links to) still resolve. The runner refuses to start on a host whose mx has no worker-skills file. The worker prompt names no skill a worker cannot load; the artefact table in both prompts drops its /mx:retro pointer for that reason.
- feat(session-page): a to-do is only what max alone can do, and holds up only what depends on it
  The session page's To do line now holds what only the user can do: a review whose call is theirs (a design, a change to architecture or infrastructure), a message only they can send, a secret only they can type. Such a to-do holds up only the work that depends on it, so a turn ends on one only once nothing else is left, and a step the agent's tools reach (a CLI, a browser, data it can make, a login in with-secrets, a sudo through job run --tty) is the agent's. Rule 34 of the prose catalogue loses "a step the rule leaves to the writer is done and reported", whose catches deleted asks or posted under max's name.

## 1.0.145

- A dispatched worker lists only the mx skills a worker can use
  run-worker.sh now gives each worker a per-run view of the mx install: every file linked, less the SKILL.md of each skill that mx/skills/dispatch/worker-skills does not name. A worker's skill list holds the 24 skills on that file instead of all of mx, and a skill added to mx stays off it until named there. Only SKILL.md is left out, so the hook scripts and reference files inside a hidden skill's folder (session-page's hooks, handoff's checkpoint, grilling/DESIGN.md that tracker links to) still resolve. The runner refuses to start on a host whose mx has no worker-skills file. The worker prompt names no skill a worker cannot load; the artefact table in both prompts drops its /mx:retro pointer for that reason.
- feat(session-page): a to-do is only what max alone can do, and holds up only what depends on it
  The session page's To do line now holds what only the user can do: a review whose call is theirs (a design, a change to architecture or infrastructure), a message only they can send, a secret only they can type. Such a to-do holds up only the work that depends on it, so a turn ends on one only once nothing else is left, and a step the agent's tools reach (a CLI, a browser, data it can make, a login in with-secrets, a sudo through job run --tty) is the agent's. Rule 34 of the prose catalogue loses "a step the rule leaves to the writer is done and reported", whose catches deleted asks or posted under max's name.

## 1.0.144

- Skills state outcomes and what those outcomes keep, not the moves that reach them
  The guidance for agents now says a goal names what has to survive the work, not only the target: PRINCIPLES 2 gains that clause, from Ben Vinegar's agent that sped up preview builds by deleting the source-map uploads (State of Agent Coding 12, 59:21). dispatch's Redo and Reject now describe the end state a discarded build leaves, including the landing's show that still presents the other tickets, instead of a command list. diagnosing-bugs names its loop techniques in one sentence, drops "Tighten the loop" (its completion criterion already demands fast and deterministic), and turns the five-step regression-test recipe into its red-then-green criterion.

## 1.0.143

- The orient skill is deleted; its routing is in the always-loaded prompt
  mx/skills/orient is gone. The workflow block of claude/CLAUDE.md now routes every intent itself: grill what is too unclear to say what to build, prototype rival shapes, build a single one, and build when unsure; delegate the build to a worker through a ticket, with the two reasons for delegating; build without waiting for max to ratify a call, and show each landing as what was built, why, its strengths and weaknesses and the alternatives. The worker prompt carries a worker's part of it: where fog and rival shapes go, that the open calls are its own, that its report argues for the build. Orient's step rules moved to the skill that owns each step or were cut where it already said them; dispatch gained a QA section, and tracker, grilling and prototype a sentence each. A session carries 120 more words than before, a worker 44.

## 1.0.142

- Every mx skill is reworded down to the rules it carries
  A second pass over all 46 skills under mx/skills, after the pass that deleted whole sentences: this one rewrites a sentence down to its rule, taking skill text from 70,948 to about 68,580 words (3.3% less). Four whole rules are cut, each in a commit of its own that gives its reason (a second ask for prototype's shared switcher, struktogramm's standard-library note, a duplicate pointer in gh-stack, and the writing-for-agents no-ops bullet this pass contradicts). writing-for-agents' Pruning gains "The test a sentence passes to stay", with three before-and-after pairs from these skills, which is how the two passes cut. Twelve skills had nothing to gain and are unchanged. The branch was rebased twice onto a moving master; in every conflict the sentences master added or changed stand as master wrote them.

## 1.0.141

- Merge branch 'ticket/retro-runs-after-ten-merges'
  A retro now runs when it is due, checked nightly: `retro --after-merges N` starts a run once the trunks of the project's repos took N merges since its last committed run, or 14 days passed with any commit, and never more than once a calendar day or three times in seven days. A merge is a merge commit on a trunk's first-parent line, local or at origin, so branch commits count for none. The workflow retro counts the agents repo's trunk alone. `--if-active` and its activity check are removed with their only callers, and a check that skips logs why as its last line. The dotfiles' timers and list change in the same step (their branch of the same name), since either half alone breaks the nightly runs.

## 1.0.140

- Agents put pages on the hub with `container-hub open`, and a hubless session page opens with xdg-open
  The agent instructions name `container-hub open` in place of claude-browser, which dotfiles reduced to a stub (max's Q10 a). The Stop hook, which opens a session's page only where no hub answers, now hands it to xdg-open. RULES.md no longer claims the Stop hook hands links to the hub; the page lists them under "to look at". make check and make test (1150) pass on the branch, whose tree the merge result is.

## 1.0.139

- Grilling maps the solution space; the smell list names parse-don't-validate and the hidden dependency; a technique is named, never taught
  Four sentences. The grilling skill treats the options the user named as points in the solution space, never its edges, and maps the space before choosing options. The smell list's fix for needless guards opens on "parse, don't validate", and it gains Hidden Dependency: logic that reaches for the clock, the network, the disk or a child process itself, fixed by passing it in, however large the refactor. PRINCIPLES.md says a technique is named, never taught, and that a list of names is not the boundary.

## 1.0.138

- fix(retro): the page test's browser carries its run
- feat(retro): the report's page is built by script, takes max's comments, and the run's why moves to its commit
  Each retro run now builds `retro/report.html` with `mx/skills/retro/report_page.py` in place of a model-drawn page, and commits it with the report and max's comments file, `report.html.state.json`. The page opens on every entry grouped, with its area and every state it names. It derives What changed entry by entry from the report's previous committed version, and shows each entry's State across every committed version in its sheet, beside any artefact an entry's **Artefacts** field names. Comments typed in a sheet save through the container hub, and the next run reads the open ones. REPORT.md says a comment weighs as a message of max's in a session: a verdict only where it clearly rules, the newer of the two counting. The run answers each comment in its entry's History, and drops no entry carrying an unanswered one. The report loses its What changed prose: synthesize writes the why of each change to `changes.md`, which becomes the run's commit body. Every key the page answers to is declared in a `page-keys` block, which its `?` list and the hub's ctrl+alt+? list read, and its copy holds no em dash. Entries carry an **Area** written by the run.

## 1.0.137

- Merge branch 'ticket/coverage-trial-on-mx'
  `make coverage` measures the fast suite's line coverage of mx's Python, the scripts its tests start as their own processes included, and stands at 100%. Getting there added about 200 tests, most holding a refusal or a failure path, and made the code that reaches for a browser, a clock, a timeout or a model call take it as an argument (render-lint, the page cache, the struktogramm layout checker, change-summary, the plugin-update hook), so fast tests reach it with a stand-in. Dead guards and two callerless retro subcommands are deleted; transcript lines are parsed once at the boundary in scan_sessions. The testing skill gains a Coverage section and the worker's instructions name it: a change reaches its review with every line the fast suite can run, run; a line no clean, fast test reaches is answered by a refactor; an exclusion is for what the measurement cannot see.

## 1.0.136

- The turn review keeps the session's plan honest, flagging only a step the records contradict
  Each turn record's review now also reads the session's plan and sends back at most one finding where the records contradict it (a step still open that shipped, a step waiting on an answered question, an open question or running work with no step), so a stale plan is caught when it goes stale and a correct one costs nothing. max's pick (Q4 a). On this session's own history it flagged the stale plan of turn 08 and passed the current one twice; make check and make test (1008) pass on the branch, whose tree the merge result is.

## 1.0.135

- Every question and to-do card says the hour and minute it was put
  Where the transcript shows no write of a turn's record, its cards fell back to the day alone; they now take the record file's own time. Asked for by max, who ruled merging; make check, make test (1007) and the 42 browser tests pass on the branch, whose tree the merge result is.

## 1.0.134

- The session page's tasks column labels its sections and dates its cards
  The "Tasks" heading gave way to three section labels: "waiting on you" (questions and to-dos), "to look at" (artefacts) and "the agent's plan" (the session's own steps, the open circles max asked about); the count of what waits sits on the play icon. Each question's and to-do's card now says when its turn's record was written. Asked for by max, who ruled merging; make check, make test (1007) and the 42 browser tests pass on the branch, whose tree the merge result is.

## 1.0.133

- The session page in a narrow hub pane no longer leaves an empty black column
  With the tasks folded, a session page narrower than 44rem (a phone, or a narrow pane in the hub) split into a 170px column and an empty one, since the folded tasks' grid rule outranked the phone layout's single column. It is one column again. Reported by max on a screenshot; the 42 browser tests pass on the branch, whose tree the merge result is.

## 1.0.132

- The session page's log opens and closes all its steps from an icon
  The log drawer's "open all" / "close all" text became one icon (chevrons apart to open every step, together to close them), whose tooltip names it and its key, O. Asked for by max, who ruled merging. make check, make test (1007) and the 42 browser tests pass on the branch, whose tree the merge result is.

## 1.0.131

- The session page's tool-call log shows the newest step on top, with its time
  The log drawer and the tasks' box of the turn under way now list steps newest first, and each log row ends on the clock time the step started. Its columns (failed, sizes, duration, time) line up down the list, what the step acted on is cut with an ellipsis, and the verb moved into the icon's tooltip. On a narrow drawer the sizes give their room to the subject; durations past an hour read in hours.

## 1.0.130

- The session page's timeline folds to a strip, giving the turns its width
  The timeline gets a chevron in its head, and the key Q, that folds it to a strip of its controls; with the tasks folded too (q), the whole side is two thin strips and the turns take the width, which is what max asked for when the session page shares the hub with an artefact. On a narrow window the folded timeline leaves its head under the tasks, which take the column's height. A reload keeps the fold; a phone's timeline sheet does not fold.

## 1.0.129

- A bug is fixed once a run shows it, a review fix corrects or removes, and the retro's architecture lens reads what its tests lens found
  A correctness finding now names the run that shows the bug, and the branch's owner makes that run before fixing: the failing test stays as the regression test, or the lightest run that can show it stands in. A fix corrects or removes; one that would add a guard, an abstraction or a test for behaviour the spec does not name is filed as a proposed ticket, as is a bug no run shows and a module boundary. The tests reviewer answers a surviving mutation with deleted code or a sharper existing test before a new one. In the retro's lens pass the architecture lens starts once the tests lens has written its findings, and reads them.

## 1.0.128

- Comments only for outside-forced behaviour; a new test's red; the testing repertoire by name; state-diagram labels
  The agent instructions now allow a code comment or docstring only for behaviour forced from outside (a dependency, platform, vendor or protocol), with a link to its issue where one exists. Anything else has another home: a property in a test or assertion, a decision in an ADR or the commit message, a hack in a ticket. The rule replaces the style block's comment sentence, its copy in the worker prompt, and the reviewer's Narrating Comments entry. The artefact table no longer sends a leftover fact into a code comment, and a timer kept where no event exists says why in its name. A new test is seen red before it is kept. The testing skill names its repertoire (property, metamorphic, model-based and differential tests, deterministic simulation, mutation) without explaining it, and no longer rests the standard on who reads the tests. show labels a state diagram in the reader's words.

## 1.0.127

- attack-the-premise loses two lines; pstack baseline moves to e1cc031
  The skill keeps only the case it exists for, a premise the evidence contradicts. The upstream-sync baseline for pstack moves to e1cc031 with the rejections recorded in its commit (max's rulings, Q15/Q16 in the prompt-audit session).

## 1.0.126

- The session page dismisses an artefact, and folds its tasks to a slim strip
  On the session page's tasks, an artefact under "to look at" can now be dismissed, by its ✕ or `x`, instead of only marked seen: the batch tells the agent `<path>: dismissed`, it shows struck through, and choosing seen or dismissed clears the other. Folded beside the timeline, the tasks are a narrow strip of their buttons with no heading, and the count of what waits on the user sits as a superscript on the play icon. A test now guards the to-do card ids that faca732a fixed.
- fix(session-page): the live log keeps a running turn's calls when a message arrives
  The live hook no longer empties live-calls.js on a prompt that arrives before the turn ended (a message sent mid-turn, a background agent reporting back, a cross-session message, or the prompt after an Esc). The Stop hook deletes the file when a turn really ends, so a prompt that finds it continues the turn under way and keeps its calls and first prompt. Previously the drawer lost every call of the running turn until the Stop render.

## 1.0.125

- The session page opens a to-do's card from the tenth to-do on
  The timeline's row for turn N and the card of to-do AN shared the id `aN` once both numbers reached ten, so the page opened the wrong element for A10: an empty strip in place of the card. Timeline rows take the prefix `tl`. Asked for by max on a screenshot ("broken a10 window -- pls fix"); make check and make test pass on the merge result, and the session page's 42 browser tests pass on the branch. Left: a test that builds a session past ten turns and ten to-dos.

## 1.0.124

- The gh-stack skill matches upstream v0.3.0
  The vendored skill is re-copied from github/gh-stack at v0.3.0 (2a49e67) and pruned again, with the local additions put back. What it now says that the v0.1.1 copy got wrong: every worktree of a clone shares one stack catalog, so an agent in a worktree runs the same commands as in the main checkout and finds a branch held elsewhere with --print-path, where the old text sent it to `gh stack link`; pushes are atomic unless --no-atomic; the lock files sit in the common dir; checkout has a flag; the unstack recovery path has its init step. One section is local, because upstream's skill leaves the case out: what to do when GitHub moved a stack to a new base (--accept-base-change).

## 1.0.123

- The artefact table is always loaded, and orient holds the flow alone
  Where each artefact of the workflow lives (glossary, ADR, ticket, board, research, prototype, show, handoff, retro) is now a table in claude/CLAUDE.md's workflow block and, word for word, in the worker prompt; make check fails when the two differ or either holds a second table. It replaces the Durable docs paragraph and costs about 450 tokens a session. Orient loses its table and the sections that described other skills and is 1710 words of flow from intent to merge. Skills that spelled out a path name the artefact instead, and the commit-trailer rule names artefacts where it listed paths.

## 1.0.122

- Skills drop what a current model does unprompted
  Every skill under mx/skills was read whole and cut by deletion, one commit per skill: opening summaries, "read X first", worked examples of work whose steps are obvious, slogans after a rule, generic lists. Skill text goes from 74,707 to about 70,100 words. A rule that a commit shows was added after an observed failure stays unless its case is covered elsewhere; one such line was cut (tmux, a taken session name). writing-for-humans' rule 31 is rewritten, not cut: a precise technical term the reader holds is the plain word and is never paraphrased, and rules 33 and 55 agree with it. The failure behind it: a Slack draft that turned "the service is now idempotent" into a sentence of paraphrase.

## 1.0.121

- The struktogramm fixture test passes on any font set
  The full-path test that holds the checker to the original render's faults named the block the dead space sits in, which differs between the worker host's fonts and the laptop's; it now asks only that dead space is found. This unblocks the mx release max approved, whose full-path run failed on the laptop for this reason alone (219 of 220 passed).
- Skills keep their knowledge apart from the mx workflow, and the README lists them by kind
  A skill's SKILL.md now holds what is true in any chat with any model; text about this setup's machinery (tickets, the session page, dispatch, forks) is cut where another file already states it, and what is particular to a skill sits in a WORKFLOW.md beside it. Four skills keep one (show, grilling, improve-codebase-architecture, project-setup); prototype, research and testing needed none. One sentence in claude/CLAUDE.md and the worker prompt points at these files, and make check holds the two copies equal and every named WORKFLOW.md section real. The convention and its test are in writing-for-agents' SKILL-MECHANICS.md. General facts that had no home got one in orient's artefact table and tracker's board paragraph. Mermaid moves inside show, as struktogramm is, and leaves the skill listing. mx/README.md is rewritten around mx's parts, its layout and its skills in three tables.
- Struktogramm is one of show's media, repaired and importable into claude.ai
  The user's Nassi-Shneiderman skill comes into mx/skills/show/struktogramm/ as a folder complete as a skill (one SKILL.md, scripts, examples), reached by one bullet in show's Media craft and not listed by Claude Code. The renderer is rewritten so a diagram has no dead space, one line per boundary, no line through text and no word split across lines (the diagram widens instead); the case fan and the two-way branch are drawn the right way up; colours follow the reader's scheme or a host page's variables. The checker reads the painted pixels and fails the original renders on each fault. An early-exit block is new, and four optional extensions outside DIN 66261: an inputs block, a duration on a node, return and raise as kinds of exit, and a named resource on a parallel track.
- The session page's tasks show the live turn's newest steps, and the log covers the right side
  While a turn is running, the tasks column shows a box with that turn's step count and its four newest tool calls, the running one's time moving, in place of the one-line "A turn is running" notice, which only repeated the hub's "working on it" block. A click on the box opens the log on the running turn, even with another turn picked. The log drawer starts at the tasks' left edge and covers the tasks and the timeline whole at every layout, where it used to cut the tasks in half. log.js alone polls the live hook's file now, every 2 s while the page is in view. The running turn's label is "live" instead of "under way".
- Skills and reviewers ask for the fix at the cause, never the smallest fix
  Several agent instructions now ask for a fix at the cause where they asked for the smallest one. The bug-diagnosis skill says the fix goes where the wrong state is made, however far that is from where the bug showed. The workflow retro proposes the fix at the traced cause that leaves the least to keep up. The grug reviewer no longer asks for a cut-down "80/20" version, only whether something already at hand does the job. The spec reviewer counts requirements plain from what the work is for, and reports speculative generality where it reported any behaviour that was not asked for.
- Pele draws every diagram mx draws, validates or teaches
  The board's graph, the mx:mermaid validator and /mx:show move from mermaid.js to Pele 1.13.0, which reads the same Mermaid syntax. The board loads one script pinned by hash, inks its nodes from the stylesheet by status class (a scheme switch redraws nothing), and loses the colour probe, the ELK import map and the undrawn-chunk path. The validator runs Pele in Node, no browser, from a lockfile pinned by hash, and reports errors at line and column. The reasons for Pele live in mx:mermaid alone.

## 1.0.120

- feat(session-page): a change staged in another browser shows without a reload
  When the session page sits inside a container hub tab, it now picks up changes another browser makes to the staged answers without a reload: the hub tab calls its waitingChanged, and the page waits for its own pending saves, fetches the hub's copy and redraws. If the reader changes something here in the meantime, that newer change wins and goes to the other browser instead. A note the reader is typing stays as typed, though the other browser's choice on that item is still taken. Before, a second open browser held a stale copy, and its next pick wrote that copy over the first browser's picks.

## 1.0.119

- Session page cards read their recap as body text, not as a quote
  The card's recap loses its left rule and indent (page.css), so a question's or to-do's content no longer looks like a blockquote; the rule now only marks text that is actually quoted, the user's own echoed words. Checked against a rendered card before and after; make check, make test and the session page's browser tests pass.
- show: a figure in a GitHub README wears the house ink on a transparent ground
  The GitHub skin in mx/skills/show is rewritten. A figure embedded in a markdown file GitHub renders now takes the house style's ink tokens, surfaces as washes mixed with transparent, and ships as a light and a dark PNG embedded through <picture>, in place of the grey-and-orange Geist skin that covered the dark theme alone. SVG-FIGURES.md's pointer names it the default for such a figure.

## 1.0.118

- Session page's timeline links fit beside the hub's dot, and cards and artefacts open by key
  The hub puts a status dot before each timeline link, and the type icon had pushed the link into a sliver, so the icon and link are now one cell. In an open card, 1 to 9 open its links, which show their numbers. O opens an artefact in a browser tab of its own.

## 1.0.117

- Session page shows turns, tasks and timeline side by side, the tasks drawn from a plan
  The session page is three columns where they fit, each scrolling on its own: the turns, the tasks and the timeline. The tasks read what needs the user, what to look at, what is in flight and what is next, drawn from a plan file the agent keeps in the session's directory. A question clears when the plan step naming it is done. Every question put to the user is a session Q, with its ticket handle beside it. Options are marked as nobody's pick and show what each leads to, gives and costs. Question and to-do cards carry their recap and links. Artefacts open only when the user opens them, and leave when marked seen, commented on, or retired by a turn record.

## 1.0.116

- Review asks what should not exist, and the architecture scan runs without a report
  Code review's read reviewer gains a fourth pass asking what in a diff should not exist. /mx:improve-codebase-architecture stops after writing its candidates down, builds its HTML report or grills only when the user asks, and its scan, which the periodic retro inherits, also asks what could be removed whole. Its report rules become five conditions a page must meet, with the card layout and module-depth figures moved to /mx:show. /mx:bloat-audit counts superfluous tests among its deletions and points at both smell lists. test_following_draws_what_ps_prints no longer compares the seconds of an age, which ticked between its two reads under load and failed two release runs.
- Session page sizes show the token types billed differently
  A turn's size is now three token counts by how each is billed, cached input, uncached input and output, behind their own icons. A prompt is its bytes alone, and a tool call shows the bytes the model wrote, then the bytes it read. The download and upload arrows are gone, since max found them misleading on bytes.
- maybe useful, maybe not
- a bit less slop

## 1.0.115

- Session page sizes drawn as icons and counts
  Sizes on the session page are a count behind an icon, down for what the model consumed and up for what it produced, replacing text like "in ≈3 tok 10 B · out ≈17 tok 65 B". Turns show the API's exact tokens; prompts and tool calls show exact bytes. Hovering half a second opens a styled tooltip with both figures, drawn above panes that would clip it. Multi-message prompts show their count behind a messages icon.
- Session page copies any link or code on c
  On the session page the c key now copies any link or code under the pointer or any link focused with Tab, where it used to copy only file paths. A web link copies its URL, a link to a local file its path, and code its text. The "c copy" hint appears on everything copyable.
- A resumed dispatch worker keeps its round's effort
  When the dispatch tool resumes a worker, the worker now keeps the effort of its previous round instead of falling back to medium. An explicit --effort or DISPATCH_EFFORT still overrides it, and that level carries into later resumes. Fresh spawns default to medium, as do resumes of runs started before the manifest recorded effort.

## 1.0.114

- feat(house-style): the UI principles from max's steering, for anything drawn for him
  Sixteen principles mined from weeks of max's steering on dashboards, boards and hubs now live in /mx:house-style and /mx:show: habits that hold for anything drawn, rules for apps in PARTS.md (controls behave like controls, nothing moves unless the user moved it, direct controls, answer at once, keyboard first with keys shown on demand), icons for actions with styled tooltips, an "on" switch filled, labels in sentence case, and a page that opens on what it is for. The agent drives what it built the way max would before showing it, and a UI change is shown running or deployed. render-lint gains a `--narrow` flag for a narrow and a 150% zoom render, off by default because it costs more than a couple of seconds.

## 1.0.113

- feat(workflow): tickets cut by independent context, workers hand off at 400k, review is two reviewers
  Large work now stays with one worker unless a part is independent of the rest, because each split loses context and needs coordinating. A worker whose context passes 400k tokens commits a handoff and stops, and the orchestrator resumes it or starts a fresh worker from the handoff. Code review drops its four separate reviewers and light mode for two reviewers: one reads the diff for correctness, spec and standards, and one mutates code and runs the tests. Scripts using the old review options switch to `--reviewers` or `--effort`.
- fix(model-runs): a run with no result says why and never passes for an answer
  The wrapper that runs Claude and logs each call now exits 1 when Claude exits 0 without reporting a result. Before, plain text such as "Not logged in" came back as a successful answer. Log entries for runs with no result keep the last 2 KB of Claude's stdout and stderr; callers see Claude's stderr only once it has ended.

## 1.0.112

- dispatch and tracker accept rounds merged through team PRs, reset rounds, re-cut parents and no-code tickets
  Four bookkeeping bugs behind the refused accepts in helferline's 2026-11-05 batch are fixed. A merge-commit PR from the team's own `feature/<slug>`, which carries copies of the ticket's commits, now records the copy's range and lets the ticket branch go once GitHub holds each of its patches. A range a later round reset away leaves `diff:` as that round lands, while a range already on the branch the round merges into stays. A parent that ran a round of its own before it had children gets that round's agent branch merged by its accept, with its report imported first as `land` would. A ticket the user is in the loop for, with no round, is accepted as done. `merged_tip` also finds a merge from any branch ending in `/<slug>`, and `tracker set field=` drops the field.

## 1.0.111

- feat(session-page): prompts, turns and tool calls show their size; o, O and k reach every turn and step; Ctrl+Alt shows the keys
  Each prompt on the session page shows its size in bytes, its tokens on hover, and each turn and tool call shows the tokens and bytes it consumed and produced. `o` opens or closes every turn, Enter one, and `O` every step in the open log; `k` past the newest turn reaches the turn under way, so the log's "under way" and close buttons are gone. Holding Ctrl+Alt shows each control's key over it, and the controls drop their key text.

## 1.0.110

- board speed held by tests: a render asks git each question once and reads new transcripts
  Two tests at the board's `read` seam guard the 1.0.107 speed work: a git shim on PATH sees no command repeat in one render over a parent with siblings in review, and a transcript written between two renders is listed by the second. The first caught one repeat, the board's own repo-root lookup beside the tracker's memoised one, which now shares it.

## 1.0.109

- The hub box's Enter sends what the session page's review shows while it is open
  The session page now tells a hub tab whether its review of staged answers is open (waitingReviewing). The hub's box asks it on Enter: while the review is open, Enter in the box sends the batch with the box's words below it, as the review shows, instead of the words alone. The hub half is the dotfiles commit "the box's Enter sends what the session page's review shows while it is open".

## 1.0.108

- A chat turn's reply lays out like a turn record's Details, wide tables included
  On the session page, a chat turn (one that ended on a plain chat reply instead of writing a turn record) now shows `chat` in the rail where a record shows its number. The user's messages sit at the top, and the reply goes below them in the column a record's Details use, at the same size and without `overflow-wrap: anywhere`. Wide tables in a chat reply now spread past the text as they do in a record, instead of squeezing columns to a few letters a line.

## 1.0.107

- tracker board renders fast, dispatch stops waiting on it, and done subtrees leave open umbrellas
  Finished subtrees can now leave the ticket tracker while their parent ticket stays open, as long as that parent is an umbrella: no branch of its own in the code repo and no close-out review. A parent being built keeps its done children for its close-out, which reads every one. Tickets that wait on a retired one keep the edge and read it from git history as done, and a new ticket cannot reuse a retired ticket's slug. Dispatch draws the board in the background, so `review` and `accept` no longer wait on a render. Repeated read-only git calls are memoised per render, cutting 2,240 git processes to about 240, and the board reuses its markdown converters and lists transcripts once.

## 1.0.106

- feat(session-page): the review's preview follows the hub box as it is typed
  When the session page sits in a hub tab, its review of the batch now keeps up with what the user types into the hub's message box. The page exposes waitingWords(), which the hub calls on each change to the box, and redraws only the message preview, leaving the rest of the review (an open "not answered" list) alone. Before, the preview held the box's words as they stood when r opened the review, so later typing was sent unseen. The hub half is the dotfiles commit "the box tells its session page each change to its words".

## 1.0.105

- tyro-cli: a flag whose value is optional
  PATTERNS.md gains a section showing a PrimitiveConstructorSpec with nargs="*" as a flag taken alone or with one value, the help hint that hides an empty default, and the case where the flag takes the word a positional needed; SKILL.md's pointer names the branch.

## 1.0.104

- feat(workflow): the retro's top proposals of 2026-11-02 — workers cut their own diff, architecture is the user's, answers settle where they land
  Workers now trim their own branch before review, and their taste block matches the global one again. Agents ask the user before a build rests on an architecture call the user has not made, and decide everything else themselves. A question whose options look different is asked with a render of each, and a UI is shown running. On the session page, a reply line such as "Q7: a" settles its question as the user sends it, marked "answered in your message", with no record needed. A parent's accept no longer marks its tree's open questions as answered. Merges into the trunk are staged with `--no-commit`, checked, then committed with `git commit -F -` or aborted. Releases refuse, before bumping the version, when nothing under mx/ changed since the last one.

## 1.0.103

- A paged turn ends on its record, and the terminal shows its headline
  When an agent turn writes its answer to the session page, it no longer ends with a short summary in the chat, so each answer is written only once. The Stop hook's message in the terminal takes its place: it opens with the record's headline, then gives the page link and the open questions and to-dos. Send-backs from both hooks now tell the agent to end without a chat message.

## 1.0.102

- What waits on you: questions, to-dos and links to open, one card at a time, sent as one batch
  A session page's top band now holds everything waiting on the user: open questions, to-dos, and files linked since they last spoke. It shows one card at a time, with a strip of ticks that groups the cards by kind. The user answers each with a key, and the review screen sends every staged answer as one message through the hub's box; outside the hub, the review copies the batch instead. Turn records gain a `## To do` section whose items persist until a later record clears them, and an option can carry `Gives:` and `Costs:`, shown as a table that stacks in a narrow card. The chat recap no longer lists action items. The hub keeps staged answers in a file per session, so a crash loses none, counts open to-dos as needing the user, and says at its box what stays staged.
- Seams go where interaction is weak: near-decomposability and cohesion in the design skills
  codebase-design said where a seam goes is its own decision and gave no rule for it. Its glossary gains near-decomposability (Simon, The Architecture of Complexity, 1962) and cohesion, and its principles gain one: cut where interaction is weak, the traffic across a seam sparse, slow and summarised in a few values, what changes for the same reason on one side, measured by the commit history. improve-codebase-architecture's scan asks which files of two modules keep changing in the same commits, with the counts in the candidate. The Duplicated Code smell extracts only copies that change for the same reason, and says how to undo the wrong abstraction.
- Session pages open a record's show/ links from the session's own directory
  A turn record's path under show/ now resolves from the session's directory, where /mx:show puts session work's artefacts, instead of from the repo root, where it pointed at nothing: in a turn's Links, in its prose and code spans, and in what the Stop hook hands the hub. RULES.md says so. The write hook also sends back a record whose Links name a file that does not exist.
- Agents wait on the event, not the clock: a taste rule and two review smells
  claude/CLAUDE.md's taste table gains Polling | Events, with a rule beside the ladder: a process with nothing to do costs nothing, code and tests wait on the event, a clock is for what nothing can tell (a deadline on a wait that may never end, a backstop, a remote host with no push) and says which, and the minimum code is the least the system does at runtime. The code-review baselines gain Clock Where an Event Exists (SMELLS.md) and Clock-Waiting Test (TEST-SMELLS.md).

## 1.0.101

- A secret only max can type runs as one --tty job he switches to
  The tmux skill gains a section for a step that needs a password, a passphrase or a 2FA code: the whole task runs as one `job run --tty`, max switches to its pane to type only the secret, and the agent waits with a deadline and reads the pane through job, which now redacts secret-shaped tokens. claude/CLAUDE.md points at the skill in one line under "Don't ask me to do things that you could do yourself".
- Merge branch 'ticket/session-successors-read-once' into session-page/c-yaml
  When the session page tool builds a page, it finds which sessions continued from this one by reading the previous file in each neighbouring session. Reading N sessions in one process read each of those files N times; now each is read once per version of the file, checked by one stat. A file changed in the last two seconds is always read again, since a coarse filesystem clock can hide a rewrite. A network filesystem whose clock runs more than two seconds behind can still return a stale answer. 300 chained sessions: 2.96 s -> 0.57 s.

## 1.0.100

- mx: model-runs, dispatch through hosts, and the session bar naming the account it runs on
  The tool that logs each model run's cost and time is renamed from run-log to model-runs, and its log-path variable is now `MODEL_RUNS_LOG`, so it no longer shares a name with dotfiles' run-log, which shadowed it on max's PATH. Dispatch now places and lists workers through dotfiles' `hosts` command (`hosts place`, `hosts targets`) instead of worker-hosts; without it, a spawn asks for an explicit host. The auto-mode rule covers those `hosts` subcommands and its view, never `hosts unlock`. The session page names the account a session runs on, taken from `CLAUDE_ACCOUNT` where the wrapper exported one, since a profile can run on another account's token.

## 1.0.99

- The session page's tool-call log can be walked and opened from the keyboard
  The session page's tool-call drawer, which lists the steps a turn took, can now be driven from the keyboard. With it open, Tab or a click on a step moves the keys into the drawer. There, j and k walk the steps, g g and G jump to the first and last, o or Enter opens one, and O opens or closes them all. A highlight marks the current step. Tab, or a click outside, hands the keys back to the turns, where j and k move between turns as before and the log follows. The drawer's header also gains an "open all" button. Esc still closes the log in one press.

## 1.0.98


## 1.0.97

- The session page's log shows the turn under way's tool calls as they happen
  The session page's tool-call log now shows the current turn's calls as they happen; before, it showed a turn only once that turn had ended. A new async hook (live_hook.py) records each prompt, call start, result and failure in live-calls.js beside the page, and the open log reloads that file every two seconds. With no turn picked, the log shows the running turn with a pulsing dot and ticking timers; from another turn, an "under way" button returns to it. When the turn ends, the stop hook deletes the file. Subagent calls and sessions without a page are ignored. The step helpers moved to a stdlib-only steps.py so the hook runs in ~40ms.
- The session page reader parses frontmatter with libyaml, 8 times faster
  The reader now loads every record's frontmatter with PyYAML's CBaseLoader, libyaml's, where PyYAML was built with it, and BaseLoader otherwise; both give every scalar as written. The same data on all 660 records under ~/.claude*/session-pages on zephylux, 8 times faster. The container hub reads every unit's session through this reader on its first read after a start: page_says there went 4.44 s -> 2.39 s on zephylux's 287 units.

## 1.0.96

- dispatch names the machine it runs on by user@host, as it names every host
  dispatch called the machine it runs on `local`, in run records, messages and --host, while placement and every other host used user@host. One host had two names, and an `is_here` check against `id -un`@`uname -n` now stands where `= local` was compared. Run records that still say `local` are renamed the first time they are read, so runs in flight keep working. `--host local` is refused, and the message names the host to use instead.

## 1.0.95

- Rule 54 says what a headline is for: a title names its subject, a status line states where things stand
  Rule 54 of the prose catalogue now splits headlines by their job. A title is there to be found, so it names what the thing is about, never what was done to it; a status line or a report's headline says where things stand, so its verdict, finding or state is the point. Hooks, counts or bare ids where names belong, and figurative wording fail either kind. The turn review, the code review's standards axis and /mx:writing-for-humans all read the rule.
- pull references out of prompt

## 1.0.94

- wrap opens on its verdict, so the hub shows whether a session can close
  wrap's answer now opens the turn headline and the chat recap on a fixed verdict, Closable: <subject>, <what landed> or Open: <what keeps it open>, followed by three fixed Details lines (Landed, Stopped, Waits on you). The hub shows the newest headline as a session's status, so the verdict reads from a phone without opening the page. RULES.md names the headline as that status line and treats a skill-fixed opening as shape, so the turn review stops flagging it.
- Merge branch 'ticket/show-a-turns-tool-calls-on-demand'

## 1.0.93

- feat(dispatch): the spawn places its worker, and each machine caps and shares its workers
  Starting a worker no longer requires naming a machine. Without a host, the spawn goes to the machine under least CPU pressure that has a free slot and offers what the ticket needs; the orchestrator passes those needs, and the account to run on (DISPATCH_ACCOUNT from a project's .envrc, else personal), as flags. Each machine caps how many workers it runs: a spawn or resume tries the next machine, or waits and retries every minute while all are full. A time-critical ticket can ask for a larger CPU share with --cpu-weight. Workers on hosts marked isolated bypass permissions by default. Placement and slots live in dotfiles' worker-hosts --place and host-slots; the pytest process cap is gone.

## 1.0.92

- session-page: the bar names the account the session runs under
  The session page's bar now ends its left part with the Claude Code account the session runs under (personal for ~/.claude, <x> for ~/.claude-<x>), in accent text, so a glance at the page, alone or in the hub's sidebar, tells a work session from a personal one. It is read off where the session's directory sits; a directory under no account shows none. The bar's separators before the short name and the account are vertical bars.

## 1.0.91

- session-page: the Stop hook leaves the session page to the hub, and claude-browser puts pages on the hub
  Where a container hub answers, the Stop hook no longer hands the session page to claude-browser at a turn's end: the hub finds the page on disk and reloads it once rewritten, and nothing opens a hub tab any more. Without a hub the first render still opens it as a tab. The global CLAUDE.md and the session page RULES now say claude-browser puts a page on the hub rather than opening it in max's browser.

## 1.0.90

- The effort-forwarding check can fail again now that workers default to medium
  The remote-host check for DISPATCH_EFFORT forwarding sent medium, which became the worker default in b21459f1, so it could no longer tell a forwarded level from the host's fallback; it sends low now.
- Prompt audit against Opus 5.5: plain-volume instructions, workers at medium effort
  Workers that dispatch spawns now run at medium effort by default instead of high, steered by --effort alone (low for trivial tickets, high for hard reasoning or extra rigour), with no Sonnet tier; the models index in CLAUDE.md says the same. CLAUDE.md's "How you work" block, the amend rule and the defuddle line say what they said at normal volume, once, and "bd" asks for a re-derivation via /mx:sharpen instead of "think harder". Orient now says /mx:wrap is typed by the user, writing-for-agents fixes a weak word by naming what it must cover rather than by a louder one, the hypervisor's prompt stops restating its tool list, tell_session describes what happens after delivery, and the board briefing loses its 150-word cap.

## 1.0.89

- fix(tests): dispatch's tmux checks pass from a shell started before the last Home Manager switch
  Dispatch's two tmux checks that failed on zephylux now pass whatever environment runs them: the shells a check starts read no zsh config of the user's, which could put back the user's PATH and tmux socket directory and send the checks to the real claude and the user's own tmux server. All 127 full-path checks of the dispatch, session-page and board files pass.
- perf(workflow): run-log counts each run once; short claude -p runs and mechanical subagents cost less
  Resumed worker sessions are no longer counted more than once in the run log's cost reports. A resumed Claude run reports the session's running total, so the log now records each run's own cost and API time, keeps the totals alongside, and reads older lines the same way when reporting; on the real log workers fall from $11,281 to $6,069 for Sep 27 - Oct 23, which matches their transcripts. The code reviewers, the change summarizer and the turn reviewer now write their prompt cache at the 5-minute rate, 1.25x input instead of 2x: a reviewer's calls come seconds apart and every one of these runs ends within minutes. The retro's readers, its report builder and the /mx:show artifact builders now run at medium effort instead of inheriting the session's high.

## 1.0.88

- feat(retro,triage): read max's TODO files as context
  The retro and triage skills now read the TODO files at the root of each repo, where max jots quick thoughts and which are mostly untracked by git. A retro run copies every file named TODO or todos (any case, any extension) as it stands at collect time. Its stages treat these as context: they steer which code the lens pass reads and get quoted as his notes, but never count as his verdict on a finding. Triage uses them as context and never files tickets from them. It puts stale lines to the user as one call before cutting any, because a cut in an untracked file cannot be undone.

## 1.0.87

- feat(workflow): merges into the trunk open with change-summary's paragraph, and /mx:changelog writes from it
  Merges into the trunk open their body with a paragraph on what the whole branch changed, drafted by `change-summary` from the three-dot diff and corrected by the agent. `/mx:changelog` reads the trunk's first-parent history and writes each branch's entries from that paragraph, reading a branch's own commits only where the paragraph leaves a change unclear. `change-summary`'s prompt describes a set of changes rather than assuming a pull request.
- Agent sessions from any device: session records outside every checkout, two main checkouts kept in step
  The agents side of the dotfiles tree agent-sessions-from-any-device. A running session's page records live under the account (~/.claude*/session-pages/<id>/) and are committed into the agent repo as the session ends, so a checkout synced between two machines never carries another session's half-written files. `tracker sync` and the hooks `tracker hook` installs push the agent repo's main checkout after every commit, merging what the other machine pushed first; a tracker write during a stopped merge is staged and goes in with its resolution. The Stop hook finds the container hub on its unix socket.

## 1.0.86

- docs(dispatch): each comment in the dispatch scripts says what its code does
- test(dispatch): the scripts' text functions, remote failures and the zsh quoting under test

## 1.0.85

- feat(tracker): land takes a round whole, and every tracker write commits

## 1.0.84

- feat(wrap): /mx:wrap checks a session for what is left, then cleans it up to close
- fix(tests): flaky checks wait on what they check, and dispatch fixes a flaky check at once
- fix(code-review): review writes its reports outside every working tree
- test(render-lint): the board-row collision page becomes two fixtures
- Revert "test(render-lint): the board-row collision page becomes two fixtures"
- test(render-lint): the board-row collision page becomes two fixtures

## 1.0.83

- docs(dispatch): the worker contract's scratch sentence moved beside the listed-repo rule
- feat(workflow): project instructions live in AGENTS.md, landed again on max's word
- docs(dispatch): the worker contract calls ignored files in a worktree scratch

## 1.0.82

- better safe than sorry
- feat(dispatch): every round reads its ticket from a context staged for it
- revert: hold agents-md-instead-of-claude-md back from the release
- feat(session-page): session-page prints where the next record goes, and session.md is its title alone
- feat(dispatch): the probe retires the run of every done or untracked ticket whose work merged
- feat(tracker): check refuses a session turn a ticket cites without quoting it
- refactor(board): the page is a module of its own and the layout probes are scripts
- fix(board): the layout check fails on any text a box cuts that its own .clip did not, and render-lint names every box that cuts
- fix(skills): mermaid and code-review load in claude -p in the default permission mode
- feat(dispatch): a worker reviews its branch once per ticket
- chore(figures): ticket-life's figure record matches its HTML on master
- feat(figures): make check fails on a README image whose sources changed since its render
- feat(code-review): review says which reviewer died and why, and names the fixed point's order
- fix(dispatch): dispatch-ctl --help back within its 400-word budget after two accepted builds
- fix(dispatch): cleanup refuses over work no spawn put in the ticket worktree
- fix(dispatch): the runner resumes a worker that stops early, and the prompt says how to wait
- feat(triage): the agent applies the bookkeeping and puts only design calls to the user
- feat(prototype): variants offered for a pick differ at rest and are each whole, with no fixed count
- test(board): the demo tracker carries a question cut at the copy cap
- fix(session-page): a block under a question's options is refused and pointed at Details
- fix(board): proposed rows ask for a triage, copy-all counts what is on show, the graph name shows whole, the keep-alive says what it guards
- fix(dispatch): a host's stale git remote is repointed or refused, and a spawn names its setup's source
- fix(dispatch): DISPATCH_EFFORT reaches the worker on every host
- feat(workflow): project instructions live in AGENTS.md, which Claude Code and Codex both load

## 1.0.81

- feat(workflow): fewer workflow concepts: no hinge, no loose work, no gate, debrief or review session; trunk; qualified, linked tags
- feat(tracker): the hinge retired; no child ticket is ruled alone

## 1.0.80

- feat(session-page): the line under a turn names each open question by its headline, and the recap stops listing them

## 1.0.79

- feat(mx): /mx:pickup starts a session from a handoff's path

## 1.0.78

- "Brief" means a ticket's, and what an agent is handed is its prompt

## 1.0.77

- The retro proposes auto mode entries in both directions, checked by the critique
- A tracker's first retro reads eight weeks back, set by --first-weeks
- pstack's benchmark-checklist and attack-the-premise join mx, and the agents repo is MIT

## 1.0.76

- The board watcher's test counts the cadence from the run's own clock
- One retro per tracker, its sessions read for max's corrections and their cause

## 1.0.75

- proposed tickets are more general; codebase arch report has more creative freedom
- bloat begone

## 1.0.74

- Session page drops its brief; grilling shows a ticket's brief as it moves

## 1.0.73

- /mx:sharpen replaces /mx:expert and wf, and is the one home of grilling's expert bar
- fix(house-style): code comments recede, quotes match, ALL_CAPS names stay plain

## 1.0.72

- feat(session-page): turns and whole sessions copy as their markdown
- feat(house-style): Flexoki at half chroma as the house's colour source, and a darker night ground

## 1.0.71

- fix(session-page): local slash commands are no longer shown as something the user said

## 1.0.70

- pstack takeaways: uv and fd rules cut, /mx:transcript deleted, agent-contributor scan, growing figures in show

## 1.0.69

- fix(session-page): the open question keeps room to be read in a crowded questions band

## 1.0.68

- feat(handoff): a session's first context checkpoint is at 500k

## 1.0.67

- feat(session-page): a wider text column, centred in a wide pane, with tables that spread past it instead of wrapping

## 1.0.66

- feat(session-page): c copies the path under the pointer, as the turn shows it

## 1.0.65

- feat(retro): a repo planned from another project's tracker gets its repo retro there
- docs(github): change-summary drafts the PR's opening, the agent adapts it

## 1.0.64

- feat(session-page): a copy button in each code block's top right corner

## 1.0.63

- feat(retro): a weekly retro per repo keeps one living report, and the workflow retro reads every session
- docs(readme): the workflow map, a ticket's life and the story page, in the house style at mx 1.0.62

## 1.0.62

- fix(dispatch): dispatch --help back within its word budget
- feat(dispatch): ps puts running workers first and folds exited ones to fit the screen

## 1.0.61

- feat(session-page): the page's top, timeline and copy redesigned, and the turns' end times the hub reads

## 1.0.60

- fix(session-page): clickable links, and a reload that follows a new turn when you were caught up

## 1.0.59

- feat(tracker): proposed tickets wait off the frontier for a triage the user starts

## 1.0.58

- docs(git): commit subjects are conventional commits, the outcome sentence opens the body

## 1.0.57

- feat(grilling): blind questions for taste decisions, rendered by blind-test

## 1.0.56

- house-style: a quieter night accent, centred button labels, a muted select arrow
- house-style: five series colours for a chart with three or more series
- dispatch ps --follow: one ssh login per host for as long as it follows
- board: the watcher restarts on new code, says a failing pass once, and marks an open board stale
- tracker: the Board briefing hands its prompt to claude on stdin

## 1.0.55

- mx: a session moved to a newer mx hears what changed, from a changelog each release writes

