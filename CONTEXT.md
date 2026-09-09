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
The provenance tag on a call in a draft spec: who settled it, or that nobody has yet.
_Avoid_: marker, annotation, tag, label

**Frontier**:
What can be worked now: in a grilling, the decisions nothing open still gates; on the tracker, the open tickets nothing gates and nobody holds.
_Avoid_: backlog, todo, next steps

**Fog**:
In-scope work whose question cannot yet be stated.
_Avoid_: Further Notes, Not yet specified, unknowns, TBD

**Gate**:
The point where a spec is confirmed and reads cold from then on.
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

**Proposed**:
The status of a ticket an agent filed that the user has not yet ruled worth doing.
_Avoid_: backlog, suggested, draft ticket, idea

**Ruling**:
The user's verdict on a proposed ticket: open it, delete it, or send it to grilling.
_Avoid_: approval, triage, verdict (a grilling's verdicts settle calls, not tickets)

**Synthesis**:
The orchestrator's one reading of a feature besides its diff: what it fixed, what it proposes, what it left.
_Avoid_: report, summary, PR description

**Board**:
The rendered view of the whole tracker: every feature, its dependency graph, the frontier, the review pages.
_Avoid_: dashboard

**Retire**:
Take a shipped feature's or ticket's record out of the live tracker; history keeps it.
_Avoid_: archive, clean up

**Tombstone**:
The one-line header that marks a file as historical and names its successor.
_Avoid_: deprecation notice, banner

### Dispatch

**Orchestrator**:
The one agent that works a feature's tickets through workers: the sole claim-writer and the only judge of done.
_Avoid_: dispatcher, coordinator, parent

**Worker**:
The agent that works one ticket in its own worktree, unattended.
_Avoid_: subagent, implementer

**Tick**:
One pass of the orchestrator's loop.
_Avoid_: iteration, cycle

**Wave**:
The tickets one tick hands to workers together.
_Avoid_: batch, round

**Land**:
A ticket's work is on the feature branch and verified there.
_Avoid_: merged, finished, complete

### Testing

**Oracle**:
What a test compares the code's behaviour against, chosen so that it is not the code itself: a property from the spec, a worked example, a reference implementation, a round trip, a model.
_Avoid_: expected value, ground truth, reference (an oracle may be one)

### Sessions

**Brief**:
The prompt a subagent is started with.
_Avoid_: brief for anything filed on the tracker

**Smart zone**:
The stretch of a context window within which reasoning stays sharp; the limit is a fraction of the window, not a feeling.
_Avoid_: context budget, token budget
