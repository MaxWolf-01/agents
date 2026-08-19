---
name: grilling
description: Grill the user about a plan, design, decision, or idea — proportionally: one question for a small ambiguity, a full interview for a feature. Invoke unprompted whenever the user states an intent that is not fully mechanical ("I want X, maybe like this") before implementing anything; also on any "grill" trigger phrase. Skip only when the request is fully specified and mechanical. The goal is a shared mental model and a default the user can just say yes to.
---

Interview the user relentlessly until you reach a shared understanding. Relentless is about depth, not volume: a small unclear intent gets one round of one or two questions; the full tree treatment below is for designs and features.

Map the design as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled — the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Each question is one decision, formatted like so:

```
❓ **Q1** — **<the decision, as a question>**
   ➡️ **(a)** <the option you recommend>
      **(b)** <option>
      **(c)** <option>

💡 <why you'd pick it, and what it costs>
```

The question line states the decision and nothing else. The arrow marks the winner where it sits, so no scanning; every reason, consequence and preference lives under the 💡, which is the skim path — reading only the 💡 lines tells the user what you would build. Labelled options make answering cheap (`q1 -> a`, sharpened where they disagree). A decision over an open range takes concrete candidate values as its options.

Offer only options you would defend. Two live options beat three padded with one you dismiss in the same breath. **One live option means it is not a question** — it is a fact to look up, or a call to make and state as an assumption. Ask a yes/no only when both sides are named and both are live; a question shaped "accept my proposal?" leaves the user rubber-stamping and turns the 💡 into "yes".

Entangled decisions split — `Q1` and `Q1b`, with the dependency named under the 💡 — or become combined options. Never one question carrying two halves.

Reach for a table instead when 3+ options differ along shared axes _and_ why-not-the-others is load-bearing: same `❓` line, then a row per option with the `➡️` on the recommended one, columns for the axes that separate them. Two options fit the default — a table's columns demand content, and a demanded cell gets filler.

Each round the user answers reshapes the tree — settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, web, tools), look it up rather than asking. A fact needing real investigation (external docs, APIs, knowledge bases) → fire a background `/mx:research` agent and keep grilling: only the questions that depend on its findings wait for a later round — ask the rest of the frontier now. A question only answerable — or better answered — by seeing or running something → propose a `/mx:prototype` detour, or ticket it if a wayfinder map is live. The _decisions_ are the user's — put each to them and wait.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.
