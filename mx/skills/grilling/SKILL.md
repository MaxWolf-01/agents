---
name: grilling
description: Grill the user about a plan, design, decision, or idea — proportionally: one question for a small ambiguity, a full interview for a feature. Invoke unprompted whenever the user states an intent that is not fully mechanical ("I want X, maybe like this") before implementing anything; also on any "grill" trigger phrase. Skip only when the request is fully specified and mechanical. The goal is a shared mental model and a default the user can just say yes to.
---

Interview the user relentlessly until you reach a shared understanding. Relentless is about depth, not volume: a small unclear intent gets one round of one or two questions; the full tree treatment below is for designs and features.

Map the design as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled — the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Each question should be formatted like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Each round the user answers reshapes the tree — settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, web, tools), look it up rather than asking. A fact needing real investigation (external docs, APIs, knowledge bases) → fire a background `/mx:research` agent and keep grilling: only the questions that depend on its findings wait for a later round — ask the rest of the frontier now. A question only answerable — or better answered — by seeing or running something → propose a `/mx:prototype` detour, or ticket it if a wayfinder map is live. The _decisions_ are the user's — put each to them and wait.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.
