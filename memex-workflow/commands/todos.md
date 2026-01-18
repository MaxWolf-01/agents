---
description: Grouped overview of active task files
---

# Task Overview

Generate a grouped overview of active task files with size hints and staleness flags.

## Process

1. Find active tasks via Grep tool (not bash):
   ```
   Grep: pattern="^status: active", path="agent/tasks", output_mode="files_with_matches"
   ```

2. Read task files using parallel Read tool calls (not bash for loops) — title + first ~40 lines each

3. Group by category — infer from task content, use whatever groupings make sense for this project (typically 4-8 categories)

4. Assign size: `[S]` small, `[M]` medium, `[L]` large

5. Flag issues:
   - `⚠️ done?` — task content suggests completion ("done", "complete", "merged", checklist all ticked)
   - `⏸️ stale?` — started 2+ weeks ago, might need review

## Output Format

```
## Category Name
- task-name [S]
- other-task [M] ⚠️ done?
- old-task [L] ⏸️ stale?

## Another Category
...

---
⚠️ X tasks potentially done
⏸️ Y tasks potentially stale
```

## Guidelines

- One line per task, keep it scannable
- Size is gut estimate from scope, not hours
- Don't prioritize or suggest order — just report
- If very few tasks, skip empty categories
