# Skill mechanics

The skill-specific branch of [`writing-for-agents`](SKILL.md): what changes when the document is a skill: frontmatter, the invocation choice, and router skills. Everything else about writing it is the universal reference in `SKILL.md`.

## Invocation

Two choices, trading the two loads:

- A **model-invoked** skill keeps a `description`, so the agent can fire it autonomously, and other skills can reach it. You can still type its name: model-invocation always _includes_ user reach; a description only ever adds agent discovery, never removes the human's. The description is the skill's top-level context pointer, forced to stay loaded at all times: permanent context load in exchange for discoverability. A model-invoked skill whose content is all reference is also one home for shared reference: another skill can invoke it, so reference needed by several skills lives in one place. Mechanics: omit `disable-model-invocation`, and write a model-facing description carrying the trigger branches (the pointer-writing rules in `SKILL.md` apply in full).
- A **user-invoked** skill strips the description from the agent's reach: only the human typing its name can invoke it, and no other skill can. Zero context load, but it spends cognitive load: you are the index that must remember it exists. Mechanics: set `disable-model-invocation: true`; the `description` becomes human-facing: a one-line summary, trigger lists stripped.

Pick model-invocation only when the agent must reach the skill on its own, or another skill must. If it only ever fires by hand, make it user-invoked and pay no context load.

Shared reference that two user-invoked skills both need can live in neither: with no descriptions, neither can fire the other. Push it to a plain file outside the skill system: external reference any skill can point at.

## Splitting by invocation

The invocation cut of splitting (the sequence cut lives in `SKILL.md`): split off a model-invoked skill when you have a distinct leading word that should trigger it on its own (a trigger word you actually use in your prompts) or another skill must reach it. You pay context load for the new always-loaded description, so that independent reach has to be worth it.

## Router skills

When user-invoked skills multiply past what you can remember, that piled-up cognitive load is cured by a **router skill**: one user-invoked skill that names the others and when to reach for each, so the human has one skill to remember instead of many. It can only hint, never fire them: user-invoked skills have no description, so nothing but the human can reach them.

## Knowledge and workflow

A skill carries two kinds of text. Its **knowledge** holds in any chat with any model: what to show, how to write, how to test. Its **workflow** text is about this setup's machinery: tickets, the session page, the hub, dispatch, forks, the agent repo and where files go in it. `SKILL.md` holds the knowledge. The workflow text goes in one file beside it, `WORKFLOW.md`, reached from `SKILL.md` by a single line that says when to read it, placed before the first section that text applies to. A skill with no workflow text has no `WORKFLOW.md`; a skill that is workflow by nature (`dispatch`, `tracker`) keeps it all in `SKILL.md`.

The test, run on a finished split:

1. Delete `WORKFLOW.md` and read `SKILL.md` as a reader with no tickets, no session page and no dispatch. It is a complete skill for them: no step waits on something only the workflow supplies, and no sentence leans on a section that left.
2. Read `WORKFLOW.md` against the old skill: every rule the workflow carried is still read at the moment it applies, because the pointer line fires in every workflow session that reaches the rule.

The unit is the sentence. A clause naming the workflow moves only where the sentence stands without it; an example that happens to be about a ticket stays. Text is moved, never copied. The `description` keeps the triggers of both halves. A file reached only from `WORKFLOW.md` is workflow too. A file a script hands to a reader on its own (a review's catalogue) keeps its workflow clauses, since that reader never opens `WORKFLOW.md`.
