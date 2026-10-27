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

