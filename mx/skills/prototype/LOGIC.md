# Logic Prototype

A single, self-contained HTML file that lets anyone drive a state model by clicking buttons. The shape for questions about **business logic, state transitions, or data shape**: what looks reasonable on paper and only feels wrong once pushed through real cases. One file with nothing to install is what lets a designer, a PM, or a domain expert feel the model for themselves, so it speaks their language, not the code's.

## Process

### 1. State the question

Before writing code, write down what state model and what question you're prototyping. One paragraph, at the top of the demo (in a visible intro, not just a comment), so the answer can be checked against it later, whether the user is watching now or returning to it AFK.

### 2. Isolate the logic in a portable module

Put the actual logic, the bit that's answering the question, in a single `<script>` block written as a small, pure module that could be lifted out and dropped into the real codebase later. The page around it is throwaway; this module isn't.

The right shape depends on the question:

- **A pure reducer**: `(state, action) => state`. Good when actions are discrete events and state is a single value.
- **A state machine**: explicit states and transitions. Good when "which actions are even legal right now" is part of the question.
- **A small set of pure functions** over a plain data type. Good when there's no implicit current state, just transformations.
- **A class or module with a clear method surface** when the logic genuinely owns ongoing internal state.

Pick whichever shape best fits the question being asked, _not_ whichever is easiest to wire to a page. Keep it pure: the page calls into it; nothing flows the other direction. A module that touches the DOM has stopped being liftable.

### 3. Build the shareable HTML file

One file, plain HTML/CSS/JS, everything inline so it opens by double-click and survives being emailed around.

Write it for a non-developer. Every label is in **domain language**, not code: buttons and state read like the business, not the reducer. Explain in plain words what's happening.

Lay it out with a clean hierarchy, top to bottom:

1. **Title and one-line explanation** of what this demo lets you explore (the question from step 1).
2. **Current state**: the full relevant state, rendered as a readable panel (labelled fields, not a raw JSON dump), re-rendered after every click so the change is visible. Where it helps a non-developer follow, call out what just changed.
3. **Free-play buttons**: one button per action, always available, so anyone can poke at the model in any order. Each click dispatches its action and re-renders the state.
4. **Guided walkthroughs**: a set of **scenarios**, one per tab. Each tab holds a short plain-language description of the scenario (the situation it sets up and what to watch for) and underneath it, the ordered **buttons to press** for that scenario. Each step is a real button: clicking it performs that action and moves to the next step. Starting a walkthrough resets to a known initial state so the scenario runs the same way every time.

Choose scenarios that demonstrate the awkward cases (the happy path, a tricky edge case, an attempt at something that should be illegal), the ones hard to reason about on paper.

Keep it beautiful but restrained: clean typography, generous spacing, one accent colour; nothing that competes with the state and the buttons.

### 4. Hand it over

Send them the file, or open it for them. The interesting moments are "wait, that shouldn't be possible" and "huh, I assumed X would be different": those are the bugs in the _idea_, which is the whole point. If they want new actions or a new scenario, add them.

### 5. Capture the answer and the prototype

Once the prototype has answered its question, capture the answer, then capture the prototype the way the [SKILL](SKILL.md) describes. The logic-specific mapping: the validated reducer / machine / function set lifts into the real module (the decision, absorbed); the HTML shell rides along to `agent/prototypes/`, where the prototype lives on as a primary source, and being one self-contained file, it stays trivially re-runnable there.
