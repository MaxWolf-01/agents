---
name: retro
description: "Work the session repo's living report: grill the findings max picks into tickets and write his verdicts into it; or start a retro run by hand, optionally on a focus."
disable-model-invocation: true
---

# Retro

A retro reads a repo's code through every code lens, and its proposed tickets, and keeps one living report, `retro/report.md` and its page `retro/report.html` in that repo's agent repo, read and committed in its main checkout. A repo with no agent repo of its own, planned from another project's tracker, keeps its report in that project's agent repo instead, as `retro/<name>/report.md`, `<name>` what the project's `agent/repos.toml` calls it. Every repo's is a repo retro, which reads no session; the workflow retro is the agents repo's, and also reads every Claude Code session since its last run for the friction that recurs, and traces it to what produces it. The vocabulary is `GLOSSARY.md`'s, under Retros; the report's shape and rules are [REPORT.md](REPORT.md).

## Working the report

`/mx:retro` in a session opens the living reports the agent repo of the session's project holds: `retro/report.md`, and `retro/<name>/report.md` for each repo planned from its tracker. Where it holds more than one, name each with its repo and let max pick; the steps below work the one he picks. A project with no report has no retro yet: say so, and offer a run by hand where `retro --help` takes the repo.

1. **Show max where the report stands**: its What changed section, its top recommendation, then one line per finding and candidate outside Dismissed, its id, title and state. Done when max has picked the ones to work, in his order, or given verdicts on them outright.
2. **Work each pick**, one at a time. A finding (`F<n>`) gets a design round, `/mx:grilling`, on its proposal: its evidence and cause are the brief, and its proposal is the default the round tests, not a frame max has accepted. A candidate (`A<n>`) of the architecture code lens gets `/mx:improve-codebase-architecture`'s grilling loop, its step 3, with the report's fields standing in for the scan; one of another code lens gets a design round, as a finding does. Done when max has ruled on it: taken up, amended, dismissed, or left as it is.
3. **What he rules becomes tickets**, filed per `/mx:tracker` in the session's repo. A ticket cut from `retro/<name>/report.md` names `<name>` in its `repos:`, which is how that report's runs find it. Each brief opens by naming the id it was cut from and its report ("From the retro's A3, `retro/quartz/report.md` of 2026-10-11."), so later runs follow the fix to its ticket.
4. **Write each verdict into the report**, as REPORT.md's max's verdicts section says, a run in flight included. Done when every ruling of the session is in a commit.

## A run by hand

`retro <repo>`, with `--focus "<focus>"` when max names one: a pattern ("the tests are overbuilt"), which becomes one of a workflow retro's deep-dives, or a module or pain point, which directs the lens pass. A run takes an hour or more: start it in the background with `job` (`/mx:tmux`), and come back when it ends. In a session that also works the report, start it once the verdicts are committed, so it reads them. `retro --help` says which repos a run takes, what it reads, where it writes and when it leaves the report uncommitted; `runs.log` in the retro's data directory says how each run ended.

## The weekly run

Two weekly timers in max's dotfiles run the retros on his laptop: `workflow-retro` runs `retro <agents repo> --if-active`, and `repo-retros` runs `retro <repo> --if-active` for each repo on its list of repo retros, with `--tracker <project>` for a repo the list names a project's tracker beside. `workflow-retro --help` there names the list and the job run logs each run's outcome goes to.

## The parts

- `retro_collect.py`, stage 1, by script: what the later stages read, which its docstring lists per kind. `scan_unapproved.py` is its scan of the Bash calls no allowlist rule covers.
- `stages/`, a prompt per later stage, each one model run. Both kinds run follow-up, the lens pass and synthesize; the workflow retro runs read-fresh before them and go-deep before the lens pass.
- `LEADING-WORDS.md`, the workflow retro's leading words and max's questions, which go-deep searches the period's sessions for; the code lenses are the lens pass's own, in its prompt. `PERMISSIONS.md`, what go-deep's permissions reading knows of its data and the bar a proposed rule meets; `REPORT.md`, the living report's shape, its rules, the weighing and how a session writes max's verdicts.
- `retro_run.py`, the run: collect, the stages of the repo's kind in order, then the commit of the report's two files alone.
