---
name: grilling
description: "Grill the user about a plan, design, decision, or idea, proportionally: one question for a small ambiguity, a full interview for a large design, whose design lands in the ticket as it settles, over as many sessions as the frontier takes. Invoke unprompted on fog, an intent too unclear to draft a brief for. Also on any \"grill\" trigger phrase. The goal is a shared mental model and a default the user can just say yes to."
---

Interview the user relentlessly until you reach a shared understanding. Relentless is about depth, not volume: a small unclear intent gets one round of one or two questions; the full treatment below is for a whole design.

Map the design as a **design tree**: every decision branches into the decisions that hang off it. The **frontier** is every decision whose prerequisites are already settled: what can be decided _now_ without guessing at answers you haven't heard yet. Work the tree in **rounds**: each round delivers the design as it stands and the frontier's open questions as one message, then waits for the user's answers.

## The round

**A big idea's first round is breadth-first**: fan out across the whole space before going deep on any thread, so the frontier and the fog are both visible from round one and the questions that are already sharp separate from the ones that are not.

**The design first.** One coherent whole, as it currently stands, sketched past the frontier to the leaves under your best calls, so the user judges shape and consequences instead of reconstructing them from answers. Every call carries its **call mark**, who made it: `(you, rN)` settled by the user in round N, `(my call)` yours and vetoable, `(open → Qn)` put to a question below, `(fog)` where nothing can be sketched yet. Sharpen the design before you deliver it (`/mx:sharpen`), so each call is the one the best expert in that field would make.

When more than one design survives that bar, deliver each with the questions that refine it, then the questions that choose between them: the trade-offs one pays and the other doesn't. That second level is where the framing of the problem gets decided explicitly, since rival designs usually embody rival readings of it. A rival whole joins only under the same bar as an option: one you would defend.

**Then the questions**, only where two live options survive expert judgment. They lean to the intent, what gets built, since the agent fills in an implementation better than the user does. How far the intent reaches depends on what is grilled: a grilling of one function is about that function's trade-offs, and in a larger one some of the architecture, algorithms and data structures belong to the intent too. Each names the part of the design it would change, and that part carries its `(open → Qn)` mark: a question's decision is always visible in the design.

Each question's headline states the decision and nothing else. Ask only where two true experts would argue over the options, a genuine trade-off; where there is one proper way, the call is yours to make, and no question is asked. Mark no option as yours. Each option argues for itself in what it leads to, gives and costs, as the best expert in the field would argue it. Labelled options make answering cheap (`q1 -> a`, sharpened where they disagree). A decision over an open range takes concrete candidate values as its options.

Offer only options you would defend. Two live options beat three padded with one you dismiss in the same breath. **One live option means it is not a question**: it is a fact to look up, or a call to make in the design and mark as yours. Ask a yes/no only when both sides are named and both are live; a question shaped "accept my proposal?" leaves the user rubber-stamping.

Entangled decisions split (`Q1` and `Q2`, with the dependency named in the second's detail line) or become combined options. Never one question carrying two halves. Reach for a table when 3+ options differ along shared axes _and_ why-not-the-others is load-bearing: in the question's `Recap:`, a row per option, columns for the axes that separate them. With only two options, write them as options and skip the table, since a table with so little to compare gets padded with filler.

**A blind test** takes the place of a question of taste (wording, naming, an output format, a UI) whose two options can each make three or more samples of the same things: the user picks between samples without knowing which option made which, so your pick cannot anchor them. Make both sides of every pair the same way, both run or both written by hand, since a real sample beside a written one is a tell. Write the pairs file `blind-test --help` describes, render it, and ask the question as a blind one, so the page holds your pick; leave the pick out where you have none. The answer line the user pastes back names each pair's pick; the pairs that went against the majority are the next round's material. The user can ask for one on any question.

**The answers.** The user reacts to the whole: vetoes or amends calls by name, answers questions by number. A `(my call)` the user has not ruled on stays marked in the design, unconfirmed, until they rule on it; the mark is the whole of its asking, so no line of a round lists the calls for the user to acknowledge, and silence never ratifies. A call that reached the design, an ADR or the glossary without the user ruling on it gets its unconfirmed mark back, put there by you, not reported to the user to pass on. Each round's answers reshape the tree: settled decisions push the frontier outward and unblock what depended on them. Recompute the frontier and deliver the next round. A question whose answer depends on another still open belongs to a later round.

## Terms and figures

The grilling runs with `/mx:domain-modelling` throughout: terms are challenged and settled into the glossary, and an ADR offered where a decision meets its bar, as the rounds go.

A decision a figure shows better than prose arrives as one (`/mx:show`), drawn in the round that states it, rebuilt in the round that moves it and removed in the round that drops it.

## Facts and decisions

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, web, tools), look it up rather than asking. A fact needing real investigation (external docs, APIs, knowledge bases) → fire a background `/mx:research` agent and keep grilling: only the questions that depend on its findings wait for a later round; ask the rest of the frontier now. A question only answerable, or better answered, by seeing or running something → propose a `/mx:prototype` detour.

## Fog and scope

`(fog)` marks in-scope work whose question cannot yet be stated, written as loosely or as fully as the view allows. Fog is coarser than a slice: leave it uncut, since one patch graduates into several tickets, or none, once an answer sharpens it, and resolving a question is the only thing that graduates fog.

The brief fixes the scope: work past it is out of scope, not fog; a part found to sit past it is dropped and never graduates.

## The frontier empties

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed.

