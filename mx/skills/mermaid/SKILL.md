---
name: mermaid
description: "Must read guide on creating/editing mermaid charts with valiation tools"
---

# Mermaid Skill

Validate a Mermaid diagram before it goes anywhere: `bash <skill-dir>/tools/validate.sh diagram.mmd` parses and renders it with the official CLI (`--help` for what it needs and prints).

## Workflow

1. **If the diagram will live in Markdown**: draft it in a standalone `diagram.mmd` first (the tool only validates plain Mermaid files).
2. Write/update `diagram.mmd`.
3. Run `bash <skill-dir>/tools/validate.sh diagram.mmd`.
4. Fix any errors shown by the CLI.
5. Once it validates, copy the Mermaid block into your Markdown file.
