"""Nassi-Shneiderman diagram (Struktogramm) renderer: nested dicts -> HTML."""
from html import escape

CSS = """
.ns { font-size: 15px; line-height: 1.4; color: var(--text-primary, #1a1a18); }
.ns .seq { display: flex; flex-direction: column; min-height: 100%; }
.ns .seq > * + * { margin-top: -1px; }
.ns .seq > :last-child { flex: 1 1 auto; }
.ns .col > .seq { height: 100%; }
.ns .blk { border: 1px solid var(--border-strong, #c9c7bd); padding: 12px 14px; }
.ns .sub { display: block; font-size: 12.5px; color: var(--text-secondary, #6b6a64); margin-top: 2px; }
.ns .call { border-left-width: 5px; border-right-width: 5px; border-left-style: double; border-right-style: double; }
.ns .loop { border: 1px solid var(--border-strong, #c9c7bd); }
.ns .loop > .cap { padding: 7px 14px; font-size: 12.5px; color: var(--text-secondary, #6b6a64); }
.ns .loop > .body { padding-left: 20px; }
.ns .loop.pre > .body { margin: -1px -1px -1px 0; }
.ns .loop.post > .body { margin: -1px -1px 0 0; }
.ns .fork { border: 1px solid var(--border-strong, #c9c7bd); }
.ns .fork > .cond { background-repeat: no-repeat; }
.ns .fork > .cond > .q { padding: 8px 14px 0; text-align: center; }
.ns .fork > .cond > .yn { display: flex; justify-content: space-between; padding: 3px 12px 6px; font-size: 12.5px; color: var(--text-secondary, #6b6a64); }
.ns .fork > .cols { display: flex; margin: -1px -1px -1px 0; }
.ns .fork > .cols > .col { flex: 1 1 0; min-width: 0; margin-right: -1px; }
.ns .fork > .cols > .col:last-child { margin-right: 0; }
.ns .case > .cond { min-height: 46px; }
.ns .case > .cond > .q { text-align: right; padding: 8px 14px 8px 40%; }
.ns .case > .lbls { display: flex; margin-right: -1px; }
.ns .case > .cond { min-height: 46px; }
.ns .case > .cond > .q { text-align: right; padding: 8px 14px 8px 40%; }
.ns .case > .lbls > div { flex: 1 1 0; min-width: 0; margin-right: -1px; border: 1px solid var(--border-strong, #c9c7bd); border-top: none; padding: 5px 10px; font-size: 12.5px; color: var(--text-secondary, #6b6a64); text-align: center; }
.ns .case > .cols { margin-top: -1px; }
.ns .empty { min-height: 22px; }
.ns .par { border: 1px solid var(--border-strong, #c9c7bd); }
.ns .par > .cap { padding: 6px 30px; font-size: 12.5px; color: var(--text-secondary, #6b6a64); text-align: center; background-repeat: no-repeat; background-size: 26px 100%, 26px 100%; }
.ns .par > .cap.top { background-position: left top, right top; background-image: linear-gradient(to bottom right, transparent calc(50% - .5px), var(--border-strong, #c9c7bd) calc(50% - .5px), var(--border-strong, #c9c7bd) calc(50% + .5px), transparent calc(50% + .5px)), linear-gradient(to bottom left, transparent calc(50% - .5px), var(--border-strong, #c9c7bd) calc(50% - .5px), var(--border-strong, #c9c7bd) calc(50% + .5px), transparent calc(50% + .5px)); }
.ns .par > .cap.bot { background-position: left bottom, right bottom; background-image: linear-gradient(to top right, transparent calc(50% - .5px), var(--border-strong, #c9c7bd) calc(50% - .5px), var(--border-strong, #c9c7bd) calc(50% + .5px), transparent calc(50% + .5px)), linear-gradient(to top left, transparent calc(50% - .5px), var(--border-strong, #c9c7bd) calc(50% - .5px), var(--border-strong, #c9c7bd) calc(50% + .5px), transparent calc(50% + .5px)); }
.ns .par > .cols { display: flex; margin: -1px -1px 0 0; }
.ns .par > .cols > .col { flex: 1 1 0; min-width: 0; margin-right: -1px; }
.ns .blk, .ns .loop, .ns .fork, .ns .par { break-inside: avoid; }
"""

# two half-width gradients: left half TL->bottom-centre, right half TR->bottom-centre
_DIAG = ("background-size:50% 100%,50% 100%;background-position:left top,right top;"
         "background-image:linear-gradient(to bottom right,transparent calc(50% - .5px),"
         "var(--border-strong, #c9c7bd) calc(50% - .5px),var(--border-strong, #c9c7bd) calc(50% + .5px),transparent calc(50% + .5px)),"
         "linear-gradient(to bottom left,transparent calc(50% - .5px),var(--border-strong, #c9c7bd) calc(50% - .5px),"
         "var(--border-strong, #c9c7bd) calc(50% + .5px),transparent calc(50% + .5px))")

