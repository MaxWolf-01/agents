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
One design decision as the spec states it, carrying a spec mark that says who settled it.
_Avoid_: choice, assumption (an assumption is an implementer's unescalated call, recorded as such in a ticket)

**Spec mark**:
The provenance tag on a call in a draft spec: who settled it, or that nobody has yet.
_Avoid_: marker, annotation, tag, label

**Frontier**:
What can be worked now: in a grilling, the decisions nothing open still gates; on the tracker, the open or proposed tickets nothing gates and nobody holds.
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
The status of a ticket an agent filed that the user has not yet ruled on: built like an open one while the ruling waits.
_Avoid_: backlog, suggested, draft ticket, idea

**Review**:
The status of a ticket whose work is finished and waits for the user's ruling.
_Avoid_: needs ruling, pending, awaiting approval, done

**Ruling**:
The user's answer on what a ticket built, made on its review page and demo: accept, amend, redo or reject.
_Avoid_: approval, triage, verdict (a verdict settles a call in grilling)

**Ticket question**:
A decision only the user can make, held on the ticket it belongs to and open until the answer is recorded under it.
_Avoid_: ask, call (a call is a spec's decision), needs-human entry, queue item

**Needs-me group**:
The board's group for every ticket waiting on the user: a build to rule on, a ticket stopped on a ticket question, a near design session.
_Avoid_: needs my review, needs human, inbox

**Ticket brief**:
The few sentences under a ticket's name that tell the user, reading cold, what the ticket is and why it matters.
_Avoid_: summary, description, tldr

**Board briefing**:
The board's own account of where the tracker stands and what to take up next, written by a model.
_Avoid_: brief (a ticket's), digest, status report

**Ticket priority**:
The agent's reading of how soon a ticket matters to the user, from now to someday.
_Avoid_: urgency, rank, importance

**Ticket size**:
How much of the user's time a ticket will take, never the agent's.
_Avoid_: effort, estimate, points

**Board**:
The rendered view of the whole tracker: every feature, its dependency graph, the frontier, the review pages.
_Avoid_: dashboard

**Row mark**:
One tag on a board row, carrying a single fact for scanning: what the ticket asks of the user, its priority, its time, a blocker. Says on hover what it means.
_Avoid_: mark (a spec mark's provenance), badge, chip, pill, label

**Retire**:
Take a shipped feature's or ticket's record out of the live tracker; history keeps it.
_Avoid_: archive, clean up

**Tombstone**:
The one-line header that marks a file as historical and names its successor.
_Avoid_: deprecation notice, banner

### Dispatch

**Orchestrator**:
The one agent that works a feature's tickets through workers: the sole claim-writer, and the one that marks a ticket done on the user's accept.
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

**Debrief**:
What the orchestrator tells the user when a feature is finished: what the workers and the harden report found, and what it proposes to do about it.
_Avoid_: synthesis, report, summary, PR description

### Testing

**Oracle**:
What a test compares the code's behaviour against, chosen so that it is not the code itself: a property from the spec, a worked example, a reference implementation, a round trip, a model.
_Avoid_: expected value, ground truth, reference (an oracle may be one)

**Expected failure**:
The strict annotation a property carries while the behaviour it tests does not exist yet: it names the ticket that lifts it, and at a stub tolerates only the not-implemented exception.
_Avoid_: mark (a spec mark or a row mark), xfail, skip

### Sessions

**Smart zone**:
The stretch of a context window within which reasoning stays sharp; the limit is a fraction of the window, not a feeling.
_Avoid_: context budget, token budget

**Session page**:
The one page a session's answers live on, the questions waiting on the user at its top; the chat reply is only its index.
_Avoid_: session artifact, transcript, notebook, log
