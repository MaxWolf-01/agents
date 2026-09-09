---
status: done
diff: [ba9fd9f..132ae97]
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
