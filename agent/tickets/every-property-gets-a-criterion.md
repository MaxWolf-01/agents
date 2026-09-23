---
status: review
---

# to-tickets checks that every spec Property lands in some slice's criteria

Cut from the whole-feature review of one-flow (Spec axis, A1): the spec disposes every Property as *reviewed*, which makes the slices' acceptance criteria the place a property is checked, and seven of one-flow's fifteen Properties reached no slice. Twelve `Property, reviewed` criteria exist across tickets 01 to 08: one names something that is not a spec Property, one Property is claimed twice, and four (reads cold, the landing-message shape, the per-slice review page, the unratified-call chain) were left to nobody. All seven hold on the branch, and two of the pass's confirmed defects sit inside that gap.

## What to build

`/mx:to-tickets` ends with a check a script can run: every Property in the spec's `## Properties` is named by at least one ticket's acceptance criteria, and every `Property, reviewed` criterion quotes a Property that exists. Where a property genuinely belongs to no single slice, the breakdown says so in the same place rather than leaving it absent, since an absent property and an unsliceable one read the same today.

## Acceptance criteria

- [x] A breakdown whose slices miss a Property fails the check, naming the property.
- [x] A criterion naming a property the spec does not have fails it too.
- [x] The check runs where to-tickets publishes, and the skill says the breakdown is not finished until it passes.
- [x] Demo in the closing comment: the check run against one-flow's own spec and tickets, before and after.

## Comments

### Closing, worker on `ticket/master/every-property-gets-a-criterion`

`property-coverage` holds a breakdown's criteria against its spec's properties, to-tickets publishes only when it comes back clean, and a spec's properties now carry permanent ids the criteria cite. Three commits on `ticket/master/every-property-gets-a-criterion`, unmerged: the build, one wording fix, and the four-axis review round.

**Demo.** One command, against the breakdown the ticket was cut from: one-flow's spec and its nine tickets, read back out of git and run through the check in three states.

```
$ bash agent/show/every-property-gets-a-criterion/demo.sh

== 1. as it shipped: fifteen properties, twelve criteria, no ids anywhere
$ property-coverage /tmp/property-coverage.XXXX/one-flow
.../one-flow/spec.md:94: the Properties list carries no ids; number it P1 onward, 15 properties
0 properties, 0 disposed of, 1 finding

== 2. the spec numbered P1..P15, each criterion stamped with the property it paraphrases
$ property-coverage /tmp/property-coverage.XXXX/one-flow
.../spec.md:94: P1 reached no ticket: A ticket reads cold: a worker builds from the ticket and...
.../spec.md:96: P3 reached no ticket: Before the user sees a diff with judgment in it, an agent...
.../spec.md:98: P5 reached no ticket: A landing message leads with the outcome, the demo and the...
.../spec.md:103: P10 reached no ticket: Every landed slice, standalone or feature, has a review...
.../spec.md:106: P13 reached no ticket: Every unratified call is visible on the review page as an...
.../06-worker-contract.md:20: P16 is not a property of .../one-flow/spec.md
15 properties, 10 disposed of, 6 findings

== 3. the five properties that reached no ticket disposed of, the sixteenth criterion dropped
$ property-coverage /tmp/property-coverage.XXXX/one-flow
15 properties, 15 disposed of, 0 findings
```

State 2 is the gap the whole-feature review found, as findings that name it: five of the seven properties, plus the criterion that named something the spec never stated. The other two of the seven are criteria that quoted half their property, and an id names a property whole, so the check reads those as claimed (`[D2]`). Each state asserts its own exit code and summary, so the demo fails rather than printing different text.

Two more runs, both quick:

```
$ mx/bin/property-coverage agent/show/mx-readme-figures/demo/tracker/csv-import
3 properties, 3 disposed of, 0 findings          # the README's own fixture breakdown, now conforming

$ make test
125 passed in 24s                                # 26 of them the new checker's
```

**I need from you**

