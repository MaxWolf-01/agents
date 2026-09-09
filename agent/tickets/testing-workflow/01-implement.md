---
status: claimed
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

- [ ] Every Decision in `spec.md` has a home you can name in the closing comment.
- [ ] `grep -rn "tdd" mx/ claude/` shows only what should remain, and `/mx:tdd` resolves nowhere.
- [ ] The script's tests pass, and the script runs end to end on a small project with a suite (the memex repository at `/var/tmp/memex-proto` exists only on the orchestrator's machine; on this host clone `https://github.com/MaxWolf-01/memex.git` into the worktree's ignored scratch or `/var/tmp`, `uv sync`, add `numpy` to its dev group, since its suite does not run without it) and prints the report shape above.
- [ ] Every skill touched reads against `/mx:writing-for-agents` and stays short: PRINCIPLES.md §2 and §3, and the spec's Problem Statement on tutorial-shaped skills.
- [ ] Judgment calls made alone are an anchored `Assumptions` block in the closing comment, per `/mx:implement`.
