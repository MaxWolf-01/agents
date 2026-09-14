---
status: draft
---

# One flow

Round 2 draft. Marks: `(you, r0)` is what max stated in the opening messages before any round, `(you, r1)` what round 1's answers settled; `(my call)` is the agent's and vetoable; `(open → Qn)` is put to a question in the current round.

## Problem Statement

All of max's work runs through this workflow, and the prompts it carries produce tens of thousands of lines every few days. Any per-piece gain in quality, in reading load, or in fun compounds. The bottleneck is max's capacity to read code and interact with agents without it draining them `(you, r1)`: the workflow's job is to spend that capacity at the critical junctions and nowhere else.

Today the workflow has two ends and no middle. At one end, loose work: chat, edits made in the session that discussed them, no written brief. At the other, the full feature: a grilled spec, a ticket graph, an orchestrator, workers on a host, a board. The middle, a piece of work with judgment in it but no design round, has no home. It either gets done loose, in a context already spent on the discussion, with the brief living only in the chat, or it pays the full ceremony, which for a two-file change is out of proportion.

The implement skill shows the symptom. It serves two readers, a worker alone in a pane and an agent chatting with the user, and its closing rules contradict each other: a closing comment in a ticket versus a chat reply, friction filed by an orchestrator versus reported to nobody `(you, r0)`.

