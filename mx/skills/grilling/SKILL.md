---
name: grilling
description: "Grill the user about a plan, design, decision, or idea, proportionally: one question for a small ambiguity, a full interview for a feature, whose design lands in the spec as it settles. Invoke unprompted whenever the user states an intent that is not fully mechanical (\"I want X, maybe like this\") before implementing anything; also on any \"grill\" trigger phrase. Skip only when the request is fully specified and mechanical. The goal is a shared mental model and a default the user can just say yes to."
---

Interview the user relentlessly until you reach a shared understanding. Relentless is about depth, not volume: a small unclear intent gets one round of one or two questions; the full treatment below is for designs and features.

Map the design as a **design tree**: every decision branches into the decisions that hang off it. The **frontier** is every decision whose prerequisites are already settled: what can be decided _now_ without guessing at answers you haven't heard yet. Work the tree in **rounds**: each round delivers the design as it stands and the frontier's open questions, then waits for the user's answers.

## The round

**The design first.** One coherent whole, as it currently stands, sketched past the frontier to the leaves under your best calls, so the user judges shape and consequences instead of reconstructing them from answers. Every call carries who made it: `(you, rN)` settled by the user in round N (`(you, <ticket name>)` when a wayfinder ticket settled it), `(my call)` yours and vetoable, `(open → Qn)` put to a question below, `(fog)` where nothing can be sketched yet. Argue each call as the best expert in that field would: what they'd concretely choose here, what they'd reject about your current pick and why; make the call that expert would judge correct, never the one that satisfies the stated constraints most cheaply.

When more than one design survives that bar, deliver each with the questions that refine it, then the questions that choose between them: the trade-offs one pays and the other doesn't. That second level is where the framing of the problem gets decided explicitly, since rival designs usually embody rival readings of it. A rival whole joins only under the same bar as an option: one you would defend.

**Then the questions**, only where two live options survive expert judgment. Each names the part of the design it would change, and that part carries its `(open → Qn)` mark: a question's decision is always visible in the design.

```
❓ **Q1**: **<the decision, as a question>**
   ➡️ **(a)** <the option you recommend>
      **(b)** <option>
      **(c)** <option>

💡 <why you'd pick it, and what it costs, argued as the best expert in the field would>
```

The question line states the decision and nothing else. The arrow marks the winner where it sits, so no scanning; every reason, consequence and preference lives under the 💡. Labelled options make answering cheap (`q1 -> a`, sharpened where they disagree). A decision over an open range takes concrete candidate values as its options.

Offer only options you would defend. Two live options beat three padded with one you dismiss in the same breath. **One live option means it is not a question**: it is a fact to look up, or a call to make in the design and mark as yours. Ask a yes/no only when both sides are named and both are live; a question shaped "accept my proposal?" leaves the user rubber-stamping.

Entangled decisions split (`Q1` and `Q1b`, with the dependency named under the 💡) or become combined options. Never one question carrying two halves. Reach for a table when 3+ options differ along shared axes _and_ why-not-the-others is load-bearing: same `❓` line, a row per option with the `➡️` on the recommended one, columns for the axes that separate them. Two options fit the default: a table's columns demand content, and a demanded cell gets filler.

**The answers.** The user reacts to the whole: vetoes or amends calls by name, answers questions by number. A `(my call)` the user has not ruled on stays unconfirmed and is re-listed at the end of every round until they rule on it or ratify the rest in one word; silence never ratifies. Each round's answers reshape the tree: settled decisions push the frontier outward and unblock what depended on them. Recompute the frontier and deliver the next round. A question whose answer depends on another still open belongs to a later round.

## The spec

In a repo, the design lives in the spec from the first round that has one, published per `/mx:tracker` (`agent/tasks/<slug>/spec.md` on the markdown backend), frontmatter `status: draft`, in the shape of [SPEC-FORMAT.md](SPEC-FORMAT.md); user stories grow from round one, since that is where misunderstandings show. Rewrite it at the end of each round (skip a round when you must clarify first or the picture is mid-flip), open it on the review surface (`diffview --watch HEAD..`) so the user reads this round's delta rather than the whole document, and commit the round's state when the answers arrive, on the branch that carries this grilling in a worktree of its own, merged `--no-ff` so the integration branch shows one entry. The draft changes only through a round the user is in: a research finding or a prototype verdict is proposed in a round before it lands in the file. The spec stays textual; a visual that would help a round is a `/mx:show` artefact, linked or embedded. Outside a repo, the design is a section of the message instead.

A standalone task (`agent/tasks/<slug>.md`) that gets grilled is absorbed: its text becomes the problem statement. Then the file is deleted, unless another task blocks on its slug or it should stay on the frontier for a worker: then it moves into the directory as `01-<slug>.md`, and every `blocked-by` naming the old slug (grep `agent/tasks/`) is repointed to `<slug>/01`.

## Facts and decisions

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, web, tools), look it up rather than asking. A fact needing real investigation (external docs, APIs, knowledge bases) → fire a background `/mx:research` agent and keep grilling: only the questions that depend on its findings wait for a later round; ask the rest of the frontier now. A question only answerable, or better answered, by seeing or running something → propose a `/mx:prototype` detour, or ticket it if a wayfinder map is live. The _decisions_ are the user's: put each to them and wait.

## The gate

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Bring the draft current, then walk the unconfirmed list with the user; when they confirm the understanding is shared, strip the markers and set `status: confirmed`. Only then comes the size call: build from the spec in this session, or `/mx:to-tickets` when the work goes to the frontier (workers, parallel or later sessions). Do not act before that confirmation. Capturing what was settled (glossary terms, decisions worth an ADR) goes through `/mx:domain-modelling`; the spec references ADRs, it doesn't restate them.
