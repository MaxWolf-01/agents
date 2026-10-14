---
status: done
priority: 3
size: XS
---

# Pin the Python version

## Brief

The suite ran on whatever Python a machine had, and two workers saw different failures for it. The
project now names its interpreter, and every run uses that one.

## Acceptance criteria

- [x] `uv run` picks the pinned interpreter on a machine that has never seen the project.
