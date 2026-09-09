---
name: pocock-sync
description: Review upstream mattpocock/skills changes since the recorded baseline and adopt what fits the adapted mx skills. Use when the user asks to check, sync, or adopt Matt Pocock's latest skill changes.
---

# Sync with mattpocock/skills

**Baseline**, the last upstream commit reviewed: `3cca18b` (2026-09-03). Every sync ends by moving this line forward; it is the single source of truth for "where we left off".

## Process

1. **Clone fresh**: `git clone https://github.com/mattpocock/skills /tmp/mattpocock-skills` (full history; the baseline may be far back).
2. **Walk the log**: `git log <baseline>..HEAD`, then classify every commit as either touching a mapped skill (below), a new upstream skill (including `in-progress/`; note each with one line), or noise (changesets, plugin manifests, `agents/openai.yaml`, docs site, README). Done when every commit is classified.
3. **Read before judging**: for each substantive change, read the full diff *and* the commit message; Matt's reasoning lives in the message body. Then read the current mx version, `PRINCIPLES.md` at the repo root, and the rejections recorded in earlier baseline bumps (`git log --grep='pocock-sync: move baseline'`). An upstream move either already answers is still presented, with that answer quoted beside it: the new version may add a nuance the answer lacks, and that is judged in the same per-item presentation as everything else. The mx skills are adaptations, not copies: a line upstream deletes as redundant may be load-bearing in mx (e.g. to-tickets' routing to `/mx:dispatch`), and upstream vocabulary translates (`.scratch/` → `agent/`, `/skill` → `/mx:skill`, `docs/adr/` → `decisions/`, GitHub issues → the mx `tracker` conventions).
4. **Present before editing**: one section per affected skill with a table quoting actual lines (current mx text vs proposed text) plus Matt's reasoning and your recommendation (adopt / adapt / skip, and why). The user decides per item; a go-ahead on one item doesn't cover the rest.
5. **Apply what's approved**, adapted to mx conventions, one commit per skill citing the upstream hash. Record deliberate rejections in the baseline-bump commit message so the next sync doesn't re-propose them.
6. **Move the baseline**: update the Baseline line above to the upstream HEAD you reviewed, and commit it. Done when the recorded hash equals the reviewed HEAD.

## Mapping (mx ← upstream)

Same-named: grilling, grill-with-docs, code-review, codebase-design, diagnosing-bugs, improve-codebase-architecture, prototype, research, to-tickets, implement, handoff, wait-what, to-questionnaire, wizard, writing-for-agents.

Dissolved:
- to-spec → grilling writes the spec round by round; upstream changes to to-spec's template map onto grilling's `SPEC-FORMAT.md`, changes to its process onto grilling's gate.
- wayfinder → grilling spans sessions through decision tickets on the tracker; upstream changes to wayfinder's map body map onto grilling's `SPEC-FORMAT.md`, to its ticket types onto the tracker skill, to its charting or work-through process onto grilling's Across sessions.

Renamed:
- testing ← tdd (red-green is no longer the frame: upstream changes to tdd's loop map onto diagnosing-bugs' regression test, its test-quality material onto `code-review/TEST-SMELLS.md`)
- orient ← ask-matt
- domain-modelling ← domain-modeling
- tracker ← the one-file-per-ticket local tracker conventions (upstream folded these into setup-matt-pocock-skills)

Everything else in mx is homegrown; everything else upstream is unadopted; flag interesting new skills, don't auto-adopt them.
