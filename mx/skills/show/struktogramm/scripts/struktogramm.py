#!/usr/bin/env python3
"""Render a Nassi-Shneiderman diagram (Struktogramm) from a JSON node list to HTML.

Standard library only. The node schema is in ../SKILL.md.

Two layout rules hold every diagram together, and most of the CSS serves one or the other:

- One line per boundary. Only cells draw borders, every cell draws all four, and every cell is
  pulled 1px up and 1px left so its top and left borders land on the lines its neighbours
  already drew. The root's 1px padding is where the outermost cells land. Containers (a branch,
  a parallel block, a column) draw nothing.
- No empty space. Every sequence is a flex column whose last block grows, and every container
  grows its columns, so a block that stretches passes the stretch on down to its innermost cells.

Band lines are inline SVG stretched over their band, so they meet the band's corners exactly at
any size. Text is placed where the lines cannot reach it: a branch's condition in the middle half
of the band's top half, its labels in the outer quarters of the bottom half, and the two halves
are grid rows of equal height. The diagonals pass through the corners of those regions and
through nothing else.

Columns are equal by the notation, so a word too long for the narrowest column cannot widen that
column alone. Instead the whole diagram gets a minimum width, estimated from every text's longest
word, at which every column holds its longest word; a page narrower than that scrolls sideways.
"""

import argparse
import json
import re
import sys
from html import escape

CSS = """
.ns { --ns-ink: var(--text-primary, #1a1a18); --ns-dim: var(--text-secondary, #6b6a64); --ns-line: var(--border-strong, #c9c7bd);
      font-size: 15px; line-height: 1.4; color: var(--ns-ink); padding: 1px 0 0 1px; overflow-wrap: break-word; }
@media (prefers-color-scheme: dark) {
  .ns { --ns-ink: var(--text-primary, #f0efe9); --ns-dim: var(--text-secondary, #9c9a92); --ns-line: var(--border-strong, #5a5954); }
}
.ns .seq, .ns .col, .ns .fork, .ns .par, .ns .loop, .ns .body { display: flex; flex-direction: column; }
.ns .seq { flex: 1 1 auto; }
.ns .seq > :last-child, .ns .fork > .cols, .ns .par > .cols, .ns .loop > .body { flex: 1 1 auto; }
.ns .cols, .ns .lbls { display: flex; }
.ns .cols > .col, .ns .lbls > * { flex: 1 1 0; min-width: 0; }
.ns .cell { border: 1px solid var(--ns-line); margin: -1px 0 0 -1px; position: relative; break-inside: avoid; }
.ns .blk { padding: 12px 14px; }
.ns .empty { min-height: 22px; }
.ns .sub { display: block; font-size: 12.5px; color: var(--ns-dim); margin-top: 2px; }
.ns .small { font-size: 12.5px; color: var(--ns-dim); }
.ns .call { border-left: 5px double var(--ns-line); border-right: 5px double var(--ns-line); padding: 12px 10px; }
.ns .exit { padding-left: 34px; }
.ns .loop > .cap { padding: 7px 14px; }
.ns .loop > .body { margin: 0 -1px 0 20px; }
.ns .loop.pre > .body { margin-bottom: -1px; }
.ns .cond { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); grid-template-rows: 1fr 1fr; }
.ns .cond > .q { grid-area: 1 / 2 / 2 / 4; padding: 8px 4px 2px; text-align: center; }
.ns .cond > .yes, .ns .cond > .no { grid-row: 2; align-self: end; padding: 2px 8px 5px; }
.ns .cond > .yes { grid-column: 1; }
.ns .cond > .no { grid-column: 4; text-align: right; }
.ns .case > .cond { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.ns .case > .cond > .q { grid-area: 1 / 2 / 2 / 3; padding: 8px 14px 2px 8px; text-align: right; }
.ns .lbls > * { padding: 5px 10px; text-align: center; }
.ns .par > .cap { padding: 6px 30px; text-align: center; }
.ns .ln { position: absolute; top: -1px; left: -1px; width: calc(100% + 2px); height: calc(100% + 2px);
          overflow: visible; pointer-events: none; stroke: var(--ns-line); stroke-width: 1px; fill: none; }
.ns .ln path { vector-effect: non-scaling-stroke; }
.ns .ln.l, .ns .ln.r { width: 26px; }
.ns .ln.r { left: auto; right: -1px; }
.ns .exit > .ln { width: 22px; }
.ns .exit.raise { padding-left: 44px; }
.ns .exit.raise > .ln { width: 34px; }
.ns .kw { font-variant: small-caps; letter-spacing: 0.04em; margin-right: 6px; }
.ns .time { float: right; margin: 0 0 0 14px; font-variant-numeric: tabular-nums; }
.ns .cond .time { display: block; float: none; margin: 2px 0 0; }
.ns .inputs > .kw, .ns .exit > .kw { display: block; margin-bottom: 2px; }
.ns .inputs > ul { display: flex; flex-wrap: wrap; gap: 2px 22px; margin: 0; padding: 0; list-style: none; }
"""