Prose quality has the same shape. The rules against AI tells live in always-loaded prompts (the output style, the worker prompt's style block, the user CLAUDE.md), so every generator carries them on every turn, while the one place a rule reliably holds, a reviewer reading a finished artifact, gets only a pointer. Chat has no reviewer at all. A regex linter for tells is rejected: the catalogue is model-relative and shifts with every model update, so only a model can apply it `(you, r0)`.

Wanted `(you, r0)`: one flow, not tiers, whose intensity scales with the work; the ticket as the standard brief on disk, visible on the board, so parallel work stays orientable and a brief the user does not need to read costs them nothing; the user's attention spent on renders (review pages, QA), never on reading briefs or on flagging slop. And `(you, r1)`: no agent ever blocks on the user reading a ticket, a spec or a note; the flow is git-tracked and asynchronous even where that looks like overhead for a small piece.

## Solution

Every piece of work travels one flow: an intent arrives in chat; the session grills it as deep as it needs; the settled design lands on disk as a brief; a fresh worker builds from the brief; a fresh reviewer reads the result; the session holding the branch integrates it; the user judges on the review page. Intensity is four dials, each with a default the agent applies without asking:

| Dial | Settings | Set by |
| --- | --- | --- |
| Grilling | none, one question, a full interview | the intent's ambiguity, per the grilling skill (unchanged) |
| Brief | none, a standalone ticket, a spec sliced into tickets | the brief test below |
| Worker | this session, a fresh worker on this machine, a fresh worker on a host | whether a brief exists, then where the machine that stays awake is |
| Review | light, full | whether a spec exists (unchanged) |

**The brief test** decides the second dial and thereby the third `(my call)`: *would a stranger need a brief to build this right?* No, the edit is dictated or mechanical: loose, the session does it. Yes, and the ticket can be written cold, so a worker builds from it alone: a standalone ticket, a fresh worker. Yes, and the ticket cannot be written cold: the design is not settled, and what is missing is a grilling round, not a bigger brief; a design that needs a document to hold it is a spec. Writing the ticket is itself the test: a ticket that needs the conversation to make sense marks a decision that has not been made.

Loose is the absence of a brief, not a lower tier: no ticket, no worker, the session commits on its branch with the `loose` trailer, and the review page is still the gate before the user sees it. Loose work gets no code review `(you, r2)`: by the brief test it carries no judgment, so there is nothing for a reviewer to find; the global instruction that every batch is reviewed before the user sees it, and the commit hook that repeats it, existed because the old in-session mode did judgment work with no other review station. Both retire; review runs inside the worker contract and at the whole-feature pass.

Everything past the brief is the flow that exists today, with three changes:

1. **Every ticket is worked by a fresh worker from the file** `(you, r1)`, a feature's only ticket included. A feature always slices, into one ticket or many; the size call at the grilling gate ("build here, or to-tickets") goes away.
2. **A standalone ticket is dispatched by the same scripts as a feature's, pointed at this machine** `(my call, restated)`, cut from and merged into the repo's integration branch, with no feature worktree, no feature branch and no host pick. In plain words: what starts the worker is the same command that starts a feature's workers on a remote host, with "this machine" as the host. The worker runs in a terminal pane the user can attach to, writes a worklog, can be stopped and resumed, and outlives the session that started it, so the session can be cleared and any later session can integrate the result. The alternative, a subagent spawned inside the session, was rejected: it dies with the session, cannot be watched, and keeps the session alive as a waiting orchestrator.
3. **The implement skill is the worker's contract only.** It reads a ticket (and the spec when there is one), builds, reviews, and closes into the ticket. The session in chat relays the closing to the user; it never loads implement for loose work.

Prose enforcement moves to the same shape, a reviewer reading a finished artifact:

- The unslop catalogue and writing-for-humans become one skill `(you, r0)`: the catalogue, with its stable rule ids, is the skill's one companion file; the skill body keeps only what the catalogue cannot hold (cold reader, one home per fact, referencing by title). Rules carry a scope tag, artifact, chat, or both `(you, r1)`.
- The Standards reviewer in code-review receives the catalogue by path, not the skill's link to it `(my call)`: the diff is where the rules bind.
- Chat gets its reviewer: a Stop hook that has a small model read the turn's final message against the chat-scoped rules and block once with the hits, so the message is rewritten before the user reads it. Built as a prototype, [chat-review-hook](../../prototypes/chat-review-hook/ANSWER.md), whose measurements and findings are in its answer file; the verdict is `(open → Q5)`.

## User Stories

1. As max, I want to state an intent in chat and have the agent pick the intensity itself, so that I never choose between "loose" and "ticketed" by hand.
2. As max, I want a dictated edit (a keybinding, a version bump, an exact line) done in the session with no ticket, so that the flow costs nothing where nothing needs deciding.
3. As max, I want a piece of work with judgment in it to become a ticket on disk before it is built, so that a stranger, human or agent, can build or check it from the file alone.
4. As max, I want to be able to skip reading the ticket and read only the review page, so that a brief written for the worker costs me nothing.
5. As max, I want every ticket in flight, standalone or feature, on the board, so that when I lose track across parallel sessions I reorient from one page.
6. As max, I want the worker for a ticket to run in a fresh context, so that the work is not done in a context spent on the discussion that produced it.
7. As max, I want to clear my session after writing a ticket and have any fresh session pick it up, so that no handoff is needed between the design and the build.
8. As max, I want the same worker contract whatever spawned the worker, so that a ticket built on my machine and a ticket built on a host read the same on landing.
9. As max, I want a feature's integrated branch reviewed as a whole once every ticket has landed, so that incoherence between slices is caught before I QA it.
10. As max, I want the reply I read in chat free of AI tells without the agent carrying the catalogue in every prompt, so that my reading load drops and the generator's context does not grow.
11. As max, I want artifact text (comments, docs, UI copy, commit bodies) checked against the tells catalogue on every diff, so that slop is flagged by a reviewer, never by me.
12. As max, I want to turn the chat reviewer off if it proves annoying, so that a failed experiment costs one setting.
13. As max, I want no agent to stop and ask me to read a ticket or a spec it just wrote, so that my attention goes to renders at the junctions I chose.
14. As max, I want the flow to accept several workers on one ticket later without a redesign, so that spending compute for quality is an extension, not a rewrite.
15. As a session agent, I want one checkable test at the moment of intent, so that I pick loose or ticket without weighing tiers.
16. As a session agent, I want the standalone-ticket dispatch to be a few commands with no feature setup, so that the ticket path is not heavier than doing the work myself.
17. As a worker, I want my whole contract in one skill and one prompt, so that nothing in it addresses a reader I am not.
18. As an orchestrating session, I want a worker's closing comment to carry the QA surface, the action items and the assumptions, so that I relay it to the user rather than reconstruct it.
19. As a reviewer, I want the tells catalogue as a file with rule ids, so that a finding cites a rule the author can look up.

## Properties

- A ticket reads cold: a worker builds from the ticket and its spec alone, never from the conversation that produced them.
- No step blocks on the user reading a brief. The user's stations are the spec gate, the review page per landed slice, QA, and the needs-human queue; a ticket written by an agent is dispatched, not presented.
- Loose work never appears on the board; ticketed work always does.
- One worker contract: a worker's obligations do not depend on what spawned it or where it runs.
- The implement skill addresses only the worker.
- A rule about prose lives in one catalogue; every prompt that needs it points there.
- A chat reply the user reads has been checked against the chat-scoped rules, and the check never runs more than once per turn.
- Every landed slice, standalone or feature, has a review page before the user is asked to judge it.
- The unit of the flow is one ticket, one worker, one branch, one review page; an extension that runs several workers on one ticket plugs in at spawn and at landing and changes nothing else.

## Decisions

- **The brief test** `(my call)`: the single entry decision, stated in the orient skill as the question above, replacing the size call at the grilling gate. Its failure mode, a ticket that cannot be written cold, routes back to grilling.
- **Fresh worker per ticket** `(you, r1)`: the in-session build from a confirmed spec leaves the main flow; a grilling session that wants to build its own ticket does so as that ticket's worker, in a worktree, under the same contract.
- **A feature always slices** `(my call)`: to-tickets runs after every confirmed spec and yields one ticket or many. Follows from the previous decision.
- **Standalone tickets dispatch locally by default** `(my call)`, cut from and merged into the integration branch; a feature worktree and a host pick belong to features. The host setup (the bare repo, the host record) happens once per repo and is reused by every feature and standalone ticket. Each session claims its own standalone ticket by committing the status flip on the integration branch; two sessions colliding is an ordinary one-line conflict.
- **What starts a local worker** `(my call, restated in Solution, change 2)`: the dispatch scripts, pointed at this machine.
- **Implement is the worker contract** `(my call)`: reads the ticket and spec, builds, runs the review, closes into the ticket's closing comment with the QA surface, the action items, the assumptions block and the friction it hit. The orchestrator's duties (sorting friction, filing proposals, merging) and the chat duties (relaying the closing, showing the review page) leave the skill. No interactive companion file: the interactive side is already steered by the system prompt (user CLAUDE.md, output style), and the worker side by the worker prompt.
- **Whole-feature review on frontier-empty** `(my call)`, adopted from upstream's implement-spec: a full code-review of the feature branch against the integration branch, with the spec as the spec axis, fixed by one worker before the debrief.
- **Review has two stations and no third** `(you, r2)`: the worker's own review inside implement (light for a standalone ticket, since it has no spec; full for a feature's), and the whole-feature pass. The user CLAUDE.md line that asks for a review before every batch shown to the user, and the commit hook that nudges it, are deleted; they competed for attention with the workflow that already carries the rule. Light mode stays: it is what a standalone ticket's worker runs `(my call)`.
- **Best-of-N stays an extension** `(you, r1)`: its own feature, filed as the standalone decision ticket [Best-of-N: several workers build one ticket, one result is chosen](../best-of-n.md), grilled after this ships. This feature keeps the seam it needs (the last Property) and adds nothing for it.
- **One catalogue** `(you, r1)`: unslop's numbered rules absorb the current patterns file, whose rules without an id (throat-clearing openers, rhetorical setups, false agency, dramatic fragmentation, negative listing, binary contrasts) get ids in the same sequence; scope tags mark which rules bind artifacts, chat, or both. The chat-scoped rules state rule 16's bold lead-in exception beside them, which the prototype showed the reviewer needs.
- **Catalogue reaches the Standards reviewer by path** `(my call)`.
- **Chat reviewer** `(open → Q5)`: a command hook on Stop that calls a bare, non-thinking small model with the message and the chat-scoped rules, blocks once per turn with quoted hits, fails open, logs every decision. Its production home is the mx plugin's own hooks, so every machine gets it with the plugin `(my call)`; it returns early in sessions nobody reads, a dispatched worker's for one `(my call)`; one environment variable turns it off. The scope of what it reviews is `(open → Q6)`.
- **Deferred, typed**: which model the chat reviewer uses is an interchangeable part behind a settled seam and defers safely; how many instances of a tell the reviewer quotes, or whether a second check runs before the re-entry passes, is user-visible in effect (residual tells survive the rewrite) and is settled by the prototype's verdict.

## Testing Decisions

The artefacts here are skills, prompts and a hook: prose that is the logic. No executable seam exists for them; every property is **reviewed**, checked against the diff by the Spec reviewer. The chat reviewer's behavioural claims (one check per turn, a targeted rewrite, latency under a few seconds) are verified by running it: the prototype's `try` driver and its log are the test, and the answer file records the measurements.

## Out of Scope

- **A regex or script linter for prose tells** `(you, r0)`: the catalogue is model-relative and changes with the models; a script encodes one snapshot of it and rots.
- **Best-of-N** `(you, r1)`: its own feature, see Decisions.
- **A subagent spawned by the session as the local worker**: dies with the session, unobservable, keeps the session waiting; see Solution, change 2.
- **An exploration subagent before implementation** (upstream's implement-spec): workers read the code they change under their own contract, and a research decision ticket already covers a question that spans tickets.
- **Shrinking the style blocks in the user CLAUDE.md and the worker prompt to pointers**: right once the reviewer-side enforcement has been seen to hold; a follow-up, not this feature.
- **Sandcastle or another sandbox runtime**: dispatch on an isolated host is the same boundary with less overhead.

## Fog

None.
