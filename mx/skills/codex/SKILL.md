---
name: codex
description: "Second opinion from a different model (OpenAI Codex). Use when exploring different design choices (more diversity with heterogenous models), debugging hard problems, or when the user wants a second perspective, you want second perspective, are stuck, ..."
---

# Codex — Second Opinion

Run OpenAI's Codex CLI non-interactively from Claude Code. Different model family = different blind spots, different strengths.

## Example use cases

- To increase diversity of opinions when exploring design choices
- Code review or architecture critique
- Debugging when stuck — different model may see different patterns
- User explicitly asks for a second perspective

## Command

```sh
_id=$(date +%s%N); codex exec -s read-only -c 'sandbox_permissions=["disk-full-read-access"]' -c 'model_reasoning_effort="xhigh"' -o "/tmp/codex-${_id}.md" "<prompt>" > "/tmp/codex-${_id}-log.md" 2>&1
```

- `-s read-only` + `disk-full-read-access` — can read any file on disk, not write (no codebase conflicts)
- `-o` — final answer to file. `_id` = epoch-nanosecond timestamp
- `-c 'model_reasoning_effort="xhigh"'` — always `xhigh`
- `-C <dir>` — working directory (defaults to cwd, set when reviewing a different project)

Run via Bash with `run_in_background: true`. You already have `_id` from the command — read `/tmp/codex-${_id}.md` directly. Log at `/tmp/codex-${_id}-log.md` if debugging.

## How to Prompt Codex

Codex has **zero context** from your session. Everything it needs must be in the prompt or readable from the filesystem.

**Give it orientation first:**
- Tell it to read `./CLAUDE.md` (project root) for project context, knowledge map, and conventions
- Point it to `CONTEXT.md`, `decisions/`, and `agent/tasks/` when relevant — written records is more efficient than re-explaining what's already documented
- Name the specific files and directories to review — it can read them, but won't know which ones matter unless told

**Add session context it can't get from files:**
- Describe the current approach, decisions made, constraints discovered — things only in your conversation
- State the question clearly: what you want reviewed, what kind of answer you want

**Request structured output:**
- "List the top 5 issues, each with: what's wrong, where, and how you'd fix it"
- "Pros and cons of this approach as a numbered list"
- Not: "What do you think?"

**GPT-5 is sensitive to contradictory instructions** — more so than other models. Keep prompts clean and unambiguous.
