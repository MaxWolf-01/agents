---
status: confirmed
---

# Design-first grilling writes the spec

## Problem Statement

A grilling round is a numbered list of questions, each with a recommended option. The design is never shown: it is the implicit product of the recommended answers, and the user rebuilds it in their head, round after round. The frontier rule makes this worse: downstream questions wait until their prerequisites settle, so the consequences of a root choice are exactly what a round cannot show. Judgment is render-triggered: the same person who is blank on an abstract question produces sharp criticism in front of a render, and a question list is not a render of a design.

The spec, the one artefact that would hold the design, is written by a separate user-invoked skill after grilling, and only on the multi-session branch. Agents never suggest it, and the user never wants an extra document to check afterwards, so every single-session grilled design lives and dies in chat.

## Solution

The unit of a grilling round is the design, not the question. Every round above a one-or-two-question ambiguity delivers the design as it currently stands, written to the feature's spec file as a draft, with every call marked by who made it and whether it is confirmed. Questions follow, only where two live options survive expert judgment. The spec is the byproduct of grilling, single- or multi-session alike, and to-spec dissolves into grilling.

## User Stories

1. As the user in a grilling, I want each round to show the whole design as it currently stands, so that I judge shape and consequences instead of reconstructing them from answers.
2. As the user, I want every call in the design tagged with who made it and whether I confirmed it, so that I veto or amend calls by name and nothing an agent decided passes as mine.
3. As the user, I want unconfirmed calls re-listed each round until I rule on them or say "rest ok", so that silence never ratifies.
4. As the user, I want questions only where both options hold up, so that I am not rubber-stamping.
5. As the user, I want each question to name the part of the design it would change, so that I see what an answer does.
6. As the user, when more than one design survives, I want each design with its own refining questions and then the questions that choose between designs, so that the framing of the problem is decided explicitly.
7. As the user, I want the design in a file at a stable path from the first design round, so that the full shape is always available without re-reading chat.
8. As the user, I want to watch the file's per-round delta in the browser, so that I read only what changed.
9. As the user, I want user stories written from the first round, so that I catch misunderstandings in them as they form.
10. As the user, I want the spec to exist for single-session work too, so that the size decision (tickets or not) is made at the gate, not at round one.
11. As the user, I want a spec marked draft until I confirm it, so that no worker or later session reads an unconfirmed design as settled.
12. As the user, I want the confirmation gate to walk the unconfirmed list and then strip the markers, so that the confirmed spec reads cold.
13. As an implementing agent, I want a confirmed spec with no provenance residue, so that I build what was decided.
14. As a wayfinding session, I want to update the spec draft as each decision resolves, so that the destination document grows with the journey and no end-of-map translation is needed.
15. As a wayfinding session, I want research and other AFK results to reach the spec only through a round with the user, so that agent findings never pile up in the spec unproposed.
16. As the user grilling outside a repo, I want the design delivered as a section in chat, so that the primitive works anywhere.
17. As the user, I want a standalone task that gets grilled to be absorbed into its spec directory, so that the brief and the design have one home.
18. As a later reader, I want no skill, README, or tracker line still teaching the to-spec flow, so that agents do not follow a retired step.

## Properties

- The spec draft changes only as the result of a round the user is in: every line is either user-settled or was proposed to the user in that round.
- A spec with `status: draft` is never read as settled truth by any skill.
- A confirmed spec carries no provenance markers.
- A question never carries a call the design section has not made visible.
- The skill encodes structure (design, then questions, two question levels), never presentation (tables, diagrams, layout).

## Implementation Decisions

- **Round structure**: design section, then questions. When designs compete: per-design refining questions, then the questions that choose between designs. Question-only rounds remain for one or two ambiguities; a rival design appears only under the same bar as an option.
- **Sketch depth**: the design is sketched to the leaves under the agent's defaults, each marked; `(fog)` marks what cannot be sketched yet.
- **Markers**: `(you, rN)` settled, `(my call)` vetoable, `(open → Qn)`, `(fog)`. Stripped at the gate.
- **File**: `agent/tasks/<slug>/spec.md` from the first design round, in any repo, frontmatter `status: draft | confirmed`. Outside a repo the design is a section in chat.
- **Update granularity**: rewritten at the end of each round by default; skipped when clarification must come first or the picture is mid-flip; current at the gate.
- **Per-round commit**: on the grilling worktree's branch, landing when the answers for round N arrive, so the page shows that round's delta during the answer window; merged `--no-ff`, so the integration branch's first-parent log shows one entry.
- **Review surface**: `diffview --watch HEAD..` on the worktree. The spec stays textual; visuals are show artefacts, linked or embedded as images.
- **User stories from round one**.
- **to-spec dissolves**: its template becomes `SPEC-FORMAT.md` in the grilling skill; the seam step becomes a round topic; the gate is the finalize step; the skill directory is deleted.
- **Roles**: spec = the design. Ticket = the execution unit with state, sliced by to-tickets when the work goes to the frontier. Standalone task = a ticket with no spec, for work that needs no design round or a brief filed for later; a grilled brief is absorbed into its spec directory (text into the problem statement; file deleted, or moved in as the single ticket if it should stay on the frontier).
- **Feature structure**: the directory is the feature; no feature ticket file. Standalone tasks take `blocked-by`, referencing a standalone task by slug or a feature ticket by `<feature>/NN`; no blocking on a whole feature.
- **Frontier**: tickets only. A spec-only directory is invisible to scanners; handing it to a worker means to-tickets.
- **Wayfinder**: charting creates the spec draft beside the map; each HITL-resolved ticket updates the sections it touches; AFK results (research artefacts, prototype ANSWER.md) enter the spec only through a round; the final session is the gate plus one whole-document read for cross-session coherence, and tombstones the map. A decision ticket writes into its answer and the spec draft; when the destination is a decision rather than a spec, the ADR is the artefact.
- **Sweep**: tracker MARKDOWN.md (written-by line, standalone `blocked-by`, wayfinding operations), orient (flow steps 1 and 3, artefacts table), README (flow line, spec-review bullet), to-tickets input line, expert ("last frontier round" becomes the design). grill-with-docs is unchanged.
- **Deferred, typed**: a rendered preview of the spec with figures, and anchoring questions to spec lines in the review surface, are tooling. If nobody builds them, the raw-markdown diff stays the surface, which works.

## Testing Decisions

Prose in skills is the logic, so the test is a grilling run under the new skill: a round arrives as design plus questions; the draft file exists after round one with markers; the unconfirmed list re-appears until ruled on; the gate strips markers and sets `confirmed`. One run on this change, one on the next feature.

## Out of Scope

- HTML as the spec format: the spec is data that agents consume; visuals are derived from it.
- A commit-free grilling mode, and a spec-only frontier item.
- A cap on how far past the frontier the sketch goes.

## Further Notes

Principles this rests on: humans judge in front of a render; decisions are the human's, with provenance per claim; deliver through artefacts, not chat; state the goal at the right altitude and leave presentation to judgment.
