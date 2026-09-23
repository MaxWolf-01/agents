---
status: proposed
priority: 3
size: S
---

# A loose branch gets its review page from the plugin, not from one machine's config

## Brief

The workflow states that loose work is gated by a review page, and nothing in the plugin renders one: the only instruction lives in your own config. Either `dispatch review` gains a branch mode or the docs name diffview as the dependency.

Cut from the whole-feature review of one-flow (Spec axis, A6): the spec says of loose work that "the session commits on its branch with the `loose` trailer, and the review page is the gate before the user sees it", and orient states the rule. Nothing in `mx/` renders that page. `dispatch review` is ticket-bound: it reads `agent/tickets/<id>.md` and needs `ticket/<branch>/<id>` to exist, and dies without them. The only instruction that covers the loose case is `claude/CLAUDE.md`'s `diffview --watch --open`, which is max's own config rather than the plugin every machine installs, so a reader who has only the plugin reaches a stated gate with no tool behind it.

## What to build

One of two, and choosing is part of the ticket: give `dispatch review` a branch mode (a range and a title, no ticket, output under `agent/diffviews/<branch>.html`), or state in orient and the README that the loose gate is `diffview` on the branch's range and that the plugin assumes it on the machine. The first keeps one command for every page the workflow renders; the second keeps dispatch about tickets and admits an external dependency.

## Acceptance criteria

- [ ] A branch carrying only `loose` commits reaches a review page by a documented command that the plugin either ships or names as a dependency.
- [ ] The rule has one home: orient, the README and the skill that owns the command agree, and no artefact states a gate with no tool behind it.
- [ ] Demo in the closing comment: a loose branch in a toy repo, the command, the page.
