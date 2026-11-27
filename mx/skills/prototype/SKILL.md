---
name: prototype
description: Build a throwaway prototype to answer a design question. Use when several designs have to be compared, or when a state model, a piece of logic or a UI has to be seen or driven before anyone can judge it.
---

# Prototype

A prototype is **throwaway code that answers a question**. The question decides the shape.

It earns its detour on **rival shapes**: several designs to compare, or one that has to be seen or driven before anyone can judge it. A design with one clear shape goes straight to the build and is judged as the thing itself; prototyping it first is a slower way of implementing it.

## Pick a branch

- **"Does this logic / state model feel right?"** → a state chart with a runnable artefact that drives the model through the cases hard to reason about on paper (`/mx:show`), or, where it has to be driven by hand, a plain prototype under the rules below.
- **"What should this look like?"** → [UI.md](UI.md). Radically different UI variations on one route, switched by a URL search param and a floating bottom bar.

Where the question fits both and the user isn't reachable, take the branch the surrounding code suggests (a backend module → logic; a page or component → UI) and state the assumption at the top of the prototype.

## Rules that apply to both

1. **Throwaway from day one, and clearly marked as such.** Put the code next to the module or page it prototypes for, and name it so a casual reader sees it is a prototype, not production.
2. **Trivial to run.** A UI prototype starts from one command in the project's task runner: `pnpm <name>`, `uv run <path>`, `bun <path>`, etc. A logic prototype is one script or one file the user opens.
3. **No persistence by default.** State lives in memory. Persistence is the thing the prototype is _checking_, not something it should depend on. Where the question involves a database, use a scratch DB or a local file named plainly "PROTOTYPE: wipe me".
4. **Skip the polish.** No tests, no error handling beyond what makes the prototype _runnable_, no abstractions.
5. **Surface the state.** After every action (logic) or on every variant switch (UI), print or render the full relevant state so the user can see what changed.
6. **Decisions stay the user's.** A prototype produces observations and options. Put each design or architecture choice to the user and record *their* answer; in any notes you commit, label your own rankings and recommendations as proposals.
7. **Capture it when done.** Write `ANSWER.md` in the prototype's directory: the question, what was tried, and the user's verdicts as given in the session (proposals labeled as proposals, per rule 6). Phrase each verdict as a **rule with its reason** ("blue = wake surface and nothing else"; "three per-level layouts were bewildering"), not as a winner's name alone: a name compresses screenshots the next agent will never see. Then move the prototype out of the production tree to where the project keeps its prototypes. The session that asked the question (grilling, implementation) reads `ANSWER.md` and folds its decisions into the durable artefacts (ADR, ticket, code), each with a pointer to the prototype.
8. **Floor promotion, on the user's word only.** By default only the prototype's verdicts travel; its craft binds nothing, and the real implementation may look different. When the user says they like the shape or feel of the artifact itself ("make this the floor"), record in `ANSWER.md` which aspect is now the **floor**, the minimum-quality reference, for which surface: implementers match it or consciously beat it, and its incidental slop is not part of it. Commit the script or command that regenerates its screenshots; the screenshots themselves stay gitignored.
9. **Pin what loads from the internet.** A script the prototype loads by URL names an exact version and carries an `integrity` hash, the way `/mx:show` says under Produce and present.
