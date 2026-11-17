#!/usr/bin/env python3
"""Check a rendered Struktogramm for the faults that cannot be seen in its markup.

Struktogramm correctness is a property of the rendered page, not of the HTML: a broken diagram
and a correct one differ by a CSS rule. So this opens the page in headless Chromium, measures
every box, and reads the painted pixels of a second screenshot taken with all text made
transparent, where any ink left is a line.

Checks:
  dead-space         a point inside the diagram that no block covers: a column, branch, loop
                     or parallel block whose parts stop short of its edge. Only a loop's own
                     strip, left of its body, belongs to the loop itself.
  doubled-border     two parallel lines under 3px apart where one shared line belongs
  overflow           a block reaching past the diagram's outer rectangle
  text-crossed       a band's line drawn through the box of a text
  broken-word        a line break inside a word, where a column narrower than the word's
                     own width split it; a break after a hyphen in the text is a word break
  text-contrast      a text whose colour stands out from the diagram's background by less
                     than 3:1, the WCAG minimum for large text, as when a colour scheme's
                     text colour is the other scheme's
  band-shape         a branch band whose lines do not run from its top corners to the column
                     boundary, or a case band whose lines do not fan from its top-left corner
                     to each column boundary (references/notation.md)
  column-widths      columns of one group at unequal widths, a meaning the notation lacks

Exit codes: 0 every check passed, 1 a check failed, 2 the page could not be measured (no
Playwright, no browser), which leaves the layout unverified.
"""

import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # preview.py, beside this file

TOL = 1.5  # px: fractional flex widths round by up to a pixel
DOUBLED = 3  # px: two lines closer than this read as one line drawn twice

PROBE = r"""
() => {
  const root = document.querySelector('.ns');
  const box = el => { const r = el.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
  const desc = el => {
    const cls = typeof el.className === 'string' ? el.className : '';
    const words = el.textContent.trim().replace(/\s+/g, ' ');
    return `${el.tagName.toLowerCase()}.${cls.trim().replace(/\s+/g, '.')} "${words.slice(0, 40)}"`;
  };
  const padBox = el => {
    const s = getComputedStyle(el), [l, t, r, b] = box(el);
    return [l + parseFloat(s.borderLeftWidth), t + parseFloat(s.borderTopWidth),
            r - parseFloat(s.borderRightWidth), b - parseFloat(s.borderBottomWidth)];
  };
  const inFlow = el => !(el instanceof SVGElement) && getComputedStyle(el).position !== 'absolute';
  const all = [root, ...root.querySelectorAll('*')].filter(el => !(el instanceof SVGElement));

  const containers = [root, ...root.querySelectorAll('.seq, .col, .cols, .lbls, .fork, .par, .loop, .body')]
    .map(el => {
      const exempt = [];
      // A loop's strip left of its body is the loop's own L-shaped block, not dead space.
      const seq = el.matches('.loop') ? el.querySelector(':scope > .body > .seq')
                : el.matches('.body') ? el.querySelector(':scope > .seq') : null;
      if (seq) { const [l, t, , b] = box(el); exempt.push([l, t, box(seq)[0], b]); }
      return { desc: desc(el), box: padBox(el), exempt,
               kids: [...el.children].filter(inFlow).map(box) };
    });

  const borders = [];
  all.forEach((el, i) => {
    const s = getComputedStyle(el), [l, t, r, b] = box(el);
    for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
      const w = parseFloat(s[`border${side}Width`]);
      if (!(w > 0) || ['none', 'hidden'].includes(s[`border${side}Style`])) continue;
      const rect = { Top: [l, t, r, t + w], Bottom: [l, b - w, r, b],
                     Left: [l, t, l + w, b], Right: [r - w, t, r, b] }[side];
      borders.push({ el: i, desc: desc(el), side, vertical: side === 'Left' || side === 'Right', rect });
    }
  });

  const texts = [], breaks = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.data.trim()) continue;
    const range = document.createRange(); range.selectNodeContents(n);
    for (const r of range.getClientRects())
      if (r.width > 0 && r.height > 0)
        texts.push({ text: n.data.trim().slice(0, 40), rect: [r.left, r.top, r.right, r.bottom],
                     color: getComputedStyle(n.parentElement).color.match(/[\d.]+/g).slice(0, 3).map(Number) });
    // A new line starting between two letters of one word, which is a line box the next
    // character begins below the one before it.
    const at = i => { const c = document.createRange(); c.setStart(n, i); c.setEnd(n, i + 1); return c.getBoundingClientRect(); };
    for (let i = 1; i < n.data.length; i++) {
      if (/[\s\-\u00ad\/]/.test(n.data[i - 1]) || /\s/.test(n.data[i])) continue;
      const a = at(i - 1), b = at(i);
      if (b.width > 0 && a.width > 0 && b.top >= a.bottom - 1) {
        const from = n.data.lastIndexOf(' ', i) + 1, to = n.data.indexOf(' ', i);
        breaks.push(n.data.slice(from, i) + '/' + n.data.slice(i, to < 0 ? undefined : to));
      }
    }
  }

  const bands = [...root.querySelectorAll('.fork > .cond')].map(el => ({
    desc: desc(el), kind: el.parentElement.matches('.case') ? 'case' : 'if', box: box(el),
    bounds: [...el.parentElement.querySelectorAll(':scope > .cols > .col')].map(c => box(c)[2]) }));

  const groups = [...root.querySelectorAll('.cols')].map(el => ({
    desc: desc(el.parentElement), widths: [...el.children].filter(inFlow).map(c => c.getBoundingClientRect().width) }));

  const blocks = root.querySelectorAll('.blk, .cell, .loop, .fork, .par').length;

  return { root: box(root), containers, borders, texts, breaks, bands, groups, blocks,
           elements: all.map(el => ({ desc: desc(el), box: box(el) })) };
}
"""

