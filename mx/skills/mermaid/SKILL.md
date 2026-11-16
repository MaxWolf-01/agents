---
name: mermaid
description: "Mermaid diagrams, validated before they go anywhere. Use when creating or editing a mermaid chart."
---

# Mermaid Skill

Validate a Mermaid diagram before it goes anywhere, with `bash <skill-dir>/tools/validate.sh`, `<skill-dir>` being this skill's base directory. Its `--help` is the manual: run it before your first validation.

mx draws Mermaid with [Pele](https://github.com/obsidianmd/pele): it reads Mermaid syntax and draws every diagram type Mermaid 12.1 has, takes its colours from CSS, is smaller and faster than mermaid.js, and runs no code from a diagram. The validator checks with it.

## Workflow

1. **If the diagram will live in Markdown**: draft it in a standalone `diagram.mmd` first (the tool only validates plain Mermaid files).
2. Write/update `diagram.mmd`.
3. Run `bash <skill-dir>/tools/validate.sh diagram.mmd`.
4. Fix every error it reports, at the line and column it names.
5. Once it validates, copy the Mermaid block into your Markdown file.
