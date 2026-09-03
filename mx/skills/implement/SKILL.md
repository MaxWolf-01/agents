---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
---

Implement the work described by the user in the spec or tickets (fetch them per `/mx:tracker`).

Use /mx:tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Read before you write: the files you are changing, their callers, the tests that cover them. Never speculate about code you haven't opened.

If you find yourself making a design decision mid-ticket, or reaching for a hack, workaround, or deviation from intent, stop. That belongs upstream: escalate to the user, or see /mx:orient for the flow and circle back to the right stage.

Your blast radius is your worktree: everything you create, install, or modify lives inside it. A missing system dependency, an absent global tool, a service that isn't running: report it as a **blocker**, never solve it. Say what you hit, finish whatever doesn't depend on it, and stop there. This holds on every host, and a dispatched worker's blocker is what routes its ticket to the human queue.

A decision you make alone is an **assumption**, not a decision. When one is genuinely too small to escalate, record it as such: an `Assumptions` block in the ticket's closing comment, attributed to you, never woven into spec, map, or ADR language. QA ratifies or reverses assumptions; presenting your judgment call as settled poisons every later agent's picture of what the user chose.

Write each one anchored, so it can be shown where it applies:

```
- A3 `path/file.py:118`: the call and why
```

The id and the anchor are what let the ticket's review page project the assumption onto the line it concerns, which is where the user rules on it. Ids are permanent, and a later round continues from the highest already in the ticket: a reversed call gets a fresh id that supersedes the old bullet, and a duplicate id fails the render outright. When you answer the user's review comments, open that round's comment with `Addressed: C1, C4`, naming them as the export shows them; that line is what marks them resolved on the page.

Inherited framing has the same status: an approach or option list an agent wrote into the ticket, even one the user waved through with a "sure, try it", is an assumption, settled only by a grilling verdict, an ADR, or a spec decision. Before building, name the premise the ticket's approach rests on; if an option outside that frame beats everything inside it, escalate first.

Once done, use /mx:code-review to review the work.

Close with **evidence, not claims**: when announcing what now works, hand the user something they can skim in seconds (a screenshot, a driven CLI or app transcript, the exact command to reproduce) instead of making them re-derive the demo. Before a drivable surface exists, this evidence *is* the QA surface.

If something fought you (a missing feedback loop, a tooling gap, a slow or flaky suite), name it in your closing comment rather than just enduring it: what you hit, what you did instead, what would have saved the time. Deciding what becomes of it belongs to the agent that dispatched you, which fixes it, raises it, or files it as a task once the user has ruled.

Commit your work to the current feature branch.
