# Cutting a ticket into child tickets

Work bigger than one fresh worker is cut into **child tickets**: tracer-bullet vertical slices of the ticket that holds the design, each declaring the tickets that **block** it. One slice means no cut, and the ticket is itself the thing built.

Cut as soon as the grilling's frontier is empty (`/mx:grilling`), ratified or not: what the user has not ruled on travels into the child tickets as the assumptions their workers carry. The ticket being cut is not rewritten, beyond numbering properties an earlier round left without ids; an id is bookkeeping, not design.

## 1. Read the code first

Understand the current state of the code before slicing. Ticket titles and bodies use the vocabulary of `CONTEXT.md` and respect the ADRs in `decisions/` for the area being touched. Look for prefactoring that makes the implementation easier: make the change easy, then make the easy change.

## 2. Draft the slices

<vertical-slice-rules>

- Each slice cuts a narrow but COMPLETE path through every layer (schema, API, UI, tests): vertical, NOT a horizontal slice of one layer
- A completed slice is demoable or verifiable on its own
- Each slice is sized to fit in a single fresh context window
- Any prefactoring should be done first

</vertical-slice-rules>

Give each its **blocking edges**: the tickets that must be done before it can start. Prefer orderings that make the work **drivable early**: human QA is gated on demo cost, and every slice that lands before a drivable surface exists accumulates unreviewed taste debt.

**The properties stay where they are.** They hold for the ticket being cut and every descendant reads them through its ancestry, so no slice restates them and no criterion stamps one. That ticket's Testing seams already disposed of each: every property marked **executable** shares one child ticket that builds them all as checks in the project's properties directory (`tests/properties/`), blocked by nothing and blocking every slice at their seams, briefed with the ancestry and the seams' interfaces, since the implementation it must not copy does not exist yet when its worktree is cut. Where a seam is a function or a module API that does not exist yet, that ticket lands its interface as a stub so the suite collects, and a property that cannot hold yet lands as an expected failure (`/mx:testing`) naming the slice that lifts it; that ticket's body assigns each property its one lifting slice beside its seam. It is an ordinary child ticket in the cross-cutting position below. A property marked **reviewed** is checked by each slice's review, which reads the ancestry with the diff. A property no single slice can make hold is a slicing signal: merge the slices, or split the property at the seam.

**Stamp floors.** A slice building a surface with a promoted floor (the ticket's Decisions) carries it as an acceptance criterion: "the prototype at `<path>` is the quality floor: match it or consciously beat it; its incidental slop is not the target; name deviations in the closing comment."

**A part whose question you can state now, but whose answer nobody holds, is a child ticket like any other**: its acceptance criteria say what is decided, the answer lands in the Decisions of the ticket being cut, and every slice that needs the answer is blocked by it. One the user has to be in the loop for carries `needs-user`. A part whose question cannot yet be phrased stays in Fog, sliced once an answer sharpens it.

**Wide refactors are the exception to vertical slicing.** A **wide refactor** is one mechanical change (rename a column, retype a shared symbol) whose **blast radius** fans across the whole codebase, so a single edit breaks thousands of call sites at once and no vertical slice can land green. Don't force it into a tracer bullet; sequence it as **expand-contract**. First expand: add the new form beside the old so nothing breaks. Then migrate the call sites over in batches sized by blast radius (per package, per directory), each batch its own ticket blocked by the expand, keeping CI green batch to batch because the old form still exists. Finally contract: delete the old form once no caller remains, in a ticket blocked by every migrate batch. When even the batches can't stay green alone, keep the sequence but let them share an integration branch that all block a final integrate-and-verify ticket; green is promised only there.

**Cross-cutting capabilities are the second exception.** A property usually needs one deliberately horizontal capability ticket (the shared renderer, the error boundary) that exists so every vertical slice after it can lean on it. Schedule it early and block the slices that need it on it. Greenfield is where these are most invisible: nothing exists yet to make their absence obvious.

## 3. File them

`tracker new <slug> --parent <the ticket being cut> --priority <1 to 5> --size <XS to XL>` per slice, in dependency order, each `proposed`: its ruling comes from what it built. The **priority** comes from what the user has said about the work and the slice's place in it; the **size** is the user's own time on the slice, which for most of them is reading the closing comment and driving the demo.

Write each body per the ticket file's shape (`/mx:tracker`, The ticket file). The brief names the calls of the parent ticket this slice rests on, by their call marks, so its worker carries them as anchored assumptions and the review page puts each in front of the user on the line it shaped.

**The breakdown is filed when the check is clean.** `property-coverage` holds every executable property to having a check and names what does not line up, at the line it read; its `--help` is its reference. Fix what it names and run it again.

## 4. Show the breakdown, then dispatch

Render the board (`/mx:tracker`) and present the breakdown in chat as a numbered list: slug, blocked by, what it delivers, with the granularity and the edges you are least sure of named, so the user knows where to look. The step is done when the board is on disk and `/mx:dispatch` holds the frontier.

`/mx:dispatch` takes it straight away, at any size: a fresh worker per ticket, one at a time or in waves. Each is then ruled on from what it built, on its review page and its demo.
