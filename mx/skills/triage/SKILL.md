---
name: triage
description: "Triage the proposed tickets: group the pile by shared cause, decide the bookkeeping, and put only the design calls to the user. Use when the user starts a triage."
---

# Triage

The pile is every proposed ticket: `tracker data | jq -r '.tickets[] | select(.status == "proposed") | .slug'`, each read with `tracker context`. The project's retro report, `retro/report.md` in its agent repo, is one more input where it exists, since it may already group the pile by cause.

Group the pile by shared cause, then sort each group into one of two kinds of call. The test: would the user, seeing the result, find the product doing something different or built a different way than they chose?

- **Bookkeeping: yours.** Priorities and sizes; a merge of tickets with one cause; a drop of what an ADR already records, what landed since, or what no longer applies; a promotion of work that asks no design call, a bug or a research question included, whose fix is shaped when it is worked; refiling a ticket where its fix lives, such as workflow friction into the tracker of the repo that holds the workflow. Apply each without asking.
- **Design: the user's.** A proposal that changes what the product does or how it is built: a new feature or surface, a cut, a change of direction, a reversal of an ADR or a ruling. Each becomes a `## Questions` item on its ticket (`/mx:tracker`, Questions), which stays proposed until the ruling, and is shown with the smallest artefact the user can rule on by looking (`/mx:show`): the figure, the before and after, the render.

The writes: a promotion is `tracker set <slug> status=open`, a drop `tracker drop <slug>`; a merge writes what the dropped ticket adds into the one it joins, then drops it; a refile files it in the other tracker with what it was cut from, then drops it here. Commit in the agent repo with each call's reason in the message, and render the board (`/mx:tracker`).

The triage is done when every proposed ticket is either moved by a call of yours or carries an open question. Close it with one turn on [the session page](../session-page/RULES.md), in two parts that name which is which: your calls, applied, one line per group with its reason; then the user's calls alone, each with its artefact.
