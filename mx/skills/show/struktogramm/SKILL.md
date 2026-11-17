---
name: struktogramm
description: "Draws a procedure as a Nassi-Shneiderman diagram (Struktogramm, DIN 66261), nested boxes with no arrows, rendered to HTML and checked in a browser. Use when someone asks for a Nassi-Shneiderman diagram, a Struktogramm or a structured flowchart, or wants an algorithm, recipe, protocol or troubleshooting procedure drawn as boxes rather than arrows."
---

# Struktogramm

A Nassi-Shneiderman diagram has no arrows: a block's successor is the block below it, and its body
is the block inside it. Anything drawn in it is therefore structured, and every point inside the
outer rectangle belongs to exactly one block.

## Drawing one

1. Write the procedure as a node list (Modelling, then Node schema).
2. Render it: `python scripts/struktogramm.py diagram.json -o out.html`.
3. Check it: `python scripts/check_layout.py out.html`, then again with `--scheme dark`. The
   step is done when both print PASS; `--help` lists what each FAIL means. Then render a picture
   with `python scripts/preview.py diagram.json` and look at it, for what no check judges: whether
   the diagram reads well. Where neither script can run, say the layout is unverified.

## Modelling

**Find the hidden loops.** "Simmer until reduced", "knead until smooth" and "retry until the
connection succeeds" are post-tested loops written as single steps. Drawn as loops, their exit
conditions are on the page instead of buried in a verb, which is most of what the notation adds
over a numbered list.

**Draw a branch only where the paths differ.** A branch earns its place when its two paths do
different things afterwards; "season to taste" is a statement.

**Extract before you nest deeply.** Past three levels the diagram gets too wide to read
(Rendering says why): pull the inner part into a diagram of its own and reference it with a
`call` node.

## Node schema

A diagram is a JSON list of nodes, each with a `type`. Any `body` or track takes a full node list,
so constructs nest to any depth.

```json
[
  {"type": "stmt", "text": "Render guanciale", "sub": "until crisp, keep the fat"},
  {"type": "call", "text": "Refresh starter", "sub": "see separate diagram"},
  {"type": "loop", "cond": "while lo <= hi", "body": [ ... ]},
  {"type": "loop", "kind": "post", "cond": "until the centre reads 96 °C", "body": [ ... ]},
  {"type": "exit", "text": "binary search"},
  {"type": "if", "cond": "Guanciale available?", "yes": {"body": [ ... ]}, "no": {"body": [ ... ]}},
  {"type": "case", "cond": "compare a[mid] with x", "branches": [
    {"label": "a[mid] < x", "body": [ ... ]},
    {"label": "a[mid] = x", "body": [ ... ]},
    {"label": "a[mid] > x", "body": [ ... ]}]},
  {"type": "par", "cap": "in parallel", "join": "wait for both, then plate", "tracks": [[ ... ], [ ... ]]}
]
```

- `stmt` is one step; `sub` is an optional dimmer second line for detail that would bloat the
  text (temperatures, doneness cues, caveats).
- `call` is a step that expands into a diagram of its own, drawn with doubled side bars.
- `loop` tests its `cond` before each pass of its body; `"kind": "post"` tests after, for a body
  that always runs once.
- `exit` leaves the enclosing block its `text` names, and execution goes on with the block after
  that one: DIN 66261's *Abbruchanweisung*, as the RWTH Aachen course notes draw it
  (<https://www.igpm.rwth-aachen.de/Download/ws2021/cpp/nassi.pdf>, section 1.3.3).
- `if` labels its columns `yes` and `no`; a `"label"` inside `yes` or `no` replaces either. An
  empty `body` is an empty box.
- `case` has one column per branch, each under its `label`.
- `par` tracks run at the same time, and nothing below the block starts until every track has
  finished.

## Extensions

These optional fields are this skill's own, outside DIN 66261, so a reader who knows
Struktogramme will not have seen them.

- **Inputs.** `{"type": "inputs", "title": "ingredients", "items": ["2 eggs", "100 g flour"]}` is
  a block listing what the procedure takes: ingredients, arguments, state. Put it first.
- **Duration.** `"time": "20 min"` on any node sets a duration apart from its text, at the block's
  right edge, in its loop's band, or under its branch's condition. A block's height says nothing
  about how long it takes.
- **Return and raise.** `"kind": "return"` or `"kind": "raise"` on an `exit` leaves the whole
  procedure, with its `text` as the result or the error; a raise draws a doubled notch.
- **Shared resource.** A `par` track written as `{"uses": "the oven", "body": [ ... ]}` names
  what it holds, in a row under the top band, so tracks contending for one thing show it.

## Rendering

```bash
python scripts/struktogramm.py diagram.json -o out.html     # standalone page
python scripts/struktogramm.py diagram.json --fragment      # <style> and the diagram, for embedding
```

From Python: `page(nodes)` returns the document, `fragment(nodes)` the embeddable part, and
`min_width(nodes)` the diagram's width in pixels.

Width carries no meaning in the notation, so a block's columns are drawn equal whatever their
content, and the diagram is at least as wide as its narrowest column needs to be to hold that
column's longest word; a page narrower than that scrolls sideways, and a host that
embeds the fragment in a narrower box gives the box `overflow-x: auto`.

Colours are the CSS variables `--text-primary`, `--text-secondary` and `--border-strong`. Without
them the diagram follows the reader's light or dark setting; a page with a palette of its own (a
house style's tokens) maps that palette onto these three variables in its own CSS.

## Delivering

Prefer a file the user can open, print or keep; where the host renders inline HTML, the
`--fragment` output embeds as it is. When the diagram is one of several alternatives under
discussion, render each and let the user compare.
