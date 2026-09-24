# Writing the design into the ticket

The sections a design fills, and what makes each one worth reading. Their order and the rest of the ticket's shape are `/mx:tracker`'s; this is how a grilling session writes them, in the vocabulary of `CONTEXT.md`. A section with nothing to say is left out, and a decision that passes the ADR gate lives in `decisions/` with the ticket referencing it rather than restating it.

**User stories.** A LONG, numbered list, extremely extensive, covering every actor and every aspect of the work: `As an <actor>, I want <a capability>, so that <a benefit>`. The user reads them as they grow during grilling, which is where misunderstandings surface, and the child tickets are cut from them and checked against them.

**Properties.** What the work must *be*, where a story says what a user can *do*; the story format cannot express these, and a property with no story still earns its line. One sentence each, phrased as an always or a never that a reviewer can check a diff against: rendering, error containment, lifecycle and session models, copy discipline. A living list that starts small and grows as the build surfaces new ones, so discovering one mid-build means adding it here rather than noting it in a comment.

Each opens with its **id**, `- P1 <the property>`, assigned in order and permanent: descendants cite it as `<slug>#P<n>`, so a retired property leaves its number behind rather than passing it on, and one added in a later round takes the next.

**Decisions.** The calls, each carrying the call mark that says who settled it. This can include:

- The modules that will be built or modified
- The interfaces of those modules
- Technical clarifications from the user
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Several of those name a shape `/mx:show`'s table gives a figure. The call links that figure and states what the figure cannot: the why, and the rejected alternative.

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly. A link to a figure or a prototype is not one of these.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts: not a working demo, just the important bits.

List any **floors**, prototypes (or aspects of one) the user promoted to minimum-quality references, with their `agent/prototypes/` paths, so the cut can stamp them onto the child tickets building those surfaces (`/mx:tracker`, SLICING.md).

**Type every deferral.** A decision left to build time behaves differently by kind: an interchangeable part behind a settled seam (which test runner) defers safely; anything user-visible defers to agent taste; and a deferred dependency pick can silently defer the *capability* itself (no markdown library chosen → nothing renders markdown). For each deferred item, name what happens if nobody decides it.

**Testing seams.** The seams the work is tested at: a design call put to the user in a round like any other. Existing seams over new ones, the highest seam possible; new seams proposed at the highest point they can sit. The fewer seams across the codebase, the better; the ideal number is one. Per seam:

- The **oracle**: the independent truth its tests compare against, in one phrase (a sentence of this ticket, a worked example, a reference implementation, an invariant of the domain, a captured production payload). A seam whose only available answer is what the code returns today says so, and the reviewer reads its tests knowing it.
- Prior art: the existing tests at that seam, named, as the pattern the new ones follow.

Then **dispose of every property**, one line each by its id:

- **executable**: a check over generated inputs at a named seam, built by one early child ticket ahead of the slices.
- **reviewed**: prose the reviewer checks each diff against.

**Out of scope.** What the work will not do, each with its reason: the decisions against, and a rival design that lost with what it would have cost.

**Fog.** In-scope work whose question cannot yet be stated (`/mx:grilling`, Fog and scope).
