---
status: review
---

# A script launches the code-review axes; the skill keeps only the judgment

Cut from the user's review of the one-flow branch (C7): the code-review skill is long because it carries the four reviewer briefs word for word and the mechanics around them (pin the fixed point, compute the range, write the delivery and discipline lines, spawn, wait for the report files). Every caller copies that boilerplate into subagent prompts by hand.

## What to build

A script beside the skill, `review <fixed-point> [--axes correctness,standards,spec,tests] [--spec <path>] [--light]`, that does the mechanics: resolves the fixed point, computes the merge-base range, writes each axis's brief from a template file beside the skill (one file per axis, the delivery and discipline lines included, the standards sources and the spec path substituted), runs the axes as `claude -p` reviewers two at a time with an explicit model, and returns when every report exists under `agent/reviews/<range>/`, naming an axis whose report is missing. The skill shrinks to what needs judgment: which fixed point, where the spec is, light or full, and step 5's dispositions. `make check` runs the script's `--help`; the briefs are the templates, so a change to a brief is one file.

## Acceptance criteria

- [ ] `review <fixed-point>` from a branch produces the four report files (or one, with `--light`) and exits nonzero naming a missing one.
- [ ] The skill's step 4 is one paragraph pointing at the script; the brief texts exist once, in the templates.
- [ ] Demo in the closing comment: one run on a toy branch, the report directory listed, and the skill's line count before and after.
