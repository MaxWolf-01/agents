---
status: proposed
priority: 3
size: XS
---

# The dispatch scripts' comments say what the code does, briefly

## Brief

About half of the two dispatch scripts is comment, much of it workflow prose whose home is the skills. A pass that leaves each comment saying what the code beside it does.

Cut from the user's review of the one-flow branch (C11, C12): about half of `mx/skills/dispatch/dispatch` and `dispatch-ctl` is comment, and much of it describes the workflow (why a proposal waits, what the user rules on) rather than what the script does. The workflow's home is the dispatch and tracker skills; the script's `--help` describes its commands, and an inline comment gives a reader the context to follow the code without parsing all of it.

## What to build

A pass over both scripts: every comment block becomes a short inline comment stating what the adjacent code does or the non-obvious constraint it obeys; workflow prose moves to the skill where it is not already there, or goes. The `--help` text describes commands and their effects, not the workflow around them, and keeps the two facts a caller needs about a merge (the `--no-ff` merge commit is how `review` finds a range after the merge; a branch waits unmerged for a ruling).

## Acceptance criteria

- [ ] No comment in either script explains the workflow; each states what the code beside it does or the constraint it obeys, in one to three lines.
- [ ] `--help` for both scripts reads as a command reference; `make check` still passes.
- [ ] Demo in the closing comment: comment line counts before and after, and the `--help` output of both.
