---
name: mermaid
description: "Mermaid diagrams, validated before they go anywhere. Use when creating or editing a mermaid chart."
---

# Mermaid Skill

Validate a Mermaid diagram before it goes anywhere, with `bash <skill-dir>/tools/validate.sh`, `<skill-dir>` being this skill's base directory. Its `--help` is the manual: run it before your first validation. The tool validates plain Mermaid files only, so a diagram that will live in Markdown is drafted in a standalone `diagram.mmd` first.

mx draws Mermaid with [Pele](https://github.com/obsidianmd/pele), which draws every diagram type Mermaid 12.1 has, takes its colours from CSS and runs no code from a diagram; the validator checks with it.
