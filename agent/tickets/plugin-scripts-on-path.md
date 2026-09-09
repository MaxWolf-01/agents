---
status: open
type: grilling
---

# Where the plugin's scripts live for a project and a shell

`make harden` in a project's Makefile finds `harden.py` by globbing `~/.claude/plugins/cache/*/mx/*/skills/testing/`. That puts a harness path into a project file, ties the plugin to one harness's cache layout, and hides the script from a shell: `dispatch`, `dispatch-ctl` and `harden.py` have `--help` worth reading, and none of them is on `PATH`.

## Question

How do the plugin's scripts reach a project's Makefile and the user's shell without naming the cache? Candidates: a `bin/` the plugin installs or the dotfiles symlink (which couples the dotfiles the way `tre` already is); a published package run through `uvx`; the plugin's own install step writing shims. The Makefile template and the dispatch skill's setup are the two callers.

Raised from review comment C15 on the testing-workflow implementation; left as the glob for that feature.
