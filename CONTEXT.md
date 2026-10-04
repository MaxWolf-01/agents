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

**Intent-side call**:
A call on what a thing is for and its shape, which is the user's to make; a call on how it is built is an implementation call, the agent's.
_Avoid_: product decision, design call (bare; every call is a design decision)

**Call mark**:
The provenance tag on a call: who settled it, or that nobody has yet.
_Avoid_: spec mark, mark (bare; a row mark is one too), marker, annotation, tag, label

**Frontier**:
What can be worked now: in a grilling, the decisions nothing open still gates; on the tracker, the open or proposed tickets nothing gates, nobody holds, and the user is not in the loop for.
_Avoid_: backlog, todo, next steps

**Fog**:
In-scope work, or a whole intent, whose question cannot yet be stated.
_Avoid_: Further Notes, Not yet specified, unknowns, TBD

### Tracker

**Agent repo**:
The repo of everything that plans a project, held inside the repo it plans and ignored by it: its tickets, show directories, prototypes and research.
_In code_: `agent/`
_Avoid_: tracker repo (the tracker is one directory in it), meta repo, planning repo

**Ticket**:
The unit of work on the tracker: one file, or one issue.
_Avoid_: task, item, story

**Parent ticket**:
The ticket another ticket is part of. It holds the design its children are slices of, and is ruled whole, with them.
_Avoid_: parent (bare; a graph has parents too), epic, feature, spec

**Child ticket**:
A ticket that is part of another: one slice of it, built and reviewed on its own, and ruled with its parent ticket unless it is a hinge.
_Avoid_: subtask, sub-ticket, step

**Hinge**:
A child ticket its dependents would have to be rewritten, not amended, were it wrong, so it is ruled alone.
_In code_: `hinge: true`
_Avoid_: checkpoint (a context checkpoint is a session's), gate (orient's gate routes an intent), milestone

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
The user's answer on what a ticket built: accept, amend, redo or reject.
_Avoid_: approval, triage, verdict (a verdict settles a call in grilling)

**Standing yes**:
The user's accept, given in advance, of every build that carries no call worth their time that they have not already made.
_Avoid_: auto-accept, auto-merge, silent approval

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
Take a finished tree out of the live tracker: a top-level ticket and every ticket under it done, and no ticket that stays citing their properties; history keeps it.
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

**Worker report**:
What a worker hands back for its ticket: its closing comment and the questions its build raised.
_Avoid_: closing comment (one part of a report), handoff, debrief (the orchestrator's)

**Tick**:
One pass of the orchestrator's loop.
_Avoid_: iteration, cycle

**Wave**:
The tickets one tick hands to workers together.
_Avoid_: batch, round

**Land**:
A ticket's work is on the branch the user's accept merges it into, and verified there.
_Avoid_: merged, finished, complete

**Debrief**:
What the orchestrator tells the user when a ticket's tree is finished: what the workers and the harden report found, and what it proposes to do about it.
_Avoid_: synthesis, summary, PR description, report (a worker's is one)

### Testing

**Oracle**:
What a test compares the code's behaviour against, chosen so that it is not the code itself: a property the ticket states, a worked example, a reference implementation, a round trip, a model.
_Avoid_: expected value, ground truth, reference (an oracle may be one)

**Expected failure**:
The strict annotation a property carries while the behaviour it tests does not exist yet: it names the ticket that lifts it, and at a stub tolerates only the not-implemented exception.
_Avoid_: mark (a call mark or a row mark), xfail, skip

### Showing

**Show**:
An explanation carried by an artefact the reader looks at, built for their understanding of a thing rather than as proof of it.
_Avoid_: demo (the user's word for a show of the built thing's own output)

### Sessions

**Smart zone**:
The stretch of a context window within which reasoning stays sharp; the limit is a fraction of the window, not a feeling.
_Avoid_: context budget, token budget

**Session page**:
The one page a session's answers live on, the questions waiting on the user at its top.
_Avoid_: session artifact, transcript, notebook, log
