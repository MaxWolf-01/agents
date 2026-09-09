---
status: confirmed
---

# Proposed tickets, and where friction goes

## Problem Statement

The human wants to read one thing per feature besides the diff: the orchestrator's proposal. Today the orchestrator's readings (a worker's friction from its closing comment, a harden report, the punts dispatch files) either become tickets that look like the user's own or entries on the needs-human queue, and the user cannot tell an orchestrator's suggestion from a decision they made in grilling.

What exists, verified against the skills at v0.1.40. A worker names friction and its unescalated assumptions in its closing comment (`/mx:implement`), and is told the dispatcher decides what becomes of it "once the user has ruled". Dispatch's tick (`/mx:dispatch`, step 1) tells the orchestrator to fix what it can between waves and file the rest "as a new ticket with blocking edges" or as a needs-human entry, with no ruling step: a ticket filed that way is `status: open`, sits on the frontier, and the next wave works it. Step 5 already says the harden report's leftovers become "a proposed ticket" that the user rules on, but a proposed ticket has no home: it is chat prose. The tracker's only provenance is a sentence about who sketched a ticket's framing; nothing machine-readable says whether the user wanted the ticket at all, so the board cannot show it and the frontier cannot respect it. `/mx:reflect` asks a session the same friction questions and writes its answer nowhere.

Raised from review comment C12 on the testing-workflow implementation (mx v0.1.40): "the agents should do these, orchestrator reads these, suggests follow ups / tickets, I read THAT + the diff + say yay or nay".

## Solution

A ticket an agent files without a ruling from the user carries `status: proposed`. It is a ticket in every other respect (a build ticket or a decision ticket, numbered, with blocking edges), but it is off the frontier by construction and a worker can never be spawned on it. The user rules on each: open it, delete it, or send it to grilling. Nothing but a ruling writes `open`.

The friction pipeline then has one shape from worker to ruling. A worker names what fought it in its closing comment, as today. At the tick the orchestrator sorts every such line, and every harden line, the same way: fixable now → fixed on the feature branch in a commit naming it; action-shaped but not now → a proposed ticket carrying its origin and the reason; a question only the user can answer → a needs-human entry, as today; nothing statable → left, and said so. When the frontier empties the orchestrator's debrief (fixed, proposed, left) is one needs-human entry, so the board carries it and no chat message has to. The user reads the diff, which already contains the proposed ticket files because they are committed on the feature branch, and rules; the merge commit body records the rulings.

The same rule holds outside dispatch: a review session, a code-review follow-up too large to fix, a session that built a feature without an orchestrator all file `proposed`; a ticket the user asks for in conversation is a ruling and is `open`.

## User Stories

1. As max, I want to read one debrief per feature besides the diff, so that I rule on what the orchestrator found without reading closing comments or harden reports myself.
2. As max, I want a ticket an agent proposed to look different from one I decided, so that I never work or dispatch something I did not ask for.
3. As max, I want to rule on a proposed ticket with one word per ticket (open, delete, grill), so that the ruling costs less than the reading.
4. As max, I want the proposed tickets in the feature diff I already read, so that the proposal and the diff are one page.
5. As max, I want the board to count and list proposed tickets, so that a pile of unruled proposals is visible rather than buried in feature directories.
6. As max, I want a proposal to say where it came from and why it is worth doing, so that I can rule without opening the worker's comment it was cut from.
7. As max, I want a rejected proposal gone from the live tracker, so that the next reader does not take it for planned work.
8. As max, I want friction with the workflow itself (a skill that misled, a dispatch script that broke) to reach me as a proposal too, so that mx improves from its own runs and not only from what I notice in chat.
9. As an orchestrator, I want one rule for every line a worker or harden hands me, so that sorting friction is mechanical and nothing stays in a comment with an audience of zero.
10. As an orchestrator, I want to file a punt as a proposed ticket that other tickets can block on, so that the dependency is explicit and the user's ruling is what unblocks it.
11. As a worker, I want to report friction and nothing more, so that I never write a ticket file another worker's numbering collides with.
12. As a review session, I want to read a feature's proposed tickets instead of its landed comments, so that the picture is already sorted when I rebuild it.
13. As a session that built a feature without an orchestrator, I want the same closing rule, so that my friction has the same home as a worker's.
14. As a fresh orchestrator on the next feature, I want proposals from the last one either ruled or standalone, so that retiring a feature never deletes an unruled proposal.
15. As the board, I want the frontier definition unchanged, so that a proposed ticket is off it without a new rule.
16. As `spawn`, I want to refuse a proposed ticket the way I refuse a decision ticket, so that the rule is enforced and not exhorted.

## Properties

- A proposed ticket is never on the frontier and is never spawned.
- A ticket reaches `open` only through a ruling by the user.
- Every proposed ticket names its origin and the reason it is worth doing.
- Every line of friction a worker names is fixed, proposed, queued or listed as left; none stays only in the closing comment.
- The user reads one debrief per feature.
- A rejected proposal leaves no live artefact.
- A feature is retired only once every proposed ticket in it is ruled.
- The tracker's state machine has one home; no other skill restates it.

## Decisions

- `proposed` is a fourth value of `status`, before `open`: `proposed | open | claimed | done`. Not a `type`: whether the user wanted a ticket is orthogonal to whether it is a build ticket or a decision ticket, and an orchestrator proposes both kinds (the three standalone tickets the testing-workflow feature left behind are proposed grilling tickets in all but name). Not a separate directory or file: the frontier and `spawn` already key on `status`, so one value gives both the exclusion for free.
- Only a ruling by the user writes `open`. Grilling and to-tickets write `open` because their output is the user's (the frontier is theirs, the breakdown was approved). Every other agent-filed ticket, in dispatch or out of it, is `proposed`. Silence never ratifies.
- Workers never file tickets: a worker's closing comment names friction and assumptions; the orchestrator files. A worker owns one ticket file and one worktree, and two parallel workers scanning a directory for the next number collide.
- A ruling has three outcomes: **open** (flip the status; the origin line stays), **delete** (the commit message carries the reason; a reason the next feature must know goes where rules live: an ADR, the project CLAUDE.md, the tool's config), **grill** (set `type: grilling`, open it; a feature-sized one becomes a standalone grilling ticket that a later session grills into a spec).
- A proposed ticket's body opens with one line of provenance: which closing comment, harden line or review finding it was cut from, and why it is worth a ticket. The tracker's existing framing-provenance rule still governs the options it sketches.
- The orchestrator's sort at the tick, for a worker's friction line, an assumption with a taste call, and every harden line alike: fixable now → fixed here, commit names it; action-shaped, not now → proposed ticket, blocking edges where a ticket waits on it; a question only the user can answer → needs-human entry; nothing statable → left, named in the debrief. This replaces dispatch's "file it as a new ticket with blocking edges" and implement's "once the user has ruled", which contradict each other today.
- The debrief is a needs-human entry: summary `debrief`, detail the fixed commits, the proposed tickets by number, and what was left with its reason. The board renders it under Needs human like every entry; it is deleted when the rulings land, and the merge commit body records them. No new file, and the chat report becomes a pointer to it.
- Reading surface: the board, where a proposed ticket is an ordinary node and row in every view, in its own colour, so it is triaged from the graph with its edges; a count in the top bar; and the feature diff, where the ticket files already are. Ruling channel: a diffview comment or a line in chat; the session flips the files. The board stays a render.
- Friction with the workflow itself (a skill that misled, a dispatch script that broke) is a proposed ticket in the project's tracker like any other, its body saying the fix lives in the plugin; the ruling "open" means the user moves it to the plugin's tracker.
- Retiring a feature requires every proposed ticket in it ruled; an opened one that outlives the feature moves to a standalone ticket, as the tracker's retire rule already implies for shipped work.
- `/mx:reflect` is retired: the closing rule in implement asks its questions with a durable output, and the retro ticket keeps the cross-session half.
- A ticket blocked on a proposed ticket stays blocked until the ruling; a deleted proposal counts as done by the tracker's existing missing-file rule, so a rejection unblocks.
- Board and dispatch's `claim` enforce; the skills state the rule once, in the tracker: `claim` refuses `status: proposed` where the frontier is read, the board's frontier excludes it, and dispatch, implement and orient point at the tracker rather than restating the state machine. Each rule has one door: a decision ticket is claimed and routed, and `spawn` is what refuses to hand it to a worker.

Deferrals: none.

## Testing Decisions

Two seams in the board script, both driven against a fixture tracker in a temp directory: the tracker loader (the functions that read a tracker directory into ticket and queue state) and the rendered page's status classes (what the loader read, drawn: the node class in each graph, the lane, the row, the counts); oracle: the tracker's MARKDOWN.md (the frontier sentence, the missing-file rule, the queue's bullet shape); prior art `mx/skills/testing/test_harden.py`. "A proposed ticket is never on the frontier" and "a rejected proposal leaves no live artefact" (its deletion unblocks) are executable at the loader; that a proposed ticket is drawn in every view is executable at the render. `claim`'s refusal is bash, driven by hand against a fixture repository. Every other Property is reviewed: the Spec axis reads the skill diffs against this document.

## Out of Scope

- Mining friction across sessions (the session index, workers over transcripts): the user ruled it out for the workflow in C12; the standalone ticket `retro-semi-automated` holds the idea.
- Deriving the needs-human queue from ticket state instead of its file: a separate feature; the file stays, and the debrief entry uses it as it is.
- A write-back from the board: rulings go through a session, the board stays a render.
- Filing into another repository's tracker: an unattended orchestrator writes only where it holds the checkout.
- Changing what grilling and to-tickets file: their output is already the user's.

