---
status: review
parent: ticket-file-contract
blocked-by: [scripts-go-through-tracker-command, skills-and-glossary-speak-one-ticket-kind]
priority: 1
size: L
---

# Workers report, the orchestrator writes the tickets

## Brief

A worker stops writing its own ticket file on its code branch: it writes code and a report, and the orchestrator alone writes tickets, in the tracker's own checkout. That removes the two copies of one ticket file during a build, lets the tracker live in another repo than the code (a secrets/dotfiles session is blocked on exactly that today), and leaves the board one directory to read.

Child ticket of `ticket-file-contract`, building on its Decisions: only the orchestrator writes ticket files and a worker reports (you, r7), ticket files committed in the tracker's own checkout and never on a code branch (you, r7), a code repo naming a tracker elsewhere with `git config mx.tracker` (you, r7), repo-qualified `diff:` ranges (my call, r7), and its P7 (you, r7). The shape is drawn at `agent/show/ticket-file-contract/ticket-writer.html`, section 5 listing the places it touches by file and line.

## What to build

- **The report.** The runner names a report file beside the worklog, outside the worktree, and the worker writes its closing comment, questions and assumptions there in the ticket file's shapes. The report existing is the finished signal: the runner's retry decision and its status line read it, where they read the ticket's `status` today. `dispatch fetch` brings the report with the branch.
- **The import.** `dispatch review` brings the report into the ticket through `tracker` (a write `tracker` gains, checked like every other): the `review` status, the comment under `## Comments`, the questions under `## Questions`, and the assumptions as the review page's notes. From then the questions are in the tracker's copy, so `tracker rule` answers them before or after the merge alike; the order rule written for D22 (B) goes.
- **One writer, one place.** `dispatch` commits every ticket change in the tracker's checkout, found through `tracker`: the code repo's own `agent/tickets/`, or the path `git config mx.tracker` names in the code repo's clone. `spawn` no longer needs the ticket on the code branch; the `needs-user` guard reads the tracker. A resume carries the user's rulings in its guidance and never edits a ticket on the worker's branch.
- **`diff:` across repos.** Where the code repo is not the tracker's, `dispatch review` writes `<repo>@<sha>..<sha>`; the review page renders from the named repo.
- **The board** reads the tracker's directory alone: the worktree overrides go.
- **The prose.** The worker contract (it never touches a ticket file; the report and its shapes), the dispatch and tracker skills (one writer, where ticket files are committed, `mx.tracker`), `/mx:grilling` (a round commits the ticket in the tracker's checkout, with no branch of its own), and the glossary where it leans on any of it.

## Acceptance criteria

- [x] `ticket-file-contract#P7`: no file under `mx/` has a worker write a ticket file, and the worker contract says what it writes instead.
- [x] A throwaway pair of repos, the tickets in one and the code in the other with `mx.tracker` set, runs one ticket end to end through `dispatch`: claim, spawn, the report, the import, a question ruled with `tracker rule` before the merge, the landing with a repo-qualified range.
- [x] The same run with the tracker in the code repo needs no setting at all.
- [x] The board renders a tracker with a build in flight without reading any worktree.

## Questions

- [D1] **Where does a ticket's show directory live when the tracker is another repo?** The worker commits its demo and figures on its code branch, which is where `dispatch review` stages the demo from; the board reads a row's artefacts beside the tracker, and `tracker retire` collects them there too. In one repo these are the same directory. In two, the board's artefacts block renders empty and retiring silently leaves the show directory, the prototypes and the research notes in the code repo while saying it took them. Either the board and `retire` learn the code repo (both already take a repo handle, and `dispatch review` could pass it), or show directories move to the tracker, which means a worker writing outside its worktree and `stage_demo` staging a file its branch does not carry.
- [D2] **Who ticks the acceptance criteria, and in what shape?** The worker used to tick them in the ticket file; it now names the ones it meets in its closing comment and the orchestrator re-types them as ticks. The transcription is derivable, so a report section carrying them in the ticket's own `- [x]` form, imported as ticks the orchestrator disputes by unticking, would keep the judgment where it is and take the typing out; against it, a third report section widens the import's surface and needs its own refusals.
- [D3] **`ticket-file-contract`'s Decision that dispatch wires the commit hook into the worker host's repo.** Nothing on a worker host reads or writes a ticket file now, so `dispatch-ctl init` installs no hook there and the host needs neither `uv` nor `jq`. The Decision (r4) still says it does; it is that ticket's to amend or to keep as a case I have missed.

## Comments

A worker writes code and a report now, and the orchestrator alone writes ticket files, in the tracker's own checkout; on `ticket/workers-report-orchestrator-writes-tickets`, nothing merged. The runner names the report beside the worklog and stops retrying once it exists, `dispatch fetch` brings it back with the branch, `dispatch review` imports it through `tracker import`, and a code repo whose tickets live elsewhere says so with `git config mx.tracker`. The board reads that one directory and no branch or worktree.

**Demo**

```
$ /home/agent/repos/dispatch/agents-workers-report-orchestrator-writes-tickets/agent/show/workers-report-orchestrator-writes-tickets/demo
wrote /home/agent/repos/dispatch/agents-workers-report-orchestrator-writes-tickets/agent/show/workers-report-orchestrator-writes-tickets/out/index.html
no display here; open the file above to read it
```

It builds two repos, `plans` for the tickets and `lamp` for the code, joined by `mx.tracker` and nothing else, and drives one ticket end to end: the claim committed in `plans` while `lamp`'s log stands still, the spawn and the brief the worker is given, the report it leaves outside its worktree, the branch that carries code and nothing of the tracker, the import, a question ruled with `tracker rule` before the merge, and the landing with `lamp@<sha>..<sha>` as the range. Every command on the page is a real one; the worker is a stub on `dispatch-ctl`'s `DISPATCH_RUNNER` seam and `diffview` is a stub, so what runs is `dispatch`, `dispatch-ctl` and `tracker` themselves.

The before and after the change owes is at the top of that page: `before.svg` and `after.svg` beside the demo, two sequence diagrams of who writes a ticket file, drawn from `before.mmd` and `after.mmd`. The board of `plans` with the build still in flight is the last panel, `out/board.png`.

**Details, if you want them**

- [D4] Assumptions
  - A1 `mx/skills/tracker/tracker.py:1381`: the tracker is the repo's main checkout's copy, wherever the command runs. Dispatch runs in the worktree a parent ticket is built in, which has an `agent/tickets` of its own, and without this every ticket change would land on that code branch, which is what this ticket's parent decided against.
  - A2 `mx/skills/tracker/tracker.py:88`: `check` with no paths keeps the plain filesystem lookup while every other command follows `mx.tracker` and the main checkout. A commit is made of one repo's staged files, and the setting says where ticket files are written, which is nothing that commit does.
  - A3 `mx/skills/tracker/tracker.py:403`: `done` reads the ticket branch and its merge in the checkout the command runs in rather than the tracker's, since with two repos the branch is in the code one. A session sitting in the tracker's repo gets the refusal, which now says where the landing is written.
  - A4 `mx/skills/dispatch/dispatch:113`: a range is bare where the tracker is the code repo's own and `<repo>@<sha>..<sha>` otherwise, so a tracker planning one repo reads as it always did. A round built in another repo is left off the review page with a line saying so, rather than rendered from the checkout dispatch happens to run in.
  - A5 `mx/skills/dispatch/dispatch:222`: the ticket parser is no longer staged on a worker host, `dispatch-ctl init` installs no commit hook there, and the host needs neither `uv` nor `jq`. Nothing on that side reads a ticket. This is what D3 asks about.
  - A6 `mx/skills/dispatch/worker-prompt.md:33`: the worker names the acceptance criteria it meets in its closing comment and the orchestrator ticks them. The ticket lists what the import brings and criteria are not in it; D2 is the call.
  - A7 `mx/skills/tracker/tracker.py:1064`: a report is a ticket's `## Comments` and `## Questions` and nothing else, held to the same rules those sections carry; a third heading, or words under none, is refused with the report's own line rather than dropped. The alternative was a format of its own, which would have needed refusals of its own.
  - A8 `mx/skills/dispatch/dispatch:588`: a round's report is set aside once imported, since `dispatch review` runs again after the merge; `tracker import` refuses a ticket already in `review` as well, so the command is safe without its caller.
  - A9 `mx/skills/tracker/board.py:232`: the board finds its tracker the way the command does, so `board` run in a code repo renders the tracker that repo names.
  - A10 `mx/skills/dispatch/test_dispatch.py:272`: `ticket-file-contract#P7` is executable, at two seams: `dispatch`'s command line for the flow (the ticket branch's diff touches nothing of the tracker, in both repo layouts) and the plugin's source for the contract (nothing a worker host holds reads a ticket file). That ticket's Testing seams was written at r3 and P7 arrived at r7, so it names neither; the section is amended when this lands, and P7 moves out of what is reviewed.
  - A11 `mx/skills/writing-for-humans/SKILL.md:33`: a link example carrying a ticket path in the feature-directory shape this tracker no longer has, swept here though it is the previous ticket's leftover; the same shape in `docs/figures/landing.html`, which is rendered into the README's landing figure, went with it.
