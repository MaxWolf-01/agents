---
description: Resume work from a previous handoff
argument-hint: [handoff-slug]
disable-model-invocation: true
---

Resumes work from a previous handoff session stored in `agent/handoffs/`.

Requested handoff: `$ARGUMENTS`

## Process

### 1. Find the Handoff

If no handoff was specified, list unconsumed ones:

```bash
echo "## Available Handoffs"
echo ""
grep -l "consumed: false" agent/handoffs/*.md 2>/dev/null | while read file; do
  title=$(grep -m 1 "^# " "$file" | sed 's/^# //')
  basename=$(basename "$file" .md)
  echo "* \`$basename\`: $title"
done
echo ""
echo "To pickup: /pickup <name>"
```

### 2. Load the Handoff

If a handoff was specified:
1. Look for it in `agent/handoffs/`
2. The user might have given a partial name or just the slug — find the best match
3. If multiple matches, ask which one to continue

### 3. Read and Continue

Read the handoff file. It contains:
- **Purpose** — What you need to accomplish
- **Intent & Context** — User's goals and mental model
- **Technical State** — Where things stand
- **Gotchas** — Things to avoid re-learning
- **What's Next** — Your starting point
- **Relevant Links** — Task files and knowledge to read

### 4. Load Context

Before starting work:
1. Read any linked task files (`[[task-name]]`)
2. Read any linked knowledge files (`[[knowledge-file]]`)
3. Fetch any external docs listed

### 5. Confirm and Proceed

Briefly summarize:
- What you understand the purpose to be
- What you're about to do (the "What's Next" from handoff)

Then ask the user to confirm before proceeding, or clarify if something seems off.

### 6. Mark as Consumed

After loading successfully, update the handoff frontmatter:

```yaml
consumed: true
```

This prevents it from showing in future `/pickup` listings.

## Notes

- If the handoff references a task file, that task file is the source of truth for intent
- The handoff captures session-specific context the task file doesn't have
