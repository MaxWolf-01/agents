---
name: codex
description: "Second opinion from a different model family (OpenAI Codex). Use when exploring design choices, debugging a hard problem, when stuck, or when the user wants a second perspective."
---

# Codex: Second Opinion

## Command

`<slug>` is the repo's name and a few words naming what you asked about (`agents-auth-redesign`, `memex-flaky-test`).

```sh
job run codex-<slug> -- codex exec -s read-only -c 'sandbox_permissions=["disk-full-read-access"]' -o "/tmp/codex-<slug>.md" "<prompt>"
```

- `-s read-only` + `disk-full-read-access`: codex reads any file on disk and writes none, so it cannot conflict with your work.
- `-o`: the file codex writes its final answer to, which you read when the wait returns.
- Model and reasoning effort ride the codex config defaults. Add `-c 'model_reasoning_effort="high"'` (or `"xhigh"`) only for especially reasoning-intensive tasks, such as a hard bug or a subtle design question.
- Reviewing a different project: `job run --cwd <dir>` rather than codex's own `-C`, so the pane is there too if you attach.

Then run `job wait codex-<slug> --deadline <secs>` as a background task, the deadline sized to what you asked (a whole-codebase read takes longer than one file); it only keeps a wedged `codex exec` from waiting out the session. Read `/tmp/codex-<slug>.md`, `job log codex-<slug>` if it failed, then `job rm codex-<slug>`. `/mx:tmux` has the rest.

## How to Prompt Codex

Codex has **zero context** from your session. Everything it needs must be in the prompt or readable from the filesystem.

**Give it orientation first:**
- Codex loads the project's `AGENTS.md` itself; where the project keeps its instructions in a `CLAUDE.md` instead, tell it to read `./CLAUDE.md`.
- Point it at the glossary, the ADRs and the ticket where relevant, rather than re-explaining what they record.

**Add the session context it can't get from files:** the current approach, the decisions made, the constraints discovered.

**GPT-5 is sensitive to contradictory instructions**, more so than other models: keep the prompt consistent and unambiguous.
