---
status: open
type: grilling
priority: 3
size: M
---

# Comment density in a diff gets a mechanical ceiling

## Brief

Comment density keeps arriving above what you call reasonable, because a rule read while generating washes out and this one is a count a script can make. Settles what is counted, where the ceiling sits and which rung enforces it.

## Questions

Ruled worth grilling by the user in chat, 2026-09-15. The failure: a PR the user expected to be small came back long, and its author's own account was half a comment line per line of code; the in-repo instance is [The dispatch scripts' comments say what the code does, briefly](dispatch-comments.md), where about half of `dispatch` and `dispatch-ctl` is comment. The prose rules already say what a comment may say (`/mx:writing-for-humans`, one home per fact), the Standards reviewer applies them, and the density keeps arriving: a rule read while generating washes out (PRINCIPLES.md, 1), and this one is a count a script can make, like a cyclomatic-complexity lint.

A ceiling, not a target: the user's line is that 0.5 is unreasonable, that at that density either the comments or the code is bad, and that nothing should chase a value.

To decide; the options are the agent's sketch (2026-09-15), frame unconfirmed:

1. **What is counted.** Comment lines over code lines per file the diff touches, or over the diff's added lines only; whether docstrings, `--help` text and license headers count as comment; whether a file below some size is exempt.
2. **Where the ceiling sits.** Measure first: the ratio across this repo's scripts and a few of the user's other repos, so the number comes from code the user already accepts, not from a guess.
3. **Which rung.** (a) A script in `make check` that fails a file over the ceiling, run where the project's other checks run; (b) the Standards reviewer's brief carries the number and cites it per file, so the finding lands with the review and the worker disposes of it; (c) both: the script as the check, the reviewer for files under the ceiling that still read as over-commented.
4. **Where it lives.** Beside `/mx:code-review` in the plugin, so every repo the plugin reaches has it; in `/mx:project-setup`'s Makefile template, per repo; or in the worker's own pass before its self-review, the moment the comments are written.
5. **What it prints.** The files over the ceiling with their ratios, or every comment block in them, so the fix is a read and not a hunt.
