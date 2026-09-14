---
status: draft
---

# One flow

Round 4 draft. Marks: `(you, rN)` settled by max in round N (r0 is the opening messages before any round); `(you, side)` settled in max's parallel grilling on review delivery, folded in here; `(my call)` is the agent's and vetoable; `(open → Qn)` is put to a question in the current round.

## Problem Statement

All of max's work runs through this workflow, and the prompts it carries produce tens of thousands of lines every few days. Any per-piece gain in quality, in reading load, or in fun compounds. The bottleneck is max's capacity to read code and interact with agents without it draining them `(you, r1)`: the workflow's job is to spend that capacity at the critical junctions and nowhere else.

Today the workflow has two ends and no middle. At one end, loose work: chat, edits made in the session that discussed them, no written brief. At the other, the full feature: a grilled spec, a ticket graph, an orchestrator, workers on a host, a board. The middle, a piece of work with judgment in it but no design round, has no home. It either gets done loose, in a context already spent on the discussion, with the brief living only in the chat, or it pays the full ceremony, which for a two-file change is out of proportion.

The implement skill shows the symptom. It serves two readers, a worker alone in a pane and an agent chatting with the user, and its closing rules contradict each other: a closing comment in a ticket versus a chat reply, friction filed by an orchestrator versus reported to nobody `(you, r0)`. The user CLAUDE.md and a commit hook carry a second copy of the review rule for the in-session mode, which competes with the workflow's own review stations and does the same thing worse `(you, r2)`.

Review delivery has the same failure `(you, side)`: a session that implemented, reviewed and fixed in one context closed with a ninety-line chat message carrying every axis report verbatim, findings already fixed included, plus a verification block and a per-axis summary; the six lines the user needed sat inside it. The code-review skill mandates that message and deletes the report files after reading them, so chat is the only home the findings have left.

