# Nassi-Shneiderman notation

Ike Nassi and Ben Shneiderman published the notation in 1973 as a replacement for
flowcharts. German-speaking countries standardised it as DIN 66261 and call the
result a *Struktogramm*; that is where most surviving material comes from.

The defining property: **there are no arrows.** Control flow is expressed purely
by containment and vertical adjacency. A block's successor is the block below it;
a block's body is the block nested inside it. This is not a stylistic choice —
it is what makes the notation refuse to express `goto`. Anything you can draw is
structured by construction.

Two consequences worth holding onto while drawing:

- **No empty space.** Every point inside the outer rectangle belongs to exactly
  one block. If a branch's column is shorter than its sibling, it stretches. An
  empty branch is an empty *box*, not a gap.
- **Borders are shared.** Two adjacent blocks meet along one line, not two
  parallel lines a pixel apart. Doubled borders are the most common rendering
  bug and they make the diagram look like a table of unrelated cells.

## Constructs

| Construct | Drawing | Node type |
|---|---|---|
| Statement | Plain rectangle | `stmt` |
| Sub-diagram call | Rectangle with doubled left and right edges | `call` |
| Pre-tested loop | Condition band across the top, body inset from the left | `loop` |
| Post-tested loop | Body first, condition band across the bottom | `loop`, `kind: post` |
| Two-way branch | Triangle band splitting into two columns | `if` |
| n-way case | Fan of diagonals over n labelled columns | `case` |
| Parallel | Two trapezoid bands enclosing side-by-side tracks | `par` |

The inset on a loop body is the visual signature of iteration: the L-shape of the
enclosing block wraps the repeated part. A post-tested loop puts the condition at
the bottom because the body runs at least once before the test — the drawing
mirrors the execution order.

The branch band is a triangle whose apex points down at the boundary between the
two columns. The `yes` and `no` labels sit in the bottom corners, each above its
own column. For an n-way case the diagonals fan from the top-left corner to each
column boundary, and the condition text sits in the wedge on the right.

The parallel block is the one construct that breaks the single-thread reading.
Tracks inside it run concurrently and the bottom band is a join: nothing below
the block starts until every track has finished. Standard NS diagrams are
otherwise strictly sequential.

## Choosing loop vs. branch for real-world processes

Recipes, protocols, and procedures usually contain more iteration than their
prose form admits. "Simmer until reduced by half" is a post-tested loop, not a
statement — the cook checks, and repeats if not. "Knead until the dough passes
the windowpane test" likewise. Rendering these as loops is the main thing a
Struktogramm adds over a numbered list: the repetition and its exit condition
become visible instead of buried in a verb.

Conversely, do not manufacture branches. "Add salt to taste" is a statement. A
branch is warranted when the two paths genuinely differ in what happens next.

## What the notation cannot express

- **Quantities and data.** There is no parameter or variable notation. Ingredient
  amounts, function arguments, and state have to live in the block text or in a
  separate list beside the diagram.
- **Timing.** A block's height is determined by its text, not its duration. A
  20-second step and a 12-hour step look identical.
- **Interrupts and early exit.** `break`, `return` from the middle, and exception
  handling have no standard drawing. Convention is to write them as a statement
  and accept that the containment no longer tells the whole story.
- **Shared resources.** Parallel tracks that contend for one oven or one mutex
  look independent. Note the contention in the join band's text.

## Layout facts that matter when rendering

- Column widths in a branch or case are equal by default. Unequal widths carry no
  meaning in the notation, so do not size columns by content length.
- Nesting depth is unbounded but readability collapses past three or four levels.
  Past that, extract the inner part into a sub-diagram and reference it with a
  `call` block. This is the same refactoring as pulling out a function, and the
  doubled side bars are the visual cue.
- A wide diagram is a design smell. Deeply nested branches inside branches
  produce columns too narrow for their text. The fix is extraction, not a wider
  canvas.
