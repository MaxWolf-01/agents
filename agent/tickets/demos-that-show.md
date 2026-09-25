---
status: open
priority: 2
size: M
---

# Demos that show instead of scroll

## Brief

The demos workers write for a command-line change have not been useful to the user: they come out as a wall of commands and output, or a walkthrough page of text, and the user learns nothing from them. The explainers and figures built with `/mx:show` have been useful; the landing demos have not. This ticket finds out what a demo of a script, a hook or a CLI has to be so the user understands the change from it, and changes `/mx:show` and the worker contract to produce that.

Filed on the user's request on 2026-09-24, after the demos of `tracker-command-and-commit-check` and `scripts-go-through-tracker-command` ("completely useless, just a wall of text"). The demos they judged are in `agent/show/tracker-command-and-commit-check/` and `agent/show/scripts-go-through-tracker-command/` on the `ticket-file-contract` branch until it merges.

## Acceptance criteria

- [ ] What made the useful artifacts useful and the CLI demos not is written down, from the demos in this repo's history and the user's verdicts on them.
- [ ] `/mx:show`'s demo guidance and the worker contract's Demo line say what a CLI change's demo is, and one past demo redone that way is put in front of the user.

## Comments
