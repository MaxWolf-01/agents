---
name: retro
description: "Work the session repo's living report: grill the findings max picks into tickets and write his verdicts into it; or start a retro run by hand, optionally on a focus."
disable-model-invocation: true
---

# Retro

A retro reads a repo for the friction that recurs, traces it to what produces it, and keeps one living report, `retro/report.md` and its page `retro/report.html` in that repo's agent repo, read and committed in its main checkout. The workflow retro is the agents repo's, and reads every Claude Code session since its last run. The vocabulary is `GLOSSARY.md`'s, under Retros; the report's shape and rules are [REPORT.md](REPORT.md).

## Working the report

`/mx:retro` in a session opens the report of the repo the session is in. A repo with no `retro/report.md` has no retro yet: say so and offer a run by hand.

1. **Show max where the report stands**: its What changed section, its top recommendation, then one line per live finding and candidate, its id, title and state. Done when max has picked the ones to work, in his order, or given verdicts on them outright.
2. **Work each pick**, one at a time. A finding (`F<n>`) gets a design round, `/mx:grilling`, on its proposal: its evidence and cause are the brief, and its proposal is the default the round tests, not a frame max has accepted. A candidate (`A<n>`) gets `/mx:improve-codebase-architecture`'s grilling loop, its step 3, with the report's fields standing in for the scan. Done when max has ruled on it: taken up, amended, dismissed, or left as it is.
3. **What he rules becomes tickets**, filed per `/mx:tracker` in the session's repo. Each brief opens by naming the id it was cut from ("From the retro's F3, `retro/report.md` of 2026-10-11."), so later runs follow the fix to its ticket.
4. **Write each verdict into the report**, as REPORT.md's max's verdicts says, and commit `retro/report.md` alone. Done when every ruling of the session is in a commit.

A run in flight (`pgrep -af '[r]etro_run'`) read the report when it began, and leaves its own uncommitted when the report changes under it. While one runs, hold the verdicts, wait for it to end, and write them into the report it committed.

## A run by hand

`retro <repo>`, with `--focus "<pattern>"` when max names one ("the tests are overbuilt"), which becomes one of the run's deep-dives. A run takes an hour or more: start it in the background with `job` (`/mx:tmux`), and come back when it ends. In a session that also works the report, start it once the verdicts are committed, so it reads them. `retro --help` says which repos a run takes, what it reads, where it writes and when it leaves the report uncommitted; `runs.log` in the retro's data directory says how each run ended.

## The weekly run

The `workflow-retro` timer in max's dotfiles runs `retro <agents repo> --if-active` early every Monday, on his laptop, and records each run's outcome in its job run log.

## The parts

- `retro_collect.py`, stage 1: the period's session digests, git across the repos `retro/repos` lists, the versions, an older sample, each profile's permission data, and the agents repo's proposed tickets, by script. `scan_unapproved.py` is its scan of the Bash calls no allowlist rule covers.
- `stages/`, a prompt per later stage, each one model run: read fresh, follow up, go deep, synthesize.
- `LENSES.md`, the leading words and max's questions go-deep searches the period for; `PERMISSIONS.md`, what go-deep's permissions reading knows of its data and the bar a proposed rule meets; `REPORT.md`, the living report's shape, its rules, the weighing and how a session writes max's verdicts.
- `retro_run.py`, the run: collect, the stages in order, then the commit of the report's two files alone.
