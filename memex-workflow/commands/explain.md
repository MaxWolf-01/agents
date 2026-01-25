---
description: Explain code changes with fresh eyes
argument-hint: [scope]
allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(tre:*), Bash(cat:*)
disable-model-invocation: true
---

<project-overview>
!`cat agent/knowledge/overview.md 2>/dev/null || true`
</project-overview>

You are explaining code changes to someone who didn't write them.

The user specified scope: `$ARGUMENTS`

If no scope specified, explain uncommitted changes (`git diff`).

## Determine What to Explain

Based on arguments (usually natural language):
- No args → `git diff` (uncommitted changes)
- "staged" → `git diff --cached`
- A file path → changes to that file
- A commit hash → that specific commit
- A range → commits in that range
- Natural language description → interpret and find the right diff

## Gather Context

Run the appropriate git commands to get:
1. The diff itself
2. Recent commit messages for context (`git log --oneline -10`)
3. File structure if helpful (`tre` on affected directories)

## Explain

For each significant change:

### [File or area]
**What changed:** [Factual description]

**Why (inferred):** [What this seems to accomplish, based on context]

**Observations:** [Anything that seems inconsistent, potentially problematic, or worth a second look]

## Be Factual

- You didn't write this code, so you have no stake in defending it
- If something looks wrong, say so
- If something is unclear, say it's unclear
- Don't speculate beyond what the code shows

## Output Summary

End with:
> **Summary:** [1-2 sentences on what the overall change accomplishes]
>
> **Concerns:** [Any issues spotted, or "None"]
