---
name: mermaid
description: "Must read guide on creating/editing mermaid charts with valiation tools"
allowed-tools: Bash(bash ${CLAUDE_SKILL_DIR}/tools/validate.sh --help)
---

# Mermaid Skill

Validate a Mermaid diagram before it goes anywhere, with `bash <skill-dir>/tools/validate.sh`:

```text
!`bash ${CLAUDE_SKILL_DIR}/tools/validate.sh --help`
```

## Workflow

1. **If the diagram will live in Markdown**: draft it in a standalone `diagram.mmd` first (the tool only validates plain Mermaid files).
2. Write/update `diagram.mmd`.
3. Run `bash <skill-dir>/tools/validate.sh diagram.mmd`.
4. Fix any errors shown by the CLI.
5. Once it validates, copy the Mermaid block into your Markdown file.
