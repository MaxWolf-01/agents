---
name: run-log
description: "What the workflow's model runs cost and how long they took, one line per run in ~/logs/agent/runs.jsonl. Use when choosing a model or effort for a worker or a review, when asked what a review round or a worker run cost, or when tuning which reviewers to run."
allowed-tools: Bash(run-log report *), Bash(run-log report), Bash(run-log --help)
---

# Run log

Every `claude -p` the workflow starts (a worker, a review axis, the board briefing, change-summary) runs through `run-log run`, which appends one line to the log with the call site, ticket, model, effort, cost, duration, turns and tokens claude reported. `run-log --help` is the reference: the line's fields, `report` for the rollups, `pull` for bringing a worker host's lines back, which `dispatch` does when it fetches or cleans up a ticket there.

Decisions about effort, model and which reviewers to run are made from this file, not from impressions: `run-log report` shows what a medium-effort review round costs against a high one, which axis takes the time, and what a ticket's worker cost; `reviewer-ablation` measures against it. A line whose `end` is `no result` is a run that died or was stopped before claude reported, its tokens summed from what arrived.

```text
!`${CLAUDE_SKILL_DIR}/run-log --help`
```
