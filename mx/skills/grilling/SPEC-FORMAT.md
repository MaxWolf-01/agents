# Spec format

The spec is the work order for one feature: what `/mx:to-tickets` slices and `/mx:implement` reads. Published per `/mx:tracker` (`agent/tasks/<slug>/spec.md` on the markdown backend), written round by round during grilling, in the vocabulary of `CONTEXT.md`; decisions that pass the ADR gate live in `decisions/` and the spec references them without restating them.

Frontmatter `status: draft | confirmed`. A draft carries the provenance markers the grilling skill defines; the gate strips them and sets `confirmed`, and from then on the document reads cold.

<spec-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective. Rival designs still in play sit here side by side until one is chosen; the loser moves to Out of Scope with its reason.

## User Stories

A LONG, numbered list of user stories: extremely extensive, covering every actor and every aspect of the feature. The user reads them as they grow during grilling, which is where misunderstandings surface; tickets are later sliced from and checked against them. Each user story should be in the format of:

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

The **seams** at which the feature is tested: a design call put to the user in a round like any other. Existing seams over new ones, the highest seam possible; new seams proposed at the highest point they can sit. The fewer seams across the codebase, the better; the ideal number is one. Also:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

The things that are out of scope for this spec, each with its reason: the decisions against.

## Further Notes

Anything still too foggy to state as a slice lives here; to-tickets tickets it when the frontier reaches it.

</spec-template>