# Reads the textless screenshot in the page itself, where the browser decodes the PNG.
RASTER = r"""
async ({ png, dpr, root, texts, bands }) => {
  const img = new Image(); img.src = 'data:image/png;base64,' + png; await img.decode();
  const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
  const ctx = c.getContext('2d'); ctx.drawImage(img, 0, 0);
  const W = c.width, H = c.height, px = ctx.getImageData(0, 0, W, H).data;
  const at = (x, y) => (y * W + x) * 4;

  // The background is the colour most of the diagram's area is painted in.
  const counts = new Map();
  for (let y = Math.max(0, Math.round(root[1] * dpr)); y < Math.min(H, root[3] * dpr); y += 2)
    for (let x = Math.max(0, Math.round(root[0] * dpr)); x < Math.min(W, root[2] * dpr); x += 2) {
      const i = at(x, y), k = (px[i] << 16) | (px[i + 1] << 8) | px[i + 2];
      counts.set(k, (counts.get(k) || 0) + 1);
    }
  const bg = [...counts].sort((a, b) => b[1] - a[1])[0][0];
  const ink = (x, y) => {
    if (x < 0 || y < 0 || x >= W || y >= H) return false;
    const i = at(x, y);
    return Math.abs(px[i] - (bg >> 16)) + Math.abs(px[i + 1] - ((bg >> 8) & 255)) + Math.abs(px[i + 2] - (bg & 255)) > 60;
  };
  const inkIn = ([l, t, r, b]) => {
    let n = 0;
    for (let y = Math.ceil(t * dpr); y < Math.floor(b * dpr); y++)
      for (let x = Math.ceil(l * dpr); x < Math.floor(r * dpr); x++) if (ink(x, y)) n++;
    return n;
  };
  const dist = ([ax, ay, bx, by], x, y) => {
    const dx = bx - ax, dy = by - ay, t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)));
    return Math.hypot(x - ax - t * dx, y - ay - t * dy);
  };

  // A glyph's own box, less a pixel each side so a line passing a corner's antialiasing is no crossing.
  const crossed = texts.map(({ rect: [l, t, r, b] }) => inkIn([l + 1, t + 1, r - 1, b - 1]));

  const shapes = bands.map(({ segs, box: [l, t, r, b] }) => {
    let samples = 0, missing = 0;
    for (const s of segs) {
      const len = Math.hypot(s[2] - s[0], s[3] - s[1]);
      for (let d = 0.08 * len; d < 0.92 * len; d += 2) {
        const x = s[0] + (s[2] - s[0]) * d / len, y = s[1] + (s[3] - s[1]) * d / len;
        samples++;
        let hit = false;
        for (let oy = -3; oy <= 3 && !hit; oy++) for (let ox = -3; ox <= 3 && !hit; ox++)
          hit = ink(Math.round(x * dpr) + ox, Math.round(y * dpr) + oy);
        if (!hit) missing++;
      }
    }
    let stray = 0;
    for (let y = Math.ceil((t + 3) * dpr); y < Math.floor((b - 3) * dpr); y++)
      for (let x = Math.ceil((l + 3) * dpr); x < Math.floor((r - 3) * dpr); x++)
        if (ink(x, y) && segs.every(s => dist(s, x / dpr, y / dpr) > 2.5)) stray++;
    return { samples, missing, stray };
  });
  return { crossed, shapes, background: [bg >> 16, (bg >> 8) & 255, bg & 255] };
}
"""

