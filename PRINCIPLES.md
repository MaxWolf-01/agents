# Workflow principles

Read this before changing a skill, a `CLAUDE.md`, or anything else about how the workflow runs, and when judging an upstream change (`pocock-sync`). Every principle here is a rule this workflow re-learned more than once; the citations are the evidence. Use it as a test on the change in front of you: which principle does it serve, which does it strain, and where does the rule already live, so it keeps one home. A change that strains a principle says so in its commit message.

The workflow's why: automate every check a machine can make, even at compute cost; human attention goes to design decisions and taste, at deliberate stations, never to flagging obvious slop.

Citations: a bare hash is this repo; `up:` is mattpocock/skills; `yt:<id> <mm:ss>` is a YouTube video; `workshop <h:mm:ss>` is Pocock's AI Engineer Europe 2026 workshop (https://youtu.be/-QFHIoCo-Ko; a transcript is linked at `resources/full-walkthrough-workflow-for-ai-coding-matt-pocock.md` on max's machines); `retro §N` is the skilltree retrospective, a gitignored research note, so its glosses here are what a cold reader gets; an author's name is a web post from the research survey. Observations about one model or one harness are not principles; they live beside the mechanism they affect (dispatch's and code-review's model rules, `permissions-review`).

## 1. Enforce, don't exhort

A rule enforced at a check beats a rule stated in prose. Three rungs: (1) the rule is a linter, a type, a test, a script, or a tool-level block, and the agent is corrected the moment it breaks it; (2) the rule is pushed to a reviewer as a checklist against a finished diff; (3) the rule is prose the agent reads while generating. Rung one is the target; a hook that injects a message is rung three, not rung one. A rule read while generating washes out under the pressure of finishing; the same rule read against a finished diff holds (eb47809).

- **Put the rule at the moment of temptation, as a test the writer can run.** "Would a mechanism change force an edit here?" at the glossary step beat "no implementation details" at the top of the skill (a8c9a9a); "mechanical" is defined where the skip decision is made (055fdd9). A step's done-condition, stated so done is checkable, is the defence against premature completion (up:0e9a072).
- **Grow rules only from observed failures, and prune them like code.** Each rule change here cites the session where the old text failed (4ed2207, 08bff5c); a bullet reaches an always-loaded file only when the failure keeps recurring (6ee35a4). Exhortation bullets ("question assumptions", "think deeply") were deleted after being watched not firing in the exact scenario they target (d09f56d, c3bec7f); a rule was retired once the sandbox covered its case (a8fc837).
- **A script that does the thing beats a paragraph of prompt about it, and beats a tool definition carried in context.** Judgment stays prose; the deterministic protocol becomes a script whose echoed commands double as the by-hand recipe (581a2a6, f687a85); a permissions allowlist tuned from real calls (c01c2a0).

Home: code-review's smell baseline and the post-commit review nudge (c322cbf) are this principle running.

Evidence beyond the hashes above: up:cac4704 (Fowler's smells as an always-on review baseline), up:8fa1886 (a `retro` skill feeding instruction updates); workshop 1:28:00 (standards pulled by the implementer, pushed to the reviewer), yt:3CSi8QAoN-s 01:08 (a `CLAUDE.md` line lowers the odds, a PreToolUse hook prevents), yt:llwTBpPqo9A 03:41 (a rule a hook already enforces is redundant in `CLAUDE.md`); Hashimoto (every mistake becomes a fix the agent cannot repeat), Ronacher (`gh` beats the GitHub MCP), Anthropic best practices (`CLAUDE.md` is advisory, hooks are deterministic).

## 2. State the goal at the right altitude

Say what the work is for; automate the precise parts; leave the rest to inference. Overspecified rules overfit the run they came from, carry their author's mistakes and contradictions, and the agent follows the wrong rule faithfully; a vaguer goal sometimes produces the better choice because the agent reasons from the destination. Contradictory rules burn reasoning on reconciling them. A required prose slot can always be satisfied with words, so it always is: keep only slots that cannot be padded (7d5902d). The one long precise list that works is the review smell baseline, and it works because a reviewer reads it against a finished diff (see Enforce, don't exhort).