- [D5] Findings, from `/mx:code-review` over `c47f795..dee7b4c`, four axes, reports in `agent/reviews/c47f795..dee7b4c/`
  - Fixed in `371284c`: the tracker resolving to a parent ticket's worktree (A1); `caused()` assuming a write changes one place, which had an import into a ticket carrying a standing refusal blame the report at a line the report never touched; the `needs-user` guard covering `spawn` and not `resume`; `git fetch` failing while `dispatch fetch` exited 0; a failed hop to a host reported as a fact about the worker; a round built elsewhere rendered from this checkout; `mx.tracker` read from every config scope and accepting any directory; `tracker import` taking a second report; the worker contract saying both that a worker never opens a ticket file and where the ticket files are; `board --help`, the dispatch skill's claim step and the landing figure still describing the flow this ticket replaced; and the smaller standards findings (a hand-rolled section lookup, an escaped arrow, a plural in a shape the file does not use, an alias that renamed what it aliased, two lines of change narration, the glossary entry's mechanism, the host's stated requirements).
  - Fixed in `947da00`, tests: the shipped `run-worker.sh` under a stubbed `claude` rather than a stub of itself; the landing range taken from git; the specs `dispatch review` hands diffview; the run that left no report; `ticket-file-contract#P7` at the source; a report with duplicate ids and one with no question; the board following `mx.tracker`; `mx.tracker` written with a `~` and written empty; a row's `data-path`; and the board check's two copies made to say different things. A ruling check that could not fail without failing two others first is gone.
  - Filed, not fixed: nothing. What is left is the three questions above.
  - Declined: `agent/show/workers-report-orchestrator-writes-tickets/write_page.py:78`, the page scaffolding copied from the sibling ticket's show directory. A show artefact is disposable and self-contained and is retired with its ticket, and the copied block names its home. `mx/skills/dispatch/dispatch:394`, `dispatch ctl resume` has no check: testing it takes a second spawn on a recorded session id, which is `dispatch-scripts-under-test`'s ground, and the reclaim it does is one line of `tracker set`.
- [D6] Friction
  - The four-axis review took 23 minutes against a 1,300-line diff and was the difference between this landing and this landing working: the tracker resolving to a parent ticket's worktree would have put every ticket change on a code branch, in the one ticket whose point is that they never go there, and my own demo could not have shown it, since a demo runs in a main checkout.
  - The dispatch checks spawn a real tmux session named after the toy repo and the slug, so a crashed run leaves a session the next run types its worker into, in a worktree that is gone. Two of my runs hung on that before I saw it. The checks now kill them either side of themselves; a session name carrying the pid or the tmp dir would make it impossible rather than tidied up.
  - `/tmp` is shared between the workers on this host and two of my scratch files collided with another session's, one of them executable and running someone else's code when I invoked it. A worker writing scratch under its own worktree, or `mktemp -d`, is the answer; I moved to `mktemp -d` after the second one.
  - The full suite is 3m45s and the dispatch checks are 70s of it, most of that `uv` resolving the board's dependencies once per subprocess. Running one file at a time kept the loop short, which is what the contract asks for anyway.