HIDE_TEXT = ".ns, .ns * { color: transparent !important; -webkit-text-fill-color: transparent !important; }"


def band_lines(band: dict) -> list[list[float]]:
    """The lines references/notation.md draws in a band, as [x0, y0, x1, y1] in page pixels."""
    l, t, r, b = band["box"]
    if band["kind"] == "if":
        mid = band["bounds"][0]
        return [[l, t, mid, b], [r, t, mid, b]]
    return [[l, t, x, b] for x in band["bounds"]]


def measure(html_path: str, *, width: int = 680, scheme: str = "light") -> dict:
    from playwright.sync_api import sync_playwright

    from preview import find_browser

    dpr = 2
    with sync_playwright() as p:
        # --mx-run names the run that launched the browser, so a stuck one can be killed without
        # touching another run's on a shared host. Chromium ignores a flag it does not know.
        browser = p.chromium.launch(executable_path=find_browser(),
                                    args=["--no-sandbox", f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
        try:
            page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=dpr,
                                    color_scheme=scheme)
            page.goto("file://" + os.path.abspath(html_path))
            # A diagram wider than the window scrolls sideways; measure all of it.
            if (wide := page.evaluate("document.documentElement.scrollWidth")) > width:
                page.set_viewport_size({"width": wide, "height": 900})
            geo = page.evaluate(PROBE)
            for band in geo["bands"]:
                band["segs"] = band_lines(band)
            page.add_style_tag(content=HIDE_TEXT)
            png = base64.b64encode(page.screenshot(full_page=True)).decode()
            geo.update(page.evaluate(RASTER, {"png": png, "dpr": dpr, "root": geo["root"],
                                              "texts": geo["texts"], "bands": geo["bands"]}))
        finally:
            browser.close()
    return geo


def faults(geo: dict) -> list[str]:
    """Every fault the measurements show, one line each."""
    out = []
    for c in geo["containers"]:
        if hole := _largest_hole(c["box"], c["kids"] + c["exempt"]):
            x, y, w, h = hole
            out.append(f"dead-space: {c['desc']} leaves {w:.0f}x{h:.0f}px at ({x:.0f}, {y:.0f}) that no block covers")

    seen = set()
    for i, a in enumerate(geo["borders"]):
        for b in geo["borders"][i + 1:]:
            if a["el"] == b["el"] or a["vertical"] != b["vertical"]:
                continue
            along, across = (1, 0) if a["vertical"] else (0, 1)
            overlap = min(a["rect"][along + 2], b["rect"][along + 2]) - max(a["rect"][along], b["rect"][along])
            gap = max(a["rect"][across], b["rect"][across]) - min(a["rect"][across + 2], b["rect"][across + 2])
            key = (a["el"], b["el"])
            if overlap > 4 and -0.25 <= gap < DOUBLED and key not in seen:
                seen.add(key)
                out.append(f"doubled-border: {a['side'].lower()} of {a['desc']} and {b['side'].lower()} of "
                           f"{b['desc']} are two lines {gap + 1:.1f}px apart over {overlap:.0f}px")

    rl, rt, rr, rb = geo["root"]
    for e in geo["elements"][1:]:
        l, t, r, b = e["box"]
        past = max(rl - l, rt - t, r - rr, b - rb)
        if past > 0.5:
            out.append(f"overflow: {e['desc']} reaches {past:.1f}px past the diagram's outer rectangle")

    for text, n in zip(geo["texts"], geo["crossed"]):
        if n >= 4:
            out.append(f"text-crossed: a line runs through \"{text['text']}\" ({n} line pixels inside its box)")

    for word in geo["breaks"]:
        out.append(f"broken-word: \"{word}\" is split across two lines")

    for text in geo["texts"]:
        if (ratio := _contrast(text["color"], geo["background"])) < 3:
            out.append(f"text-contrast: \"{text['text']}\" stands out from the background by {ratio:.1f}:1")

    for band, s in zip(geo["bands"], geo["shapes"]):
        if s["missing"] > 0.1 * s["samples"] or s["stray"] > 20:
            out.append(f"band-shape: {band['desc']} is not drawn as a{'' if band['kind'] == 'case' else 'n'} "
                       f"{band['kind']} band ({s['missing']} of {s['samples']} points on its lines unpainted, "
                       f"{s['stray']} pixels of line off them)")

    for g in geo["groups"]:
        if g["widths"] and max(g["widths"]) - min(g["widths"]) > TOL:
            out.append(f"column-widths: {g['desc']} has columns {[round(w, 1) for w in g['widths']]} wide")
    return out


def _contrast(a: list[float], b: list[float]) -> float:
    """WCAG contrast ratio of two sRGB colours given as 0-255 channels."""
    def luminance(rgb):
        lin = [(c / 255) / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _largest_hole(area: list[float], covers: list[list[float]]):
    """The largest piece of `area` no rect in `covers` reaches, as (x, y, w, h), when it is
    wider and taller than TOL. Cut along every rect edge, every piece is wholly in or out."""
    l, t, r, b = area
    xs = sorted({l, r, *(min(max(v, l), r) for c in covers for v in (c[0], c[2]))})
    ys = sorted({t, b, *(min(max(v, t), b) for c in covers for v in (c[1], c[3]))})
    best = None
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if x1 - x0 <= TOL or y1 - y0 <= TOL:
                continue
            if any(c[0] <= cx <= c[2] and c[1] <= cy <= c[3] for c in covers):
                continue
            if best is None or (x1 - x0) * (y1 - y0) > best[2] * best[3]:
                best = (x0, y0, x1 - x0, y1 - y0)
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", help="rendered HTML file to measure")
    ap.add_argument("--width", type=int, default=680, help="viewport width in CSS pixels")
    ap.add_argument("--scheme", choices=["light", "dark"], default="light", help="colour scheme the page is shown in")
    ap.add_argument("--dump", action="store_true", help="print the raw measurements as JSON")
    a = ap.parse_args()

    try:
        geo = measure(a.html, width=a.width, scheme=a.scheme)
    except Exception as exc:
        print(f"could not measure: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("layout is UNVERIFIED: do not claim it is correct", file=sys.stderr)
        return 2
    if a.dump:
        print(json.dumps(geo, indent=1))
    found = faults(geo)
    print(f"measured {geo['blocks']} blocks, {len(geo['texts'])} text boxes, {len(geo['bands'])} bands "
          f"at {a.width}px, {a.scheme} scheme")
    for f in found:
        print("FAIL " + f)
    if not found:
        print("PASS all geometry checks")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