def render(nodes: list) -> str:
    """The diagram alone, a <div class="ns">; it needs CSS beside it."""
    return f'<div class="ns" style="min-width: {min_width(nodes):.0f}px">{_seq(nodes)}</div>'


def min_width(nodes: list) -> float:
    """The narrowest the diagram can be, in px, with every column holding its longest word."""
    return _need_seq(nodes) + 1


def page(nodes: list) -> str:
    """A standalone HTML document, for a file the user opens or prints."""
    return ('<!doctype html><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="color-scheme" content="light dark">'
            f"<style>{PAGE_CSS}{CSS}</style>"
            f'<body><div class="wrap">{render(nodes)}</div></body>')


def fragment(nodes: list) -> str:
    """<style> and the diagram, for embedding in a page whose theme it takes on."""
    return f"<style>{CSS}</style>\n{render(nodes)}"


PAGE_CSS = """
body { margin: 0; padding: 24px; background: #fdfdfb; font-family: system-ui, sans-serif; }
@media (prefers-color-scheme: dark) { body { background: #262624; } }
.wrap { width: min(720px, 100%); min-width: fit-content; margin: 0 auto; }
@media print { body { padding: 0; background: #fff; } }
"""


# The width of each character in em, near DejaVu Sans, the widest of the common sans faces, and a
# word's sum is taken 5% wider: an estimate, since the fonts are the reader's. A character not
# listed is 0.65em, and a CJK one 1em.
_EM = {**dict.fromkeys("ijlI.,:;'!|", 0.3), **dict.fromkeys("frt()[]/\\-\"", 0.42),
       **dict.fromkeys("ABCDGHKNOQRUVXYZw#&+<=>^~", 0.8), **dict.fromkeys("mMW%@\u2014", 1.0)}
BODY, SMALL = 15, 12.5  # px: the font sizes the CSS gives text and captions


def _word(text: str, size: float) -> float:
    """The width in px of the longest word in `text`, set at `size` px. A line may break after a
    hyphen, so each part of a hyphenated word counts alone."""
    em = lambda c: _EM.get(c, 1.0 if ord(c) >= 0x2E80 else 0.65)
    return max((sum(map(em, w)) * size for w in re.split(r"\s+|(?<=-)", text)), default=0) * 1.05


def _need_seq(nodes: list) -> float:
    return max(map(_need, nodes), default=0)


def _need(n: dict) -> float:
    """The narrowest a block can be with no word split: its widest text's longest word plus that
    text's padding, and for a block with columns, as many times its neediest column as it has."""
    kind = n.get("type", "stmt")
    text = max(_word(n.get("text", ""), BODY), _word(n.get("sub") or "", SMALL), _word(n.get("time") or "", SMALL))
    if kind == "inputs":
        return max(_word(n.get("title", "inputs"), SMALL), *(_word(i, BODY) for i in n["items"])) + 30
    if kind == "stmt":
        return text + 30
    if kind == "call":
        return text + 32
    if kind == "exit":
        return max(text, _word(n.get("kind", ""), SMALL)) + (60 if n.get("kind") == "raise" else 50)
    if kind == "loop":
        return max(_word(n["cond"], SMALL) + 30, 21 + _need_seq(n["body"]))
    if kind == "if":
        arms = [n.get("yes", {}), n.get("no", {})]
        band = max(2 * (_word(n["cond"], BODY) + 10),
                   *(4 * (_word(a.get("label", "yes"), SMALL) + 18) for a in arms))
        return max(band, 2 * max(_need_seq(a.get("body", [])) for a in arms))
    if kind == "case":
        branches = n["branches"]
        each = max(max(_word(b.get("label", ""), SMALL) + 22, _need_seq(b.get("body", []))) for b in branches)
        return max(2 * (_word(n["cond"], BODY) + 24), len(branches) * each)
    if kind == "par":
        tracks = _tracks(n)
        caps = max(_word(n.get("cap", "in parallel"), SMALL), _word(n.get("join", "wait for all"), SMALL),
                   _word(n.get("time") or "", SMALL)) + 62
        each = max(max(_word(f"uses {uses}", SMALL) + 22, _need_seq(body)) for uses, body in tracks)
        return max(caps, len(tracks) * each)
    return 0


def _seq(nodes: list) -> str:
    # An empty body is still one cell: the notation has no gaps, and an empty branch is a box.
    inner = "".join(_node(n) for n in nodes) if nodes else '<div class="cell blk empty"></div>'
    return f'<div class="seq">{inner}</div>'


def _lines(d: str, cls: str = "") -> str:
    """Band lines in a 100x100 box stretched over the band, so 0 and 100 are its edges."""
    return (f'<svg class="ln {cls}" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
            f'<path d="{d}"/></svg>')


