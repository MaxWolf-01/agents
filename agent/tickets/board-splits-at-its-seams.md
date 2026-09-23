---
status: proposed
priority: 3
size: S
---

# The board splits at its seams

## Brief

`mx/skills/tracker/board.py` is over 3000 lines, four times the next-largest script this repo ships, and holds the CLI, the watcher, the loaders, the graph and a 950-line embedded page. A change to any one of them is read against all of it, and the next slice of board work pays that cost again.

Cut from the whole-feature review of board-orients (`7093bf7..be76e6c`, Standards axis, S13), which named it a judgement call. The feature grew the file by 2352 lines.

## What to build

The page out of the loader, as `briefing.py` and `github.py` already came out: `PAGE`, `OVERLAY`, `GRAPH_WINDOW`, `VIEW_JS` and the CSS depend on the loader only through the names they substitute, and `board.py` already imports siblings through `sys.path`. The watcher and its schedule are the next line if one file is still too much after that.

## Acceptance criteria

- [ ] `board` and `board --watch` behave as they do now, and the suite passes unchanged.
- [ ] The page is a module of its own, and `board.py` is under 2000 lines.
- [ ] Demo: the diff is the demo.
