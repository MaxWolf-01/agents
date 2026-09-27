# Cutting a ticket into child tickets

Work bigger than one fresh worker is cut into **child tickets**: tracer-bullet vertical slices of the ticket that holds the design, each declaring the tickets that **block** it. One slice means no cut, and the ticket is itself the thing built.

Cut as soon as the grilling's frontier is empty (`/mx:grilling`), ratified or not: what the user has not ruled on travels into the child tickets as the assumptions their workers carry. The ticket being cut is not rewritten, beyond numbering properties an earlier round left without ids; an id is bookkeeping, not design.

## 1. Read the code first

Understand the current state of the code before slicing. Ticket titles and bodies use the vocabulary of `CONTEXT.md` and respect the ADRs in `decisions/` for the area being touched. Look for prefactoring that makes the implementation easier: make the change easy, then make the easy change.

## 2. Draft the slices

<vertical-slice-rules>

- Each slice cuts a narrow but COMPLETE path through every layer (schema, API, UI, tests): vertical, NOT a horizontal slice of one layer
- A completed slice is drivable or verifiable on its own
- Each slice is sized to fit in a single fresh context window
- Any prefactoring should be done first

</vertical-slice-rules>

Give each its **blocking edges**: the tickets that must be done before it can start. Prefer orderings that make the work **drivable early**: human QA is gated on what it costs to drive the work, and every slice that lands before a drivable surface exists accumulates unreviewed taste debt.

**Mark the hinges.** A slice is a **hinge** when the slices it blocks would have to be rewritten, not amended, were it wrong: an interface or data shape they consume. The user rules on a hinge alone before its dependents start; every other slice is ruled with the ticket being cut, at its close-out, and its dependents build on it unruled. Test each blocking edge: if the blocker came back wrong, would the fix to the dependent be an amend? Then it is no hinge.

**Properties stay on the ticket being cut.** Every slice reads them through its ancestry and cites one as `<slug>#P<n>`; no slice copies one. The ticket's Testing seams already marked each property executable or reviewed:

- **Executable**: one child ticket turns them all into checks in the project's properties directory (`tests/properties/`) before any slice is built, so no check can copy an implementation, since none exists yet. It is blocked by nothing, blocks every slice whose seam it checks, and is a hinge, since every slice builds against its checks. Its brief is the ancestry and the seams' interfaces; where an interface does not exist yet, it lands a stub so the suite collects. A check that cannot hold yet lands as an expected failure (`/mx:testing`) naming the one slice that makes it pass, and the ticket's body lists that slice beside each property. It sits in the cross-cutting position below.
- **Reviewed**: each slice's review checks it, reading the ancestry with the diff.

A property no single slice can make hold means the cut is wrong: merge the slices, or split the property at the seam.

**Stamp floors.** A slice building a surface with a promoted floor (the ticket's Decisions) carries it as an acceptance criterion: "the prototype at `<path>` is the quality floor: match it or consciously beat it; its incidental slop is not the target; name deviations in the closing comment."

**A part whose question you can state now, but whose answer nobody holds, is a child ticket like any other**: its acceptance criteria say what is decided, the answer lands in the Decisions of the ticket being cut, and every slice that needs the answer is blocked by it. One the user has to be in the loop for carries `needs-user`. A part whose question cannot yet be phrased stays in Fog, sliced once an answer sharpens it.

**Wide refactors are the exception to vertical slicing.** A **wide refactor** is one mechanical change (rename a column, retype a shared symbol) whose **blast radius** fans across the whole codebase, so a single edit breaks thousands of call sites at once and no vertical slice can land green. Don't force it into a tracer bullet; sequence it as **expand-contract**. First expand: add the new form beside the old so nothing breaks. Then migrate the call sites over in batches sized by blast radius (per package, per directory), each batch its own ticket blocked by the expand, keeping CI green batch to batch because the old form still exists. Finally contract: delete the old form once no caller remains, in a ticket blocked by every migrate batch. When even the batches can't stay green alone, keep the sequence but let them share an integration branch that all block a final integrate-and-verify ticket; green is promised only there.

**Cross-cutting capabilities are the second exception.** A property usually needs one deliberately horizontal capability ticket (the shared renderer, the error boundary) that exists so every vertical slice after it can lean on it. Schedule it early and block the slices that need it on it. Greenfield is where these are most invisible: nothing exists yet to make their absence obvious.

## 3. File them

`tracker new <slug> --parent <the ticket being cut> --priority <1 to 5> --size <XS to XL>` per slice, `--hinge` on a hinge, in dependency order, each `proposed`: its ruling comes from what it built. The **priority** comes from what the user has said about the work and the slice's place in it; the **size** is the user's own time on the slice, which for most of them is reading the closing comment and the show.

Write each body per the ticket file's shape (`/mx:tracker`, The ticket file). The brief names the calls of the parent ticket this slice rests on, by their call marks, so its worker carries them as anchored assumptions on the lines they shaped, and the landing shows the user each one on the intent side.

**The breakdown is filed when the check is clean.** `property-coverage` holds every executable property to having a check and names what does not line up, at the line it read; its `--help` is its reference. Fix what it names and run it again.

## 4. Show the breakdown, then dispatch

Render the board (`/mx:tracker`) and present the breakdown in chat as a numbered list: slug, blocked by, what it delivers, with the granularity and the edges you are least sure of named, so the user knows where to look. The step is done when the board is on disk and `/mx:dispatch` holds the frontier.

`/mx:dispatch` takes it straight away, at any size: a fresh worker per ticket, one at a time or in waves. Each hinge is then ruled on alone from what it built, and the rest with the ticket being cut, at its close-out, on the calls their landing shows the user.
