---
name: codex
description: "Second opinion from a different model (OpenAI Codex). Use when reviewing plans, code reviewing, debugging hard problems, or when the user wants a second perspective."
---

# Codex — Second Opinion

Run OpenAI's Codex CLI non-interactively from Claude Code. Different model family = different blind spots, different strengths.

## When to Use

- Code review or architecture critique (standalone or as part of `/roast`)
- Second opinion on a plan or approach
- Debugging when stuck — different model may see different patterns
- User explicitly asks for a second perspective

## Command

```sh
codex exec -s read-only -c 'sandbox_permissions=["disk-full-read-access"]' -c 'model_reasoning_effort="xhigh"' -o "/tmp/codex-$$.md" "<prompt>" > "/tmp/codex-$$-log.md" 2>&1
```

- `-s read-only` + `disk-full-read-access` — can read any file on disk, not write (no codebase conflicts)
- `-o` — final answer to file. `$$` = unique per invocation
- `-c 'model_reasoning_effort="xhigh"'` — always `xhigh`
- `-C <dir>` — working directory (defaults to cwd, set when reviewing a different project)

Run via Bash with `run_in_background: true`, then read `/tmp/codex-<pid>.md` for the answer. Log at `/tmp/codex-<pid>-log.md` if debugging.

## How to Prompt Codex

Codex has **zero context** from your session. Everything it needs must be in the prompt or readable from the filesystem.

**Give it orientation first:**
- Tell it to read `./CLAUDE.md` (project root) for project context, knowledge map, and conventions
- Point it to `agent/knowledge/` and `agent/tasks/` when relevant — written records is more efficient than re-explaining what's already documented
- Name the specific files and directories to review — it can read them, but won't know which ones matter unless told

**Add session context it can't get from files:**
- Describe the current approach, decisions made, constraints discovered — things only in your conversation
- State the question clearly: what you want reviewed, what kind of answer you want

**Request structured output:**
- "List the top 5 issues, each with: what's wrong, where, and how you'd fix it"
- "Pros and cons of this approach as a numbered list"
- Not: "What do you think?"

**GPT-5 is sensitive to contradictory instructions** — more so than other models. Keep prompts clean and unambiguous.

## Maintenance

- **Update CLI**: `bun install -g @openai/codex`
- **Models last checked**: 2026-02-12. Default: `gpt-5.3-codex` (ChatGPT account). Auth is ChatGPT-based, not API key.
