# Skill mechanics

The skill-specific branch of [`writing-for-agents`](SKILL.md).

## Invocation

Two choices, trading the two loads:

- A **model-invoked** skill keeps a `description`, so the agent can fire it on its own and other skills can reach it; the user can still type its name, since a description adds agent discovery and never removes the human's reach. The description is the skill's top-level context pointer, always loaded: permanent context load paid for discoverability. A model-invoked skill whose content is all reference can be the one home of reference several skills need, since each can invoke it. Mechanics: omit `disable-model-invocation`, and write a model-facing description carrying the trigger branches (the pointer rules in `SKILL.md` apply in full).
- A **user-invoked** skill keeps its description out of the agent's reach: only the human typing its name invokes it, and no other skill can. It costs no context load and spends cognitive load, since you are the index that must remember it exists. Mechanics: set `disable-model-invocation: true`, and make the `description` a human-facing one-line summary with no trigger lists.

Pick model-invocation only when the agent must reach the skill on its own, or another skill must.

Reference two user-invoked skills both need can live in neither, since neither can fire the other. Put it in a plain file outside the skill system that any skill can point at.

## Splitting by invocation

The sequence cut lives in `SKILL.md`. Split off a model-invoked skill when a distinct leading word you actually use in your prompts should trigger it on its own, or another skill must reach it, and that independent reach is worth the context load of one more always-loaded description.

## Router skills

When user-invoked skills multiply past what you can remember, add a **router skill**: one user-invoked skill that names the others and when to reach for each, so the human remembers one skill instead of many. It can only hint at them, never fire them.

## Knowledge and workflow

A skill carries two kinds of text. Its **knowledge** holds in any chat with any model: what to show, how to write, how to test. A tool that ships with the skill (a script beside it, a command the plugin puts on `PATH`) is part of its knowledge, named at the step that uses it. Its **workflow** text is about this setup's machinery: tickets, the session page, the hub, dispatch, the agent repo and where files go in it.

Most workflow text already has a home: `claude/CLAUDE.md`, `session-page/RULES.md`, `/mx:tracker`, `/mx:dispatch`. A skill restates none of it, and names the home only where a sentence needs it. Workflow text particular to one skill goes in `WORKFLOW.md` beside its `SKILL.md`, as whole passages, each rule with its reason; a skill with none has no `WORKFLOW.md`. A fact general to the workflow that has no home yet gets one, once, in the file that owns it. The one pointer to these files is the line in `claude/CLAUDE.md`'s workflow block, copied in `dispatch/worker-prompt.md` for workers; no `SKILL.md` carries one.

The test, run on a finished skill:

1. Read `SKILL.md` as a reader with no tickets, no session page and no dispatch. It is a complete skill for them: no step waits on something only the workflow supplies.
2. Read `WORKFLOW.md` sentence by sentence and name the home of each fact. Delete each sentence whose fact another home states; what is left is particular to this skill.

An example that happens to be about a ticket stays in `SKILL.md`. The `description` keeps the triggers of the skill's workflow uses too. A file a script hands to a reader on its own (a review's catalogue) keeps its workflow clauses, since that reader never opens `WORKFLOW.md`.
