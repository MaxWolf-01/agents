---
name: pickup
description: This skill should be used when resuming work from a handoff file. Invoked when /task is called with a handoff path (agent/handoffs/...) or when continuing from a previous session's handoff.
---

# Pickup

Resume work by reading a handoff file from a previous session.

## Process

### 1. Find the Handoff

If the handoff path was provided, use it directly.

If no specific handoff was given but continuation is needed, list unconsumed ones:

```bash
echo "## Available Handoffs"
grep -l "consumed: false" agent/handoffs/*.md 2>/dev/null | while read file; do
  title=$(grep -m 1 "^# " "$file" | sed 's/^# //')
  basename=$(basename "$file" .md)
  echo "* \`$basename\`: $title"
done
echo ""
echo "To continue: /task agent/handoffs/<name>.md"
```

### 2. Read the Handoff

**Curated handoffs** (markdown with frontmatter) have explicit sections — Purpose, Context, What's Next, Sources.

**Session exports** (`<session-export>` format) are raw conversation from a previous session. As you read, track all files mentioned (code, docs, knowledge files) — you'll read these in step 3.

### 3. Explore the Knowledge Base

**This is non-negotiable.** Before doing any work:

- [ ] **Read `overview.md`** — the entry point to project knowledge, always
- [ ] **Read the linked task file** — understand the intent you're continuing
- [ ] **Read relevant knowledge files** — follow wikilinks from overview that relate to your task
- [ ] **Read project context files** — dev setup, conventions, things needed to work effectively in this codebase
- [ ] **Read files from the previous session** — MUST READ sources from curated handoffs, or all files referenced throughout a session export

Continue until you feel confident about the codebase structure and task context.

Don't skim. The knowledge, pointers, and bigger picture help you build an accurate mental representation — the foundation for effective work. Documented gotchas help you avoid repeating past mistakes.

**See the task command for what good exploration looks like** — the concrete example there shows how to navigate from overview through wikilinks to the files you need.

### 4. Confirm Understanding

Briefly summarize:
- What the purpose is (from handoff)
- What you're about to do (the "What's Next")
- Any clarifications needed

Ask the user to confirm, or clarify if something seems off.

### 5. Mark as Consumed

After loading successfully, update the handoff frontmatter:

```yaml
consumed: true
```

### 6. Ready to Implement

When you understand the task and are ready to write code:

**→ Invoke the implement skill**

Do not write code without completing the implement checklist.

This applies even for seemingly trivial changes — they often have cross-cutting concerns you'll miss without the checklist.

## Notes

- The task file is the source of truth for intent
- The handoff captures session-specific context the task file doesn't have
