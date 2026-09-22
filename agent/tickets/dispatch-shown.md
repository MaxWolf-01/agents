---
status: open
---

# The dispatch and job machinery, shown: the flow, and what each role types

Ruled worth doing by the user in chat, 2026-09-18, reviewing figures-and-demos ticket 03: the landing, the staged demo, the ticket states and `job` have grown past what a diff conveys, and the user wants to see the whole before a pass that simplifies it.

## What to build

A show artefact (`/mx:show`), two views of one machinery. The flow at its own altitude: the states a ticket passes through (proposed, open, claimed, review, done) and the transitions between them, who writes each, what can reach what (a state diagram, or the sequence per ruling), and which script or skill is responsible for each step. And the concrete view under it: for one ticket landed once, every command the orchestrator types and every command the worker types, in order, with the frontmatter as it stands after each; the same from the worker's side. Facts come from the scripts and skills as they are on the branch, never from prose about them. The user reads it to put themselves in either role and spot what is doubled, what could be a pointer, and what could go.

## Acceptance criteria

- [ ] One artefact carries the state-and-transition view and the command-by-command view, each role's, for one ticket from claim to retirement.
- [ ] Every command shown is one the scripts run, taken from `dispatch`, `dispatch-ctl`, `job` and the skills on the branch, with the frontmatter after each step.
- [ ] Opened for the user in both colour schemes; the user judges it.
- [ ] Demo: the artefact itself, opened.
