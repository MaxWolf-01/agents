#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "playwright"]
# ///
"""Find text that escapes, crowds or overlaps its box in a rendered HTML page.

Opens each address in a tab of its own, in one headless Chromium context at the given
width, and measures every text element against its box. Findings are geometric, so a
clean run means nothing sticks out or collides, not that the page looks good.

Kinds, by severity:
- escapes: an SVG text runs past the rect it starts in, or past the SVG itself;
  an HTML element's text is wider than its box while its overflow is visible.
- overlap: two SVG texts intersect, or two pieces of HTML text are drawn over each
  other, measured where their glyphs land rather than on their elements' boxes, and
  only where the engine says the browser paints both of them there.
- tight: an SVG text sits closer to its rect's edge than --pad, in a rect that is a
  box rather than a mask sized to the label (reported, never fatal).
- clipped: a box with overflow hidden cuts an HTML text off, by an ellipsis or plainly
  (reported, never fatal: a truncated title is sometimes the design).
- unmeasurable: the page never stopped moving, so nothing on it was measured.

Every finding names the element it was measured on, as a path up to the nearest ancestor
carrying an id: a graph label reads as its node.

A page is measured at rest and at the top. The run waits for the page's geometry to hold
still before it reads the height, resizes the window to it, waits again, then scrolls to
the top, so what an address' fragment slides under sticky or fixed chrome is no finding.

Skipped on purpose: overflow under 2px; the touching line boxes of a multi-line label; text a
clip leaves less than 4px of, or a collapsed box hides; and two texts whose glyphs cross by
less than half the shorter one's height. Text in a scrolling ancestor never counts as escaping
or being cut off, and still counts as overlapping.

How far the paint-over rule reaches: a surface counts as covering a text when its background
resolves to an opaque colour, so a card drawn as an image or a gradient does not, and neither
does an SVG shape, whose fill is not a background. Where the two texts meet outside the window
the engine cannot be asked and the finding stands.

Exit codes: 0 nothing found, 1 an escape or an overlap, 2 a page that never stopped moving,
3 the run itself failed, a usage error among them. A page that never stopped moving outranks a
finding, so a run holding both exits 2.

Examples:

    render-lint figure.html
    render-lint page.html?theme=night#row-3    # a query and a fragment go on the address
    render-lint figure.html --crops /tmp/lint  # a PNG per finding, to look at
    render-lint a.html b.html --json | jq '.[] | select(.kind != "tight" and .kind != "clipped")'
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import tyro

if TYPE_CHECKING:
    from playwright.sync_api import Page

# The kinds that never fail a run: a crowded label and a truncated title can both be the design.
SOFT = ("tight", "clipped")

# A hash of the page's geometry: every box on it, weighted by where in the document it sits so
# that two boxes trading places do not cancel, and the height the page asks for. A script that
# polls, or a class the page toggles, reads as still because neither moves a box. Readings that
# agree to 0.01px of total drift count as equal.
STILL = r"""
() => {
  let n = 0, s = 0
  for (const el of document.querySelectorAll('body *')) {
    const b = el.getBoundingClientRect()
    s += ++n * (b.x + 2 * b.y + 3 * b.width + 5 * b.height)
  }
  return `${n}:${Math.round(s * 100)}:${document.documentElement.scrollHeight}`
}
"""
# Readings that have to agree before a page counts as at rest: three, so the quiet window is two
# poll intervals wide and a tab the machine stopped scheduling for one cannot answer for the page.
AGREE = 3

MEASURE = r"""
(pad) => {
  const out = []
  // Hit-testing is how the paint-over check below asks what the browser draws where, and it
  // passes straight through a box that takes no pointer. Nothing here moves any layout.
  const relax = document.createElement('style')
  relax.textContent = '* { pointer-events: auto !important }'
  document.head.append(relax)
  const vis = (el) => { const cs = getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden' }
  const box = (b) => ({ x: b.left + scrollX, y: b.top + scrollY, w: b.width, h: b.height })
  const snip = (s) => s.trim().replace(/\s+/g, ' ').slice(0, 70)
  // Where a finding sits, as a path to look up on the page: the element, and the nearest
  // ancestors up to the first one carrying an id.
  const at = (el) => {
    const one = (e) => (e.tagName || '').toLowerCase() + (e.id ? '#' + e.id : (e.classList && e.classList[0] ? '.' + e.classList[0] : ''))
    if (el.id) return one(el)
    const parts = [one(el)]
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      if (a.id) { parts.unshift(one(a)); break }
      if (parts.length < 3) parts.unshift(one(a))
    }
    return parts.join(' ')
  }
  const scrolls = (el) => { for (let a = el.parentElement; a; a = a.parentElement) { const o = getComputedStyle(a).overflowX; if (o === 'auto' || o === 'scroll') return true } return false }
  const span = (bs) => { const left = Math.min(...bs.map((b) => b.left)), top = Math.min(...bs.map((b) => b.top)), right = Math.max(...bs.map((b) => b.right)), bottom = Math.max(...bs.map((b) => b.bottom)); return { left, top, right, bottom, width: right - left, height: bottom - top } }
  const round = (n) => Math.round(n * 10) / 10
  for (const el of document.querySelectorAll('body *')) {
    if (el instanceof SVGElement || !vis(el)) continue
    if (getComputedStyle(el).overflowX !== 'visible' || el.clientWidth === 0 || scrolls(el)) continue
    if (el.scrollWidth > el.clientWidth + 2)
      out.push({ kind: 'escapes', where: 'html', el: at(el), text: snip(el.textContent), by: el.scrollWidth - el.clientWidth, box: box(el.getBoundingClientRect()) })
  }
  // Whether an ancestor's clip reaches a box positioned this way: an absolute box is cut only
  // by its containing-block chain, a fixed one only by an ancestor that takes it out of the
  // viewport's frame. The properties are the ones Chrome answers yes for, probed one at a time;
  // container-type, will-change: opacity and will-change: content-visibility read like they
  // belong and do not, and will-change is matched whole, since transform-origin is not transform.
  const WILL_HOLD = ['transform', 'translate', 'rotate', 'scale', 'perspective', 'filter', 'backdrop-filter', 'contain', 'transform-style', 'offset-path']
  const wants = (cs, ...names) => cs.willChange.toLowerCase().split(',').some((w) => names.includes(w.trim()))
  const holds = (cs, pos) =>
    (pos === 'absolute' && (cs.position !== 'static' || wants(cs, 'position'))) ||
    cs.transform !== 'none' || cs.translate !== 'none' || cs.rotate !== 'none' || cs.scale !== 'none' ||
    cs.perspective !== 'none' || cs.filter !== 'none' || cs.backdropFilter !== 'none' || cs.offsetPath !== 'none' ||
    cs.transformStyle === 'preserve-3d' || cs.contentVisibility !== 'visible' ||
    /paint|layout|strict|content/.test(cs.contain) || wants(cs, ...WILL_HOLD)
  // How far a clipping edge reaches: a box the reader can scroll shows everything inside it, one
  // that cannot stops at its own frame.
  const far = (overflow, frame, whole) => (['hidden', 'clip'].includes(overflow) ? frame : Math.max(frame, whole))
  // What a reader sees of one text rect: every ancestor that clips it narrows it, and the ones
  // it cannot scroll say how much they cut off.
  const clip = (el, r) => {
    let seen = { left: r.left, top: r.top, right: r.right, bottom: r.bottom }, cut = 0, pos = 'static'
    for (let a = el; a; a = a.parentElement) {
      const cs = getComputedStyle(a)
      // Overflow on the root elements is the viewport's, which cuts every box on the page rather
      // than only what its own border box holds; body hands its overflow up only while html has
      // none. The viewport was resized to the page's height, and a page whose own height follows
      // the viewport's outgrows that, so the clip reaches the rest only where the root scrolls.
      const root = a === document.documentElement || (a === document.body && getComputedStyle(document.documentElement).overflowX === 'visible')
      if (a !== el && !root && (pos === 'absolute' || pos === 'fixed') && !holds(cs, pos)) continue
      pos = cs.position
      if (cs.overflowX === 'visible' || cs.display === 'inline') continue
      const ab = a.getBoundingClientRect()
      const c = root
        ? { left: 0, top: 0, right: far(cs.overflowX, innerWidth, document.documentElement.scrollWidth), bottom: far(cs.overflowY, innerHeight, document.documentElement.scrollHeight) }
        : { left: ab.left + parseFloat(cs.borderLeftWidth), top: ab.top + parseFloat(cs.borderTopWidth), right: ab.right - parseFloat(cs.borderRightWidth), bottom: ab.bottom - parseFloat(cs.borderBottomWidth) }
      if (!['auto', 'scroll'].includes(cs.overflowX) && !['auto', 'scroll'].includes(cs.overflowY))
        cut = Math.max(cut, c.left - r.left, r.right - c.right, c.top - r.top, r.bottom - c.bottom)
      seen = { left: Math.max(seen.left, c.left), top: Math.max(seen.top, c.top), right: Math.min(seen.right, c.right), bottom: Math.min(seen.bottom, c.bottom) }
    }
    return { seen, cut }
  }
  // display: contents leaves an element with no box, and checkVisibility calls a box-less element
  // hidden; its text is laid out and painted by the formatting context above it.
  const shown = (el) => { const cs = getComputedStyle(el); return el.checkVisibility({ visibilityProperty: true, opacityProperty: true }) || (cs.display === 'contents' && cs.visibility === 'visible' && !!el.parentElement && shown(el.parentElement)) }
  const runs = []
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const el = n.parentElement
    if (!n.nodeValue.trim() || !el || el instanceof SVGElement) continue
    if (!shown(el)) continue
    const range = document.createRange()
    range.selectNodeContents(n)
    const seen = []
    let cut = 0
    for (const r of [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0)) {
      const c = clip(el, r)
      cut = Math.max(cut, c.cut)
      if (c.seen.right - c.seen.left >= 4 && c.seen.bottom - c.seen.top >= 4) seen.push(c.seen)
    }
    if (!seen.length) continue
    const text = snip(n.nodeValue)
    if (cut > 2) out.push({ kind: 'clipped', where: 'html', el: at(el), text, by: round(cut), box: box(span(seen)) })
    runs.push({ el, text, rects: seen })
  }
  // An overlap is a collision only where the browser paints both texts. At the point the two
  // meet, elementsFromPoint says what the browser draws there: a card over the page hides the
  // text under it, and two texts nothing covers still collide.
  const SOLID = 0.99
  // A surface Chrome states any way but rgb() is not read as covering, which keeps a finding
  // rather than losing one to a colour space this cannot take an alpha out of.
  const covers = (el) => {
    const cs = getComputedStyle(el)
    const said = cs.backgroundColor.match(/^rgba?\(([^)]+)\)/)
    if (!said) return false
    const parts = said[1].split(/[,/]/)
    return (parts.length < 4 || parseFloat(parts[3]) >= SOLID) && parseFloat(cs.opacity) >= SOLID
  }
  // elementsFromPoint lists the stack topmost first, so what precedes a text's own box in it is
  // drawn over that text.
  const drawn = (el, x, y) => {
    const stack = document.elementsFromPoint(x, y)
    const i = stack.findIndex((e) => e === el || e.contains(el))
    return i >= 0 && !stack.slice(0, i).some(covers)
  }
  // Nine points across the rectangle the two share. A point outside the window cannot be asked
  // about, and a pair with no point inside it keeps its finding rather than losing it unseen.
  const collide = (ea, eb, p, q) => {
    const x0 = Math.max(p.left, q.left), x1 = Math.min(p.right, q.right)
    const y0 = Math.max(p.top, q.top), y1 = Math.min(p.bottom, q.bottom)
    let asked = false
    for (let i = 1; i < 4; i++) for (let j = 1; j < 4; j++) {
      const x = x0 + (x1 - x0) * i / 4, y = y0 + (y1 - y0) * j / 4
      if (x < 0 || y < 0 || x > innerWidth - 1 || y > innerHeight - 1) continue
      asked = true
      if (drawn(ea, x, y) && drawn(eb, x, y)) return true
    }
    return !asked
  }
  const flat = []
  runs.forEach((run, i) => run.rects.forEach((r) => flat.push({ i, r })))
  flat.sort((p, q) => p.r.top - q.r.top)
  const paired = new Set()
  for (let a = 0; a < flat.length; a++)
    for (let b = a + 1; b < flat.length && flat[b].r.top < flat[a].r.bottom; b++) {
      const [p, q] = [flat[a].r, flat[b].r]
      const pair = [flat[a].i, flat[b].i].sort((x, y) => x - y).join(':')
      if (flat[a].i === flat[b].i || paired.has(pair)) continue
      const over = Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top)
      if (Math.min(p.right, q.right) - Math.max(p.left, q.left) < 2) continue
      if (over < 0.5 * Math.min(p.bottom - p.top, q.bottom - q.top)) continue
      const [one, two] = [runs[flat[a].i], runs[flat[b].i]]
      if (!collide(one.el, two.el, p, q)) continue
      paired.add(pair)
      out.push({ kind: 'overlap', where: 'html', el: at(one.el) + ' | ' + at(two.el), text: one.text + ' | ' + two.text, by: 0, box: box(span([p, q])) })
    }
  const inside = (a, b, p) => a.left >= b.left + p && a.right <= b.right - p && a.top >= b.top + p && a.bottom <= b.bottom - p
  const meets = (a, b) => a.left + 2 < b.right - 2 && b.left + 2 < a.right - 2 && a.top + 2 < b.bottom - 2 && b.top + 2 < a.bottom - 2
  for (const svg of document.querySelectorAll('svg')) {
    if (!vis(svg)) continue
    const sb = svg.getBoundingClientRect()
    const rects = [...svg.querySelectorAll('rect')].map((r) => r.getBoundingClientRect())
    const texts = [...svg.querySelectorAll('text')].filter(vis).map((t) => ({ t, b: t.getBoundingClientRect() })).filter(({ b }) => b.width > 0)
    for (const { t, b } of texts) {
      const text = snip(t.textContent)
      const host = rects.find((rb) => b.left >= rb.left && b.left < rb.right && b.top >= rb.top && b.top < rb.bottom)
      if (host && !inside(b, host, 0)) {
        const by = Math.max(b.right - host.right, host.left - b.left, b.bottom - host.bottom, host.top - b.top)
        out.push({ kind: 'escapes', where: 'svg rect', el: at(t), text, by: round(by), box: box(b) })
      } else if (host && !inside(b, host, pad) && host.width > b.width + 3 * pad && host.height > b.height + 3 * pad) {
        const gap = Math.min(b.left - host.left, host.right - b.right, b.top - host.top, host.bottom - b.bottom)
        out.push({ kind: 'tight', where: 'svg rect', el: at(t), text, by: round(gap), box: box(b) })
      }
      if (!inside(b, sb, 0)) out.push({ kind: 'escapes', where: 'svg', el: at(t), text, by: round(Math.max(b.right - sb.right, sb.left - b.left, b.bottom - sb.bottom, sb.top - b.top)), box: box(b) })
    }
    for (let i = 0; i < texts.length; i++)
      for (let j = i + 1; j < texts.length; j++)
        if (meets(texts[i].b, texts[j].b) && collide(texts[i].t, texts[j].t, texts[i].b, texts[j].b))
          out.push({ kind: 'overlap', where: 'svg', el: at(texts[i].t) + ' | ' + at(texts[j].t), text: snip(texts[i].t.textContent) + ' | ' + snip(texts[j].t.textContent), by: 0, box: box(texts[i].b) })
  }
  relax.remove()
  return out
}
"""


@dataclass
class Args:
    files: Annotated[list[Path], tyro.conf.Positional]
    """HTML files to check. A query string and a fragment may follow the path (page.html?theme=night#row-3)."""
    width: int = 1400
    """Viewport width in CSS pixels; the page gets the height it asks for."""
    pad: float = 6.0
    """Clearance in pixels an SVG text needs from its rect's edge before it counts as tight."""
    settle: float = 0.25
    """Seconds between readings of the page's geometry; three that agree mean it is at rest."""
    patience: float = 20.0
    """Seconds to wait for a page to come to rest before reporting it unmeasurable."""
    crops: Path | None = None
    """Directory for one PNG per finding, the finding's box with a margin around it."""
    json: bool = False
    """Emit findings as a JSON array. Schema: [{"file": str, "kind": "escapes"|"overlap"|"tight"|"clipped"|"unmeasurable", "where": str, "el": str, "text": str, "by": float, "box": {"x","y","w","h"}, "crop": str|null}]"""


def main(args: Args) -> None:
    from playwright.sync_api import sync_playwright

    findings: list[dict] = []
    if args.crops:
        args.crops.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=browser_path())
        # One context, a tab per address: a fresh document and window each time, and whatever the
        # pages fetch in common, a graph engine among them, fetched once.
        context = browser.new_context(viewport={"width": args.width, "height": 900})
        for spec in args.files:
            page = context.new_page()
            try:
                for f in measure(page, spec, args):
                    findings.append({"file": str(spec), "crop": None} | f)
            finally:
                page.close()
        browser.close()

    if args.json:
        print(json.dumps(findings, indent=1))
    else:
        for f in findings:
            by = f"{f['by']}px" if f["kind"] not in ("overlap", "unmeasurable") else ""
            crop = f"  {f['crop']}" if f["crop"] else ""
            print(f"{f['file']}: {f['kind']:12} {f['where']:9} {by:>8}  {f['el']}  {f['text']!r}{crop}")
        fatal = sum(f["kind"] not in SOFT for f in findings)
        print(f"{len(findings)} findings, {fatal} fatal", file=sys.stderr)
    if any(f["kind"] == "unmeasurable" for f in findings):
        sys.exit(2)
    sys.exit(1 if any(f["kind"] not in SOFT for f in findings) else 0)


