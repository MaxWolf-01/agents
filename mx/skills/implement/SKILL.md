---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
---

Implement the work described by the user in the spec or tickets (fetch them per `/mx:tracker`).

Use /mx:tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

If you find yourself making a design decision mid-ticket, or reaching for a hack, workaround, or deviation from intent — stop. That belongs upstream: escalate to the user, or see /mx:orient for the flow and circle back to the right stage.

A decision you make alone is an **assumption**, not a decision. When one is genuinely too small to escalate, record it as such — an `Assumptions` block in the ticket's closing comment, attributed to you — never woven into spec, map, or ADR language. QA ratifies or reverses assumptions; presenting your judgment call as settled poisons every later agent's picture of what the user chose.

Once done, use /mx:code-review to review the work.

Close with **evidence, not claims**: when announcing what now works, hand the user something they can skim in seconds — a screenshot, a driven CLI or app transcript, the exact command to reproduce — instead of making them re-derive the demo. Before a drivable surface exists, this evidence *is* the QA surface.

If something fought you — a missing feedback loop, a tooling gap, a slow or flaky suite — encode the fix rather than just enduring it: file it as a small task per `/mx:tracker`, so the system improves for every later ticket.

Commit your work to the current feature branch.
