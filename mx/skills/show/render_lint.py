#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "playwright"]
# ///
"""Find text that escapes, crowds or overlaps its box in a rendered HTML page.

Opens each file in headless Chromium at the given width, waits for fonts, and
measures every text element against its box. Findings are geometric, so a
clean run means nothing sticks out or collides, not that the page looks good.

Kinds, by severity:
- escapes: an SVG text runs past the rect it starts in, or past the SVG itself;
  an HTML element's text is wider than its box while its overflow is visible.
- overlap: two SVG texts intersect.
- tight: an SVG text sits closer to its rect's edge than --pad, in a rect that is a
  box rather than a mask sized to the label (reported, never fatal).

Skipped on purpose: text inside a scrolling ancestor, overflow under 2px, and the
touching line boxes of a multi-line label.

Exit code 1 when any escape or overlap was found.

Examples:

    render-lint figure.html
    render-lint figure.html --crops /tmp/lint    # a PNG per finding, to look at
    render-lint a.html b.html --json | jq '.[] | select(.kind != "tight")'
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import tyro

MEASURE = r"""
(pad) => {
  const out = []
  const vis = (el) => { const cs = getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden' }
  const box = (b) => ({ x: b.left + scrollX, y: b.top + scrollY, w: b.width, h: b.height })
  const snip = (s) => s.trim().replace(/\s+/g, ' ').slice(0, 70)
  const scrolls = (el) => { for (let a = el.parentElement; a; a = a.parentElement) { const o = getComputedStyle(a).overflowX; if (o === 'auto' || o === 'scroll') return true } return false }
  for (const el of document.querySelectorAll('body *')) {
    if (el instanceof SVGElement || !vis(el)) continue
    if (getComputedStyle(el).overflowX !== 'visible' || el.clientWidth === 0 || scrolls(el)) continue
    if (el.scrollWidth > el.clientWidth + 2)
      out.push({ kind: 'escapes', where: 'html', text: snip(el.textContent), by: el.scrollWidth - el.clientWidth, box: box(el.getBoundingClientRect()) })
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
        out.push({ kind: 'escapes', where: 'svg rect', text, by: Math.round(by * 10) / 10, box: box(b) })
      } else if (host && !inside(b, host, pad) && host.width > b.width + 3 * pad && host.height > b.height + 3 * pad) {
        const gap = Math.min(b.left - host.left, host.right - b.right, b.top - host.top, host.bottom - b.bottom)
        out.push({ kind: 'tight', where: 'svg rect', text, by: Math.round(gap * 10) / 10, box: box(b) })
      }
      if (!inside(b, sb, 0)) out.push({ kind: 'escapes', where: 'svg', text, by: Math.round(Math.max(b.right - sb.right, sb.left - b.left, b.bottom - sb.bottom, sb.top - b.top) * 10) / 10, box: box(b) })
    }
    for (let i = 0; i < texts.length; i++)
      for (let j = i + 1; j < texts.length; j++)
        if (meets(texts[i].b, texts[j].b))
          out.push({ kind: 'overlap', where: 'svg', text: snip(texts[i].t.textContent) + ' | ' + snip(texts[j].t.textContent), by: 0, box: box(texts[i].b) })
  }
  return out
}
"""


@dataclass
class Args:
    files: Annotated[list[Path], tyro.conf.Positional]
    """HTML files to check. A query string may follow the path (page.html?theme=night)."""
    width: int = 1400
    """Viewport width in CSS pixels; the page gets the height it asks for."""
    pad: float = 6.0
    """Clearance in pixels an SVG text needs from its rect's edge before it counts as tight."""
    crops: Path | None = None
    """Directory for one PNG per finding, the finding's box with a margin around it."""
    json: bool = False
    """Emit findings as a JSON array. Schema: [{"file": str, "kind": "escapes"|"overlap"|"tight", "where": str, "text": str, "by": float, "box": {"x","y","w","h"}, "crop": str|null}]"""


def browser_path() -> str | None:
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        if found := shutil.which(name):
            return found
    return None


def main(args: Args) -> None:
    from playwright.sync_api import sync_playwright

    findings: list[dict] = []
    if args.crops:
        args.crops.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=browser_path())
        page = browser.new_page(viewport={"width": args.width, "height": 900})
        for spec in args.files:
            path, _, query = str(spec).partition("?")
            url = Path(path).resolve().as_uri() + (f"?{query}" if query else "")
            page.goto(url, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            page.set_viewport_size({"width": args.width, "height": page.evaluate("document.documentElement.scrollHeight")})
            for n, f in enumerate(page.evaluate(MEASURE, args.pad), start=1):
                f["file"] = str(spec)
                f["crop"] = None
                if args.crops:
                    b, m = f["box"], 24
                    out = args.crops / f"{Path(path).stem}-{n:02d}-{f['kind']}.png"
                    page.screenshot(path=str(out), clip={"x": max(0, b["x"] - m), "y": max(0, b["y"] - m), "width": b["w"] + 2 * m, "height": b["h"] + 2 * m})
                    f["crop"] = str(out)
                findings.append(f)
        browser.close()

    if args.json:
        print(json.dumps(findings, indent=1))
    else:
        for f in findings:
            by = f"{f['by']}px" if f["kind"] != "overlap" else ""
            crop = f"  {f['crop']}" if f["crop"] else ""
            print(f"{f['file']}: {f['kind']:8} {f['where']:9} {by:>8}  {f['text']!r}{crop}")
        fatal = sum(f["kind"] != "tight" for f in findings)
        print(f"{len(findings)} findings, {fatal} fatal", file=sys.stderr)
    sys.exit(1 if any(f["kind"] != "tight" for f in findings) else 0)


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
