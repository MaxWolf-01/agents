---
status: proposed
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

- [ ] `ticket-file-contract#P7`: no file under `mx/` has a worker write a ticket file, and the worker contract says what it writes instead.
- [ ] A throwaway pair of repos, the tickets in one and the code in the other with `mx.tracker` set, runs one ticket end to end through `dispatch`: claim, spawn, the report, the import, a question ruled with `tracker rule` before the merge, the landing with a repo-qualified range.
- [ ] The same run with the tracker in the code repo needs no setting at all.
- [ ] The board renders a tracker with a build in flight without reading any worktree.

## Comments
