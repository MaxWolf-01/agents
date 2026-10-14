# A {{kind}}: lens pass

You run the lens pass of a {{kind}} of `{{repo}}`, over the period from {{since}} to {{until}}. Its job is to read the repo's code through every lens below and propose candidates: changes to the code or to the environment around it, each with the evidence that pointed at it, smallest first. Every later run rechecks what this one proposes, so a candidate the code keeps confirming rises in the living report, and one it does not is dropped.

{{focus}}

The run directory, `{{run}}`, is your working directory and the only place you write. It holds:

- `touched.md`: the files the period's commits touched, most-touched first.
- `git/<repo>.md`: the period's commits with their messages, its reverts, and the agent repo's tickets filed, ruled and dropped, and its worker reports.
- `proposed.md`: the agent repo's proposed tickets, which agents filed on what they hit and max has not ruled on, and how to read each.
- `follow-up.md`: what the period did to each finding and candidate the living report already carries; `previous/`, the earlier reports, `current.md` with max's verdicts.
- In a workflow retro, also `notes/` and `deep/`: the period's friction, read from max's sessions.

The report's rules and the weighing are `{{skills}}/retro/REPORT.md`. You may read the repos below, and the agent repo `{{agent}}`, and run git's read commands in them as `git -C <repo> <command>`:

{{repos}}

## Steps

1. Read REPORT.md, `follow-up.md`, `touched.md`, `proposed.md` and every ticket it names; in a workflow retro, `notes/` and `deep/` too. Then list the agent repo's tickets in flight, those in `{{agent}}/tickets/` of every status but done, each by its slug and a line on what it changes.
2. Point the pass: the code the period's commits touched, the code the proposed tickets name, the focus max named, and in a workflow retro the code the period's friction touched. Write this direction down, a path or module per line with what pointed at it, as `lens-pass/direction.md`.
3. Spawn one subagent per lens, in parallel, each given the brief below, its lens's section, `lens-pass/direction.md`, the list of tickets in flight, and the candidates of its lens that `previous/current.md` carries, Dismissed included.
4. When they return, check each wrote its file; spawn a fresh one for any that did not.

The stage is done when `lens-pass/` holds `architecture.md`, `bloat.md`, `tests.md`, `footguns.md` and `escaped-defects.md`.

## A lens's brief

You read `{{repo}}`'s code through one lens, starting from the direction you were given and following what you find past it. A candidate is a change the code or its environment should get. Each carries:

- **Files**, and the **Problem**: what in the code produces it, by path and line, and its evidence, the commits, tickets or reports that show it, each with its short sha or slug and absolute date, and in a workflow retro the friction that pointed at it, quoted with its source and date.
- **Proposal**: a deletion or a narrowing first; one that adds a mechanism names the recurrence behind it and what keeping it costs.
- **Weighing**, as REPORT.md's weighing says.
- **In flight**: the ticket in flight that already takes it up, where one does. The candidate then cites that ticket, and proposes nothing beside it.
- **Standing**: the id of the candidate in `previous/current.md` it is, where it is one, so it is rechecked under that id. One max dismissed comes back only on evidence dated after his verdict, which it names.

Write `{{run}}/lens-pass/<lens>.md`: the candidates in order of impact, then a line on where you looked. A lens the code gives nothing to gets that line alone. Reply with the file's path alone.

## The lenses

### architecture

Seams and deepening. Run the scan of `{{skills}}/improve-codebase-architecture/SKILL.md`, its step 1 alone, with the direction as the user's; its vocabulary is `{{skills}}/codebase-design/SKILL.md`. Each candidate carries every field the scan names, beside the brief's.

### bloat

Code, comments, docs, config, tests and tooling grown past what they earn: dead code and options nobody passes, a layer that only forwards, a comment restating its line, a doc restating `--help` or config, a second copy of what the repo or a dependency already has. The deletion test of `{{skills}}/codebase-design/SKILL.md` decides: would deleting it concentrate complexity, or just remove it?

### tests

What the suite holds the code to, against the three jobs a test does in `{{skills}}/testing/SKILL.md`: behaviour the period's commits changed that no test reaches; a test doing none of the jobs, or pinned to internals so a refactor breaks it; an oracle recomputed the way the code computes it; a suite slow or flaky enough that its failures stop being read, which fix commits to tests and reruns in the git records show.

### footguns

Both sides of max's footguns lens, as he widened it on 2026-10-14. A pattern that makes a bug easy: a call whose misuse looks like its use, a default that surprises, state shared where nobody expects it, two ways to do one thing that drift apart. And the obvious way to do things: where a thing goes, how a service or a script is added, which command runs the checks, should be obvious from the environment (the repo, the code, the infra), said by a lint rule, a fixed place for each kind of thing, a script or a Makefile target, never left to the memory of whoever wrote it. A choice the environment leaves to memory is a candidate, and its proposal is what in the environment would say it.

### escaped defects

Bugs found after they merged: fix commits, reverts, tickets filed against a defect, worker reports naming one. For each, the defect, the commit that brought it in (`git log`, `git blame`), the cheapest stage that could have caught it (a type, a lint, a test, a line of the reviewer's rules, a render check) and why that stage missed it. A class of defect that recurs gets that check proposed.
