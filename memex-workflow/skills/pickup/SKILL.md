---
name: pickup
description: This skill should be used when resuming work from a handoff file. Invoked when /task is called with a handoff path (agent/handoffs/...) or when continuing from a previous session's handoff.
---

# Pickup

Resume work from a previous handoff session stored in `agent/handoffs/`.

## Process

### 1. Find the Handoff

If the handoff path was provided, use it directly.

If no specific handoff was given but continuation is needed, list unconsumed ones:

```bash
echo "## Available Handoffs"
echo ""
grep -l "consumed: false" agent/handoffs/*.md 2>/dev/null | while read file; do
  title=$(grep -m 1 "^# " "$file" | sed 's/^# //')
  basename=$(basename "$file" .md)
  echo "* \`$basename\`: $title"
done
echo ""
echo "To continue: /task agent/handoffs/<name>.md"
```

### 2. Load the Handoff

1. Look for it in `agent/handoffs/`
2. The user might have given a partial name or just the slug — find the best match
3. If multiple matches, ask which one to continue

### 3. Read and Continue

Read the handoff file. It contains:
- **Purpose** — What to accomplish
- **Intent & Context** — User's goals and mental model
- **Technical State** — Where things stand
- **Gotchas** — Things to avoid re-learning
- **What's Next** — Starting point
- **Relevant Links** — Task files and knowledge to read

### 4. Load Context

Before starting work:
1. Read any linked task files (`[[task-name]]`)
2. Read any linked knowledge files (`[[knowledge-file]]`)
3. Fetch any external docs listed as MUST READ

### 5. Confirm and Proceed

Briefly summarize:
- What the purpose is understood to be
- What's about to be done (the "What's Next" from handoff)

Ask the user to confirm before proceeding, or clarify if something seems off.

### 6. Mark as Consumed

After loading successfully, update the handoff frontmatter:

```yaml
consumed: true
```

This prevents it from showing in future listings.

## Notes

- If the handoff references a task file, that task file is the source of truth for intent
- The handoff captures session-specific context the task file doesn't have