def measure(page: Page, spec: Path, args: Args) -> list[dict]:
    """One address, in a tab of its own: at rest, in a window as tall as the page, at the top.

    The patience is the page's, not each wait's: the two rests and the scroll share one deadline."""
    head, mark, fragment = str(spec).partition("#")
    path, _, query = head.partition("?")
    url = Path(path).resolve().as_uri() + (f"?{query}" if query else "") + (mark + fragment)
    page.goto(url, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    until = time.monotonic() + args.patience
    still = at_rest(page, args, until)
    if still:
        page.set_viewport_size({"width": args.width, "height": page.evaluate("document.documentElement.scrollHeight")})
        still = at_rest(page, args, until)
    if still:
        # instant, because a page set to scroll smoothly would still be travelling on the next call
        page.evaluate("scrollTo({top: 0, left: 0, behavior: 'instant'})")
        still = at_rest(page, args, until)
    if not still:
        return [{"kind": "unmeasurable", "where": "page", "el": "", "by": 0,
                 "text": f"still moving after {args.patience:g}s", "box": {"x": 0, "y": 0, "w": 0, "h": 0}}]
    found = page.evaluate(MEASURE, args.pad)
    if args.crops:
        for n, f in enumerate(found, start=1):
            b, m = f["box"], 24
            out = args.crops / f"{Path(path).stem}-{n:02d}-{f['kind']}.png"
            page.screenshot(path=str(out), full_page=True, clip={"x": max(0, b["x"] - m), "y": max(0, b["y"] - m), "width": b["w"] + 2 * m, "height": b["h"] + 2 * m})
            f["crop"] = str(out)
    return found


def at_rest(page: Page, args: Args, until: float) -> bool:
    """Block until AGREE readings of the page's geometry in a row agree, or `until` passes."""
    seen: list[str] = []
    while True:
        seen.append(page.evaluate(STILL))
        if seen[-AGREE:].count(seen[-1]) == AGREE:
            return True
        if time.monotonic() > until:
            return False
        page.wait_for_timeout(args.settle * 1000)


def browser_path() -> str | None:
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        if found := shutil.which(name):
            return found
    return None


def cli() -> None:
    try:
        args = tyro.cli(Args, description=__doc__)
    except SystemExit as stop:  # argparse answers a usage error with 2, which a page holds here
        raise SystemExit(3 if stop.code else 0) from None
    try:
        main(args)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    cli()
