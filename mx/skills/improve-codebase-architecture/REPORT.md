# Report

What the page carries; `/mx:show` builds it.

- **Header**: repo name, date, and a legend for the diagram marks (module, seam, leakage, deep module). The candidates follow directly.
- **One card per candidate**, titled with the deepening it proposes ("Collapse the Order intake pipeline"): strength and dependency category as badges; the files; problem and solution in one sentence each; benefits as bullets of six words or fewer, each named in glossary terms (_"locality: bugs concentrate in one module"_, _"leverage: one interface, N call sites"_); an ADR conflict as a callout. The before/after diagram is the centrepiece: if it needs a paragraph to be understood, redraw the diagram.
- **Top recommendation**: one card naming the candidate, one sentence on why, a link to its card.

## Diagrams

Before and after side by side. Pick the form that fits each candidate, and vary it across the page:

- **Graph**: calls and dependencies with the leaking edges marked, when the point is "X calls Y calls Z, and look at the mess"; a sequence diagram when the point is round-trips ("before: 6, after: 1").
- **Mass diagram**: per module, one rectangle for the interface and one for the implementation. Shallow: nearly the same height. Deep: a short interface over a tall implementation.
- **Cross-section**: the layers a call passes through, as stacked bands. Before: many thin layers, each doing little. After: one thick band named for the consolidated responsibility.
- **Call-graph collapse**: before, a tree of calls as nested boxes; after, one box with the now-internal calls faded inside it.
- **Deep module**: the after as one thick-bordered module with its internals greyed out.
