---
name: codex
description: "Second opinion from a different model (OpenAI Codex). Use when exploring different design choices (more diversity with heterogenous models), debugging hard problems, or when the user wants a second perspective, you want second perspective, are stuck, ..."
---

# Codex: Second Opinion

Run OpenAI's Codex CLI non-interactively from Claude Code. Different model family = different blind spots, different strengths.

## Example use cases

- To increase diversity of opinions when exploring design choices
- Code review or architecture critique
- Debugging when stuck; a different model may see different patterns
- User explicitly asks for a second perspective

## Command

`<slug>` is the repo's name and a few words naming what you asked about (`agents-auth-redesign`, `memex-flaky-test`).

```sh
job run codex-<slug> -- codex exec -s read-only -c 'sandbox_permissions=["disk-full-read-access"]' -o "/tmp/codex-<slug>.md" "<prompt>"
```

- `-s read-only` + `disk-full-read-access`: can read any file on disk, not write (no codebase conflicts)
- `-o`: final answer to file, which is what you read when the wait returns
- Model and reasoning effort ride the codex config defaults. Add `-c 'model_reasoning_effort="high"'` (or `"xhigh"`) only for especially reasoning-intensive tasks: a hard bug, a subtle design question.
- Reviewing a different project: `job run --cwd <dir>` rather than codex's own `-C`, so the pane is there too if you attach.

Then `job wait codex-<slug> --deadline <secs>` as a background task. Pick the deadline from what you asked for, since a question that needs a whole codebase read is not the one that needs a single file; it is there only so a `codex exec` that wedges does not wait until the session ends. Read `/tmp/codex-<slug>.md`, `job log codex-<slug>` if it failed, then `job rm codex-<slug>`. `/mx:tmux` has the rest.

## How to Prompt Codex

Codex has **zero context** from your session. Everything it needs must be in the prompt or readable from the filesystem.

**Give it orientation first:**
- Tell it to read `./CLAUDE.md` (project root) for project context, knowledge map, and conventions
- Point it to `CONTEXT.md`, `decisions/`, and `agent/tickets/` when relevant; written records is more efficient than re-explaining what's already documented
- Name the specific files and directories to review; it can read them, but won't know which ones matter unless told

**Add session context it can't get from files:**
- Describe the current approach, decisions made, constraints discovered: things only in your conversation
- State the question clearly: what you want reviewed, what kind of answer you want

**Request structured output:**
- "List the top 5 issues, each with: what's wrong, where, and how you'd fix it"
- "Pros and cons of this approach as a numbered list"
- Not: "What do you think?"

**GPT-5 is sensitive to contradictory instructions**, more so than other models. Keep prompts clean and unambiguous.
