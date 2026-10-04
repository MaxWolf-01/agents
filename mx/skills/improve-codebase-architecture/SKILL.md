---
name: improve-codebase-architecture
description: Scan a codebase for deepening opportunities, present them as a visual HTML report, then grill through its candidates in order of impact.
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities**: refactors that turn shallow modules into deep ones. The aim is testability and AI-navigability.

This command is _informed_ by the project's domain model and built on a shared design vocabulary:

- Run `/mx:codebase-design` for the architecture vocabulary (**module**, **interface**, **depth**, **seam**, **adapter**, **leverage**, **locality**) and its principles (the deletion test, "the interface is the test surface", "one adapter = hypothetical seam, two = real"). Use these terms exactly in every suggestion; don't drift into "component," "service," "API," or "boundary."
- The domain language in `GLOSSARY.md` gives names to good seams; ADRs in `decisions/` record decisions this command should not re-litigate.

## Process

### 1. Scan

**Scope before you scan: YAGNI.** Deepening a module pays off by making future changes to it easier, so put extra weight on the parts of the codebase that have recently changed. Decide *where* to look before you look:

- If the user named a direction (a module, a subsystem, a pain point), take it, and skip the inference below.
- Otherwise, walk back a good stretch of the commit history (`git log --oneline`, 30+ commits) to find the codebase's hot spots (the files and areas that keep coming up) and let those paths pull your attention first. If the changes are scattered with no clear hot spot, widen the net.

Read the project's domain glossary (`GLOSSARY.md`) and any ADRs in the area you're touching first.

Then walk the codebase. Don't follow rigid heuristics; explore organically and note where you experience friction:

- Where does understanding one concept require bouncing between many small modules?
- Where are modules **shallow**, with an interface nearly as complex as the implementation?
- Where have pure functions been extracted just for testability, but the real bugs hide in how they're called (no **locality**)?
- Where do tightly-coupled modules leak across their seams?
- Which parts of the codebase are untested, or hard to test through their current interface?
- Where does behaviour sit inside a decorated entry point (a route handler, a CLI command, a task), where every test of it pays the framework's setup?
- Which seams have a stated contract and no property checking it?
- Where does a seam's invariant resist being stated cleanly, or its test need heavy fakes? That is a finding about the seam, never a call for more test code.

Apply the **deletion test** to anything you suspect is shallow: would deleting it concentrate complexity, or just move it? A "yes, concentrates" is the signal you want.

The scan is done when every candidate carries:

- **Files**: which files/modules are involved
- **Problem**: why the current architecture is causing friction
- **Solution**: plain English description of what would change; the interface itself is designed in step 3, with the user
- **Benefits**: explained in terms of locality and leverage, and how tests would improve
- **Invariant**: what always holds at the new seam, and the check that states it (`/mx:testing`, Property tests). One that cannot be stated cleanly, or whose check needs heavy fakes, says the seam is not there yet
- **Dependency category**: which of the four in `/mx:codebase-design` the deepening falls into
- **Recommendation strength**: one of `Strong`, `Worth exploring`, `Speculative`
- **Impact**: what the deepening buys against what it costs, in one line; candidates are ordered by it, in the report and in the grilling. Strength is how sure you are the deepening holds, impact what it pays
- **ADR conflict**, when a candidate contradicts an existing ADR and the friction is real enough to warrant revisiting it: _"contradicts ADR-0007, but worth reopening because…"_. Don't list every theoretical refactor an ADR forbids.
- **Related candidates**, when it hangs together with others: it builds on one, or two are the same deepening seen from two sides and belong in one piece of work.

**Use GLOSSARY.md vocabulary for the domain, and the `/mx:codebase-design` vocabulary for the architecture.** If `GLOSSARY.md` defines "Order," talk about "the Order intake module", not "the FooBarHandler," and not "the Order service."

### 2. Build the report

Fork (`/mx:fork`) to build it: the fork inherits the scan's reading, and the build loop stays out of this session, which grills from that same reading in step 3. The fork's directive: build the report [REPORT.md](REPORT.md) describes.

### 3. Grilling loop

When the report lands, run `/mx:grilling` through its candidates in the report's order, one grilling and one ticket per candidate or group of related ones; the user's comments on the report pick, drop or reorder them. Each grilling walks the decision tree with them: constraints, dependencies, the shape of the deepened module, what sits behind the seam, what tests survive.

Side effects happen inline as decisions crystallize; run `/mx:domain-modelling` to keep the domain model current as you go:

- **Naming a deepened module after a concept not in `GLOSSARY.md`?** Add the term to `GLOSSARY.md`. Create the file lazily if it doesn't exist.
- **Sharpening a fuzzy term during the conversation?** Update `GLOSSARY.md` right there.
- **User rejects the candidate with a load-bearing reason?** Offer an ADR, framed as: _"Want me to record this as an ADR so future architecture reviews don't re-suggest it?"_ Only offer when the reason would actually be needed by a future explorer to avoid re-suggesting the same thing; skip ephemeral reasons ("not worth it right now") and self-evident ones.
- **Want to explore alternative interfaces for the deepened module?** Run `/mx:codebase-design` and use its design-it-twice parallel sub-agent pattern.
