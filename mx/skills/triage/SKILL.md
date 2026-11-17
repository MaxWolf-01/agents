---
name: triage
description: "Triage the proposed tickets: group the pile by shared cause, decide the bookkeeping, and put only the design calls to the user. Use when the user starts a triage."
---

# Triage

The pile is every proposed ticket: `tracker data | jq -r '.tickets[] | select(.status == "proposed") | .slug'`, each read with `tracker context`. Two more inputs, where they exist: the project's retro report, `retro/report.md` in its agent repo, which may already group the pile by cause; and the user's TODO files, mostly gitignored, meaning each file at the root of a repo the tracker plans named `TODO` or `todos`, in any case and with or without an extension. A TODO file is context for the calls: it may add to a proposed ticket or name the cause a group shares, but no call files a ticket from it.

Group the pile by shared cause, then sort each group into one of two kinds of call. The test: would the user, seeing the result, find the product doing something different or built a different way than they chose?

- **Bookkeeping: yours.** Priorities and sizes; a merge of tickets with one cause; a drop of what an ADR already records, what landed since, or what no longer applies; a promotion of work that asks no design call, a bug or a research question included, whose fix is shaped when it is worked; refiling a ticket where its fix lives, such as workflow friction into the tracker of the repo that holds the workflow. Apply each without asking.
- **Design: the user's.** A proposal that changes what the product does or how it is built: a new feature or surface, a cut, a change of direction, a reversal of an ADR or a ruling. Each becomes a `## Questions` item on its ticket (`/mx:tracker`, Questions), which stays proposed until the ruling, and is shown with the smallest artefact the user can rule on by looking (`/mx:show`): the figure, the before and after, the render.

A TODO line gone stale (a ticket now holds it after this triage, or its work landed) is the user's call too, since the file is untracked and a cut cannot be undone: put every such line to them in one call, quoted, and cut it once they say yes.

The writes: a promotion is `tracker set <slug> status=open`, a drop `tracker drop <slug>`, each committing itself with the call's reason as its `--message`; a merge writes what the dropped ticket adds into the one it joins, committed with its reason, then drops it; a refile files it in the other tracker with what it was cut from, then drops it here. Render the board once the calls are written (`/mx:tracker`).

The triage is done when every proposed ticket is either moved by a call of yours or carries an open question, and every stale TODO line has been put to the user. Close it with one turn on [the session page](../session-page/RULES.md), in two parts that name which is which: your calls, applied, one line per group with its reason; then the user's calls alone, each with its artefact, the TODO lines to cut among them.
