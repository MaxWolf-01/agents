---
name: retro
description: "Run a workflow retro by hand, optionally on a pattern max names; its living report lands in retro/ of the agents repo's agent repo."
disable-model-invocation: true
---

# Retro

A workflow retro reads every Claude Code session since its last run for the friction that recurs, traces it to what produces it, and rewrites one living report, `retro/report.md` and its page `retro/report.html` in the agents repo's agent repo. The vocabulary is `GLOSSARY.md`'s, under Retros.

## A run by hand

`retro <agents repo>`, with `--focus "<pattern>"` when max names one ("the tests are overbuilt"), which becomes one of the run's deep-dives. A run takes an hour or more, so a session starts it in the background and comes back when it ends. `retro --help` says what a run reads, where it writes and when it leaves the report uncommitted; `runs.log` in the retro's data directory says how each run ended.

## The weekly run

The `workflow-retro` timer in max's dotfiles runs `retro <agents repo> --if-active` early every Monday, on his laptop, and records each run's outcome in its job run log.

## The parts

- `retro_collect.py`, stage 1: the period's session digests, git across the repos `retro/repos` lists, the versions, and an older sample, by script.
- `stages/`, a prompt per later stage, each one model run: read fresh, follow up, go deep, synthesize.
- `LENSES.md`, what the retro looks for and how it weighs a finding; `REPORT.md`, the living report's shape and rules.
- `retro_run.py`, the run: collect, the stages in order, then the commit of the report's two files alone.
