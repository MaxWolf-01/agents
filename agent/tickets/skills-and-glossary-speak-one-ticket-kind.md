---
status: proposed
parent: ticket-file-contract
blocked-by: [ticket-parser-and-commit-check]
priority: 1
size: L
---

# The skills and the glossary speak of one kind of ticket

Child ticket of `ticket-file-contract`, building on every call in its Decisions; the ones still the agent's: the Properties (r2), research trimmed rather than deleted (r3), the commit check installed per repo (r3).

## Brief

Every skill, the worker contract, the always-loaded workflow block and the glossary describe the model the parent ticket settled, in one pass by one worker, since they share one vocabulary and a split would let two workers phrase it two ways. The feature, the spec, the standalone ticket, the gate and the decision ticket leave the prose; so does every branch that chose between them.

What changes, by where it lives:

- `/mx:tracker` (SKILL.md, MARKDOWN.md): one ticket kind, flat, `parent:`, slug ids; the branch a ticket file is committed on; the field for a ticket that needs the user; no decision tickets and no types; one retire rule; research landing in the ticket; the ticket's sections, which is where the spec template's sections now live, as optional ones. `SPEC-FORMAT.md` goes.
- `/mx:grilling`: the design lands in the ticket being grilled, marks and all; no draft, no confirmed, no gate; the absorb step goes; questions left open at a session's end become child tickets that need the user.
- `/mx:to-tickets`: cuts child tickets with `parent:`; no property stamping, properties are read through the ancestry; `property-coverage`'s new meaning; one slice means the grilled ticket is itself the thing built.
- `/mx:dispatch` and `worker-prompt.md`: the standalone paragraphs go; the needs-the-user field replaces routing by type; close-out at every parent ticket, its review one level up; a worker reads its ticket plus its ancestry; light or full review by the diff's size and whether it touches a contract others depend on.
- `/mx:code-review`: the spec source is the ticket's context from the parser.
- `/mx:orient`: the artefact table and the flow's step 3 (loose, or a ticket, which gains child tickets when it slices into two or more).
- `/mx:research`: trimmed to its investigation discipline, with the findings landing per the parent ticket's research decision.
- `/mx:project-setup`: wires the commit check into a project.
- `claude/CLAUDE.md`'s workflow block and its copy in `worker-prompt.md` (the project CLAUDE.md says the two are checked against each other), and `mx/README.md`.
- `CONTEXT.md`, through `/mx:domain-modelling`: Feature, Spec, Standalone ticket, Gate, Build ticket, Decision ticket and Legwork go; Parent ticket (with child ticket) comes in with the parent ticket's wording; every entry that leaned on a removed word (Frontier, Round, Debrief, Call) is re-read against the new model.

The parser's command names come from `ticket-parser-and-commit-check`'s `--help`, which is why this ticket waits on it.

## Acceptance criteria

- [ ] A grep of `mx/`, `claude/CLAUDE.md` and `CONTEXT.md` for spec, feature, standalone and decision ticket finds only uses in another sense (a spec as in a specification of an external format, say), each read and kept on purpose.
- [ ] `ticket-file-contract#P5`, reviewed: no skill distinguishes tickets by kind beyond having child tickets and needing the user.
- [ ] The demo is the before and after of what an agent writes, per `/mx:show`'s process-change row: one intent taken through grilling and to-tickets under the old skills and the new ones, role-played where the scripts are not landed.
- [ ] The mx plugin version is not bumped here; the release follows the parent ticket's merge.

## Comments
