---
name: to-spec
description: "Turn the current conversation into a spec and publish it to the project issue tracker: no interview, just synthesis of what you've already discussed."
disable-model-invocation: true
---

This skill takes the current conversation context and codebase understanding and produces a spec. Do NOT interview the user; just synthesize what you already know.

Publish per `/mx:tracker`'s conventions (or the tracker the project's CLAUDE.md declares).

## Process

1. Explore the repo to understand the current state of the codebase, if you haven't already. Use the vocabulary from `CONTEXT.md` throughout the spec, and respect any ADRs in `decisions/` in the area you're touching.

2. Sketch out the seams at which you're going to test the feature. Existing seams should be preferred to new ones. Use the highest seam possible. If new seams are needed, propose them at the highest point you can. The fewer seams across the codebase, the better - the ideal number is one.

Check with the user that these seams match their expectations.

3. Write the spec using the template below, then publish it to `agent/tasks/<feature-slug>/spec.md`. Decisions that pass the ADR gate belong in `decisions/` via `/mx:domain-modelling`; the spec references them, it doesn't restate them.

4. **Review is conditional on provenance.** A spec distilled from a conversation the user took part in only summarizes what you already share; they don't need to read it. A spec *compiled from artifacts* (a wayfinder map, an external brief, someone else's notes) is a translation, and translations drift: walk the user through it before tickets are cut. When compiling from a map, this is also the moment the map is superseded: tombstone it per `/mx:tracker`.

<spec-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories: extremely extensive, covering every actor and every aspect of the feature. No human reads this document, so exhaustiveness costs nothing; the stories carry the definition of done, and tickets are later sliced from and checked against them. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

## Properties

What the app must *be*, where stories say what a user can *do*; the story format cannot express these, and a property with no story gets no ticket. One sentence each, in the project's ubiquitous language, phrased as an always/never that a reviewer can check a diff against. Rendering, error containment, lifecycle/session models, copy discipline live here. A living list: it starts small and grows as the build surfaces new properties, so discovering one mid-build means adding it here, not noting it in a ticket comment.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts: not a working demo, just the important bits.

List any **floors**, prototypes (or aspects of one) the user promoted to minimum-quality references, with their `agent/prototypes/` paths, so to-tickets can stamp them onto the tickets building those surfaces.

**Type every deferral.** A decision left to build time behaves differently by kind: an interchangeable part behind a settled seam (which test runner) defers safely; anything user-visible defers to agent taste; and a deferred dependency pick can silently defer the *capability* itself (no markdown library chosen → nothing renders markdown). For each deferred item, name what happens if nobody decides it.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this spec.

## Further Notes

Any further notes about the feature.

</spec-template>
