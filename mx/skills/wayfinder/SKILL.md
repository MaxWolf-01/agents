---
name: wayfinder
description: Plan a huge chunk of work (more than one agent session can hold) as a shared map of decision tickets on the issue tracker, resolved across sessions until the way to the destination is clear. Use when the user mentions wayfinder, charting, or the map, or when planning is spilling past what one session can hold.
---

A loose idea has arrived, too big for one agent session and wrapped in fog: the way from here to the **destination** isn't visible yet. Wayfinding is about finding that way, not charging at the destination. This skill charts the way as a **shared map** on the repo's issue tracker, then works its **decision tickets** (questions whose resolution is a decision, not slices of a build to execute) one at a time until the route is clear.

The destination varies per effort, and naming it is the first act of charting; it shapes every ticket. It might be a spec to hand off and iterate on, a decision to lock before planning starts, or a change made in place like a data-structure migration. The map is domain-agnostic: engineering work, course content, whatever fits the shape.

## Plan, don't do

Wayfinder is **planning** by default: each ticket resolves a decision, and the map is done when the way is clear: nothing left to decide before someone goes and does the thing. The pull to just do the work is usually the signal you've reached the edge of the map and it's time to hand off. An effort can override this in its **Notes**, carrying execution into the map itself, but absent that, produce decisions, not deliverables.

## Consent

Facts are the agent's job; decisions are the user's, and **silence is not agreement**. A recommendation the user never answered is unconfirmed: record it marked as such (`(agent judgment, unconfirmed)`) and re-surface it next round, rather than letting it harden into map lines, ADRs, or glossary entries. The recurring failure this guards against: agent recommends → the user's next message goes elsewhere → the recommendation gets committed as settled, and every later agent reads it as the user's decision. The same discipline binds audits: a finding about lost consent goes into the artefact directly, not through the user as a message to relay; relays drop findings.

## Refer by name

Every map and ticket is an issue, so it has a **name**: its title. In everything the human reads (narration, the map's Decisions-so-far) refer to it by that name, never by a bare id, number, or slug. A wall of `#42, #43, #44` is illegible; names read at a glance. The id and URL don't vanish (a name wraps its link) but they ride *inside* the name, never stand in for it.

## The Map

The map is a single issue on this repo's issue tracker: the canonical artifact. Its tickets are child issues of the map.

The map is an **index**, not a store. It lists the decisions made and points at the tickets that hold their detail; a decision lives in exactly one place, its ticket, so the map never restates it, only gists it and links.

It records current truth, not an audit trail. While a decision is still paper (nothing built on it yet) a later decision that overturns a closed ticket's answer **amends** it: edit the answer and its gist line in place, marking the changed claim inline (`(amended <date>, was <old>)`). An amendment isn't done until the **same session sweeps it**: grep the retired term or claim across the map, tickets, spec, `CONTEXT.md` and `decisions/`, updating or superseding every hit; a copy left standing is what future agents will read as current truth. Once something has been built on the answer, don't rewrite it; it is the reasoning behind code someone can now read. Open a new ticket that **supersedes** it, and leave a one-line forward pointer on the old one, without which the supersession is undiscoverable.

**Where the map, its child tickets, blocking, and frontier queries physically live is tracker-specific.** Consult `/mx:tracker`'s "Wayfinding operations" section (or the tracker the project's CLAUDE.md or other context declares) for how _this_ repo expresses them.

### The map body

The whole map at low resolution, loaded once per session. Open tickets are **not** listed: they are open child issues, found by query.

```markdown
## Destination

<what reaching the end of this map looks like: the spec, decision, or change this effort is finding its way to. One or two lines; every session orients to it before choosing a ticket.>

## Notes

<domain; skills every session should consult; standing preferences for this effort>

## Decisions so far

<!-- the index, one line per closed ticket: enough to judge relevance, then zoom the link for the detail the ticket holds -->

- [<closed ticket title>](link): <one-line gist of the answer>

## Not yet specified

<!-- see "Fog of war": in-scope fog you can't ticket yet; graduates as the frontier advances -->

## Out of scope

<!-- see "Out of scope": work ruled beyond the destination; closed, never graduates -->
```

### Tickets

Each ticket is a **child issue** of the map; the tracker's issue id is its identity. Its body is the question, sized to fit comfortably in one agent session:

