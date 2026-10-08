---
name: run-log
description: "What the workflow's model runs cost and how long they took."
disable-model-invocation: true
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/run-log --help), Bash(run-log report *), Bash(run-log report), Bash(run-log --help)
---

# Run log

Every `claude -p` the workflow starts runs through `run-log run`, which appends one line to the log. `run-log --help`, below, is the reference.

Decisions about effort, model and which reviewers to run are made from this file, through `run-log report`.

```text
!`${CLAUDE_SKILL_DIR}/run-log --help`
```
