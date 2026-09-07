---
status: draft
---

# Grilling absorbs wayfinder

Round-1 brief with the flow figures and the disposition of every wayfinder concept: `agent/show/grilling-absorbs-wayfinder/index.html`.

## Problem Statement

Two flows plan a feature: grilling (one session, the spec rewritten round by round) and wayfinder (many sessions, a map plus decision tickets, the spec draft beside the map). Since grilling started writing the spec as it goes, the map body duplicates the spec draft section for section, and a session has to choose the flow before it can know whether the frontier will drain in one sitting. In practice grillings turn into wayfindings mid-way and the map is created late or never, so the copy goes stale or the tooling built for it goes unused. Two wayfinder disciplines that grilling lacks have been failing in grillings: fog gets sliced into tickets before its questions are sharp, and scope drifts with the frontier.

## Solution

One loop. Every grilling writes the spec; a session that ends with the frontier open files the open questions as decision tickets on the tracker, and the next session claims one, grills it, and rewrites the spec sections it touches. Whether that takes one session or twelve is discovered, not declared. The map, and everything that exists to carry it, is deleted; what wayfinder learned that has no other home moves into grilling, tracker, and writing-for-humans.

## User Stories

1. As the user, I want to start any planning with `/mx:grilling` and not decide up front whether it is "too big", so that a grilling that outgrows the session keeps its artefacts and its momentum.
2. As a later session, I want to read one spec top-down plus the open tickets and know where the effort stands, so that no index has to be kept beside it.
3. As a session resolving a decision ticket, I want the ticket to name the spec sections it may rewrite, so that a resolution lands in the spec the same way a grilling round does.
4. As the user, I want fog, out-of-scope, and consent discipline to hold in a long grilling exactly as they held in wayfinder, so that nothing the map enforced is lost.
5. As a reader of orient and the README, I want one main flow with session boundaries inside it, so that the picture has one fewer branch.
6. As a project that is not software (course content), I want the spec template to fit by leaving sections out, so that planning does not need a second template. `(you, r1)`
7. As a reader of any artefact or narration, I want tickets referred to by their title with the id riding inside the link, so that a list of decisions reads at a glance.

## Properties

- The spec draft is the only planning artefact of a feature; no index or summary is kept beside or inside it. `(you, r1)`
- A decision ticket resolved by any session rewrites the spec sections it touches in the same session, marked with the ticket's name.
- Fog is never pre-sliced into tickets; a ticket exists only for a question that can be stated now, and resolving a ticket is what graduates fog.
- Scope is fixed by the Solution; work past it goes to Out of Scope with its reason, never into fog.
- Silence never ratifies: an unconfirmed call is re-listed until the user rules.

## Implementation Decisions

- The map body's sections map onto the spec: Destination → Problem Statement + Solution; Decisions so far → the decisions section with `(you, <ticket>)` marks; Not yet specified → Fog; Out of scope → Out of Scope. `(you, r1)`
- The spec template's last section is named `## Fog`, replacing Further Notes; its rule is unchanged: in-scope work whose question cannot yet be stated. `(you, r1)`
- The decisions section is named `## Decisions`, dropping "Implementation": the section is domain-agnostic once non-software features are served by omission, and the frontmatter `status: draft` already says "so far". `(open → Q5)`
- Reading order for a fresh session: Problem, Solution, the marks in Decisions, Fog, plus the open tickets; the middle sections on demand. Stated in grilling. `(you, r1)`
- Domain-agnostic by omission: a section with nothing to say is left out; one sentence in the template says so. `(you, r1)`
- Ticket Types (research, prototype, grilling, legwork) move from wayfinder into the tracker skill. `(you, r1)`
- Grilling gains: a breadth-first first round for a big idea (fan out before going deep); the rule that a decision ticket's answer rewrites the spec sections it touches; the fog discipline (no pre-slicing, resolving graduates fog); one line on out-of-scope as a scoping act (close the ticket, one line in Out of Scope, never graduates); the audit line from Consent (a finding about lost consent goes into the artefact, never through the user as a relay). `(you, r1)`
- Tracker gains amend-vs-supersede beside Supersede: edit in place while nothing is built on it, supersede once code reads it. `(you, r1)`
- writing-for-humans gains refer-by-name: a ticket, map, or issue is named by its title in narration and artefact text, with the id inside the link, never a bare id standing in for it. `(you, r1)`
- The map's Notes (skills to consult, standing preferences) have no home in the spec; they are project navigation and belong in the project CLAUDE.md. `(you, r1)`
- Dropped: the wayfinder skill and its name (its trigger words join grilling's description for one release), `map.md`, the map issue and `wayfinder:map` label, the Wayfinding operations sections of both tracker backends, the tombstone-the-map step, the Map row in orient and README, the wayfinder-loop figure (replaced by a session-boundary figure), the `(you, <ticket name>)` clause's reference to wayfinder in grilling. pocock-sync's mapping records wayfinder as dissolved, like to-spec. `(you, r1)`

## Testing Decisions

Prose skills have no test suite; the check is the three-axis review on the diff plus one dry run: a grilling that deliberately ends with the frontier open, then a fresh session that claims a ticket and lands its answer in the spec.

## Out of Scope

- The testing thread (who writes tests, mutation testing, a tester agent): its own grilling; it touches Testing Decisions and the tdd skill, not the planning loop.
- Re-charting skilltree's existing map: it ships with its feature; nothing is migrated.
- A generated index from the marks: indexes drift and go stale; ruled out with Q1. `(you, r1)`

## Fog

- The GitHub backend after the map: the spec issue as the parent of ticket sub-issues is already the convention; whether anything else was leaning on the `wayfinder:map` label is unverified.
