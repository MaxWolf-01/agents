# Writing the design into the ticket

How a round fills the design sections `/mx:tracker`'s The ticket file lists, from User stories through Fog. That section owns their order and their item formats; this one is what makes each worth reading. A decision that meets `/mx:domain-modelling`'s bar lives in `decisions/`, with the ticket referencing it rather than restating it.

**User stories.** Long and extensive while the ticket is being grilled, covering every actor and every aspect of the work. The user reads them as they grow, which is where misunderstandings surface, and the child tickets are cut from them and checked against them.

**Properties.** What the work must *be*, where a story says what a user can *do*; the story format cannot express these, and a property with no story still earns its line. Phrase each as an always or a never a reviewer can check a diff against: rendering, error containment, lifecycle and session models, copy discipline. A living list that starts small and grows as the build surfaces new ones, so discovering one mid-build means adding it here rather than noting it in a comment. Ids are assigned in order, and a retired property leaves its number behind rather than passing it on.

**Decisions.** What the calls can cover:

- The modules that will be built or modified
- The interfaces of those modules
- Technical clarifications from the user
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Several of those name a shape `/mx:show`'s table gives a figure. The call links that figure and states what the figure cannot: the why, and the rejected alternative.

Leave out file paths and code snippets, which go stale fast; a link to a figure or a prototype is neither. The exception is a snippet a prototype produced that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape): inline it in the decision it settles, trimmed to the decision-rich part and marked as the prototype's.

List any **floors**, prototypes (or aspects of one) the user promoted to minimum-quality references, with their `agent/prototypes/` paths, so the cut can stamp them onto the child tickets building those surfaces (`/mx:tracker`, SLICING.md).

**Type every deferral.** A decision left to build time behaves differently by kind: an interchangeable part behind a settled seam (which test runner) defers safely; anything user-visible defers to agent taste; and a deferred dependency pick can silently defer the *capability* itself (no markdown library chosen → nothing renders markdown). For each deferred item, name what happens if nobody decides it.

**Testing seams.** A design call put to the user in a round like any other. Existing seams over new ones, the highest seam possible; new seams proposed at the highest point they can sit. The fewer seams across the codebase, the better; the ideal number is one. Per seam, name its **oracle** (`CONTEXT.md`) in one phrase, and the existing tests there as the pattern the new ones follow. A seam whose only available answer is what the code returns today says so, and the reviewer reads its tests knowing it.

A property disposed **executable** is a check over generated inputs at a named seam, built by one early child ticket ahead of the slices; one disposed **reviewed** is prose the reviewer checks each diff against.

**Out of scope.** The decisions against, and a rival design that lost with what it would have cost.

**Fog.** `/mx:grilling`, Fog and scope.