```markdown
## Question

<the decision or investigation this ticket resolves>
```

Each ticket carries a **type**, one of `research`, `prototype`, `grilling`, `task` (see [Ticket Types](#ticket-types)), recorded per the tracker's conventions.

A session **claims** a ticket per the tracker's claim convention, **first**, before any work, so concurrent sessions skip it.

Blocking uses the tracker's **native** dependency relationship where one exists: it renders the frontier _visually_ in the tracker's own UI, so the human sees what's takeable without opening the map; the file tracker expresses it as `blocked-by` frontmatter. A ticket is **unblocked** when every ticket blocking it is closed; the **frontier** is the open, unblocked, unclaimed children: the edge of the known.

The answer isn't part of the body; it's recorded on resolution (see [Work through the map](#work-through-the-map)). Assets created while resolving a ticket are linked from the issue, not pasted in.

## Ticket Types

Every ticket is either **HITL** (human in the loop, worked *with* a human who speaks for themselves) or **AFK**, driven by the agent alone. A HITL ticket only resolves through that live exchange; the agent never stands in for the human's side of it (a grilling agent that answers its own questions has broken this).

- **Research** (AFK): Reading documentation, third-party APIs, or local resources like knowledge bases to surface a fact a decision waits on. Resolved by a background `/mx:research` agent: findings land as a research artefact (`agent/research/`), the ticket's answer gists and links it, and they reach the spec draft only through a grilling round that puts them to the user. Use when knowledge outside the current working directory is required.
- **Prototype** (HITL): Raise the fidelity of the discussion by making a cheap, rough, concrete artifact to react to: an outline, a rough take, a stub, or UI/logic code via `/mx:prototype`. Links the prototype and its `ANSWER.md` (the verdicts) as assets. Use when "how should it look" or "how should it behave" is the key question, and default to it for anything user-visible: surface judgment is render-triggered, and a surface question doesn't sharpen when other decisions land, only against a built artifact.
- **Grilling** (HITL): Conversation. The default case. Always invoke `/mx:grilling` and `/mx:domain-modelling`. When the user is blank on a question, the question is usually posed backwards ("what goes in the sidebar?" assumes a sidebar); convert the ticket to a prototype rather than extracting a conceptual answer that a render will overturn.
- **Task** (HITL or AFK): Manual work that must happen before a *decision* can be made: nothing to decide, prototype, or research, but the discussion is blocked until it's done. Signing up for a service so its API can be judged, provisioning access, moving data so its shape can be seen. This is the one type that *does* rather than decides, and it earns its place by unblocking a decision, not by delivering the destination. The agent drives it alone where it can (AFK); otherwise it hands the human a precise checklist (HITL). Resolved when the work is done; the answer records what was done and any resulting facts (credentials location, new URLs, row counts) later tickets depend on.

## Fog of war

The map is _deliberately_ incomplete: don't chart what you can't yet see. Beyond the live tickets lies the **fog of war**: the dim view of decisions and investigations you can tell are coming but can't yet pin down, because they hang on questions still open. Resolving a ticket clears the fog ahead of it, graduating whatever's now specifiable into fresh tickets, one at a time, until the way to the destination is clear and no tickets remain.

The map's **Not yet specified** section is where that dim view is written down: the suspected question, the area to revisit later. It's the undiscovered frontier _toward_ the destination: everything here is in scope, just not sharp enough to ticket. Write as loosely or as fully as the view allows; it doubles as a signpost for collaborators reading where the effort is headed.

**Fog or ticket?** The test is whether you can state the question precisely now, _not_ whether you can answer it now.

- **Ticket when** the question is already sharp, even if it's blocked and you can't act on it yet.
- **Not yet specified when** you can't yet phrase it that sharply. Don't pre-slice the fog into ticket-sized pieces: it's coarser than a ticket, and one patch may graduate into several tickets, or none, once the frontier reaches it.

**Not yet specified** excludes what's already decided (Decisions so far), what's already a live ticket, and what's out of scope (the next section).

## Out of scope

Fog only ever gathers _toward_ the destination. The destination fixes the scope, so work beyond it is **out of scope**: it isn't fog, and it doesn't belong in **Not yet specified**. It gets its own **Out of scope** section on the map: work you've consciously ruled out of _this_ effort. Scope, not sharpness, lands it here.

Out-of-scope work never graduates (the frontier stops at the destination), so it returns only if the destination is redrawn, and then as a fresh effort, not a resumption.

Ruling something out of scope is a scoping act, not a step on the route. When a ticket that already exists turns out to sit past the destination (mis-scoped in while charting, or exposed by a resolution), **close it** (a closed ticket is unambiguously off the frontier) and leave one line in the **Out of scope** section: the gist plus why it's out of scope, linking the closed ticket. It stays out of **Decisions so far**, which records the route actually walked; a scope boundary isn't a step on it.

## Invocation

Two modes. Either way: resolve one ticket at a time, **recording each resolution before touching the next**. Adjacent decisions that genuinely share context may fall in the same session while it stays sharp (the real limit is how much ground the context can cover without hitting the dumb zone: <400k tokens, preferably <300k), but the map, not the conversation, is the memory: a resolution not yet recorded on the map doesn't exist. Research tickets run in the background and don't count.

### Chart the map

User invokes with a loose idea.

1. **Name the destination.** Run a `/mx:grilling` and `/mx:domain-modelling` session to pin down what this map is finding its way to: the spec, decision, or change. The destination fixes the scope, so it's settled first.
2. **Map the frontier.** Grill again, **breadth-first** this time: fan out across the whole space rather than deep on any one thread, surfacing the open decisions and the first steps takeable now. **If this surfaces no fog** (the way to the destination is already clear, the whole journey small enough for one session) you don't need a map. Say so and continue as a plain `/mx:grill-with-docs` session.
3. **Create the map**: Destination and Notes filled in, Decisions-so-far empty, the fog sketched into **Not yet specified**. Beside it, when the destination is a spec or a change, the spec draft (`spec.md`, `status: draft`, shaped per `/mx:grilling`) holding what naming the destination settled; a destination that is a decision has the ADR as its artefact instead.
4. **Create the tickets you can specify now** as child issues of the map, then wire blocking edges in a **second pass** (issues need ids before they can reference each other). Wiring sorts them into the frontier and the blocked; everything you can't yet specify stays in the fog, the **Not yet specified** section.
5. **Fire the research agents.** For each `research` ticket you just created, spin up a background `/mx:research` agent to resolve it in parallel; each writes its artefact to `agent/research/`, and the ticket's answer gists and links it.
6. Stop: charting is one session's work; it hand-resolves nothing.

### Work through the map

User invokes with a map (URL or number). A ticket is **optional**: without one, you pick the next decision, not the user.

1. Load the **map**: the low-res view, not every ticket body.
2. Choose the ticket. If the user named one, use it. Otherwise take the first frontier ticket in order. **Claim it**: assign it to yourself before any work.
3. Resolve it: read the ticket's own Comments first (the answer, or the user's prior instinct about it, may already be sitting there), then **zoom as needed**: fetch the full body of any related or closed ticket on demand; invoke the skills the `## Notes` block names. If in doubt, use `/mx:grilling` and `/mx:domain-modelling`.
4. Record the resolution: post the answer as a **resolution comment**, **close** the issue, **append a context pointer** to the map's Decisions-so-far, and rewrite the spec draft sections the decision touches, each call marked with the ticket's name. An AFK resolution updates its ticket only; its findings reach the draft through the next grilling round that uses them, so nothing lands in the spec unproposed.
5. Add newly-surfaced tickets (create-then-wire): a thread you can't pull in this session becomes a ticket, never a lost thread. Graduate any fog the answer has made specifiable, clearing each graduated patch from **Not yet specified** so it lives only as its new ticket. If the answer reveals a ticket, this one or another, sits beyond the destination, **rule it out of scope** rather than resolving it on the route. If the decision invalidates other parts of the map, update or delete those tickets.

The user may run unblocked tickets in parallel, so expect other sessions to be editing the tracker concurrently.

### Reaching the destination

When no open tickets remain and no fog is specifiable, the way is clear: the map is done, and the spec draft already holds the destination, linking the decision tickets as context pointers so implementation agents can walk back down to the reasoning. The final session reads the whole draft once for drift between sessions, then runs `/mx:grilling`'s gate: the unconfirmed list walked, markers stripped, `status: confirmed`. The confirmed spec **supersedes** the map: tombstone it per `/mx:tracker`, so no later agent reads its index as current truth, and continue at `/mx:to-tickets`. Retire the whole effort per `/mx:tracker` when it ships.
