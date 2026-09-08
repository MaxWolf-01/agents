# mx workflow

The words the mx plugin uses for a piece of work on its way from idea to shipped code, across agent sessions. The skills own the process; this file owns the vocabulary they share.

## Language

### Planning

**Feature**:
The unit the tracker holds one spec for: one directory, its spec, its tickets, whatever the size. Not the product sense; a big design splits into sibling features, never nested ones.
_Avoid_: effort, map, project, epic

**Spec**:
The work order for one feature: as much design as one gate can confirm.
_Avoid_: map, plan, PRD, design doc

**Round**:
One turn of grilling: the design as it stands with the frontier's questions, then the user's answers.
_Avoid_: iteration, pass

**Call**:
One design decision as the spec states it, carrying a mark that says who settled it.
_Avoid_: choice, assumption (an assumption is an implementer's unescalated call, recorded as such in a ticket)

**Mark**:
The provenance tag on a call in a draft spec: settled by the user in a round or by a ticket, the agent's and vetoable, open, or fog.
_Avoid_: marker, annotation, tag, label

**Frontier**:
What can be worked now. In a grilling, the decisions whose prerequisites are settled; on the tracker, the open, unblocked, unclaimed tickets.
_Avoid_: backlog, todo, next steps

**Fog**:
In-scope work whose question cannot yet be stated.
_Avoid_: Further Notes, Not yet specified, unknowns, TBD

**Gate**:
The point where a spec is confirmed: frontier empty, unconfirmed calls walked with the user, marks stripped.
_Avoid_: sign-off, approval, freeze

### Tracker

**Ticket**:
The unit of work on the tracker: one file, or one issue.
_Avoid_: task, item, story

**Build ticket**:
A ticket whose deliverable is a landed change: one vertical slice.
_Avoid_: implementation ticket, work item

**Decision ticket**:
A ticket whose deliverable is an answer, typed research, prototype, grilling or legwork.
_Avoid_: question, open item, brief

**Standalone ticket**:
A ticket with no spec: work that needs no design round, or a decision filed for later.
_Avoid_: small task, loose ticket, note

**Legwork**:
The decision-ticket type for manual work that unblocks a decision without deciding anything itself.
_Avoid_: task, chore, prep

**Board**:
The rendered view of the whole tracker: every feature, its dependency graph, the frontier, the review pages.
_Avoid_: dashboard (the name of the script that renders it, nothing more)

**Retire**:
Take a shipped feature's or ticket's record out of the live tracker; history keeps it.
_Avoid_: archive, clean up

**Tombstone**:
The one-line header that marks a file as historical and names its successor.
_Avoid_: deprecation notice, banner

### Sessions

**Brief**:
The prompt a subagent is started with.
_Avoid_: brief for anything filed on the tracker

**Smart zone**:
The stretch of a context window within which reasoning stays sharp; the limit is a fraction of the window, not a feeling.
_Avoid_: context budget, token budget