1. `[D1]` **Ids in the spec, cited by the criteria, in place of a criterion quoting the property.** The ticket asked that a criterion "quotes a Property that exists". One-flow's twelve criteria paraphrased theirs, so a text matcher's "no match" could not tell a missing property from a differently worded criterion. Properties now open with `P1`, permanent, and a criterion cites the id. The cost is that every spec numbers its properties from now on, and a breakdown cut before this reads as unnumbered until someone numbers it, which the check says in one line.
2. `[D2]` **The check is coverage-only.** It answers whether a ticket claimed the property, never whether the claim covers the whole of it, so a criterion quoting half a property counts (one-flow's P6 and P8 are exactly that). Holding the claim against the property stays the Spec reviewer's read. If you want the stronger check, the criterion would have to quote the property verbatim beside its id, and every criterion gets longer.
3. `[D3]` **Is `unsliced` a legitimate outcome or an admission of a bad cut?** The skill already answers a property no slice can hold with a slicing signal (merge the slices, or split the property at the seam). I put a third word after that signal rather than in place of it, for a property that holds across the feature. Ruling wanted on whether a breakdown may ever write it.
4. `[D4]` **A standards conflict the review surfaced, yours to settle, not mine.** The prose catalogue's rule 14 bans the colon as a mid-sentence connector, and it is the native voice of `PRINCIPLES.md` and of every skill in the plugin, mine included. Either rule 14 does not bind agent-facing prose and the catalogue says so where it lists its scope tags, or it does and the corpus is in wholesale violation. Every reviewer of a skill diff decides this alone today.
5. `[D5]` **The README figure fixtures changed and the PNGs did not.** `agent/show/mx-readme-figures/demo/tracker/` was the repo's only spec-with-properties and taught the superseded format; both its breakdowns now carry ids and pass the check. The lines I changed are not the rows those screenshots expand, so I left `mx/assets/*.png` alone rather than re-running the render.

**Details, if you want them**

`[D6]` **Assumptions.**

- A1 `mx/skills/grilling/SPEC-FORMAT.md:33`: the id convention, `[D1]`.
- A2 `mx/skills/to-tickets/SKILL.md:49`: `unsliced` is the breakdown's word, not a third spec disposition. SPEC-FORMAT keeps its two, and a property the breakdown marks `unsliced` keeps the spec's disposition for how it is checked, so nothing falls out of the Spec reviewer's reach. `[D3]`.
- A3 `mx/skills/to-tickets/property_coverage.py:28`: coverage-only, `[D2]`.
- A4 `mx/skills/to-tickets/SKILL.md:61`: publishing may number an older spec's properties, against the step's standing "Do NOT modify the spec". An id is bookkeeping, not design, and without this the check's own first finding asks for an edit the same step forbids.
- A5 `agent/show/mx-readme-figures/demo/tracker/csv-import/spec.md:31`: the fixtures renumbered, the figures not re-rendered, `[D5]`.
- A6 `mx/skills/code-review/SKILL.md:72`: two consumers outside this ticket's scope now name a property by its id, here and in `mx/skills/dispatch/worker-prompt.md:15`. Leaving them saying "by name" would have left the vocabulary with two readings the day it landed.
- A7 `mx/skills/to-tickets/property_coverage.py:128`: declined finding, `spec.is_file()` stays rather than `exists()`. A directory named `spec.md` is not a state the tracker can produce.
- A8 `mx/skills/to-tickets/test_property_coverage.py:74`: declined finding, the check-seam test for a missed property stays although the main-seam test subsumes its assertions. It is the ticket's first acceptance criterion, in one place, named.

`[D7]` **Finding index**, range `7123d63..3c9fc7f`, four axes (the diff touches a contract other skills read, so the full axes rather than light). Every finding fixed in `906a41e` except the two declined above and `[D4]`, which is yours.

- Correctness, 4: claims matched anywhere in a ticket file, both a false clean (a criterion quoted under Comments) and a false fail (a bullet opening with the domain word "Property") → fixed, claims are read from the acceptance criteria. A `## Properties` heading the parser could not see, passing as a spec with no properties → fixed, the no-section case says so and an empty section is a finding. Bold tolerated on the spec side and fatal on the ticket side → fixed, both. A sub-bullet read as a property with no id → fixed, top-level bullets only.
- Standards, 4 hard + 9 calls: a criterion with nothing after the word crashed the run with a `TypeError` → fixed, and it is a finding now. `unsliced` homeless between two documents → fixed, A2. `--help` prescribing when a breakdown is finished → fixed, that policy lives in the skill. No `Examples:` section → fixed. Then: the test's `__main__` left `.pytest_cache/` behind; the unexercised bold tolerance; `Report.disposed`'s filter untested; a demo comment narrating as history something the demo itself does; a demo that could not fail; a short SHA; a dense two-of-five description of the check; the fixture breakdowns; a shared mutable default. All fixed.
- Spec, 5: the half-quote the design does not catch → `[D2]`, and the demo and the commit message no longer overstate. Numbering versus "Do NOT modify the spec" → fixed, A4. Claims not scoped to the criteria → fixed. `unsliced` contradicting SPEC-FORMAT → fixed. Two consumers left speaking text → fixed, A6.
- Tests, 21 measured mutation survivors: the reviewer ran 42 hand-written mutants. Fixed the ones that mattered: single-digit ids only (`P\d+` → `P\d` survived, and one-flow has fifteen properties), the CLI never entered (dropping `tyro.conf.Positional` survived), `Report.disposed`'s validity filter, the counts line's dedup, three properties sharing an id, both `summarise` boundaries, finding order, nested and starred bullets, heading exactness, and the claims-scope reading itself. The suite went from 17 tests to 26, entering a third seam: the command a session types, run through the wrapper on `PATH`.

`[D8]` **Friction.**

- **A reviewer mutating the worker's own worktree.** The Tests axis ran its 42 mutants by editing `property_coverage.py` in place. One of my own `make test` runs went green against a mutated file, and another agent's report opened by saying it had read the committed blob rather than the tree because the tree was moving. A reviewer that mutates needs its own checkout; this is also what made my two pre-review commits land mid-review, which two reports had to note.
- **No `make harden` in this repo**, so the mutation measurement that found nine real test gaps was hand-rolled by a reviewer. A standalone ticket never reaches the per-feature harden trigger either, so this measurement has no home in the flow for work of this size.
- **The check's only real-data input had to be exhumed from git.** one-flow was retired when it shipped, so the demo reconstructs it from `1f26781^`. It works and it is the honest input, but the repo has no live feature directory at all, so the check's whole input population is the demo plus the README fixtures.
- **The contract's oracle did not apply.** There is no properties directory and no expected failures in this repo, so the worker prompt's "the expected failures naming your ticket are your oracle" had nothing to point at; the oracle here was the ticket and the two skills, named in the test file's docstring.
