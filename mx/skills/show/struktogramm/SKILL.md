---
name: struktogramm
description: "Render Nassi-Shneiderman diagrams (Struktogramme, DIN 66261) as clean HTML/CSS with shared borders and no arrows. Use this whenever the user mentions Nassi-Shneiderman, Struktogramm, NS diagram, or structured flowchart, and also whenever they want any procedure drawn as nested boxes rather than a flowchart with arrows: algorithms, recipes, checklists, decision procedures, protocols, or troubleshooting trees. Reach for this any time someone asks to visualize control flow, loops, or branching structure without arrows, or asks to turn a numbered list of steps into a diagram."
---

# Struktogramm

A Nassi-Shneiderman diagram draws a procedure as nested rectangles with no arrows. The block
below is the successor, the block inside is the body. `references/notation.md` says what each
construct means and what the notation cannot express; read it before drawing anything with more
than a few blocks.

## Drawing one

1. Write the procedure as a node list (schema below). This is the step that takes judgement; see
   Modelling.
2. Render it with `scripts/struktogramm.py`.
3. Measure the render with `scripts/check_layout.py`, in both colour schemes. Look at it too, with
   `scripts/preview.py`.
4. Deliver it as a file, or inline where the host renders HTML.

## Node schema

A diagram is a JSON list of nodes, each with a `type`:

```json
[
  {"type": "stmt", "text": "Salt water, bring to a boil"},
  {"type": "stmt", "text": "Render guanciale", "sub": "until crisp, keep the fat"},

  {"type": "call", "text": "Refresh starter", "sub": "see separate diagram"},

  {"type": "loop", "cond": "while lo <= hi", "body": [ ... ]},
  {"type": "loop", "kind": "post", "cond": "until the centre reads 96 °C", "body": [ ... ]},
  {"type": "exit", "text": "binary search"},

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

- `sub` is an optional dimmer second line, for the detail that would bloat the main text:
  temperatures, doneness cues, caveats.
- `call` draws doubled side bars: this block expands into a diagram of its own.
- `loop` is tested before its body unless `"kind": "post"` puts the test after it, for a body
  that always runs once.
- `exit` names in its `text` the enclosing block it leaves.
- `if` labels its columns `yes` and `no`; a `"label"` inside `yes` or `no` replaces either. An
  empty `body` draws an empty box.
- `par` tracks run at the same time, and the bottom band waits for all of them.

Any `body` or track takes a full node list, so constructs nest to any depth.

## Rendering

```bash
python scripts/struktogramm.py diagram.json -o out.html     # standalone page
python scripts/struktogramm.py diagram.json --fragment      # <style> and the diagram, for embedding
```

From Python, `page(nodes)` returns the document and `fragment(nodes)` the embeddable part:

```python
import sys; sys.path.insert(0, "scripts")
from struktogramm import page, fragment
```

The renderer needs nothing past Python's standard library. Its colours are the CSS variables
`--text-primary`, `--text-secondary` and `--border-strong`: a host page that sets them themes the
diagram, and without them it follows the reader's light or dark setting.

## Verify the layout

Whether a Struktogramm is drawn right shows only in the rendered page; the markup of a broken one
and a correct one differ by a CSS rule. The checker opens the page in headless Chromium through
Playwright and measures it:

```bash
python scripts/check_layout.py out.html                  # light scheme, 680px wide
python scripts/check_layout.py out.html --scheme dark
python scripts/preview.py diagram.json --scheme dark     # writes preview.html and preview.png
```

It prints PASS, or a FAIL line per fault, and exits non-zero on a fault; its `--help` lists the
checks. Look at the preview as well, for what no check judges: whether the diagram reads well.
Where neither script can run, say that the layout is unverified rather than that it is correct.

## Modelling

The rendering is mechanical; the modelling is where the work is.

**Find the hidden loops.** Prose flattens iteration. "Simmer until reduced", "knead until
smooth" and "retry until the connection succeeds" are post-tested loops written as single steps.
Drawn as loops, their exit conditions are on the page instead of buried in a verb, which is most
of what the notation adds over a numbered list.

**Draw a branch only where the paths differ.** "Season to taste" is a statement. A branch earns
its place when its two paths do different things afterwards.

**Extract before you nest deeply.** Past three levels the columns get too narrow for their text,
and a wider canvas only postpones it. Pull the inner part into a diagram of its own and reference
it with a `call` node, as you would extract a function.

## Delivering the result

Prefer a file the user can open, print or keep; where the host renders inline HTML, the
`--fragment` output embeds as it is. When the diagram is one of several alternatives under
discussion, render each and let the user compare.

The notation has no way to show quantities. For a recipe, put the ingredient list beside the
diagram rather than amounts in the blocks.
