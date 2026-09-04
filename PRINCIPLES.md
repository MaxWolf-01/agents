# Workflow principles

The rules this workflow re-learned more than once, distilled from its own history, upstream's, Pocock's talks, and other practitioners. Test every change to a skill, a `CLAUDE.md`, or the workflow against them: which principle does it serve, which does it strain, and where does the rule already live, so it keeps one home. A change that strains a principle says so in its commit message. The evidence behind each principle, with commits, timestamps and quotes, is `agent/research/03-agent-workflow-principles.md` (gitignored).

The workflow's why: automate every check a machine can make, even at compute cost; human attention goes to design decisions and taste, at deliberate stations, never to flagging obvious slop.

## 1. Enforce, don't exhort

A rule enforced at a check beats a rule stated in prose. Three rungs: (1) a linter, a type, a test, a script, or a tool-level block corrects the agent the moment it breaks the rule; (2) a reviewer applies the rule as a checklist against a finished diff; (3) the agent reads the rule while generating. Rung one is the target; a hook that injects a message is rung three, not rung one. A rule read while generating washes out under the pressure of finishing; the same rule read against a finished diff holds. So the style rules left `CLAUDE.md` for code-review's smell baseline, and exhortation bullets ("question assumptions", "think deeply") were deleted after being watched not firing in the exact scenario they target. Three habits follow:

- **Put the rule at the moment of temptation, as a test the writer can run.** "Would a mechanism change force an edit here?" at the glossary step beat "no implementation details" at the top of the skill. A step's done-condition, stated so done is checkable, is the defence against finishing early.
- **Grow rules only from observed failures, and prune them like code.** A rule is added after a failure was seen, and the commit that adds it names that failure; a bullet reaches an always-loaded file only when the failure keeps recurring; a rule is retired once a mechanism covers its case.
- **A script that does the thing beats a paragraph of prompt about it, and beats a tool definition carried in context.** Judgment stays prose; the deterministic protocol becomes a script (dispatch-ctl, dispatch).


## 2. State the goal at the right altitude

Say what the work is for; automate the precise parts; leave the rest to inference. Overspecified rules overfit the run they came from, carry their author's mistakes and contradictions, and the agent follows the wrong rule faithfully; a vaguer goal sometimes produces the better choice because the agent reasons from the destination. Contradictory rules burn reasoning on reconciling them. A required prose slot can always be satisfied with words, so it always is: keep only slots that cannot be padded. Eight hundred enumerated permission rules closed one hole and left the next; a classifier that reads the whole command replaced them. Long precise lists work far better for a reviewer than for a generator: a separate agent that sees only the finished diff has none of the generator's pull to finish and nothing else competing in its context, which is why the smell baseline lives in code-review. Even a reviewer's list has a length past which rules stop landing.

- **Steer with positive instructions.** A prohibition names the banned behaviour and makes it more available; where the template already lacks the thing, the absence does the work. State the target ("report the finding and leave the fix to the maintainer") and the ban goes unspoken.
- **A principle has to be checkable to survive.** "Notice your silences" was dropped upstream minutes after it landed, as legwork the agent cannot act on.


## 3. Every always-loaded word costs every turn

Material goes behind a pointer unless it applies to most sessions; the always-loaded file holds what shapes a first draft and what cannot be discovered by looking. A case that occurs once a year never belongs there; once a month, still not, perhaps a skill. Placement decides steering as much as length: the same text under-steered from `CLAUDE.md` and steered from the output style. The pointer's wording decides whether it fires; most under-use here was a description problem, fixed at the trigger, not the body. Use words the model already holds (smell names, seam, fog of war, tracer bullet) and test a word for what else it primes: a harness's own names mis-prime other harnesses and say nothing to the one that owns them, so skills describe the shape of a step, and a harness is named in exactly one place (the dispatch runner). Upstream kept one literal tool name for cross-skill invocation; mx keeps the neutral wording everywhere.


## 4. One home per fact

A fact written in two places is a copy, and the copy is the one nobody updates when the original changes. Process lives in the skills; a project artefact (a map, a ticket, a CLAUDE.md) records only where the project deliberately deviates from them. A wayfinder map note once restated the old one-question-at-a-time grilling rhythm, and for a whole session it overrode the upgraded skill. A summary keeps the name of a thing and loses its mechanism, so the primary source stays reachable: prototypes stay in-tree, a handoff file beats a compaction summary, a resumed worker is told "continue" rather than given a recap. Prototype verdicts once travelled through five hand-offs as winner-names ("the hybrid"), and the one ticket that linked the prototype's source was the one that came out precise. Superseded work is deleted or marked superseded; an artefact that still looks live teaches its old design to every later reader. The tests for all this are in writing-for-agents, under its Pruning heading.


## 5. Deliver through artefacts written for a cold reader, carrying the why

The chat and the return channel are not durable; a file is there whether or not the agent ended cleanly. A named subagent's full report once arrived as an empty idle ping and the parent redid the work; reviewers finished and ended their turn holding the report. So agents deliver to a named file, and a worklog is created up front so that emptiness itself is a reading. The reader has no conversation: the recurring slop in artefacts is conversation residue and cached facts, not style, and a ticket that under-describes its work misleads whoever reads it next. The destination and the reason come before the how: without the why the agent cannot suggest alternatives; a handoff without a stated purpose is refused; a commit body answers what the human wanted. If a thing cannot be said in plain words, it has not been decided.


## 6. Facts are the agent's to find; decisions are the human's to make

