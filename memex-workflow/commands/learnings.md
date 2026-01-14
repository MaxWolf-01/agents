---
description: Extract learnings from a session into knowledge files
argument-hint: [session-name]
allowed-tools: Read, Grep, Glob, Bash(node:*), Bash(grep:*)
model: opus
---

Extract learnings from a session and update or create knowledge files.

Arguments: `$ARGUMENTS`

## Determine Mode

**If a session name was provided:** Extract transcript from that session (external analysis).

```bash
node ${CLAUDE_PLUGIN_ROOT}/scripts/extract-session.js --name "$ARGUMENTS" > /tmp/session-transcript.txt
```

If this fails, tell the user they need to name the session first with `/rename`.

Use `--max-messages N` to limit to the last N messages if the full transcript isn't needed.

Read the transcript from `/tmp/session-transcript.txt`.

**Note:** For external analysis, running in a fresh session avoids "I just wrote this" bias.

**If no argument, or it's clear from context that this session's learnings should be captured:** Reflect on current session's work directly. You have full context — no transcript extraction needed.

## Analyze the Session

Read through the entire transcript looking for:

### 1. Gotchas & Pitfalls
- What went wrong that wasn't obvious?
- What assumptions were incorrect?
- What error messages were misleading?
- What documentation was missing or wrong?

### 2. Patterns & Workflows
- What approaches worked well?
- What sequence of steps solved the problem?
- What commands or techniques were discovered?

### 3. Confusion Points
- Where did the agent retry or change approach?
- What took multiple attempts to figure out?
- What would have been helpful to know upfront?

### 4. Key Decisions
- What trade-offs were evaluated?
- What was chosen and why?
- What was explicitly rejected?

## Check Existing Knowledge

Before creating new files, explore what already exists:

1. Use memex `search` to find related knowledge files
2. Use `explore` to follow wikilinks from discovered files
3. Check if learnings belong in an existing file vs. a new one

**Prefer updating existing files** over creating new ones. New files only when the topic is genuinely distinct.

## Update or Create Knowledge

Write wtih the perspective of future agents working on the project in mind.

For each significant learning:

**If updating existing file:**
- Add to the appropriate section
- Maintain the file's existing structure and tone
- Add wikilinks to related files if connections discovered

**If creating new file:**
- Use descriptive name: `agent/knowledge/<topic>.md`
- Keep it focused, separate concerns, cross-reference deliberately
- Link FROM relevant existing files TO the new file (bidirectional linking)

**Content guidelines:**
- State facts, not speculation
- Link to code files, don't embed snippets
- Include the "why" not just the "what"
- If a gotcha has a workaround, include it
- Capture learnings with long-term value 
- Point agents to code files and resources they should read

## Report

Tell the user:
- What learnings you extracted
- Which files you updated or created
- Any wikilinks you added
- Anything you chose NOT to capture (and why — maybe too specific, already documented, etc.)

## Don't

- Don't create knowledge for one-off issues unlikely to recur
- Don't duplicate what's already documented
- Don't add speculative content
- Don't create files for trivial learnings
- Don't add code snippets when you could point to code files/scripts instead
- Don't add speculative content (only facts from code)
- Don't rewrite sections unnecessarily
- Don't create orphan files (always link from somewhere)
- Don't write things that won't be helpful for future work
- Don't capture (true) one-off issues 
- Don't write capture knowledge that amounts to "extended code comments/docstrings"
- Don't explain trivial things/things that are obvious from reading the code

