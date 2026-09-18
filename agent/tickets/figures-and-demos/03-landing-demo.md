---
status: done
blocked-by: [01]
diff: [a1fefa8b24fef7b9eb7d4752c591947a2b4bda4a..524df30440589a8e5b265c5d41ef1075fdbc9182]
---

# A landing stages the demo file in a tmux session on the user's machine

Slice of `spec.md`, building on Solution (you, r4, r8), Decisions "The demo is one file named `demo`" (you, r4, r5), "The landing stages the demo in a tmux session" (you, r8), "Loose work demos the same way" (you, r4), "The rows" (agent's call, r2 to r5), "A heavy artefact goes to a fresh agent with a brief" (you, r4). The staged mode of `job` this leans on lands in dotfiles before this ticket starts (Decisions, "The staged mode of `job` lives in dotfiles"); a worker cannot add it.

## What to build

A worker closing a ticket writes the demo file in the ticket's show directory, runs it, and pastes the command and that run's output into the closing comment's Demo line, the medium per the table; a heavy demo goes to a fresh agent with a brief. The orchestrator landing the ticket adds the ticket branch's worktree beside the feature's, named after the ticket, and stages the demo through `job`: one detached tmux session named after the ticket, its working directory in that worktree, the demo's path typed and Enter not sent; the landing message names the session. The user runs it when they choose, and the demo opens what it produces. The ruling kills the session and removes the worktree, whichever way it goes. A demo that is missing or does not run under the worker's own hand goes back to the worker before the ruling, as a missed acceptance criterion does. A session landing loose work writes the same file under the branch's show directory, stages it the same way, and its landing message carries the same Demo line. The worker contract, the dispatch scripts and tick, orient's landing and loose steps, and the landing message shape in the output style say this in one sentence each and point at `/mx:show` for the medium; the worktree and the staging are steps of the `dispatch` script, since nothing in them is judgment.

The landing as a sequence, drawn for this spec: `docs/figures/landing.html`, promoted there by ticket 05.

## Acceptance criteria

- [x] The worker contract's Demo line names the file, its place, no arguments, and that the output is pasted from a run, and points at `/mx:show` for the medium.
- [x] `dispatch` adds the ticket worktree and stages the demo session at a landing, and removes both at the ruling; the skill's tick says so in a sentence and the script's `--help` carries the mechanics.
- [x] The landing message names the session the demo waits in; the output style's landing shape and orient's loose-work step name `agent/show/<branch>/demo` and the same staging.
- [x] Property, reviewed: every landing, whatever its size, has one demo file, and the demo's output in the comment or message is pasted from a run of that file under the command that ran it.
- [x] Property, reviewed: a demo file takes no arguments and runs from its branch on any host where the project is installed.
- [x] Demo: `agent/show/figures-and-demos/03-landing-demo/demo`, executable, no arguments: a toy landing driven end to end with a stub in place of the harness (the precedent is `agent/show/host-per-spawn/demo.sh` in git history, deleted by ticket 04's sweep: `git log --diff-filter=D -- agent/show/host-per-spawn` finds it), the stub worker writing a demo file, the landing step adding the worktree and staging the session, and the session's pane captured with the command typed; where that is out of reach, a driven closing comment from a print-mode worker, and the comment says so.

## Comments

A landing stages its demo instead of describing it: `dispatch review` checks the ticket branch out beside the feature worktree and leaves `agent/show/<feature>/<NN-slug>/demo` typed unrun in a tmux session, `dispatch ctl cleanup` and the next round's `dispatch fetch` take it away again, and the worker contract, the dispatch tick, orient's landing and loose steps and the output style's landing shape each say it once. Nothing is merged; `job`'s staged mode has not landed in dotfiles, so on this machine the staging step reports that and the landing stands without a session (see `[D1]`).

**Demo**: `./agent/show/figures-and-demos/03-landing-demo/demo`

```
== the landing: dispatch review stages the demo, and runs nothing

+ git commit -q -m lamp-ui: 01-warm-preset for review -- agent/tickets/lamp-ui/01-warm-preset.md
+ git worktree add /tmp/landing-demo.djeO/lamp-lamp-ui-01-warm-preset ticket/lamp-ui/01-warm-preset
Preparing worktree (checking out 'ticket/lamp-ui/01-warm-preset')
HEAD is now at 188a2e7 lamp-ui: the warm preset
+ job stage lamp-lamp-ui-01-demo --cwd /tmp/landing-demo.djeO/lamp-lamp-ui-01-warm-preset -- ./agent/show/lamp-ui/01-warm-preset/demo
staged lamp-lamp-ui-01-demo  (tmux attach -t job-lamp-lamp-ui-01-demo)
demo staged unrun in tmux session job-lamp-lamp-ui-01-demo: /tmp/landing-demo.djeO/lamp-lamp-ui-01-warm-preset/agent/show/lamp-ui/01-warm-preset/demo

  the pane of job-lamp-lamp-ui-01-demo, as the user finds it:

    | JOB_STATE_DIR=/tmp/landing-demo.djeO/home/.local/state/jobs JOB_AWAKE=0 /home/agent/.local/bin/job __exec lamp-lamp-ui-01-demo ./agent/show/lamp-ui/01-warm-preset/demo
  ok  the ticket branch is checked out beside the feature worktree
  ok  the demo's path is typed at the session's prompt
  ok  nothing ran it: the demo has produced nothing yet
  ok  the ticket waits for the ruling on the feature branch
  ok  the build is off the feature branch until the user rules
```

Nine checks over five acts; the whole transcript and the captured pane land in `out/` beside the file. The three lines between the fourth diffview stub and the worktree add are cut here for length.

**I need from you**

- `[D1]` **The staged mode of `job`, in dotfiles.** It has not landed, and a worker cannot add it, so nothing on a real landing is staged yet: `dispatch review` prints ``the `job` here has no staged mode (`job --help`)`` and the rest of the landing stands. `dispatch` calls `job stage <name> --cwd DIR -- <command>`, and the demo ships a six-line shim of it that the run announces. Two things the real mode owes beyond typing the line, both learned here: it has to create the job's state directory, or `job rm` refuses to free the name at the ruling and the next landing collides with a live session; and it is worth having it print the session name, so `dispatch` reads that instead of rebuilding `job-<name>` from `job`'s own naming rule. The line it types is `job`'s private `__exec` half, which is why staging through `job run` is not an option: the user's Enter would spawn a second session and print nothing in front of them.
- `[D2]` **The demo worktree is checked out, not set up** (`A2`). A demo needing more than the repo finds whatever the user's machine has installed. Running the project's setup line in every landing's worktree would cost minutes per ruling and write into the user's machine; the alternative is to say a demo may assume nothing but a checkout.
- `[D3]` **The worker contract now restates `/mx:show`'s demo-file rule** (`A3`): the file's name, its two paths, and the no-arguments rule. The first acceptance criterion asked for exactly that, and it strains one home per fact; the pointer at `/mx:show` beside it carries only the medium. Rule it in or cut it back to the pointer.
- `[D4]` **The spec's Testing Decisions has a line this build contradicts.** It says *"the orchestrator's landing read checks that the demo file exists **and runs**"*, where round 8's decision says *"The orchestrator runs no demo itself"*. The build follows round 8, and the dispatch tick now says a demo that is missing or that the worker's own run did not carry goes back to the worker. That Testing Decisions line wants amending when this ticket lands.
- `[D5]` **The amend loop is the one path the demo cannot drive.** Its unstage-before-fetch needs a remote worker host, and this machine has one host; the demo's step says so and drives the same ticket landed twice instead. Worth a look by hand at the first real amend.

**Details, if you want them**

- `[D6]` **Assumptions**

  - A1 `mx/skills/dispatch/dispatch:460`: the staging calls `job stage <name> --cwd DIR -- <command>`. This stands in for the spec's `(my call, r8; unconfirmed)` mark on *"The staged mode of `job` lives in dotfiles"*, which the ticket names as a precondition that did not hold.
  - A2 `mx/skills/dispatch/dispatch:77`: the demo worktree is checked out and not set up.
  - A3 `mx/skills/dispatch/worker-prompt.md:32`: the contract states the demo file's name, place and no-arguments rule rather than only pointing at `/mx:show`.
  - A4 `mx/skills/dispatch/dispatch:407`: the amend round's unstage hangs off `dispatch fetch` rather than off the ruling, since a fetch is the next round arriving and git refuses to fetch into a branch a worktree holds. A local host, whose worker owns that same worktree and moves it itself, is left alone.
  - A5 `mx/skills/dispatch/dispatch:445`: a ticket branch carrying no demo gets one line saying which path was looked at. The spec puts *"a `dispatch review` warning on a missing demo"* out of scope; this reports and gates nothing, so the two states are distinguishable without a check that fails.
  - A6 `claude/output-styles/max.md:10`: the landing shape names the demo's path and that it waits staged, and not tmux or `job`, so the harness stays out of an always-loaded file.

- `[D7]` **Findings** (`/mx:code-review`, full axes, `a1fefa8..45a39db`; three reviewers, 4 correctness, 10 hard and 8 judgement standards, 6 spec). Fixed in `f99cfff`: the staged worktree surviving an amend and breaking the next fetch; a directory taken for a worktree by its existence alone; `job rm` with no fallback when the staging registered no run; a demo committed unexecutable staging anyway; three `die`s where a warning belongs, which is what made today's missing staged mode a red exit; the `--help` reflow, its `<short>` placeholder and the unechoed `job rm`; the tick sentence and the script comment claiming cleanup covers all four rulings; orient's step-5 heading and its duplicated loose bullet; the output style's harness names; the job-name sanitiser, which defended one link of a chain that breaks in three other places; and two false references in the demo's header. Declined into the assumptions above: `A3` (the contract's copy, which the acceptance criterion asked for) and `A5` (the missing-demo line against the spec's out-of-scope entry).

- `[D8]` **Friction.** Two things cost time. The dependency this ticket declares as landed had not landed, and the only way to find that out was reading `job --help` on the host, since nothing in the tracker records whether a dotfiles precondition shipped; a ticket that waits on another repo has no blocking edge that can express it. And the demo's first two runs died on state a previous failed run had left on the host: a tmux session whose worktree was gone, and a job state directory the outer `job run` had put in the shared `~/.local/state/jobs` through an inherited `JOB_STATE_DIR`. Both are the same shape, a demo sandboxing its files but not its sessions or its job namespace, and both are now handled in the demo; a `job run` that did not export `JOB_STATE_DIR` into the command it wraps would have saved the second.
