---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets (fetch them per the `tracker` skill).

Use /mx:tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

If you find yourself making a design decision mid-ticket, or reaching for a hack, workaround, or deviation from intent — stop. That belongs upstream: escalate to the user, or see /mx:orient for the flow and circle back to the right stage.

Once done, use /mx:code-review to review the work.

If something fought you — a missing feedback loop, a tooling gap, a slow or flaky suite — encode the fix rather than just enduring it: file it as a small task per the `tracker` skill, so the system improves for every later ticket.

Commit your work to the current feature branch.
