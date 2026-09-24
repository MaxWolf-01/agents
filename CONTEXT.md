# mx workflow

The words the mx plugin uses for a piece of work on its way from idea to shipped code, across agent sessions. The skills own the process; this file owns the vocabulary they share.

## Language

### Planning

**Round**:
One turn of grilling: the design as it stands with the frontier's questions, then the user's answers.
_Avoid_: iteration, pass

**Call**:
One design decision as the ticket states it, carrying a call mark that says who settled it.
_Avoid_: choice, assumption (an assumption is an implementer's unescalated call, recorded as such in a ticket)

**Call mark**:
The provenance tag on a call: who settled it, or that nobody has yet.
_Avoid_: spec mark, mark (bare; a row mark is one too), marker, annotation, tag, label

**Frontier**:
What can be worked now: in a grilling, the decisions nothing open still gates; on the tracker, the open or proposed tickets nothing gates and nobody holds.
_Avoid_: backlog, todo, next steps

**Fog**:
In-scope work whose question cannot yet be stated.
_Avoid_: Further Notes, Not yet specified, unknowns, TBD

### Tracker

**Ticket**:
The unit of work on the tracker: one file, or one issue.
_Avoid_: task, item, story

**Parent ticket**:
The ticket another ticket is part of. It holds the design its children are slices of, and is done once every one of them is.
_Avoid_: parent (bare; a graph has parents too), epic, feature, spec

**Child ticket**:
A ticket that is part of another: one slice of it, built, reviewed and ruled on its own.
_Avoid_: subtask, sub-ticket, step

**Ticket context**:
A ticket's own body with every ancestor's: the whole of what a worker or a reviewer is given.
_Avoid_: brief (a ticket's brief is one section of it), spec, background

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
A decision only the user can make, asked as part of the ticket it concerns.
_Avoid_: ask, call (a call is a design decision), needs-human entry, queue item

**Needs-me group**:
The board's one group for every ticket whose next step is the user's own time.
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
The rendered view of the whole tracker: every ticket, the dependency graphs, the frontier, the review pages.
_Avoid_: dashboard

**Row mark**:
One tag on a board row, carrying a single fact about the ticket for scanning.
_Avoid_: mark (bare; a call mark is one too), badge, pill, label

**Retire**:
Take a shipped ticket's record out of the live tracker; history keeps it.
_Avoid_: archive, clean up

**Tombstone**:
The one-line header that marks a file as historical and names its successor.
_Avoid_: deprecation notice, banner

### Dispatch

**Orchestrator**:
The one agent that works a ticket's child tickets through workers: the sole claim-writer, and the one that marks a ticket done on the user's accept.
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
A ticket's work is on the branch it merges into, and verified there.
_Avoid_: merged, finished, complete

**Debrief**:
What the orchestrator tells the user when a ticket's tree is finished: what the workers and the harden report found, and what it proposes to do about it.
_Avoid_: synthesis, report, summary, PR description

### Testing

**Oracle**:
What a test compares the code's behaviour against, chosen so that it is not the code itself: a property the ticket states, a worked example, a reference implementation, a round trip, a model.
_Avoid_: expected value, ground truth, reference (an oracle may be one)

**Expected failure**:
The strict annotation a property carries while the behaviour it tests does not exist yet: it names the ticket that lifts it, and at a stub tolerates only the not-implemented exception.
_Avoid_: mark (a call mark or a row mark), xfail, skip

### Sessions

**Smart zone**:
The stretch of a context window within which reasoning stays sharp; the limit is a fraction of the window, not a feeling.
_Avoid_: context budget, token budget

**Session page**:
The one page a session's answers live on, the questions waiting on the user at its top; the chat reply is only its index.
_Avoid_: session artifact, transcript, notebook, log