An unconfirmed decision stays marked; silence leaves it unconfirmed. A recommendation followed by the user moving to another topic once reached the ticket, the ADR, the glossary and the spec as a decision. Every claim carries provenance, and the agent's negative claims about the environment ("there is no test suite") are as unverified as its positive ones. A casual go-ahead ratifies proceeding, not the frame. An agent's statement of its own intent is self-certification. A question offers at least two options the agent would defend. The friction a worker hits is filed by the dispatcher after the user has ruled; the worker is the party least able to judge whether it is ticket-worthy. Human attention pays most at the plan: a wrong line of code is one wrong line, a wrong line in a plan becomes hundreds. Grilling is the station.


## 7. Judge in front of a render

Humans judge far better in front of a render than in the abstract; the artefact is the decision instrument and the conversation is its brief. A blank answer means the question was posed backwards: build the thing and let them criticise it. The person blank on "what goes in the sidebar" produced publishable criticism in front of a render, and a prototype overturned a grilled ticket and an ADR within a day. The leap from spec to production code is large and from working prototype to production is small. Taste enters at QA, by hand, per landed slice; the model cannot see what it is building. Orient routes user-visible surfaces to prototype-first; `/mx:show` and diffview are the same move for explanations and diffs.


## 8. Fresh context per unit of work

Reasoning degrades well before the advertised window is full, and an agent cannot introspect the degradation, so the limit is stated as a fraction rather than a feeling. An author is the wrong reviewer of its own diff, and a model is reluctant to change code sitting in its own context; a reviewer sharing the implementer's window reviews in the dumb zone. Repeated compaction leaves sediment; a handoff file is a deliberate reset that can be read and edited before it seeds the next session, and crosses harnesses. A different model family reviewing than the one that wrote is the strongest form. Ticket-sized fresh workers stay the unit of implementation; the coherence cost of isolation is carried by slicing (principle 9) and the review session.


## 9. Slice along seams that already exist

A unit of work that spans an owner boundary or a hub file is a serialisation signal, not a scheduling problem: the per-ticket isolation that keeps workers fresh is what produced the incoherence when twelve of twenty-nine tickets wrote into one file. Vertical slices, each demoable when it lands; the model codes horizontally by default. The breakdown is reviewed for its shape (slice count, size, verticality), which is cheap to check and whose failure is visible; the text is not. A property with no user story gets no slice, so the spec states properties. Interfaces are designed, implementations delegated; test boundaries follow module boundaries. Dispatch's coherence test (shared surface, serial worker) is this principle running.


## 10. Verify against the live system, and make every failure state distinguishable from success

Documentation describes what the author believed; the live system is the authority, and a rule is written after the run, not from the reading. The permission scanner documented the same wrong model as the docs; probing a live session turned 7445 phantom findings into 5876 real ones. A render loop caught two bugs in the SVG guide's own text. A working system is one that has been seen running; the rate of feedback is the speed limit. Every state the machinery can be in needs its own reading: a killed pane that still says running got a third state, an absent worklog is different from an empty one, a subagent ceiling reads like a crash until named. A hazard that moved rather than went away is a workaround, not a fix.


## 11. Isolate what runs unattended, and write its prompt for a machine

The human's decisions are front-loaded into grilling; everything that can run without a human runs without one; what needs judgment is surfaced afterwards in the form best suited to judging it (principle 7). Permission prompts and unsandboxed workers both put the human back into steps that should not need one. The isolation is the permission boundary: a worker installing a system dependency is doing unreviewed work outside its worktree on a machine nobody is watching, so an isolated host gets permissions bypassed and no credentials. The prompt is written for a reader with no conversation: the user's `CLAUDE.md` describes a conversation the worker is not in and tells it to ask questions it cannot ask. Scratch state is namespaced per feature and per repo; two dispatchers once collided. Reversibility gates autonomy: local and reversible runs freely; destructive, shared, or ship-shaped waits for the human.


## 12. Scale the process to the work

A step (grilling, review, a map) is skipped only when the change was dictated or needed no judgment; size and medium never decide it, because in this setup prose in skills and docs is the logic. Grilling triggers proportionally on any intent that is not fully mechanical: depth, not volume. A map is for fog, an idea that will not fit one session; reaching for it on well-scoped work is the common mistake. Optimise only the artefacts someone reads: the "sacrifice grammar for concision" line left Pocock's `CLAUDE.md` once he stopped reading plans. Ticket sizing is two-sided; too small pays an agent start per slice.


## 13. Own the stack

Observability over the whole planning stack is what turns "this isn't working" into a fix; a workflow whose pieces someone else owns cannot be tuned. The agent is the tactical programmer; the strategic level, architecture and what to build and when to invest in design, is the human's, and the agent is treated like a delegate on the team with unusual constraints. Twenty-year-old books already verbalised the practice in English (Brooks, Fowler, Ousterhout, the Pragmatic Programmer, Shape Up) and are the richest prompt material; bad code is the most expensive it has ever been, so design is invested in daily. Every piece of this stack is a script or a skill this repo can edit, released through one path. Mechanism that moves out of prose into a script stays visible: every command that changes something is echoed before it runs, so the transcript shows the primitives and any step can be redone by hand when something off-script comes up. Today's dispatch move is the positive example: per-ticket naming, worktree setup, spawn and cleanup left the orchestrator's prompt for `dispatch-ctl` and `dispatch`, taking a dozen chances to break the naming or the ordering with them, and the before/after transcript sits in `agent/show/dispatch-ctl-absorb/`.

