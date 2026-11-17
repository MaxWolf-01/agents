# Nassi-Shneiderman notation

Ike Nassi and Ben Shneiderman published the notation in 1973 as a replacement for flowcharts.
Germany standardised it as DIN 66261 (1985) and calls the result a *Struktogramm*, which is why
most surviving material is German.

The notation has no arrows. Control flow is containment and vertical adjacency: a block's
successor is the block below it, and its body is the block nested inside it. So the notation
cannot express `goto`, and anything drawn in it is structured.

Two rules follow, and a render that breaks either is wrong:

- **No empty space.** Every point inside the outer rectangle belongs to exactly one block. A
  column shorter than its sibling stretches to its height, and an empty branch is an empty box.
- **Shared borders.** Two adjacent blocks meet along one line. Two parallel lines a pixel apart
  make the diagram look like a table of unrelated cells.

## Constructs

| Construct | Drawing | Node type |
|---|---|---|
| Statement | Plain rectangle | `stmt` |
| Sub-diagram call | Rectangle with doubled left and right edges | `call` |
| Pre-tested loop | Condition band across the top, body inset from the left | `loop` |
| Post-tested loop | Body first, condition band across the bottom | `loop`, `kind: post` |
| Early exit | Rectangle with a notch pointing left, naming the block it leaves | `exit` |
| Two-way branch | Triangle band splitting into two columns | `if` |
| n-way case | Fan of diagonals over n labelled columns | `case` |
| Parallel | Two trapezoid bands enclosing side-by-side tracks | `par` |

The inset of a loop's body is the sign of iteration: the L-shaped enclosing block wraps the part
that repeats. A post-tested loop puts its condition at the bottom because the body runs once
before the test.

The branch band is a triangle whose apex points down at the boundary between the two columns.
The condition sits in the triangle, and the `yes` and `no` labels in the bottom corners, each
above its own column. This skill draws an n-way case as a fan: diagonals from the top-left corner
to each column boundary, the condition in the wedge on the right, and the labels in a row of
their own above the columns. DIN 66261 draws it differently, with one diagonal from the top-left
corner to the left edge of the last column, one from the top-right corner to the same point, and
each label under the diagonal in its column.

The early exit is DIN 66261's *Abbruchanweisung*. It names an enclosing block, and execution goes
on with the block after that one, which is how a loop that only ends from inside its body is
drawn.

What this file says of DIN 66261's drawings, the case and the early exit, comes from a secondary
source: the RWTH Aachen IGPM course notes *Programmentwurf mit Struktogrammen*
(<https://www.igpm.rwth-aachen.de/Download/ws2021/cpp/nassi.pdf>, sections 1.2.3 and 1.3.3),
which draw the standard's symbols. The standard itself (DIN 66261:1985-11) is sold by DIN Media
and was not read.

The parallel block is the one construct that breaks the single-thread reading. Its tracks run at
the same time, and the bottom band is a join: nothing below the block starts until every track
has finished.

## What the notation cannot express

- **Quantities and data.** There is no notation for a parameter or a variable. Amounts,
  arguments and state go in the block text or in a list beside the diagram.
- **Timing.** A block's height comes from its text, not its duration: a 20-second step and a
  12-hour step look the same.
- **Exceptions and returns.** Only the early exit leaves a block from inside it. A `return` from
  the middle or an exception handler is written as a statement, and the containment no longer
  tells the whole story.
- **Shared resources.** Parallel tracks that contend for one oven or one mutex look independent.
  Note the contention in the join band's text.

## Layout

Columns in a branch or case have equal widths. Unequal widths carry no meaning in the notation,
so a renderer never sizes columns by their content.
