# Does a strict expected-failure mark carry a property ahead of its seam?

One Hypothesis property at a stubbed seam (`seam_stub.py` raises `NotImplementedError`), marked
`xfail(strict=True, raises=NotImplementedError)`, run under pytest 9 / Hypothesis 6 on 2026-09-09
in a throwaway tree (`/var/tmp/xfail-proto`, `pythonpath = .`). The seam was rewritten between runs.

| seam state | mark | run |
| --- | --- | --- |
| stub raising `NotImplementedError` | strict, `raises=NotImplementedError` | `1 xfailed`: green |
| correct implementation, mark left in place | same | `FAILED [XPASS(strict)]`: red until the mark is deleted |
| wrong implementation, mark left in place | same | `FAILED AssertionError` with the falsifying example: red |
| stub, and a bug in the property's own body before the seam call | same | `FAILED AttributeError`: the property's bug is visible |
| stub, and the same bug in the property's body | strict, no `raises=` | `1 xfailed`: the property's bug is hidden |
| the seam's module does not exist | any | collection error: no mark reaches it |

Verdicts: `raises=` is load-bearing, it is what makes a wrong implementation and a broken property
both visible; the seam's module has to exist before the property does, so something lands a stub.
