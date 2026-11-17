# Prototype in the mx workflow

Where a captured prototype goes, and how its floors reach the tickets, beside the rules of [`SKILL.md`](SKILL.md).

## Capture it when done (rule 7)

A captured prototype moves to `agent/prototypes/<slug>/` and is committed there: that directory is the agent repo's, so `git -C agent` is what commits it. It stays there while the work it served is built, and leaves the tree when that work retires (`/mx:tracker`, Retire), which git history keeps. A UI prototype's losing variants and switcher go there too ([UI.md](UI.md), step 6).

## Floor promotion (rule 8)

The ticket holding the design lists floors, and the cut stamps them onto the child tickets building those surfaces (`/mx:tracker`, SLICING.md).
