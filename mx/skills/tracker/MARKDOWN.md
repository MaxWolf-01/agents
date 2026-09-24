# The ticket file

All of a ticket's metadata is frontmatter, and its fields are `tracker new --help`'s. Three of them are judgments rather than bookkeeping:

- **priority**: the agent's reading of how soon the ticket matters to the user, set from what they have said and changed when they say so. Ranking tickets is never their chore.
- **size**: the user's own time on the ticket, never the agent's: reading it, trying the demo, deciding, learning. XS is under 15 minutes, S about 20, M about an hour, L half a day, XL several sessions.
- **needs-user**: the user is in the loop for this one (a grilling, work only they can do). Dispatch keeps it from a worker and their ruling is what lands it.

**The H1 is the ticket's short name**, the few words a board row shows; the sentence a title would carry goes in the brief instead.

## The body

The body is prose the agent writes, in the vocabulary of `CONTEXT.md`. `## Brief`, `## Acceptance criteria` and `## Comments` are always there; every other section appears when it has content, in this order. A ticket cut into child tickets carries what holds for all of them, and each child reads it through its ancestry rather than repeating it.

**`## Brief`** sits right under the H1: the intent and why it matters, as a technical stakeholder writes it, two or three sentences read cold. A proposal's says what it was cut from.

**`## User stories`**, numbered, `As an <actor>, I want <a capability>, so that <a benefit>`. Long and extensive on a ticket still being grilled, since that is where misunderstandings surface, and what its child tickets are sliced from and checked against.

**`## Properties`**, `- P<n> <the property>`: what the work must *be*, where a story says what a user can *do*. One always/never sentence each that a reviewer can check a diff against; rendering, error containment, lifecycle models and copy discipline live here. A living list that grows as the build surfaces new ones. The id is permanent, so a retired property leaves its number behind rather than passing it on, and every descendant cites it `<slug>#P<n>`.

**`## Decisions`**: the calls, each carrying the mark that says who settled it (`/mx:grilling`). The modules and interfaces to be built, technical clarifications, architectural decisions, schema changes, API contracts, specific interactions. Where `/mx:show`'s table gives a shape a figure, the call links that figure and states what the figure cannot: the why, and the rejected alternative. Leave out file paths and code snippets, which go stale fast; a link to a figure or a prototype is neither, and a prototype snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape) is inlined, trimmed to the decision-rich part and marked as the prototype's. List any **floors** with their `agent/prototypes/` paths: prototypes, or aspects of one, the user promoted to minimum-quality references. **Type every deferral**: an interchangeable part behind a settled seam defers safely, anything user-visible defers to agent taste, and a deferred dependency pick can silently defer the capability itself, so name what happens if nobody decides it.

**`## Testing seams`**: the seams the work is tested at, a design call put to the user like any other. Existing seams over new ones, the highest that still reaches the behaviour, and the fewer across the codebase the better. Per seam, the **oracle** in one phrase (a sentence of this ticket, a worked example, a reference implementation, an invariant of the domain, a captured payload), and the existing tests there, named, as the pattern the new ones follow. A seam whose only available answer is what the code returns today says so. Then **dispose of every property**, one line each by its id: **executable**, a check over generated inputs at a named seam, or **reviewed**, prose the reviewer checks each diff against.

**`## Out of scope`**: what this ticket will not do, each with its reason. The decisions against.

**`## Fog`**: in-scope work whose question cannot yet be stated (`/mx:grilling`, Fog and scope).

**`## Acceptance criteria`**: `- [ ]` items, what the work has to hold to be done.

**`## Questions`** holds the calls only the user can make, on the ticket they belong to. One `- [Dn] **headline** detail` item each, the tag continued from the highest the file already carries so it names one thing for good:

```markdown
## Questions

- [D1] **Retry the upload, or fake the clock?** A retry hides a real slowdown; a fake clock makes the test say nothing about timing.
- [D2] **Keep the test in the fast suite?** It takes four seconds either way.
  - Ruled 2026-09-21: keep it in the fast suite.
```

A question is open, and shows in the board's needs-me group, until a `Ruled <date>:` line sits under it, written by `tracker rule` in the tracker's own copy whatever branch the question was asked on. Every question belongs to a ticket: one with no ticket to hang on is filed as a proposed ticket, and the ruling on that proposal is the answer. A question the ruling on a build leaves open is filed as a proposed ticket then, so a done ticket carries none.

**`## Comments`** at the bottom takes notes and follow-up conversation, a worker's closing comment included.