Prose quality has the same shape. The rules against AI tells live in always-loaded prompts (the output style, the worker prompt's style block, the user CLAUDE.md), so every generator carries them on every turn, while the one place a rule reliably holds, a reviewer reading a finished artifact, gets only a pointer. Chat has no reviewer at all. A regex linter for tells is rejected: the catalogue is model-relative and shifts with every model update, so only a model can apply it `(you, r0)`.

Wanted `(you, r0)`: one flow, not tiers, whose intensity scales with the work; the ticket as the standard brief on disk, visible on the board, so parallel work stays orientable and a brief the user does not need to read costs them nothing; the user's attention spent on renders (review pages, QA), never on reading briefs or on flagging slop. And `(you, r1)`: no agent ever blocks on the user reading a ticket, a spec or a note; the flow is git-tracked and asynchronous even where that looks like overhead for a small piece.

## Solution

Every piece of work travels one flow: an intent arrives in chat; the session grills it as deep as it needs; the settled design lands on disk as a brief; a fresh worker builds from the brief; a fresh reviewer reads the result; the session holding the branch integrates it; the user judges on the review page. Intensity is four dials, each with a default the agent applies without asking:

| Dial | Settings | Set by |
| --- | --- | --- |
| Grilling | none, one question, a full interview | the intent's ambiguity, per the grilling skill (unchanged) |
| Brief | none, a standalone ticket, a spec sliced into tickets | the brief test below |
| Worker | this session, a fresh worker | whether a brief exists; the host is the repo's setup, the same for a standalone ticket as for a feature `(you, r2)` |
| Review | light, full | whether a spec exists; how a review is delivered changes, see Review delivery `(you, side)` |

**The brief test** decides the second dial and thereby the third `(my call, wording ratified r3)`, and this paragraph is what the orient skill states, without an example table `(you, r3)`. Loose: the instruction is the change; a stranger could apply it from the chat line without reading code (a keybinding, a version bump, "rename X to Y"). Ticket: a builder must read code, choose and test, but the what fits one what-to-build plus acceptance criteria, every open choice is an implementation choice behind a settled interface, and it fits one worker. Spec: the builder would have to ask the user something, about behaviour they have taste on, an interface, a data shape, a term, or the work spans several slices. Writing the ticket is itself the test: a ticket that needs the conversation to make sense marks a decision that has not been made, and the fix is a grilling round, not a bigger brief.

Loose is the absence of a brief, not a lower tier: no ticket, no worker, no agent review `(you, r3)`; the session commits on its branch with the `loose` trailer, and the review page is the gate before the user sees it. Anything with judgment in it is a ticket; if sessions turn out to keep doing judgment work loose, a hook scoped to interactive sessions is the fix then, added from an observed failure and not in advance `(you, r3)`. The user CLAUDE.md line asking for a review before every batch, and the commit hook that repeats it, are deleted `(you, r2)`.

Everything past the brief is the flow that exists today, with three changes:

1. **Every ticket is worked by a fresh worker from the file** `(you, r1)`, a feature's only ticket included. A feature always slices, into one ticket or many; the size call at the grilling gate ("build here, or to-tickets") goes away.
2. **A standalone ticket is dispatched by the same scripts as a feature's** `(you, r2)`: same host selection, same pane, same worklog, same stop and resume; the worker outlives the session that started it, so the session can be cleared and any later session integrates the result. What differs is only the branching: cut from and merged into the repo's integration branch, no feature worktree, no feature branch. The alternative, a subagent spawned inside the session, was rejected: it dies with the session, cannot be watched, and keeps the session alive as a waiting orchestrator.
3. **The implement skill dissolves into the worker prompt** `(you, r3)`. Only workers ever load it now, and the worker already has a prompt of its own that replaces the user CLAUDE.md and is appended to its system prompt; the process joins it there and the skill is deleted. Nothing in chat loads it.

**Review delivery** `(you, side)`: the reviewers' reports stay on disk, the worker that owns the branch aggregates them, and what reaches the user is the review page plus the calls only they can make. The code-review skill's one-standalone-message paragraph, its delete-after-reading line and its per-brief word caps go.

Prose enforcement moves to the same shape, a reviewer reading a finished artifact:

- The unslop catalogue and writing-for-humans become one skill `(you, r0)`: the catalogue, with its stable rule ids, is the skill's one companion file; the skill body keeps only what the catalogue cannot hold (cold reader, one home per fact, referencing by title). Rules carry a scope tag, artifact, chat, or both `(you, r1)`.
- The Standards reviewer in code-review receives the catalogue by path, not the skill's link to it `(my call)`: the diff is where the rules bind.
- Chat gets its reviewer `(you, r3)`: a Stop hook that has a small model read the turn's final message against the chat-scoped rules; with hits, the turn continues and the corrected reply follows the draft on screen, which is acceptable `(you, r3)`. The reviewer reads reply text only; code in files is the Standards reviewer's. Prototype: [chat-review-hook](../../prototypes/chat-review-hook/ANSWER.md).
- The output style and the style blocks in the user CLAUDE.md and the worker prompt shrink now, in this feature `(you, r3)`, to what a reviewer cannot check from one message: stance (candid, disagreeable, strong opinions), content (specific, teach, don't assume familiarity, show don't tell, every sentence earns its place) and structure relative to the question (answer first, brevity, the state line during multi-step work). Everything the reviewer can check from the message alone moves to the catalogue: tells, coinage and metaphor, openers and closers, meta-commentary, one idea per sentence, active voice, nominalizations, noun stacks. The cut is on the branch as a diff for the user to rule on `(open → Q9)`.

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
10. As max, I want the chat after a review to be the page, my calls, and the next steps, so that a review's cost to me is the decisions in it.
11. As max, I want the reply I read in chat free of AI tells without the agent carrying the catalogue in every prompt, so that my reading load drops and the generator's context does not grow.
12. As max, I want artifact text (comments, docs, UI copy, commit bodies) checked against the tells catalogue on every diff, so that slop is flagged by a reviewer, never by me.
13. As max, I want to turn the chat reviewer off if it proves annoying, so that a failed experiment costs one setting.
14. As max, I want no agent to stop and ask me to read a ticket or a spec it just wrote, so that my attention goes to renders at the junctions I chose.
15. As max, I want the flow to accept several workers on one ticket later without a redesign, so that spending compute for quality is an extension, not a rewrite.
16. As max, I want one rule for review, in one place, so that the workflow and my global instructions never ask for the same thing twice.
17. As a session agent, I want one checkable test at the moment of intent, so that I pick loose or ticket without weighing tiers.
18. As a session agent, I want the standalone-ticket dispatch to be a few commands with no feature setup, so that the ticket path is not heavier than doing the work myself.
19. As a worker, I want my whole contract in the prompt I start with, so that nothing in it addresses a reader I am not and no skill load can be skipped.
20. As a worker, I want the reviewers' reports on disk under the range they reviewed, so that I apply and decline findings from files and my closing comment can index them.
21. As an orchestrating session, I want a worker's closing comment to carry the QA surface, the action items, the assumptions and the finding index, so that I merge without reading the reports and relay the calls to the user.
22. As a reviewer, I want the tells catalogue as a file with rule ids, so that a finding cites a rule the author can look up.

## Properties

- A ticket reads cold: a worker builds from the ticket and its spec alone, never from the conversation that produced them.
- No step blocks on the user reading a brief. The user's stations are the spec gate, the review page per landed slice, QA, and the needs-human queue; a ticket written by an agent is dispatched, not presented.
- Before the user sees a diff with judgment in it, an agent has reviewed it; loose diffs carry no judgment by the brief test and are exempt.
- No finding a worker already fixed reaches the user; the user reads a review as a page plus the calls they must make.
- Loose work never appears on the board; ticketed work always does.
- One worker contract: a worker's obligations do not depend on what spawned it or where it runs.
- A rule about process for the worker lives in the worker's prompt; a rule about prose lives in one catalogue; every prompt that needs either points there.
- A chat reply the user reads has been checked against the chat-scoped rules, and the check never runs more than once per turn.
- Every landed slice, standalone or feature, has a review page before the user is asked to judge it.
- The unit of the flow is one ticket, one worker, one branch, one review page; an extension that runs several workers on one ticket plugs in at spawn and at landing and changes nothing else.

## Decisions

- **The brief test** `(you, r3)`: the single entry decision, stated in the orient skill as the paragraph above, replacing the size call at the grilling gate. Its failure mode, a ticket that cannot be written cold, routes back to grilling.
- **Fresh worker per ticket** `(you, r1)`: the in-session build from a confirmed spec leaves the main flow; a grilling session that wants to build its own ticket does so as that ticket's worker, in a worktree, under the same contract.
- **A feature always slices** `(my call)`: to-tickets runs after every confirmed spec and yields one ticket or many. Follows from the previous decision.
- **Standalone tickets dispatch like a feature's** `(you, r2)`: same scripts, same host selection; the host setup (the bare repo, the host record) happens once per repo and is reused by every feature and standalone ticket `(my call)`. Cut from and merged into the integration branch. Each session claims its own standalone ticket by committing the status flip on the integration branch; two sessions colliding is an ordinary one-line conflict `(my call)`.
- **Loose work gets no agent review** `(you, r3)`; no hook or rule replaces the deleted ones unless adherence fails.
- **The worker's contract lives in the worker prompt** `(you, r3)`: the implement skill's process joins the worker prompt, which the dispatch runner appends to the worker's system prompt, and the skill is deleted; every pointer to it (orient, dispatch, to-tickets, code-review, the README, the upstream sync mapping) is repointed. The contract: read the ticket and spec, build, run the review (light without a spec, full with one), aggregate its reports, close into the ticket's closing comment with the QA surface, the action items, the assumptions block, the finding index and the friction hit. The orchestrator's duties and the chat duties are not in it.
- **Review reports stay on disk** `(you, side)`: `agent/reviews/<fixed7>..<head7>/<axis>.md`, the same range the ticket's `diff:` frontmatter records per round, so `diff:` indexes a ticket's reviews. No branch in the path (a review runs in a worktree holding one branch), no retire step (the reports die with the worktree). The directory is gitignored by the project's own ignore file, added by project-setup beside `agent/research` `(my call)`: a worker host clones the repo and has no global ignore.
- **The word caps go** `(you, side)`: the 400-word cap per brief and the 600-word light cap did not triage; the three filters in the Correctness brief, the hard-violation versus judgment split in Standards, and the per-finding shape (scenario, file:line, fix) bound length.
- **The worker aggregates** `(you, side)`: reads the reports, applies accepted findings as `Workflow-stage: review` commits, writes declined findings as anchored `Assumptions` entries so the ticket's review page projects them onto their lines, and adds a finding index to the closing comment: one line per finding, fixed → commit, declined → assumption id. The orchestrator merges and never reads the reports. The whole-feature pass at frontier-empty has the same shape: the worker that fixes it aggregates, the orchestrator integrates.
- **What reaches the user** `(you, side)`: the review page; the calls they must make (declined findings, assumptions, open questions); next steps and blockers. No findings verbatim, no verification list, no per-axis summary. One rule for every caller; a standalone "review this branch" with nothing fixed anchors its findings on the page as notes and lists in chat only those needing a ruling.
- **Whole-feature review on frontier-empty** `(my call)`, adopted from upstream's implement-spec: a full code-review of the feature branch against the integration branch, with the spec as the spec axis, fixed by one worker before the debrief.
- **Review has two stations and no third** `(you, r2)`: the worker's own review inside its contract (light for a standalone ticket, full for a feature's), and the whole-feature pass. Light mode stays: three or four reviewers on every small diff is out of proportion `(you, r2)`.
- **Best-of-N stays an extension** `(you, r1)`: its own feature, filed as the standalone decision ticket [Best-of-N: several workers build one ticket, one result is chosen](../best-of-n.md), grilled after this ships; the ticket carries two rulings from round 2 (an agent synthesises, the user sees one review page; diversity of the variants is the failure mode to design against). This feature keeps the seam it needs (the last Property) and adds nothing for it.
- **One catalogue** `(you, r1)`: unslop's numbered rules absorb the current patterns file, whose rules without an id (throat-clearing openers, rhetorical setups, false agency, dramatic fragmentation, negative listing, binary contrasts) get ids in the same sequence, and the rules the output style stops carrying (nominalizations, noun stacks, coinage, meta-commentary) join with ids of their own; scope tags mark which rules bind artifacts, chat, or both. The chat-scoped rules state rule 16's bold lead-in exception beside them, which the prototype showed the reviewer needs.
- **Catalogue reaches the Standards reviewer by path** `(my call)`.
- **Chat reviewer** `(you, r3)`: a command hook on Stop, not a prompt hook (which cannot read the catalogue file) and not a display hook (display-only, holds the screen per batch, rewrites prose unchecked). It calls a bare, non-thinking small model with the message and the rules tagged chat or both, read from the one catalogue file itself, so there is no second rules file `(you, r4)`; returns the hits as feedback that continues the turn, fails open, logs every decision. Its scope is what the output style stops carrying: every rule checkable from the message alone `(my call, resolves Q6)`; structure relative to the question (answer first, brevity) stays with the generator, since the hook sees no question. Production home: the mx plugin's own hooks, so every machine gets it with the plugin `(my call)`; it returns early in sessions nobody reads, a dispatched worker's for one `(my call)`; one environment variable turns it off.
- **Deferred, typed**: which model the chat reviewer uses is an interchangeable part behind a settled seam and defers safely; how many instances of a tell the reviewer quotes, or whether a second check runs before the re-entry passes, is user-visible in effect (residual tells survive the rewrite) and is settled from the log after a week of use.

## Testing Decisions

The artefacts here are skills, prompts and a hook: prose that is the logic. No executable seam exists for them; every property is **reviewed**, checked against the diff by the Spec reviewer. The chat reviewer's behavioural claims (one check per turn, a targeted rewrite, latency under a few seconds) are verified by running it: the prototype's `try` driver and its log are the test, and the answer file records the measurements.

## Out of Scope

- **A regex or script linter for prose tells** `(you, r0)`: the catalogue is model-relative and changes with the models; a script encodes one snapshot of it and rots.
- **Best-of-N** `(you, r1)`: its own feature, see Decisions.
- **A subagent spawned by the session as the local worker**: dies with the session, unobservable, keeps the session waiting; see Solution, change 2.
- **A display-time rewrite of chat replies** (MessageDisplay hook): see the chat reviewer decision.
- **A hook or rule for loose work** `(you, r3)`: only if adherence to the brief test fails in practice.
- **An exploration subagent before implementation** (upstream's implement-spec): workers read the code they change under their own contract, and a research decision ticket already covers a question that spans tickets.
- **Sandcastle or another sandbox runtime**: dispatch on an isolated host is the same boundary with less overhead.

## Fog

None.
