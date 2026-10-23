---
name: mermaid
description: "Mermaid diagrams, validated before they go anywhere. Use when creating or editing a mermaid chart."
---

# Mermaid Skill

Validate a Mermaid diagram before it goes anywhere, with `bash <skill-dir>/tools/validate.sh`, `<skill-dir>` being this skill's base directory. Its `--help` is the manual: run it before your first validation.

## Workflow

1. **If the diagram will live in Markdown**: draft it in a standalone `diagram.mmd` first (the tool only validates plain Mermaid files).
2. Write/update `diagram.mmd`.
3. Run `bash <skill-dir>/tools/validate.sh diagram.mmd`.
4. Fix any errors shown by the CLI.
5. Once it validates, copy the Mermaid block into your Markdown file.
