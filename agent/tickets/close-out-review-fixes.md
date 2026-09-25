---
status: done
parent: ticket-file-contract
priority: 1
size: M
diff: [5090b5b..a855f5c]
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

- [x] Every finding named above is fixed as given, or answered in the closing comment with why not.
- [x] `make test` and `make check` pass.
- [ ] Your own review of this branch is a light one: the user asked for speed at this close-out.

## Questions

- [D1] **The parent ticket's Testing seams, reworded rather than the source check widened?** C2 left the call open. The check reads the three files dispatch stages on a worker host; the wording it was written against, "nothing a worker host holds writes a ticket file", cannot be checked, since a worker host holds the whole plugin and `tracker` in it writes ticket files by trade. So the seam is now a runtime refusal rather than a source fact, and `agent/tickets/ticket-file-contract.md:74` says four seams, amended in place. The alternative is to keep the old wording and give the source check an exception list, which asserts the absence of something the plugin is built to have.
- [D2] **`tracker data -` keeps stdin with `--called`, or loses it?** S2 offered both. C7 removed its only caller in `dispatch`, so `-` is now exercised only by the checks that hold the stdin read to the same answer as the read by slug and by path (`ticket-file-contract#P2`). I gave it the `--called` flag `import -` has, which is one answer to what a refusal names, at the cost of a flag nothing calls. Dropping the form outright is the YAGNI reading and costs that P2 check its third way of handing a ticket over.

## Comments

Every finding the close-out review named is fixed on `ticket/close-out-review-fixes`: C1 to C7, S1 to S5, A1 and A2. A3 and this branch's own review were dropped on your word mid-build, which is why the third acceptance criterion is unticked. Nothing is merged. `make test` (381 passed) and `make check` pass.

**Demo**

    /home/agent/repos/dispatch/agents-close-out-review-fixes/agent/show/close-out-review-fixes/demo

The three correctness fixes driven over a toy project, the worker a `claude` stub under the shipped runner. The lines that carry them, out of `agent/show/close-out-review-fixes/out/transcript.txt`:

    $ bash skills/dispatch/dispatch wait warm-preset --deadline 120
      dispatch-lamp-warm-preset exited  run=...-1790338818  attempts=1 exit=0 report=yes session=5b2962f6

      report=yes on that line is the runner saying this run wrote the report.
    ...
    $ bash skills/dispatch/dispatch wait warm-preset --deadline 120
      dispatch-lamp-warm-preset exited  run=...-1790338822  attempts=1 exit=0 report=no session=5b2962f6

      report=no, and `dispatch ctl log` is where the run says what it did.
    ...
    $ bash skills/dispatch/dispatch review warm-preset
      dispatch: the report on ticket/warm-preset is the one warm-preset already carries, so this round left none of its own to import
      + skills/dispatch/../tracker/tracker.py set warm-preset status=review
    ...
      Writing is not, from either repo's worktree:
    $ mx/skills/tracker/tracker.py set warm-preset status=done
      tracker: refused: ticket/warm-preset is the branch lamp-warm-preset has out, and a ticket file is written in the agent repo's main checkout, never from a ticket branch
      exit 1
    $ mx/skills/tracker/tracker.py new another-preset --priority 2 --size S
      tracker: refused: ticket/warm-preset is the branch lamp-warm-preset/agent has out, and a ticket file is written in the agent repo's main checkout, never from a ticket branch
      exit 1
    ...
      The ticket branch has merged into the branch that worktree holds. Before
      this ticket the two paths were compared as two repos, so the merge was
      looked for in the main checkout, on main, and `done` was refused.
    $ mx/skills/tracker/tracker.py set warm-preset status=done
      warm-preset: status: review -> done

The before and after of the one fix with a sequence to it, C1: `agent/show/close-out-review-fixes/resume-before.svg` and `resume-after.svg` beside the demo.

- [D3] Assumptions
  - A1 `mx/skills/tracker/tracker.py:157`: `data -` keeps stdin and gains `--called`, so both stdin forms name the object a refusal came from the same way. D2 is this one for your ruling.
  - A2 `agent/tickets/ticket-file-contract.md:74`: the parent ticket's Testing seams reworded to the four seams P7 has, rather than the source check widened. D1 is this one for your ruling.
  - A3 `mx/skills/dispatch/dispatch:628`: the blob of the report last imported is kept per slug under the code repo's git dir, beside the run record, and `forget_run` drops it with the run. A cleanup is the end of that build, so the next one's first report is one this has never seen; a state file lost some other way falls back to today's behaviour, which is the status check alone.
  - A4 `mx/skills/tracker/board.py:633`: the watcher's snapshot leads with both repos' heads rather than the project's alone. The page reads both, since a ticket's sessions are the agent repo's commits and its log is the project's. This also makes `changed_note`'s `[:2]` and `[2:]` right, which were already written for two leading entries and were eating the first file of every snapshot.
  - A5 `mx/skills/orient/SKILL.md:18`: research reads "committed; retired with the tickets citing it", since `retire` takes a tracked note out by `git rm` and an untracked one to `~/logs`, and the committed case is now the ordinary one.
- [D4] **No finding index.** You dropped this branch's own review, so no `/mx:code-review` pass ran over it and there are no findings to dispose.
- [D5] **Friction.** Two things, both from this repo not being split yet.
  - The worker contract has a worker write no ticket file, and C2 now refuses that write from a worker's worktree; this run was told to flip its own ticket, which is that write. I edited the frontmatter by hand rather than through `tracker set`, which is the one thing here that the shipped shape makes impossible. Once `agent/` is its own repo and the orchestrator does the flip, it goes away.
  - The pre-commit hook on this host says "no tracker on PATH, so the staged ticket files went unchecked" on every commit, since the worker plugin here is older than this branch. I ran `./mx/bin/tracker check` over the two ticket files by hand instead. A worker host gets no hook by design (r8), so what is odd is that it has one at all.
