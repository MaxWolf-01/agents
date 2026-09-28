---
name: model-log
description: "What the workflow's model runs cost and how long they took."
disable-model-invocation: true
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/model-log --help), Bash(model-log report *), Bash(model-log report), Bash(model-log --help)
---

# Model log

Every `claude -p` the workflow starts (a worker, a review axis, the board briefing, change-summary, the chat review) runs through `model-log run`, which appends one line to the log with the call site, ticket, model, effort, cost, duration, turns and tokens claude reported. `model-log --help` is the reference: the line's fields, `report` for the rollups, `pull` for bringing a worker host's lines back, which `dispatch` does when it fetches or cleans up a ticket there.

Decisions about effort, model and which reviewers to run are made from this file: `model-log report` shows what a review round costs at each effort, which axis takes the time, and what a ticket's worker cost. A line whose `end` is `no result` is a run that died or was stopped before claude reported, its tokens summed from what arrived.

```text
!`${CLAUDE_SKILL_DIR}/model-log --help`
```