- **Steer with positive instructions.** A prohibition names the banned behaviour and makes it more available; where the template already lacks the thing, the absence does the work (up:cb7db0e, 9d65390). State the target ("report the finding and leave the fix to the maintainer", 5f31d98; "finish what doesn't depend on the blocker, then stop", f470911).
- **A principle has to be checkable to survive.** "Notice your silences" was dropped upstream minutes after it landed, as legwork the agent cannot act on (up:af6d692).

Evidence: e2d196c (800 enumerated allow rules replaced by a classifier that reads the whole command), d7b96b1 (no mandated reasoning effort); up:e81f976 (TDD's step list deleted; the loop is already held), up:0847bb3 (the Negation failure mode); Anthropic context-engineering (prompts at the right altitude), GPT-5 guide (contradictions cost reasoning; the remedy for tool over-use was a softer rule), Pocock writing-for-agents (a skill built from one run over-indexes on it).

## 3. Every always-loaded word costs every turn

Material goes behind a pointer unless it applies to most sessions; the always-loaded file holds what shapes a first draft (eb47809) and what cannot be discovered by looking. A case that occurs once a year never belongs there; once a month, still not, perhaps a skill. Placement decides steering as much as length: the same text under-steered from `CLAUDE.md` and steered from the output style (edaf49e). The pointer's wording decides whether it fires; most under-use here was a description problem, fixed at the trigger, not the body (4ed2207, 08bff5c, 507debe, ba1f634).

- **Use words the model already holds, and test a word for what else it primes.** Leading words (smell names, seam, fog of war, tracer bullet) carry their definition for free; a harness's own names mis-prime other harnesses and say nothing to the one that owns them (ef90c24, 6ee35a4). The rule and its tests live in writing-for-agents, Leading words. Upstream kept one literal tool name for cross-skill invocation (up:d28dfdc, "Call the Skill tool with x"); mx keeps the neutral wording everywhere.
- **Name a harness in exactly one place.** The dispatch runner is the only file that names one; swapping the runner swaps the harness (581a2a6).

Evidence: up:4f6e25d (a 65-word `CLAUDE.md` edit cut to the one pointer line), up:cb51924 (branches → modes), up:14bfbbd (tool names dropped), up:61accb0 (a description written as the pointer that decides when it fires); Pocock writing-for-agents (context load vs cognitive load; a case in one context of ten pays load the other nine times), yt:9tmsq-Gvx6g 07:19 (an instruction budget of a few hundred, global to every use of the repo), yt:-uW5-TaVXu4 (lost in the middle; MCP servers bloat context); Ronacher (reinforcement after tool calls steers better than front-loaded instructions).

## 4. One home per fact

A fact stated twice is a cache of itself, and the copy is the one nobody sees when the home changes. Skills hold the process; a project artefact holds only its deliberate deviations (1fd0dbe: a map note cached the old grilling rhythm and kept overriding the upgraded skill, retro §12). A summary keeps the name and loses the mechanism, so the primary source stays reachable: prototypes kept in-tree (da9e80b; retro §7: prototype verdicts travelled five hops as winner-names, and the one ticket pointing at source produced the precise paragraph), a handoff file over a compaction summary (49d012b; `/compact` is off mx's ladder where up:fa1e322 keeps it as the floor), a resumed worker told "continue" rather than recapped (0189f33). Superseded work is deleted or tombstoned; an artefact left looking live teaches a superseded design to every later reader (91cc95c, d494777).

Home: the global `CLAUDE.md` `<style>` and `<workflow>` sections state the rule; writing-for-agents, Pruning, gives the tests; the mx README's "Done work gets deleted" is the flow-level form.

Evidence: 9f18fbb (`--help` documents the CLI, not the workflow around it), d8e4654 (a byte-copy of the validator drifted), 11f13c1 (a `CLAUDE.md` claim already false), f994656 (`agent/research/` gitignored because stale research steers wrong); up:d4e8664 (the cache leading word), up:3314257 (25 hand-copied install commands drifted), up:9272935 (the map is an index, not a store), up:c66bdee (a retired skill deleted, the changeset naming its replacement); yt:9tmsq-Gvx6g (`/init` writes facts the file system already states), yt:Ah9p7v7nJWg 06:16 (research lives one sprint), workshop 1:23:29 (an old PRD found a month later is doc rot).

## 5. Deliver through artefacts written for a cold reader, carrying the why

The chat and the return channel are not durable; a file is there whether or not the agent ended cleanly (0b37423: a named subagent's report arrived as an empty ping; ec262ac: reviewers ended their turn holding the report; f470911: a worker's chat is read by nobody, the ticket is the channel; 351ce7a: a worklog created up front so emptiness is a reading). The reader has no conversation: the recurring slop in artefacts is conversation residue and cached facts, not style (61961f1, 753bae3), and a ticket that under-describes its work misleads whoever reads it next (b905ec7). The destination and the reason come before the how: without the why the agent cannot suggest alternatives (yt:hX7yG1KVYhI 05:28), a handoff without a stated purpose is refused (7ca2f5c), a commit body answers what the human wanted (507debe). If a thing cannot be said in plain words, it has not been decided (retro §11: fourteen "what does this mean" queries in one session, half hiding an unmade decision).

Home: the global `CLAUDE.md` `<style>` section (artifact text states what is; narrative and decisions-against go to the commit, the ADR, or out-of-scope) and `<subagents>` (name the file the agent writes).

Evidence: up:86b07d1 (attributed opinion dates when the position moves), up:da2cb7d (change narration belongs in the changeset), up:14780a1 (a multi-way branch is a table), up:53c6219 (destination charted first); workshop 0:58:08 (negative decisions live in out-of-scope), yt:dtAJ2dOd3ko 11:10 (a handoff always states its purpose).

## 6. Facts are the agent's to find; decisions are the human's to make

An unconfirmed decision stays marked; silence leaves it unconfirmed (7f6dfb0: consent section, Assumptions block for the user to ratify; retro §4: a recommendation followed by a topic change reached five artefacts as a decision). Every claim carries provenance, and the agent's negative claims about the environment are as unverified as its positive ones (yt:hX7yG1KVYhI 28:39: "no test harness" was false). A casual go-ahead ratifies proceeding, not the frame (ddafe22). An agent's statement of its own intent is self-certification (7d5902d). A question offers at least two options the agent would defend (c50f500). The friction a worker hits is filed by the dispatcher after the user has ruled; the worker is the party least able to judge whether it is ticket-worthy (8caba61). Models, upstream issues, and anything ship-shaped are named or released by the human (1405618, 474a0e2). Human attention pays most at the plan: a wrong line of code is one wrong line, a wrong line in a plan is hundreds.

Home: grilling is the station (the mx README's "Grilling is where alignment happens" and "The spec is reviewed as it is written").

Evidence: up:e5932a7 (wayfinder grilling itself; facts split from decisions), up:0e9a072 (a confirmation gate); yt:9VNG0h4pLh0 (training rewards guessing over admitting uncertainty; "use your search tool" turns a parametric claim into a contextual one), yt:llwTBpPqo9A 05:00 (ask it to steel-man the opposite; "refreshingly minimal" is this year's "you're absolutely right"); Horthy (a bad line of a plan leads to hundreds of bad lines of code), Ball (the agent does not make architectural decisions).

## 7. Judge in front of a render

Humans judge far better in front of a render than in the abstract; the artefact is the decision instrument and the conversation is its brief. A blank answer means the question was posed backwards: build the thing and let them criticise it (retro §5–6: grilling depth tracked arguability, not importance; the person blank on "what goes in the sidebar" produced publishable criticism in front of a render; a prototype overturned a grilled ticket and an ADR within a day). The leap from spec to production code is large and from working prototype to production is small (yt:n0VhIVtviC0). Taste enters at QA, by hand, per landed slice; the model cannot see what it is building (yt:DNqsMXH6Eog 06:00).

Home: orient routes user-visible surfaces to prototype-first (7f6dfb0); `/mx:show` (61f3007) and diffview as the review surface (e065e9b) are the same move for explanations and diffs; the mx README's "QA is where you impose taste".

Evidence: 2b34e11 (grilling delivers a vetoable whole); up:d627460 (the prototype is a primary source); workshop 1:12:35 (automate the idea, the planning and the QA and the result lacks taste), yt:hX7yG1KVYhI 38:10 (a two-button menu became a checkbox only once seen; git edge cases surfaced only in QA), yt:pSritFeoYFo (front-end loops are visual; without a browser the agent flies blind).

## 8. Fresh context per unit of work

Reasoning degrades well before the advertised window is full, and an agent cannot introspect the degradation, so the limit is stated as a fraction rather than a feeling (49d012b). An author is the wrong reviewer of its own diff, and a model is reluctant to change code sitting in its own context (yt:M6mYodf0dJM 15:45, yt:EJyuu6zlQCg 11:46). Repeated compaction leaves sediment; a handoff file is a deliberate reset that can be read and edited before it seeds the next session, and crosses harnesses (yt:dtAJ2dOd3ko). A different model family reviewing than the one that wrote is the strongest form (d7c7120; 04cfa46 reverted the default for quota and kept the fresh-context reviewers). Ticket-sized fresh workers stay the unit of implementation; the coherence cost of isolation is carried by slicing (next principle) and the review session.

Home: the mx README's "Plan in one window, respect the smart zone" and "Reviews run in fresh context"; orient's phase boundaries.

Evidence: 1405618 (review model chosen per diff size), 7ca2f5c and f3970c8 (a handoff states what the next session will focus on); up:fa1e322 (the phase-boundary tree), up:2e64732 (fail fast before spawning reviewers); workshop 0:03:12 (smart zone, dumb zone; optimise for the deterministic reset), workshop 1:05:43 (clear the context and the reviewer reviews in the smart zone), yt:-uW5-TaVXu4 06:22 (clear should be the default); Ball (run `git diff` to see the code someone else wrote), Anthropic 4.6 guide (fresh context plus filesystem discovery beats compaction).

## 9. Slice along seams that already exist

A unit of work that spans an owner boundary or a hub file is a serialisation signal, not a scheduling problem: the per-ticket isolation that keeps workers fresh is what produced the incoherence when twelve of twenty-nine tickets wrote into one file (retro §10, with a runnable demo in 621ce5d). Vertical slices, each demoable when it lands; the model codes horizontally by default. The breakdown is reviewed for its shape (slice count, size, verticality), which is cheap and whose failure is visible; the text is not. A property with no user story gets no slice, so the spec states properties (retro §2). Interfaces are designed, implementations delegated; test boundaries follow module boundaries.

Home: dispatch's coherence test and to-tickets' slicing exceptions (7f6dfb0, 8f70559); the mx README's "Do review the ticket breakdown" and "Feedback loops are the ceiling".

Evidence: 34f8da6 (a reproducible setup target is what lets workers open a worktree on any host); up:a0329ba (wide refactors sliced by expand–contract); workshop 0:41:37 (tracer bullets; the breakdown is the artefact worth reviewing), workshop 1:14:00 (deep modules as gray boxes), yt:hX7yG1KVYhI 30:19 (too small a ticket pays an agent start; two slices merged).

## 10. Verify against the live system, and make every failure state distinguishable from success

Documentation describes what the author believed; the live system is the authority, and a rule is written after the run, not from the reading (d8e7b5d: the permission scanner documented the same wrong model as the docs, and probing a live session turned 7445 phantom findings into 5876 real ones; afb0928, 72ef6ba: a render loop caught two bugs in the guide's own text; c1764f4). A working system is one that has been seen running; the rate of feedback is the speed limit. Every state the machinery can be in needs its own reading: a killed pane that still says running (ba0f663, a third state, `gone`), an absent worklog versus an empty one (351ce7a), a subagent ceiling that reads like a crash (8a564d5), a watcher demoted to a hint once the probe proved the authority (0687f96). A hazard that moved rather than went away is a workaround, not a fix (aab7abf, 8937f1c).

Evidence: up:8a475c4 (a refactor whose removals landed and replacements did not), up:42a5b70 (an ADR records what was verified, on which version, and what was not); Pocock writing-for-agents (settle a disagreement by running the document; duplication is the sign it was never tested), workshop 1:09:53 (the quality of your feedback loops is the ceiling), yt:v4F1gFy-hqg 10:42 (the rate of feedback is the speed limit), yt:_IK18goX4X8 (features marked complete without testing until told to test as a user would); Willison (if you haven't seen it run, it's not a working system).

## 11. Isolate what runs unattended, and write its prompt for a machine

The human's decisions are front-loaded into grilling; everything that can run without a human runs without one; what needs judgment is surfaced afterwards in the form best suited to judging it (see Judge in front of a render). Permission prompts and unsandboxed workers both put the human back into steps that should not need one. The isolation is the permission boundary: a worker installing a system dependency is doing unreviewed work outside its worktree on a machine nobody is watching, so an isolated host gets permissions bypassed and no credentials (a5c41ab, 21d17ae, 5c96574). The prompt is written for a reader with no conversation: the user's `CLAUDE.md` describes a conversation the worker is not in and tells it to ask questions it cannot ask (f470911, 43eeee8). Scratch state is namespaced per feature and per repo (5676532, 11f13c1: two dispatchers collided). Reversibility gates autonomy: local and reversible runs freely; destructive, shared, or ship-shaped waits for the human.

Home: the global `CLAUDE.md` `<git>` section (shared checkouts, staging, ship-shaped actions; 4527ead, ed001b7, 4718b33); clankr for the sandbox.

Evidence: workshop 0:55:12 (AFK loops run in a Docker sandbox; a worktree per issue), yt:E5-QK3CDVQM 00:35 (unsandboxed yolo mode deletes home directories), yt:yv8VZpov8bk 05:47 (a worktree cut from main pushed to main by default); Codex and Anthropic docs (reversibility as the autonomy gate).

## 12. Scale the process to the work

A step (grilling, review, a map) is skipped only when the change was dictated or needed no judgment; size and medium never decide it, because in this setup prose in skills and docs is the logic (9426de6, 055fdd9). Grilling triggers proportionally on any intent that is not fully mechanical: depth, not volume (507debe, 137a3db); specless work gets a light review (04cfa46). A map is for fog, an idea that will not fit one session; reaching for it on well-scoped work is the common mistake (up:ad99c73, up:e74fee8). Optimise only the artefacts someone reads: the "sacrifice grammar for concision" line left `CLAUDE.md` once its author stopped reading plans (workshop 0:48:23). Ticket sizing is two-sided; too small pays an agent start per slice (yt:hX7yG1KVYhI 30:19).

Home: the global `CLAUDE.md` `<git>` review-gate line; grilling's proportionality; wayfinder's "no fog, no map".

Evidence: up:9b43c33, up:b56795b (a hard cap on grilling questions rejected); yt:WNx-s-RxVxk 09:49 (when you know the codebase, make the change yourself).

## 13. Own the stack

Observability over the whole planning stack is what turns "this isn't working" into a fix; a workflow whose pieces someone else owns cannot be tuned (workshop 0:23:26). The agent is the tactical programmer; the strategic level, architecture and what to build and when to invest in design, is the human's, and the agent is treated like a delegate on the team with unusual constraints (yt:v4F1gFy-hqg 17:32, yt:3MP8D-mdheA 09:12, yt:EJyuu6zlQCg 15:11). Twenty-year-old books already verbalised the practice in English (Brooks, Fowler, Ousterhout, the Pragmatic Programmer, Shape Up) and are the richest prompt material (workshop 0:46:14); bad code is the most expensive it has ever been, so design is invested in daily (yt:v4F1gFy-hqg 03:27). Every piece of this stack is a script or a skill this repo can edit, released through one path (f4b55ec, d2c170c).

Evidence: 581a2a6 and f687a85 (protocol and dashboard as owned scripts), 9f18fbb (the CLI documents itself; the workflow around it lives in the skill); yt:kZ-zzHVUrO4 00:00 (treat it like someone you delegate to); Ball (own the result from "we have a problem" to "we don't have to think about it again").
