---
name: writing-for-agents
description: "Writing documents for agents. Use when creating or editing any document agents consume: skills, AGENTS.md/CLAUDE.md, tickets, ADRs, reusable prompts, or docs agents build from, including README.md"
---

When the document is a skill, also read [`SKILL-MECHANICS.md`](SKILL-MECHANICS.md) for frontmatter, invocation choice and router skills.

## Context pointers

A **context pointer** is a reference in the agent's context that names material outside it and encodes the condition for reaching it: a skill's description, or a line in `AGENTS.md` naming a doc. The pointer's _wording_, not its target, decides when the agent reaches the material, and how reliably. A must-have target behind a weakly worded pointer is a variance bug: sharpen the wording first, and inline the material only if that fails.

A pointer states what the material is and lists the **branches** that should trigger reaching it (a branch is a distinct case the document handles, so different runs take different paths through it). An always-loaded pointer costs on every turn, so prune it harder than the body:

- **Front-load the leading word**: the pointer is where it triggers.
- **One trigger per branch.** Synonyms that rename one branch collapse into one trigger.
- **Cut identity the body already carries.**

## The two loads

Every document and pointer you add spends one of two budgets:

- **Context load**: what always-loaded material (an `AGENTS.md` line, a skill description) costs the agent's window in tokens and attention on every turn, whether or not it fires.
- **Cognitive load**: what the human must hold, which documents exist and when to reach for each; the human is the index. It is the price of human agency rather than a cost to minimise: spend it where human judgement matters and remove it where it does not.

Material reached only through a pointer escapes context load at the price of the pointer's own line; material with no pointer at all rides entirely on cognitive load.

## Information hierarchy

A document mixes two content types freely: **steps**, the ordered actions the agent performs, and **reference**, the definitions, rules and facts it consults on demand. The core decision is where each piece sits on the **information hierarchy**, a ladder ranked by how immediately the agent needs it:

1. **In-file step**: what the agent does, in order; the primary tier.
2. **In-file reference**: consulted on demand. A flat peer-set (every rule of a review on one rung) is a fine arrangement, not a smell.
3. **Disclosed reference**: in a separate file behind a context pointer, loaded only when the pointer fires.

Push too little down and the top bloats; push too much and you hide material the agent needs.

**Progressive disclosure** moves material down the ladder, out of the main file and behind a pointer, so the top stays legible. Branching is the cleanest test: inline what every branch needs, and disclose what only some branches reach. Reference that should be disclosed buries a document's steps and makes attending to them a coin-flip, so disclosure is a variance lever as well as a legibility one.

**Co-location** decides what sits beside a piece once the ladder has placed it: keep a concept's definition, rules and caveats under one heading, so reading one part brings its neighbours. The test is that the document reads like documentation written for the agent.

**Sprawl** is a document too long even when every line is live and unique: attention thins across the excess. Cure it with the ladder: disclose reference behind pointers, and split by branch or sequence so each path carries only what it needs.

## Steps and completion criteria

Every step ends on a **completion criterion**, the condition that tells the agent the step is done. Two properties make it a lever:

- **Clarity**: can the agent tell done from not-done? A vague bound ("understanding reached") invites **premature completion**, ending the step before it is done, pulled by the visible steps ahead, the **post-completion steps**; a clear criterion resists the pull. **Sharpen the bound first**, since that is local and cheap. Only if it is irreducibly fuzzy _and_ you have observed the rush, hide the later steps by splitting the sequence across a real context boundary (a hand-off or a subagent dispatch); an inline call leaves the later steps in context.
- **Demand**: how much it requires. "Every modified model accounted for" forces thorough work where "produce a change list" does not. Demand drives **digging**, the work a step's wording implies without writing it as its own step. It binds reference as well as steps: "every rule applied" gives an all-reference document its exhaustiveness bar, as "every step done" does a sequence.

## When to split

Splitting one document into two spends one of the two loads, so split only when the cut earns it:

- **By sequence**: split a run of steps where the post-completion steps tempt the agent to rush the current one; out of view, they leave more digging on it. Merging sequences does the reverse and invites premature completion.
- **By invocation**: skill-specific; see [`SKILL-MECHANICS.md`](SKILL-MECHANICS.md).

## Leading words

A **leading word** is a compact concept from the model's pretraining that the agent thinks with while running the document (_lesson_, _fog of war_, _tracer bullets_). Repeated as a token, never as a sentence, it accumulates a distributed definition and anchors a region of behaviour in the fewest tokens by recruiting priors the model already holds. Reach for an existing word first: a coined word works if you define it clearly, but recruits no priors, so you pay in definition tokens what a pretrained word gives free.

It anchors twice. In the body it anchors _execution_: the agent reaches for the same behaviour wherever the word appears, and inside flat reference it names a class of thing to look for. In a pointer it anchors _invocation_: when the same word runs through your prompts, your docs and your codebase, the agent links that shared language to the material and reaches it more reliably.

Hunt for passages a leading word can collapse into a single token, such as a triad spelled out at three sites or a pointer spending a sentence on one idea, and assume every document carries some:

- "fast, deterministic, low-overhead" → _tight_ (a _tight_ loop).
- "a loop you believe in" → _red_: a fuzzy gate becomes a binary observable state (the loop goes _red_ on the bug, or it doesn't).

Test a word for what else it primes: _branches_ in a planning skill made git-aware models create git branches, and became _modes_. A harness's own names (its spawn tool, an agent-type name) are a no-op for the harness that owns them, which already knows its own mechanism, and a mis-prime for every other. Describe the shape of the step instead ("spawn three subagents in parallel", "hand this to a fresh context"), and name a mechanism only where the neutral form demonstrably misfires, in one place.

**Negation**, steering by prohibition, drags the forbidden behaviour into context and makes it _more_ available. Prompt the **positive**: state the target behaviour ("write one-line comments") so the banned one goes unspoken. A prohibition earns its place only as a hard guardrail you cannot phrase positively, and even then is paired with the positive target so attention lands on what to do.

## Pruning

- Keep each meaning in a **single source of truth**, so changing the behaviour is a one-place edit. **Duplication**, the same meaning in more than one place, costs maintenance and tokens, and lifts a meaning's prominence on the ladder past its real rank.
- The **environment** is a source of truth too (`package.json` scripts, config files, the directory layout, `--help` output), and a document that restates it is a **cache**, worth its load only when the lookup is expensive. Write down what the agent cannot find by looking: the unwritten convention, the reason behind a choice, the gotcha no config confesses. Leave one-file, one-command lookups to the environment, where they cannot go stale.
- Check every line for **relevance**: does it still bear on what the document does? A line loses relevance by never bearing on the task (exposition, or a branch that should be disclosed) or by going stale as the behaviour or world it describes changes. Unpruned, a document collects **sediment**: stale layers that settle because adding feels safe and removing feels risky.
- Hunt **no-ops** sentence by sentence: an instruction the model already obeys by default pays load to say nothing. The test, whether it changes behaviour against the default, is model-relative, not reader-relative: two people who disagree about a no-op disagree about the default, and settle it by running the document. Delete a failing sentence whole rather than trimming words from it. A leading word too weak to beat the default (_be thorough_ when the agent is already thorough-ish) is a no-op too. Where the default falls short, the fix is demand, not volume: a criterion that names what thorough covers ("every caller read"), since a louder intensifier makes current models over-apply it everywhere it reaches.
