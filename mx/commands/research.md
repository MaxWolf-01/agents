---
description: Investigate a question and produce a research artefact
argument-hint: [topic or question]
---

Investigate a question. Produce a research artefact in `agent/research/`.

Arguments: `$ARGUMENTS`

## What Research Artefacts Are

Point-in-time snapshots of an investigation — code analysis, web searches, doc reading, trade-off evaluation — distilled into a file that other sessions can consume.

They capture what was found at a specific point in time. Code changes and docs update, so treat older artefacts accordingly.

## Process

1. **Clarify what needs answering.** If the research topic isn't specific enough, sharpen it before investigating.

2. **Investigate.** Use whatever's appropriate:
   - Read code — current state, patterns, constraints
   - Web search — docs, blog posts, comparisons
   - Memex — `mx explore` for related knowledge, `mx search` for semantic lookup
   - Prior research — check `agent/research/` for related artefacts
   - Task context — read linked tasks for intent and assumptions

3. **Produce the artefact.** Write findings to `agent/research/`:

```markdown
# <Topic>

## Question

What we're trying to find out.

## Findings

What we found. Include:
- Sources (URLs, file paths, `[[knowledge-links]]`)
- Key facts and data points
- Trade-offs between options if applicable
```

Filename: `YYYY-MM-DD-<descriptive-slug>.md`

4. **Link it.** If this research backs a task, add it to the task's `## Research` section.

## Notes

- If findings are insufficient or inconclusive, state that explicitly — don't pad to appear complete.
- Multiple research artefacts per task is normal for complex work.
- Don't pad findings. If the answer is straightforward, the artefact can be short.
