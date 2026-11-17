---
name: struktogramm
description: "Render Nassi-Shneiderman diagrams (Struktogramme, DIN 66261) as clean HTML/CSS with shared borders and no arrows. Use this whenever the user mentions Nassi-Shneiderman, Struktogramm, NS diagram, or structured flowchart, and also whenever they want any procedure drawn as nested boxes rather than a flowchart with arrows — algorithms, recipes, checklists, decision procedures, protocols, or troubleshooting trees. Reach for this any time someone asks to visualize control flow, loops, or branching structure without arrows, or asks to turn a numbered list of steps into a diagram."
---

# Struktogramm

Nassi-Shneiderman diagrams draw a procedure as nested rectangles with no arrows.
Successor means "the block below", body means "the block inside". Read
`references/notation.md` before drawing anything non-trivial — it covers what
each construct means, which real-world steps are secretly loops, and what the
notation cannot express.

## Workflow

1. Convert the procedure to a node list (schema below). This is the modelling
   step and the one that carries the judgement — see "Modelling" below.
2. Render it with `scripts/struktogramm.py`.
3. **Verify the layout.** Run `scripts/check_layout.py`, which measures the
   rendered boxes. Optionally also screenshot with `scripts/preview.py` and look
   at it.
4. Deliver as a file, or inline in the conversation if the host supports HTML.

## Node schema

A diagram is a JSON list of nodes. Every node has a `type`.

```json
[
  {"type": "stmt", "text": "Salt water, bring to a boil"},
  {"type": "stmt", "text": "Render guanciale", "sub": "until crisp, keep the fat"},

  {"type": "call", "text": "Refresh starter", "sub": "see separate diagram"},

  {"type": "loop", "cond": "while lo <= hi", "body": [ ... ]},
  {"type": "loop", "kind": "post", "cond": "until the centre reads 96 °C", "body": [ ... ]},

  {"type": "if", "cond": "Guanciale available?",
   "yes": {"body": [ ... ]},
   "no":  {"body": [ ... ]}},

  {"type": "case", "cond": "compare a[mid] with x", "branches": [
    {"label": "a[mid] < x", "body": [ ... ]},
    {"label": "a[mid] = x", "body": [ ... ]},
    {"label": "a[mid] > x", "body": [ ... ]}
  ]},

  {"type": "par", "cap": "in parallel", "join": "wait for both, then plate",
   "tracks": [[ ... ], [ ... ]]}
]
```

Field notes:

- `sub` is an optional dimmer second line. Use it for the detail that would
  otherwise bloat the main text — temperatures, doneness cues, caveats.
- `call` draws doubled side bars, the notation's marker for "this expands into
  its own diagram". Use it when nesting would otherwise exceed three levels.
- `loop` defaults to pre-tested. `"kind": "post"` moves the condition band to the
  bottom, for bodies that always run at least once.
- `if` branch labels default to `yes` / `no`; override with `"label"` inside the
  `yes` or `no` object. An empty `body` renders as an empty box, which is correct
  — the notation has no gaps.
- `par` tracks run concurrently and the bottom band is a join.

Bodies nest arbitrarily. Anything accepting a `body` or a track accepts the full
node list, including another `par`.

## Rendering

```bash
python scripts/struktogramm.py diagram.json -o out.html          # standalone page
python scripts/struktogramm.py diagram.json --fragment            # <style> + <div>, for embedding
python scripts/struktogramm.py diagram.json --dark -o out.html    # dark theme
```

Or import it:

```python
import sys; sys.path.insert(0, "scripts")
from struktogramm import render, page, CSS
html = page(nodes)          # full document
frag = render(nodes)        # just the <div class="ns">, pair with CSS
```

Colours come from `--text-primary`, `--text-secondary`, and `--border-strong`,
each with a literal fallback. The output therefore inherits a host page's theme
when one exists and still renders correctly when dropped into a bare file.

## Verify the layout

Struktogramm correctness is a property of the rendered boxes, not of the markup.
Broken and correct output differ by a CSS rule, so reading the HTML proves
nothing. Measure it:

```bash
python scripts/struktogramm.py diagram.json -o out.html
python scripts/check_layout.py out.html            # add --browser <path> if needed
```

It reports every block and column group it measured, then PASS or a specific
FAIL. Exits non-zero on failure, so it can gate a build. What it catches:

- **column-not-filled** — a column whose last block stops short of the column's
  bottom edge, leaving unbordered dead space. This is the most common fault and
  it hides easily: it is invisible whenever the sibling column happens to be a
  similar height, so it survives casual inspection and then appears the moment
  the content changes.
- **columns-equal-height** — sibling columns that failed to stretch together.
- **fan-column-widths** — unequal case columns, which would imply a meaning the
  notation does not have.
- **no-zero-size** — a block that never got laid out.

Screenshots are a useful supplement but a weak check, because these faults are
only visible in the specific content that exposes them:

```bash
python scripts/preview.py diagram.json --dark --height 1600
```

If neither tool can run — no browser, no Playwright — say the layout is
unverified rather than claiming it is correct.

## Modelling

The rendering is mechanical; the modelling is where the work is. Three habits:

**Find the hidden loops.** Prose flattens iteration. "Simmer until reduced",
"knead until smooth", "retry until the connection succeeds" are all post-tested
loops written as if they were single steps. Drawing them as loops is most of the
value the notation adds over a numbered list — the exit condition stops being
buried in a verb.

**Do not manufacture branches.** "Season to taste" is a statement. A branch earns
its place when the two paths genuinely diverge in what happens afterwards.

**Extract before you nest deeply.** Past three levels the columns get too narrow
for their text. Pull the inner section into its own diagram and reference it with
a `call` node. Same judgement as extracting a function.

## Delivering the result

Prefer a file the user can open, print, or keep. If the host renders inline HTML,
the `--fragment` output embeds directly. When the diagram is one of several
alternatives under discussion, render each and let the user compare rather than
picking for them.

Quantities have no place in the notation itself — there is no data or parameter
notation. For a recipe, put the ingredient list beside the diagram rather than
cramming amounts into the blocks.
