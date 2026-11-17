---
name: grilling
description: "Grill the user about a plan, design, decision, or idea, proportionally: one question for a small ambiguity, a full interview for a large design, whose design lands in the ticket as it settles, over as many sessions as the frontier takes. Invoke unprompted on fog, an intent too unclear to draft a brief for. Also on any \"grill\" trigger phrase. The goal is a shared mental model and a default the user can just say yes to."
---

Interview the user relentlessly until you reach a shared understanding. Relentless is about depth, not volume: a small unclear intent gets one round of one or two questions; the full treatment below is for a whole design.

Map the design as a **design tree**: each decision branches into the decisions that hang off it. The **frontier** is every decision whose prerequisites are settled, so it can be decided _now_ without guessing at answers you have not heard yet. Work the tree in **rounds**: each round delivers the design as it stands and the frontier's open questions as one message, then waits for the user's answers.

## The round

**A big idea's first round is breadth-first**: cover the whole space before going deep on any thread, so the frontier and the fog both show from round one.

**The design first.** One coherent whole as it stands, sketched past the frontier to the leaves under your best calls, so the user judges shape and consequences rather than reconstructing them from answers. Every call carries its **call mark**, who made it: `(you, rN)` settled by the user in round N, `(my call)` yours and vetoable, `(open → Qn)` put to a question below, `(fog)` where nothing can be sketched yet. Sharpen the design before you deliver it (`/mx:sharpen`), so each call is the one the best expert in that field would make.

When more than one design survives that bar, deliver each with the questions that refine it, then the questions that choose between them by the trade-offs one pays and the other does not. A rival design joins only if you would defend it, the same bar as an option.

**Then the questions**, only where two live options survive expert judgment. They lean to the intent, what gets built, since you fill in an implementation better than the user does. How far the intent reaches depends on what is grilled: for one function it is that function's trade-offs; in a larger design some of the architecture, algorithms and data structures belong to it too. Each question names the part of the design it would change, and that part carries its `(open → Qn)` mark, so every question's decision is visible in the design.

Each question's headline states the decision and nothing else. Ask only where two true experts would argue over the options, a genuine trade-off; where there is one proper way, the call is yours and no question is asked. The options the user named are points in the solution space, never its edges: map the space an expert would see before choosing which options to offer. Offer only options you would defend, none marked as yours, each arguing for itself in what it leads to, gives and costs, as the best expert in the field would argue it. Two live options beat three padded with one you dismiss in the same breath. **One live option means it is not a question**: it is a fact to look up, or a call to make in the design and mark as yours. Ask a yes/no only when both sides are named and both are live; a question shaped "accept my proposal?" leaves the user rubber-stamping. Labelled options make answering cheap (`Q1: a`, sharpened where they disagree). A decision over an open range takes concrete candidate values as its options.

Entangled decisions split (`Q1` and `Q2`, the dependency named in the second's detail line) or become combined options. Use a table, in the question's `Recap:`, when 3+ options differ along shared axes _and_ why-not-the-others is load-bearing: a row per option, a column per axis that separates them. Two options stay options without a table, since a table with so little to compare gets padded with filler.

**A blind test** replaces a question of taste (wording, naming, an output format, a UI) whose two options can each make three or more samples of the same things: the user picks between samples without knowing which option made which, so your pick cannot anchor them. Make both sides of every pair the same way, both run or both written by hand, since a real sample beside a written one is a tell. Write the pairs file `blind-test --help` describes, render it, and ask the question as a blind one, so the page holds your pick, if you have one. The answer line the user pastes back names each pair's pick; the pairs that went against the majority are the next round's material.

**The answers.** The user reacts to the whole: vetoes or amends calls by name, answers questions by number. A `(my call)` stays marked in the design, unconfirmed, until the user rules on it; the mark is the whole of its asking, so no line of a round lists calls for the user to acknowledge, and silence never ratifies. Where a call reached the design, an ADR or the glossary without the user's ruling, put its unconfirmed mark back yourself rather than reporting it for the user to pass on.

## Terms and figures

Run `/mx:domain-modelling` throughout the grilling: challenge terms and settle them into the glossary, and offer an ADR where a decision meets its bar, as the rounds go.

A decision a figure shows better than prose arrives as one (`/mx:show`), drawn in the round that states it, rebuilt in the round that moves it and removed in the round that drops it.

## Facts and decisions

Finding _facts_ is your job, never the user's. For a fact that needs real investigation (external docs, APIs, knowledge bases), fire a background `/mx:research` agent and keep grilling: only the questions that depend on its findings wait for a later round. A question only answerable, or better answered, by seeing or running something gets a `/mx:prototype`.

## Fog and scope

`(fog)` marks in-scope work whose question cannot yet be stated, written as loosely or as fully as the view allows. Leave fog uncut: it is coarser than a slice, one patch may graduate into several tickets or none once an answer sharpens it, and only a resolved question graduates fog.

The brief fixes the scope: work past it is out of scope, not fog; a part found to sit past it is dropped and never graduates.

## The frontier empties

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed.
