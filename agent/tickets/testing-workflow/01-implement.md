---
status: done
diff: [ba9fd9f..132ae97, 983bd7c..a10309f, ab5464b..ad1f748, 7eb1923..0e0c037, e1df867..c2f60dc]
---

# Implement the testing-workflow spec

One ticket for the whole spec, a deliberate deviation from vertical slicing: the pieces name each other (the Makefile template names the script, the skills name the target, the smells file is the testing skill's disclosed reference), and the user chose to judge one diff over reading the spec line by line.

## What to build

Every Decision in `spec.md` finds its home in the plugin. Read the spec whole first; then, in order:

1. `mx/skills/tdd` becomes `mx/skills/testing` (`git mv`), rewritten as the spec's Solution describes: short, nudge-shaped, no prescribed order of test and code; `tests.md` and `mocking.md` deleted, their content becoming anti-pattern entries in the smells file below. Red-first is named only in `diagnosing-bugs`; check its wording stands on its own once `tdd` is gone. Every pointer moves with the rename: `orient` (which also stops describing implement as driving red-green slices), `implement`, `codebase-design`, `mx/README.md`, and whatever `grep -rn "tdd" mx/ claude/ README.md CLAUDE.md` still shows.
2. `mx/skills/code-review/TEST-SMELLS.md`, the test-smell baseline in `SMELLS.md`'s shape (what it is → how to fix; the same binding rules), and the Tests axis in `code-review/SKILL.md`: spawned only when the diff touches test files, its brief carrying the smells file and the spec's Testing Decisions, a fourth `## Tests` section in the aggregate; light mode adds the smells file to its standards sources when tests are in the diff and runs no Tests brief.
3. `grilling/SPEC-FORMAT.md` Testing Decisions: the oracle per seam (the glossary's word) and each Property's disposition, executable or reviewed. `to-tickets`: the amendment of its disposal rule (executable Properties share one early cross-cutting ticket, `tests/properties/`, its worker briefed with the spec and the seams' interfaces; reviewed ones stay acceptance criteria). `dispatch` tick step 1: a change under `tests/properties/` in any build ticket other than that one goes back to the worker; tick step 5: harden once against the feature's fork point, report in front of the user. `orient` step 5: harden's report as a review-session input. `improve-codebase-architecture`: the testing lens. `implement`: points at `/mx:testing`; no harden step.
4. The harden script beside the testing skill, a PEP 723 uv script with a tyro command line (`/mx:tyro-cli`, `/mx:uv-script`): a repository and a commit range in (default base: the merge-base with the integration branch); one report out: new survivors with their diffs, case-flip survivors listed apart, uncovered changed lines as file:line, changes it could not measure as an explicit unmeasured section, unresolved mutants; exit code distinguishing pass, findings and could-not-measure. Its `--help` is the home of every mechanic the spec keeps out of the skills. Primary sources, copied to this host's scratch dir beside the prompt (`sources/`): `gate.py` and `mutmut_run.py` from the yapit prototype, and research snapshots 04, 05, 07 whose "What I would change" lists say what the prototype got wrong (survivors compared by mutation content, not the tool's numbering; test-only changes get targets from the tool's test-to-function map at the base; a kill needs a failing test, not an erroring one; property tests run under a small Hypothesis profile). Tests for its pure parts beside it, prior art `mx/skills/permissions-review/scripts/test_scan_unapproved.py`. Python only in this iteration.
5. `project-setup`: `assets/Makefile` gains `harden` (calling the script) and an optional `fuzz`; `PYTHON.md` names Hypothesis with a small-example settings profile for harden, mutmut's config, `COVERAGE_CORE=sysmon`, ruff's complexity rule enabled with its limit (`[tool.ruff.lint.mccabe] max-complexity`), and `tests/properties/`. The spec's per-language table goes here, one line per language, the non-Python rows as pointers.
6. `mx/README.md` (for humans; may restate) matches. Prior-art pointers go to `agent/prototypes/testing-workflow/` (committed), never to `agent/research/` (gitignored).

## Acceptance criteria

- [x] Every Decision in `spec.md` has a home you can name in the closing comment.
- [x] `grep -rn "tdd" mx/ claude/` shows only what should remain, and `/mx:tdd` resolves nowhere.
- [x] The script's tests pass, and the script runs end to end on a small project with a suite (the memex repository at `/var/tmp/memex-proto` exists only on the orchestrator's machine; on this host clone `https://github.com/MaxWolf-01/memex.git` into the worktree's ignored scratch or `/var/tmp`, `uv sync`, add `numpy` to its dev group, since its suite does not run without it) and prints the report shape above.
- [x] Every skill touched reads against `/mx:writing-for-agents` and stays short: PRINCIPLES.md §2 and §3, and the spec's Problem Statement on tutorial-shaped skills.
- [x] Judgment calls made alone are an anchored `Assumptions` block in the closing comment, per `/mx:implement`.

## Comments

### Implemented, `ba9fd9f..132ae97`

**Where each Decision lives.**

| Decision | Home |
| --- | --- |
| Testing Decisions gains the oracle and each Property's disposition | `grilling/SPEC-FORMAT.md`, Testing Decisions |
| Executable Properties share one early ticket in `tests/properties/` | `to-tickets/SKILL.md`, "Dispose of every spec property" |
| That ticket lands as its own review page; the generators are what the human reads | already how every ticket lands; nothing written |
| A feature over existing code: the brief's scope and the Tests reviewer are the guards | the brief in `to-tickets`, the Tests axis in `code-review` |
| A change under the properties directory in another ticket goes back to the worker | `dispatch/SKILL.md`, tick step 1, the `done` branch |
| Harden is `make harden` calling the plugin's script; the mechanics live in its `--help` | `project-setup/assets/Makefile`, `testing/harden.py` |
| Harden runs per feature against the fork point, read by the human at the review session | `dispatch/SKILL.md` tick step 5, `orient` step 5, `mx/README.md` |
| improve-codebase-architecture gains a testing lens | `improve-codebase-architecture/SKILL.md`, Explore |
| Prior art under `agent/prototypes/testing-workflow/` | `testing/test_harden.py` docstring (the oracle for its cases) |
| Tests axis, spawned on a test-touching diff; light mode takes the smells file only | `code-review/SKILL.md` steps 3, 4, 5 and Light mode |
| Test smells beside SMELLS.md | `code-review/TEST-SMELLS.md` |
| `/mx:tdd` → `/mx:testing`, tutorials deleted, pointers moved | `testing/SKILL.md`; `orient`, `implement`, `mx/README.md`, the main-flow figure |
| Red-first named in diagnosing-bugs only | unchanged there; its Phase 5 wording stands without tdd |
| Complexity via the linter's rule, CRAP nowhere | `project-setup/PYTHON.md` (`C901`, `max-complexity`) |
| Tools per language behind `make harden` and the properties directory | `project-setup/SKILL.md`, Stacks |
| Long fuzz runs reuse the property tests, optional `make fuzz` | `project-setup/assets/Makefile`, `PYTHON.md` |

**Evidence.** The script's own checks, `uv run mx/skills/testing/test_harden.py`: 20 passed. End to end on a clone of memex (`/var/tmp/memex-proto` on `agent@pc`, `uv sync`, numpy/pytest-cov/hypothesis added to the dev group, `[tool.mutmut]` added), replaying a two-function change as a feature commit:

```
$ make harden HARDEN=<worktree>/mx/skills/testing/harden.py ARGS="--range 2be4898..HEAD"
repo       /var/tmp/memex-proto
range      2be4898..HEAD
targets    2: memex_md.find.x__combine, memex_md.find.x_find_notes
mutants    53 at head, 42 at base (11s + 16s)
SURVIVED   memex_md.find.x__combine__mutmut_1: if AVERAGE_PARTS and part_count > 1: -> if AVERAGE_PARTS or part_count > 1:
SURVIVED   memex_md.find.x__combine__mutmut_2: if AVERAGE_PARTS and part_count > 1: -> if AVERAGE_PARTS and part_count >= 1:
SURVIVED   memex_md.find.x__combine__mutmut_3: if AVERAGE_PARTS and part_count > 1: -> if AVERAGE_PARTS and part_count > 2:
SURVIVED   memex_md.find.x__combine__mutmut_4: return total / part_count -> return total * part_count
SURVIVED   memex_md.find.x_find_notes__mutmut_31: if limit < 0: -> if limit <= 0:
SURVIVED   memex_md.find.x_find_notes__mutmut_32: if limit < 0: -> if limit < 1:
UNCOVERED  src/memex_md/find.py:104
UNMEASURED src/memex_md/find.py:14: no mutation target
UNMEASURED src/memex_md/find.py:17: no mutation target
pre-exists 6 survivors the base already had
FINDINGS
```

Both survivor groups are real: nothing pins the averaging rule, and nothing distinguishes a negative limit from zero. The uncovered line is the `raise` no test reaches; the two unmeasured lines are the module-level constants mutmut cannot mutate; the six pre-existing survivors are the integration branch's and stay out of the feature's list. Two further replays: the memex ticket from the prototype (`discover_files` guard) comes back PASS with 121 pre-existing survivors filtered out, and deleting that ticket's two tests comes back UNMEASURED, exit 2, having derived 14 targets from the tool's test-to-function map with no source change at all.

**Assumptions.**

- A1 `mx/skills/testing/harden.py:131`: findings outrank could-not-measure when a range has both, so the exit code is 1 and the report's `UNMEASURED` lines carry the rest. Reversing it would hide a survivor behind a blind spot.
- A2 `mx/skills/testing/harden.py:123`: comparing against the fork point without a committed baseline means measuring the base too, in a throwaway worktree: a feature costs two suite runs and two mutant runs. The spec ruled out a curated file, and this is the only other way to know which survivors are the feature's.
- A3 `mx/skills/testing/mutmut_runner.py:164`: "a kill needs a failing test" is read strictly, off pytest's junit report: a mutant whose tests *error* (a fixture that blows up on mutated SQL, a collection error) comes back unresolved, not killed. On memex that is 25 of 435 mutants in `db.py`, so a feature touching schema code reads UNMEASURED where mutmut alone would have said clean. Honest, and noisier than mutmut's default.
- A4 `mx/skills/testing/harden.py:120`: an edited test file names every target its tests cover, not the module its filename suggests. One edited test file in memex meant 14 targets and 435 mutants for a one-line source change; on a large suite this is the expensive case.
- A5 `mx/skills/testing/harden.py:122`: a range with no mutation target and no edited test is reported without measuring anything (a docs-only range answers in half a second); what such a range changed inside a source file still comes back as unmeasured.
- A6 `mx/skills/project-setup/assets/Makefile:8`: the `harden` target finds the script by globbing the plugin cache and taking the newest by mtime; `HARDEN=<path>` overrides it, which is also how a worktree checkout is used. `make` collapses the script's 1 and 2 into its own exit 2, so the verdict to read is the report's last line.
- A7 `mx/skills/code-review/TEST-SMELLS.md:16`: six entries have no ancestor in the deleted `tests.md`/`mocking.md` (Unagreed Seam, Assertion-Free Test, Redundant Example, Weakened Test, Order-Dependent Test, Oversized Snapshot). They come from the spec's Properties and the prototypes' findings; a shorter list is a one-line delete each.
- A8 `mx/skills/project-setup/PYTHON.md:9`: `max_examples=25` for the `harden` Hypothesis profile and `max-complexity = 10` for ruff are starting numbers in a project's own config, where a project changes them without touching a skill.
- A9 `agent/show/mx-readme-figures/main-flow.html:139`: the figure said "tdd inside"; it and its two PNGs (copied to `mx/assets/`) were re-rendered here with `render.py`. The other figures were left at their committed renders.

**Friction.**

- mutmut leaves a full copy of the suite in `mutants/`, and a project's plain `pytest` then collects both copies and dies on duplicate module basenames. Harden passes `--ignore=mutants` for its own runs; `PYTHON.md` now sets `testpaths` so the project's own `make test` survives adopting harden. Anyone running harden on a repo without that config sees a broken suite next.
- mutmut's mutants are served to the tests through `sys.path` in the process that forks the runner. Re-running pytest as a subprocess (which the yapit prototype needs, and which this script keeps) drops that, so on a src-layout project with an editable install every mutant ran against unmutated code and scored `survived` — and mutmut's own forced-fail guard reports "Unable to force test failures" rather than failing hard. The fix is a `PYTHONPATH` over the mutated roots; finding it cost about half an hour of a run that looked like it worked.
- No `/mx:code-review` axes were spawned on this diff: this session was instructed not to use the subagent tool. The review of these ~1100 lines is the orchestrator's, and the Tests axis it describes cannot review itself.

### Review round 1, `983bd7c..a10309f`

Addressed: Correctness 1, 2, 3, 4, 5 and both Minors; Standards 1, 2, 3, 5, 6, 7, 8, 9; Spec (a) whole-repo, (a) `make test`, (b) Redundant Example, (c) deletion-only, (c) dirty tree; Tests (a) all four, (b) the command-line seam, (c) 1, 2 and 3, (d) all four.

**The script.** Four states it got wrong, each now a check. A name filter matching no mutant is ordinary rather than exceptional — a function the range adds has none at the base — and it crashed the run where it should have reported a target without verdicts. A test file the range creates cannot be in the base's map, so every feature that added one read `unmeasured`; the head's map now answers the same question, for reporting only, since taking targets from it would make an untouched function's old survivors look new. A deleted file's `+++ /dev/null` left the previous path in place, handing a 200-line deletion's line numbers to whatever file sorted before it. And a range that only deletes module-level lines came back `pass`, which the spec's own property forbids: the old side is now read for what nothing measured, reported as its own line with the tree that numbered it.

`--whole-repo` mutates every target under the source paths with no base to compare against, which is the report improve-codebase-architecture was promised; that skill now names the command. A dirty tree is refused, since harden mutates the tree while reporting commits.

**The checks.** 32, of which five drive `harden.py` at its command line against a fixture repository built in a temp dir: the prototypes' two replays at fixture scale (a function the tests do not pin comes back as a survivor with its uncovered branch and its module-level constant; a deleted test brings its function back through the base's map and turns the mutant it alone killed into a finding), plus whole-repo, the dirty tree, and a range with no Python in it that creates no `mutants/` at all. They take about 18 seconds together and are the only checks that reach `main`, `mutated_source_roots` and the exit codes. The helper-level cases lost their shared cwd, gained the discriminating inputs the review named (a source path with its trailing slash, a comment line, a junit report carrying both a failure and an error, a token-unbalanced case flip, two functions sharing one mutation), and now assert the rendered report.

**One finding not implemented as described.** Spec (c) and Standards' Local Inconsistency read `module_name`'s `src.` special case as a bug for other source roots. It mirrors mutmut exactly, which I verified against the function that names every mutant:

```
$ uv run --with mutmut python -c "from mutmut.utils.format_utils import get_mutant_name; ..."
source/pkg/mod.py            -> source.pkg.mod.x_fn
lib/pkg/mod.py               -> lib.pkg.mod.x_fn
src/pkg/mod.py               -> pkg.mod.x_fn
```

mutmut strips one literal `src.` and leaves every other root in the name (`utils/format_utils.py:get_mutant_name`), so harden's rule is the matching one and changing it would break `source/` and `lib/` layouts rather than fix them. `mutated_source_roots`, which the finding compares it against, answers a different question: which directories go on `PYTHONPATH` so the mutated copies import. The rule is now named in the docstring and pinned by a check over all three layouts.

**The skills.** Dispatch passes `--integration-branch`. code-review's counts follow the fourth axis. The test-smell file points at `SMELLS.md`'s binding rules instead of copying them, and drops Redundant Example. PYTHON.md installs what the project needs rather than what harden injects, and leaves the tracer's why to `--help`. The `harden` target picks the highest installed version (`sort -V`) and prints the path it chose; `fuzz` says what it needs before failing on it. This repo's `make test` runs the checks, and `release-*` waits on them. pocock-sync maps tdd to testing.

**Evidence.** `make test` → 32 passed. The memex replay, re-run against the same range on the round's code:

```
$ make harden HARDEN=<worktree>/mx/skills/testing/harden.py ARGS="--range 2be4898..HEAD"
harden: <worktree>/mx/skills/testing/harden.py
targets    2: memex_md.find.x__combine, memex_md.find.x_find_notes
mutants    53 at head, 42 at base (12s + 17s)
SURVIVED   memex_md.find.x__combine__mutmut_1: if AVERAGE_PARTS and part_count > 1: -> if AVERAGE_PARTS or part_count > 1:
SURVIVED   memex_md.find.x__combine__mutmut_2: if AVERAGE_PARTS and part_count > 1: -> if AVERAGE_PARTS and part_count >= 1:
SURVIVED   memex_md.find.x__combine__mutmut_3: if AVERAGE_PARTS and part_count > 1: -> if AVERAGE_PARTS and part_count > 2:
SURVIVED   memex_md.find.x__combine__mutmut_4: return total / part_count -> return total * part_count
SURVIVED   memex_md.find.x_find_notes__mutmut_31: if limit < 0: -> if limit <= 0:
SURVIVED   memex_md.find.x_find_notes__mutmut_32: if limit < 0: -> if limit < 1:
UNCOVERED  src/memex_md/find.py: 104
UNMEASURED src/memex_md/find.py: no mutation target on 14, 17
UNMEASURED src/memex_md/find.py: no mutation target on 14, at the base
pre-exists 6 survivors the base already had
FINDINGS
```

The findings are the ones the first round recorded; locations now read one file at a time, and the modified module-level constant shows on both sides, as the line the range wrote and the line it replaced.

**Assumptions.**

- A10 `mx/skills/testing/harden.py:456`: a case-flip survivor (a mutant whose only change is letter case inside a string literal) is listed apart and never counted as a finding. It was 11% of unkilled mutants on yapit and 2 of 2 on one replayed ticket, and such a mutant survives only where the value is case-insensitive; the report still shows every one, so reversing this is a one-line change in `assemble`.
- A11 `mx/skills/testing/harden.py:132`: a module-level line the range *modifies* is unmeasured on both sides and reported twice, once per tree. Collapsing the pair would need the two line numbers to be matched across trees, and the deletion case is the one the spec's property is about.
- A12 `mx/skills/testing/harden.py:166`: `--whole-repo` reports every survivor as new, because there is no base for anything to pre-exist against, and its uncovered list is every uncovered line under the source paths. On a repo the size of memex that is hundreds of lines, which is why the render groups them per file.
- A13 `mx/skills/testing/harden.py:179`: the dirty-tree refusal exempts harden's own `mutants/`, `.coverage` and `.hypothesis/`, so a project that has not gitignored them yet still gets a second run rather than a refusal it cannot read.
- A14 `mx/skills/testing/harden.py:360`: the base decides which targets are measured, and the head's test map is read for reporting alone. A test file the feature *adds* therefore does not pull the functions it covers into the measurement: those functions are unchanged, and their survivors predate the feature.
- A15 `Makefile:11`: `make test` runs the harden checks (about 18 seconds, five of them driving uv, mutmut and pytest in temp repositories), and `release-*` now waits on them, so a release needs a machine with `uv` and a warm cache.

**Friction.** The end-to-end checks needed a fixture whose tests are not redundant against the mutation set: the first fixture's three `clamp` tests killed the same mutants, so deleting one changed nothing and the deleted-test check could not fail. A boundary function (`fits(value, limit)`, whose `<` -> `<=` mutant only one test catches) was what made the property observable. Worth knowing for anyone writing tests against harden: a suite where no single test uniquely kills a mutant cannot demonstrate that deleting a test costs anything.

### Review round 2, `ab5464b..ad1f748`

Addressed: C1, C3, C5, C6, C8, C9, C10, C16, C17, C18, C19.

**The smell lists nudge rather than bound (C1, C3).** Both files opened as "a fixed set of smells that the axis applies", which reads as a checklist with an edge to it. They now say what they are: the smells the reviewer already knows by name, with a finding outside the list still a finding, reported in the reviewer's own words. The "bind" framing is gone from both. Redundant Example is back, carrying the reason the user gave it: a test is a line of code and a test that catches nothing new is a liability.

**Harden's report has a reader (C5, C10).** Dispatch's step 5 no longer hands a raw report to the user. The orchestrator reads it and sorts every line: a survivor a test can pin and an uncovered line a test can reach are fixed on the feature branch in a commit that names the finding; a survivor whose fix is a design change, an unmeasured change, an uncovered line that wants restructuring become proposed tickets. The PR-ready line now carries that proposal, and the user rules on it and reads the diff. Harden also keeps every report it prints at `agent/harden/<utc timestamp>-<range>.txt` wherever an `agent/` directory exists, and prints where it went; `agent/harden/` joins the artefacts a dirty-tree check ignores, so a kept report never blocks the next run. improve-codebase-architecture reads the newest whole-repo report when no commit since it touched the area scoped, and runs `--whole-repo` otherwise.

**Overstatement removed (C8).** A decorated entry point is testable, by calling it directly or through the framework's test client; what it costs is that setup, and what genuinely cannot reach it is the mutation tool. The testing skill and the architecture scan both say that now.

**The rest.** The testing skill leads its description with the trigger (C17), gains the invariant-to-property sentence (C9) and one line on `make fuzz` (C18). SPEC-FORMAT says what prior art means: the existing tests at that seam, named, as the pattern the new ones follow (C6). project-setup drops the per-stack table for one sentence, since only PYTHON.md has tools behind those names today (C16). Harden's `--help` lost the sentences that argued a decision or named a reader; it keeps the mechanics, the exit codes, the cost line, the schema and the examples (C19).

**Evidence.** `make test` → 33 passed, the new one covering the kept report in both its shapes. The memex replay, on this round's code:

```
$ make harden HARDEN=<worktree>/mx/skills/testing/harden.py ARGS="--range 2be4898..HEAD"
targets    2: memex_md.find.x__combine, memex_md.find.x_find_notes
mutants    53 at head, 42 at base (11s + 16s)
SURVIVED   memex_md.find.x__combine__mutmut_1: if AVERAGE_PARTS and part_count > 1: -> if AVERAGE_PARTS or part_count > 1:
SURVIVED   memex_md.find.x__combine__mutmut_2: if AVERAGE_PARTS and part_count > 1: -> if AVERAGE_PARTS and part_count >= 1:
SURVIVED   memex_md.find.x__combine__mutmut_3: if AVERAGE_PARTS and part_count > 1: -> if AVERAGE_PARTS and part_count > 2:
SURVIVED   memex_md.find.x__combine__mutmut_4: return total / part_count -> return total * part_count
SURVIVED   memex_md.find.x_find_notes__mutmut_31: if limit < 0: -> if limit <= 0:
SURVIVED   memex_md.find.x_find_notes__mutmut_32: if limit < 0: -> if limit < 1:
UNCOVERED  src/memex_md/find.py: 104
UNMEASURED src/memex_md/find.py: no mutation target on 14, 17
UNMEASURED src/memex_md/find.py: no mutation target on 14, at the base
pre-exists 6 survivors the base already had
FINDINGS
kept at /var/tmp/memex-proto/agent/harden/20260909T151724Z-2be4898..HEAD.txt
```

Run again, it keeps a second report and the first one does not make the tree dirty.

**Assumptions.**

- A16 `mx/skills/testing/harden.py:146`: the kept file is always the rendered text, including on a `--json` run, so a run leaves one file of one shape; its name carries the range verbatim with `/` replaced by `-`, and a whole-repo run is named `whole-repo-<sha>`.
- A17 `mx/skills/testing/harden.py:197`: `agent/harden/` joins `mutants/`, `.coverage` and `.hypothesis/` as artefacts the dirty-tree check ignores. Without that, harden's own output would refuse the next run in any project that has not gitignored it yet.
- A18 `mx/skills/testing/SKILL.md:42`: the skill now says harden runs when a feature's frontier empties rather than "at the review session", following C5: the orchestrator reads the report there, and what reaches the review session is its proposal.

### Review round 3, `7eb1923..0e0c037`

Addressed: C1, C3, C4, C6.

**The repo's test run (C1).** `make test` ran one file by path, which reads as running harden rather than testing this repo. It is `pytest mx/` now, with the imports the checks need injected, and it collects the permissions-review script's twelve checks as well: they had no runner before. Two things stood in the way and are fixed: the runner's map helper was called `tests_in_map`, which pytest collects as a test and then errors on for missing fixtures, and is now `targets_for_test_files`; and the checks chdir'd into a temp directory at import and left the process there, which is exactly the Order-Dependent Test the smell list names, so the working directory goes back after the import that needs it. `uv run mx/skills/testing/test_harden.py` still runs the file on its own. `release-*` waits on `test` as before, so the release path picks all of this up.

**`make fuzz` without a licence (C6).** The target required hypofuzz to do anything, and hypofuzz is non-commercial. It now runs the property tests under a `fuzz` Hypothesis profile until you stop it, needing nothing beyond hypothesis, and hands over to `hypothesis fuzz` for coverage guidance as soon as hypofuzz imports. PYTHON.md registers the profile beside `harden` and keeps the licence note; the testing skill says what the target does and what HypoFuzz adds, without claiming a machine has to be idle.

**Plain sentences (C3, C4).** project-setup states the two names a project keeps and leaves the tools to the stack file, with nothing about which file has them today. PYTHON.md says the dev group takes hypothesis and nothing else for testing, because harden runs mutmut and coverage from its own environment.

**Evidence.** `make test` → 45 passed in 17s (33 harden checks, 12 permissions-review). `uv run mx/skills/testing/test_harden.py` → 33 passed. `make -n fuzz` against a copy of the template prints the branch it would take.

**Assumptions.**

- A19 `Makefile:11`: `make test` runs everything under `mx/` that pytest collects, so a script added beside a skill is tested by the repo's test run the moment its checks are named `test_*` in a `test_*.py` file. The injected dependencies (pytest, tyro, mutmut, coverage) are the union of what those files import; a new script with new imports adds to that line.
- A20 `mx/skills/project-setup/assets/Makefile:19`: without hypofuzz, `make fuzz` loops the ordinary pytest run under the `fuzz` profile and stops on the first failing run, which is the finding. With hypofuzz it defers entirely to `hypothesis fuzz`, whose own stopping behaviour applies.
- A21 `mx/skills/project-setup/PYTHON.md:18`: `max_examples=5000` for the `fuzz` profile is a starting budget in the project's own config, as `harden`'s 25 is.

### Review round 4, `e1df867..c2f60dc`

Addressed: the two rulings.

**HypoFuzz is the default.** The dev group takes `hypothesis hypofuzz`; the `fuzz` profile stays for the project that drops HypoFuzz, and the licence bullet says whose call that is: non-commercial use is the user's to rule on per project, and dropping it falls back to the profile loop, with Atheris still the one-line pointer for a project that wants coverage guidance anyway. The target keeps both branches; its comment and the testing skill's line now lead with HypoFuzz.

**Something starts the fuzz run.** `dispatch-ctl fuzz start` cuts `fuzz/<feature>` from the feature branch's pushed tip into `<worktrees-dir>/<repo>-<feature>-fuzz`, sets it up through the same `checkout` a ticket worktree uses (so the project's own setup command runs), and leaves `make fuzz` in a tmux session `fuzz-<repo>-<feature>`; `stop` takes the session, the worktree and the branch. It writes no manifest line: there is no conversation to resume and no exit status to read, so the session either exists or it does not, and `stop` is the whole of undoing it. `--help` documents both. `dispatch`'s own help describes `ctl` as running `dispatch-ctl <args>` on the host without listing its commands, so there was nothing to add there. Dispatch's tick step 5 gained two sentences: start the run and hand the user the session name and how to attach; it runs until stopped, and retiring the feature includes stopping it.

**Evidence.** `make test` → 45 passed. The new command driven against a throwaway bare repo and feature branch on this host:

```
$ dispatch-ctl fuzz start
+ git -C /var/tmp/fuzztest/demo.git worktree add /var/tmp/fuzztest/work/demo-demo-fuzz -b fuzz/demo demo
+ (cd /var/tmp/fuzztest/work/demo-demo-fuzz && make install) > .../fuzz-demo-demo.install.log 2>&1
+ tmux new-session -d -s fuzz-demo-demo -c /var/tmp/fuzztest/work/demo-demo-fuzz
+ tmux send-keys -t fuzz-demo-demo -l make fuzz
fuzzing fuzz-demo-demo  worktree=/var/tmp/fuzztest/work/demo-demo-fuzz  (tmux attach -t fuzz-demo-demo)

$ dispatch-ctl fuzz start          # a second one
dispatch-ctl: fuzz-demo-demo is already fuzzing; dispatch-ctl fuzz stop ends it

$ dispatch-ctl fuzz stop
+ tmux kill-session -t =fuzz-demo-demo
+ git -C /var/tmp/fuzztest/demo.git worktree remove --force /var/tmp/fuzztest/work/demo-demo-fuzz
+ git -C /var/tmp/fuzztest/demo.git branch -D fuzz/demo
stopped fuzz-demo-demo
```

The pane held `make fuzz` running; after `stop` the worktrees directory and the branch list were empty, a second `stop` said `no session` and exited 0, and a `start` against a branch whose Makefile has no `fuzz` target refused before creating anything.

**Assumptions.**

- A22 `mx/skills/dispatch/dispatch-ctl:331`: the fuzz run is the feature's, one per feature, and its branch is `fuzz/<feature>` cut from the feature branch's pushed tip; it does not follow later pushes, so a feature that keeps building restarts the run to fuzz the newer code.
- A23 `mx/skills/dispatch/dispatch-ctl:355`: `start` refuses when the feature branch's Makefile has no `fuzz:` target, read out of the bare repo before anything is created, rather than leaving a session with a make error in it.
- A24 `Makefile:11`: the repo's test run sets `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`, after the first run left `__pycache__` files in the tree and the commit before this one swept them in. They are removed in `c2f60dc`; the mistake is in the history rather than amended away.
- A25 `mx/skills/project-setup/PYTHON.md:13`: hypofuzz joins the dev group by default, so a fresh project's install pulls a non-commercially-licensed dependency unless the user rules otherwise. project-setup asks.
