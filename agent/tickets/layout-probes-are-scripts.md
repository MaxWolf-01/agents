---
status: proposed
priority: 4
size: XS
---

# The layout probes are scripts, not strings

## Brief

`mx/skills/tracker/test_board_layout.py` carries two playwright programs, about 250 lines, as `r'''...'''` strings piped to `uv run python -`. Nothing parses them until runtime, so a syntax error surfaces as a JSON decode failure of empty output.

Cut from the whole-feature review of board-orients (`7093bf7..be76e6c`, Standards axis, S12). Every other browser-driving file in the repo is a PEP 723 script: `mx/skills/show/render_lint.py`, `docs/figures/render.py`, `docs/figures/board-fixture/build.py`, and the figure scripts under `agent/show/board-orients/`.

## What to build

The two programs as files beside the test with their own `# /// script` headers, called the way the same test already calls `render_lint.py`.

## Acceptance criteria

- [ ] The layout checks pass unchanged, and a syntax error in a probe fails with the interpreter's own message.
- [ ] Demo: the diff is the demo.