def _time(node: dict) -> str:
    return f'<span class="time small">{escape(node["time"])}</span>' if node.get("time") else ""


def _tracks(n: dict) -> list:
    """Each parallel track as (the resource it uses or "", its node list); a track is a node list,
    or an object holding one as `body` beside the resource it names in `uses`."""
    return [(t.get("uses", ""), t.get("body", [])) if isinstance(t, dict) else ("", t) for t in n["tracks"]]


def _txt(node: dict) -> str:
    out = _time(node) + escape(node["text"])
    if node.get("sub"):
        out += f'<span class="sub">{escape(node["sub"])}</span>'
    return out


def _cols(bodies: list) -> str:
    return '<div class="cols">' + "".join(f'<div class="col">{_seq(b)}</div>' for b in bodies) + "</div>"


def _node(n: dict) -> str:
    kind = n.get("type", "stmt")
    if kind == "stmt":
        return f'<div class="cell blk">{_txt(n)}</div>'
    if kind == "call":
        return f'<div class="cell blk call">{_txt(n)}</div>'
    if kind == "exit":
        how = n.get("kind", "")
        notch = "M60 0 L0 50 L60 100 M100 0 L40 50 L100 100" if how == "raise" else "M100 0 L0 50 L100 100"
        kw = f'<span class="kw small">{escape(how)}</span>' if how else ""
        return f'<div class="cell blk exit {escape(how)}">{_lines(notch)}{_time(n)}{kw}{_txt(n | {"time": None})}</div>'
    if kind == "inputs":
        items = "".join(f"<li>{escape(i)}</li>" for i in n["items"])
        return f'<div class="cell blk inputs"><span class="kw small">{escape(n.get("title", "inputs"))}</span><ul>{items}</ul></div>'
    if kind == "loop":
        post = n.get("kind") == "post"
        cap = f'<div class="cap small">{_time(n)}{escape(n["cond"])}</div>'
        body = f'<div class="body">{_seq(n["body"])}</div>'
        return f'<div class="cell loop {"post" if post else "pre"}">{body + cap if post else cap + body}</div>'
    if kind == "if":
        yes, no = n.get("yes", {}), n.get("no", {})
        cond = (f'<div class="cell cond">{_lines("M0 0 L50 100 L100 0")}'
                f'<div class="q">{escape(n["cond"])}{_time(n)}</div>'
                f'<div class="yes small">{escape(yes.get("label", "yes"))}</div>'
                f'<div class="no small">{escape(no.get("label", "no"))}</div></div>')
        return f'<div class="fork">{cond}{_cols([yes.get("body", []), no.get("body", [])])}</div>'
    if kind == "case":
        branches = n["branches"]
        fan = " ".join(f"M0 0 L{k * 100 / len(branches):.4f} 100" for k in range(1, len(branches) + 1))
        cond = f'<div class="cell cond">{_lines(fan)}<div class="q">{escape(n["cond"])}{_time(n)}</div></div>'
        lbls = '<div class="lbls">' + "".join(
            f'<div class="cell small">{escape(b.get("label", ""))}</div>' for b in branches) + "</div>"
        return f'<div class="fork case">{cond}{lbls}{_cols([b.get("body", []) for b in branches])}</div>'
    if kind == "par":
        top = _lines("M0 100 L100 0", "l") + _lines("M100 100 L0 0", "r")
        bot = _lines("M0 0 L100 100", "l") + _lines("M100 0 L0 100", "r")
        tracks = _tracks(n)
        uses = ('<div class="lbls">' + "".join(
            f'<div class="cell small">{f"uses {escape(u)}" if u else ""}</div>' for u, _ in tracks) + "</div>"
            if any(u for u, _ in tracks) else "")
        return (f'<div class="par"><div class="cell cap top small">{top}{_time(n)}{escape(n.get("cap", "in parallel"))}</div>'
                f'{uses}{_cols([body for _, body in tracks])}'
                f'<div class="cell cap bot small">{bot}{escape(n.get("join", "wait for all"))}</div></div>')
    raise ValueError(f"unknown node type {kind!r}; the types are stmt, call, exit, inputs, loop, if, case, par")


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a Struktogramm from a JSON node list.")
    ap.add_argument("input", help="JSON file holding the node list")
    ap.add_argument("-o", "--output", help="write here instead of to stdout")
    ap.add_argument("--fragment", action="store_true", help="emit <style> and the diagram only, for embedding")
    a = ap.parse_args()
    with open(a.input) as f:
        nodes = json.load(f)
    out = fragment(nodes) if a.fragment else page(nodes)
    if a.output:
        with open(a.output, "w") as f:
            f.write(out)
        print(f"wrote {a.output}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":  # pragma: no cover: test_struktogramm.py runs it as a script only under python -I -S (stdlib_python), which no coverage hook enters
    sys.exit(main())