# n-way fan: one gradient per column, each spanning that column, drawn to the bottom-left origin
def _fan(n):
    layers, sizes = [], []
    for i in range(1, n + 1):
        layers.append(
            "linear-gradient(to bottom right,transparent calc(50% - .5px),var(--border-strong, #c9c7bd) calc(50% - .5px),"
            "var(--border-strong, #c9c7bd) calc(50% + .5px),transparent calc(50% + .5px))")
        sizes.append(f"{i * 100 / n:.4f}% 100%")
    return ("background-repeat:no-repeat;background-size:" + ",".join(sizes)
            + ";background-position:left top;background-image:" + ",".join(layers))


def _txt(node):
    out = escape(node["text"])
    if node.get("sub"):
        out += f'<span class="sub">{escape(node["sub"])}</span>'
    return out


def _seq(nodes, depth=0):
    # An empty branch is still wrapped in .seq: the stretch rule targets
    # .seq > :last-child, and without the wrapper an empty branch would sit at
    # its natural height and leave unbordered dead space beside a taller sibling.
    inner = ("".join(_node(n, depth) for n in nodes) if nodes
             else '<div class="blk empty"></div>')
    return '<div class="seq">' + inner + "</div>"


def _node(n, depth=0):
    t = n.get("type", "stmt")
    if t == "stmt":
        return f'<div class="blk">{_txt(n)}</div>'
    if t == "call":
        return f'<div class="blk call">{_txt(n)}</div>'
    if t == "loop":
        post = n.get("kind") == "post"
        cap = f'<div class="cap">{escape(n["cond"])}</div>'
        body = f'<div class="body">{_seq(n["body"], depth+1)}</div>'
        inner = body + cap if post else cap + body
        return f'<div class="loop {"post" if post else "pre"}">{inner}</div>'
    if t == "if":
        yes, no = n.get("yes", {}), n.get("no", {})
        cond = (f'<div class="cond" style="{_DIAG}"><div class="q">{escape(n["cond"])}</div>'
                f'<div class="yn"><span>{escape(yes.get("label","yes"))}</span>'
                f'<span>{escape(no.get("label","no"))}</span></div></div>')
        cols = (f'<div class="cols"><div class="col">{_seq(yes.get("body", []), depth+1)}</div>'
                f'<div class="col">{_seq(no.get("body", []), depth+1)}</div></div>')
        return f'<div class="fork">{cond}{cols}</div>'
    if t == "par":
        cols = '<div class="cols">' + "".join(
            f'<div class="col">{_seq(t_, depth+1)}</div>' for t_ in n["tracks"]) + "</div>"
        return (f'<div class="par"><div class="cap top">{escape(n.get("cap", "in parallel"))}</div>'
                f'{cols}<div class="cap bot">{escape(n.get("join", "wait for all"))}</div></div>')
    if t == "case":
        br = n["branches"]
        cond = f'<div class="cond" style="{_fan(len(br))}"><div class="q">{escape(n["cond"])}</div></div>'
        lbls = '<div class="lbls">' + "".join(
            f'<div>{escape(b.get("label",""))}</div>' for b in br) + "</div>"
        cols = '<div class="cols" style="display:flex;margin:-1px -1px -1px 0">' + "".join(
            f'<div class="col" style="flex:1 1 0;min-width:0;margin-right:-1px">{_seq(b.get("body", []), depth+1)}</div>'
            for b in br) + "</div>"
        return f'<div class="fork case">{cond}{lbls}{cols}</div>'
    raise ValueError(t)


def render(nodes):
    return f'<div class="ns">{_seq(nodes)}</div>'


# --- standalone page + CLI ---------------------------------------------------

PAGE_SHIM = """
body { margin: 0; padding: 24px; background: #fdfdfb; font-family: system-ui, sans-serif; }
body.dark { --text-primary:#f0efe9; --text-secondary:#9c9a92; --border-strong:#4a4945; background:#262624; }
.wrap { max-width: 720px; margin: 0 auto; }
@media print { body { padding: 0; background: #fff; } }
"""


def page(nodes, dark=False, extra_css=""):
    """Full standalone HTML document. Use for files the user opens or prints."""
    return (f'<!doctype html><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<style>{PAGE_SHIM}{CSS}{extra_css}</style>'
            f'<body class="{"dark" if dark else ""}"><div class="wrap">{render(nodes)}</div></body>')


def _load(path):
    import json
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    import argparse, sys
    ap = argparse.ArgumentParser(description="Render a Struktogramm from a JSON node list.")
    ap.add_argument("input", help="JSON file containing the node list")
    ap.add_argument("-o", "--output", help="write here instead of stdout")
    ap.add_argument("--dark", action="store_true", help="dark theme")
    ap.add_argument("--fragment", action="store_true",
                    help="emit <style>+<div> only, for embedding in a host page")
    a = ap.parse_args()
    nodes = _load(a.input)
    out = f"<style>{CSS}</style>\n{render(nodes)}" if a.fragment else page(nodes, a.dark)
    if a.output:
        open(a.output, "w").write(out)
        print(f"wrote {a.output}", file=sys.stderr)
    else:
        print(out)
