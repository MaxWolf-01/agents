# Does a strict expected failure carry a property ahead of its seam?

One Hypothesis property (`test_property_ahead_of_seam.py`) over the seam in `pkg/seam.py`, run from
this directory (`uv run --with pytest --with hypothesis pytest -q`; pytest 9 / Hypothesis 6, 2026-09-09).
The seam body and the annotation were rewritten between runs; the committed files hold the first row.

| seam state | annotation | run |
| --- | --- | --- |
| stub raising `NotImplementedError` | strict, `raises=NotImplementedError` | `1 xfailed`: green |
| correct implementation, annotation left in place | same | `FAILED [XPASS(strict)]`: red until the annotation is deleted |
| wrong implementation, annotation left in place | same | `FAILED AssertionError` with the falsifying example: red |
| stub, and a bug in the property's own body before the seam call | same | `FAILED AttributeError`: the property's bug is visible |
| stub, and the same bug in the property's body | strict, no `raises=` | `1 xfailed`: the property's bug is hidden |
| the seam's module does not exist | any | collection error: no annotation reaches it |
| seam exists, lacks the behaviour (`[i for i in items if i != query]`) | strict, `raises=AssertionError` | `1 failed`: an index error on one-element inputs and an assertion on the rest, which Hypothesis raises as one exception group no single `raises=` matches |
| same seam | strict, no `raises=` | `1 xfailed`: green |

The last two rows were found by the Correctness reviewer of the feature branch and re-run here.

Proposed readings (the agent's, ratified in the spec's Decisions): at a stub, `raises=` is what makes a
wrong implementation and a broken property both visible; at an existing seam no single exception type
holds, so the annotation tolerates any and the orchestrator's check for surviving annotations is the
guard; the seam's module has to exist before the property does, so something lands a stub.
