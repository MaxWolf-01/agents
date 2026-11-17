# Writing the design into the ticket

How a round fills the design sections `/mx:tracker`'s The ticket file lists, from User stories through Fog; that section owns their order and item formats. A decision that meets `/mx:domain-modelling`'s bar is an ADR, which the ticket references rather than restates.

**User stories.** Extensive while the ticket is being grilled, covering every actor and every aspect of the work: the user reads them as they grow, which is where misunderstandings surface, and the child tickets are cut from them and checked against them.

**Properties.** What the work must *be*, where a story says what a user can *do*; a property with no story still earns its line. Phrase each as an always or a never a reviewer can check a diff against: rendering, error containment, lifecycle and session models, copy discipline. Ids are assigned in order, and a retired property's number is never reused.

**Decisions.** What the calls can cover:

- The modules that will be built or modified
- The interfaces of those modules
- Technical clarifications from the user
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Where one of those has a figure in `/mx:show`'s table, the call links that figure and states what it cannot show: the why, and the rejected alternative.

Leave out file paths and code snippets, which go stale fast; a link to a figure or a prototype is neither. The exception is a prototype's snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape): inline it in the decision it settles, trimmed to the decision-rich part and marked as the prototype's.

List any **floors**, prototypes (or aspects of one) the user promoted to minimum-quality references, with their paths, so the cut can stamp them onto the child tickets building those surfaces (`/mx:tracker`, SLICING.md).

**Type every deferral.** A decision left to build time behaves differently by kind: an interchangeable part behind a settled seam (which test runner) defers safely; anything user-visible defers to agent taste; and a deferred dependency pick can silently defer the *capability* itself (no markdown library chosen → nothing renders markdown). For each deferred item, name what happens if nobody decides it.

**Testing seams.** Where the work's tests enter, chosen by `/mx:testing`'s rule (The seam), existing seams over new ones. Per seam, name its **oracle** (`GLOSSARY.md`) in one phrase, and the existing tests there as the pattern the new ones follow. A seam whose only available answer is what the code returns today says so, and the reviewer reads its tests knowing it.

**Out of scope.** The decisions against, and a rival design that lost with what it would have cost.

**Fog.** `/mx:grilling`, Fog and scope.
