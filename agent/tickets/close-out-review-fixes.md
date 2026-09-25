---
status: claimed
parent: ticket-file-contract
priority: 1
size: M
---

# The close-out review's findings, fixed

## Brief

The light review of the whole `ticket-file-contract` tree against master (`4f18476..ece4c0f`) found three bugs worth fixing before it merges, a handful of small ones, and prose that contradicts the parent ticket's Decisions. This ticket fixes them, so the tree can merge, the agent repo can be split out and the release can ship. The review's report is `agent/show/ticket-file-contract/close-out-review.md`; its finding ids are used below.

## What to build

- **C1, a resumed round's finished signal.** The runner records the report's blob when a run starts and counts the run as reported only when the blob at the end differs; `dispatch review` imports only a report whose blob differs from the one it imported last; the worker contract says each round's report holds that round's closing comment and new questions only, replacing the file. A check resumes with the report unchanged and sees `report=no` and no second import.
- **C2, a worker's `tracker` write on a local host.** The write commands (`new`, `set`, `rule`, `import`, `drop`, `retire`) refuse when the working directory's checkout, in either repo, has a `ticket/` branch out, the test `check` already makes; a check runs `tracker set` from a worker's worktree and sees the refusal. Widen the source-seam check for `ticket-file-contract#P7` to what its wording says, or reword the parent ticket's Testing seams to what it checks, your call, recorded.
- **C3, one repo read as two.** `repos_of` compares `git rev-parse --git-common-dir`, and a worktree and its main checkout are one repo.
- **C4 to C7:** as the report gives them (the board's watcher keyed on the project's `HEAD`; `dispatch --help` saying the agent branch; no "not imported" line on a landing; `notes_of` reading `tracker data <slug>`, which settles S2).
- **S1, S3 to S5:** as the report gives them. S4: `tracker hook` installs in the working directory's repo, the bare-repo positional and prose gone.
- **A1, research is committed.** The parent ticket's Decision stands: `agent/research/` is committed in the agent repo. `/mx:project-setup`'s agent `.gitignore`, `/mx:orient`, `mx/README.md`, and `claude/CLAUDE.md`'s workflow block with its copy in the worker contract say so.
- **A2, loose work.** A loose session commits its show directory in the agent repo's checkout, on the branch it has out, as a ticket's files are, and removes it there with `git -C agent rm` once its code branch merges; the tracker skill's retire sentence and `/mx:orient` say so, and its review page is the code branch's range with the agent repo's commits beside it.
- **A3:** the tracker skill back under half of its 3,116-word baseline, by cutting what the agent-repo paragraphs restate, never a rule.
- The test prose in `mx/skills/tracker/test_board.py` that still says "build ticket" or "the spec's Testing Decisions".

Out of scope: the README figures' alt text (`readme-reshoot`), and the fuzz run's agent branch (harmless, left as built).

## Acceptance criteria

- [ ] Every finding named above is fixed as given, or answered in the closing comment with why not.
- [ ] `make test` and `make check` pass.
- [ ] Your own review of this branch is a light one: the user asked for speed at this close-out.

## Comments
