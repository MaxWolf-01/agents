---
description: Grouped overview of active task files
argument-hint: [what you're interested in]
allowed-tools: Bash(cat:*)
---

# Task Overview

Generate a useful overview of active tasks — their relationships, how they fit in the project, and what state they're in.

**User asked:** `$ARGUMENTS`

## Gather Context

1. **Explore the project structure** — follow wikilinks in knowledge files to understand the main areas. This informs how you group and contextualize tasks.

2. **Find active tasks:**
   ```
   Grep: pattern="^status: active", path="agent/tasks", output_mode="files_with_matches"
   ```

   If there are "**/TODO{.md}" files, look at those too.

3. **Read task files** in parallel — enough to understand intent, relationships, and current state (~60 lines each)

4. **Build context:**
   - Follow wikilinks between tasks to understand parent/child/sibling relationships
   - Check what tasks link to what — tracking tasks aggregate subtasks, subtasks reference parents
   - Note cross-references to knowledge files for thematic grouping
   - If the user's prompt suggests a focus area, prioritize accordingly

5. **Understand project state** (if helpful):
   - Recent commits (`git log --oneline -20`) — what's actively being worked on?
   - This helps contextualize which tasks are "hot" vs backgrounded

## Output

Present the tasks in a way that answers what the user asked. If they asked about a specific area, focus there. If they want a general overview, show the landscape.

**Always include:**
- Task relationships (what depends on what, what's a subtask of what)
- Brief description of each task's purpose
- Size/complexity hint (`[S]`/`[M]`/`[L]`)
- Started date for temporal context

**Grouping:**
- By area/theme when showing the full landscape
- By relationship (parent → children) when there's clear hierarchy
- Use whatever structure makes the tasks easiest to understand

**Relationships to surface:**
- Parent/tracking tasks with their subtasks indented
- Dependencies between active tasks
- Clusters of related work

**What NOT to do:**
- Don't mechanically flag everything over X days as "stale"
- Don't add warnings unless something is genuinely worth calling out
- Don't ignore the user's focus if they specified one
- Don't show done/inactive tasks unless specifically asked

The goal is helping the user understand their task landscape — what's there, how it fits together, where they might jump in.
