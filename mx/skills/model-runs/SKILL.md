---
name: model-runs
description: "What the workflow's model runs cost and how long they took."
disable-model-invocation: true
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/model-runs --help), Bash(model-runs report *), Bash(model-runs report), Bash(model-runs --help)
---

# Run log

Every `claude -p` the workflow starts runs through `model-runs run`, which appends one line to the log. `model-runs --help`, below, is the reference.

Decisions about effort, model and which reviewers to run are made from this file, through `model-runs report`.

```text
!`${CLAUDE_SKILL_DIR}/model-runs --help`
```
