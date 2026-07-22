---
description: Overview of open tasks and the current frontier
argument-hint: [what you're interested in]
disable-model-invocation: true
---

# Task Overview

Generate a useful overview of `agent/tasks/` — what's open, how it fits together, and what's workable right now. Conventions: the `tracker` skill.

**User asked:** `$ARGUMENTS`

## Gather

1. Find open work:
   ```
   Grep: pattern="^status: (open|claimed)", path="agent/tasks", output_mode="files_with_matches"
   ```
   Show all non-done work by default; respect explicit filters if the user asks. If there are `**/TODO{.md}` files, look at those too.
2. Read enough of each file to understand intent and state (~60 lines); for feature directories, read the `spec.md` plus ticket frontmatter.
3. Recent commits (`git log --oneline -20`) — what's actively being worked on vs backgrounded.

## Output

Present the tasks in a way that answers what the user asked. If they asked about a specific area, focus there.

- Group by feature: spec title, then its tickets indented with status and blocked-by
- Mark the **frontier** — open, unblocked, unclaimed tickets, i.e. what can be started now
- List small standalone tasks flat
- Size/complexity hint (`[S]`/`[M]`/`[L]`) and a one-line purpose per item
- Flag only what's genuinely worth calling out — no mechanical staleness warnings

## Updating

When the user closes work: set `status: done`; note relevant commits/PRs under `## Comments`. Retire shipped features per the `tracker` skill (`git rm -r`).
