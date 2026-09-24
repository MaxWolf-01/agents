---
name: grilling
description: "Grill the user about a plan, design, decision, or idea, proportionally: one question for a small ambiguity, a full interview for a large design, whose design lands in the ticket as it settles, over as many sessions as the frontier takes. Invoke unprompted whenever the user states an intent that is not fully mechanical (\"I want X, maybe like this\") before implementing anything; also on any \"grill\" trigger phrase. Skip only when the request is fully specified and mechanical. The goal is a shared mental model and a default the user can just say yes to."
---

Interview the user relentlessly until you reach a shared understanding. Relentless is about depth, not volume: a small unclear intent gets one round of one or two questions; the full treatment below is for a whole design.

Map the design as a **design tree**: every decision branches into the decisions that hang off it. The **frontier** is every decision whose prerequisites are already settled: what can be decided _now_ without guessing at answers you haven't heard yet. Work the tree in **rounds**: each round delivers the design as it stands and the frontier's open questions, then waits for the user's answers.

## The round

**A big idea's first round is breadth-first**: fan out across the whole space before going deep on any thread, so the frontier and the fog are both visible from round one and the questions that are already sharp separate from the ones that are not.

**The design first.** One coherent whole, as it currently stands, sketched past the frontier to the leaves under your best calls, so the user judges shape and consequences instead of reconstructing them from answers. Every call carries its **call mark**, who made it: `(you, rN)` settled by the user in round N (`(you, <slug>)` when the answer came from another ticket), `(my call)` yours and vetoable, `(open → Qn)` put to a question below, `(fog)` where nothing can be sketched yet. Argue each call as the best expert in that field would: what they'd concretely choose here, what they'd reject about your current pick and why; make the call that expert would judge correct, never the one that satisfies the stated constraints most cheaply.

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

**The answers.** The user reacts to the whole: vetoes or amends calls by name, answers questions by number. A `(my call)` the user has not ruled on stays unconfirmed and is re-listed at the end of every round until they rule on it or ratify the rest in one word; silence never ratifies. A call that reached the ticket, an ADR or the glossary without the user ruling on it gets its unconfirmed mark back, put there by you, not reported to the user to pass on. Each round's answers reshape the tree: settled decisions push the frontier outward and unblock what depended on them. Recompute the frontier and deliver the next round. A question whose answer depends on another still open belongs to a later round.

## The ticket

In a repo, the design lives in a ticket from the first round that has a design to write, in the shape `/mx:tracker`'s MARKDOWN.md gives the body; user stories grow from round one, since that is where misunderstandings show. A ticket the conversation started from is the one that grows, and where it started from none, `tracker new` files it: grilling adds the sections the design fills, and never a second file. Rewrite it at the end of each round (skip a round when you must clarify first or the picture is mid-flip), open it on the review surface (`diffview --watch --open <base>.. -o agent/diffviews/<slug>-grilling.html`: `<base>` is the previous round's commit, or `<integration>...` in round one; the pinned sha keeps the page whole across the round's commits, the fixed path keeps the comments across rounds) so the user reads this round's delta rather than the whole document or the whole branch, and commit the round's state when the answers arrive, on a branch named after the ticket, in a worktree of its own, merged `--no-ff` so the integration branch shows one entry. The ticket changes only through a round the user is in: a research finding or a prototype verdict is proposed in a round before it lands in the file. Outside a repo, the design is a section of the message instead.

A decision of a shape `/mx:show`'s table lists arrives as its figure, drawn in the round that states it, re-rendered in the round that moves it and removed in the round that drops it, its source under `agent/show/<slug>/` and in the round's commit beside the ticket. The session opens the figure (`claude-browser`, else `xdg-open`) before the round's message goes out, and that message says so in its first line instead of narrating what the figure shows.

## Facts and decisions

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, web, tools), look it up rather than asking. A fact needing real investigation (external docs, APIs, knowledge bases) → fire a background `/mx:research` agent and keep grilling: only the questions that depend on its findings wait for a later round; ask the rest of the frontier now. A question only answerable, or better answered, by seeing or running something → propose a `/mx:prototype` detour, or file it as a child ticket the prototype answers when the detour cannot run in this session. The _decisions_ are the user's: put each to them and wait.

## Fog and scope

`(fog)` marks in-scope work whose question cannot yet be stated; it lives in the ticket's Fog section, written as loosely or as fully as the view allows. A question that can be stated is a child ticket, even while it is blocked. Fog is coarser than a slice: leave it uncut, since one patch graduates into several tickets, or none, once an answer sharpens it, and resolving a question is the only thing that graduates fog.

The brief fixes the scope: work past it is out of scope, not fog; a part found to sit past it is dropped, with one line in Out of scope giving the reason, and never graduates.

## The frontier empties

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Bring the ticket current; one that several sessions wrote is read whole once first, because each session saw only its part and the parts can disagree. Then cut it into child tickets (`/mx:tracker`, SLICING.md), or build it as it stands when it is one slice. A question the design does not hinge on, one that is naturally its own work, leaves as a child ticket so the rest can be cut; one the design hinges on holds the cut.

The marks stay on until the user rules. Walk the unconfirmed list with them whenever they are there: what they ratify loses its mark. What they have not ruled on travels into the child tickets as the assumptions their workers carry, anchored to the lines they shape, and the user rules on it from the review page of what it built; a mark is stripped when they do, in whichever session is holding the ticket. Capturing what was settled (glossary terms, decisions worth an ADR) goes through `/mx:domain-modelling`; the ticket references ADRs, it doesn't restate them.

## Across sessions

Nobody decides up front whether a grilling fits one session; the frontier either drains or it doesn't. When a session ends with questions still open, they leave the conversation as child tickets carrying `needs-user`, filed `open` since the user asked for the answer by leaving the question standing (`/mx:tracker`): questions that share their context go in one ticket, sized to one session of grilling. Such a ticket carries the questions with their options as the last round put them (the recommendation and its argument too, when the round had one) and names the sections its answers may rewrite; like any ticket it gets a priority, a size, a short name and a brief, the priority from how soon the user wants what the answer unblocks. The parent ticket's `(open → Qn)` marks become `(open → <slug>)`, and `(fog)` stays in Fog.

A fresh session reads the ticket top-down: Brief, the marks (in Decisions and wherever else they sit), Fog, plus its open child tickets; the middle sections when one of them touches them. It claims a child ticket per `/mx:tracker`, reads its Comments first (the answer, or the user's instinct about it, may already sit there), and grills it as a round like any other. The answer lands on the parent ticket as the user gave it (their reason when they gave one, none invented), each call marked `(you, <slug>)`, and the reasoning in the child ticket's Comments; the sections it named are rewritten in the same session.
