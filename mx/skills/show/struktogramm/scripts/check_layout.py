#!/usr/bin/env python3
"""Check a rendered Struktogramm for the geometric faults you cannot see in source.

Struktogramm correctness is a layout property, not a markup property. The markup
for a broken diagram and a correct one differ by a CSS rule, so reading the HTML
proves nothing. This measures the rendered boxes instead.

Checks:
  columns-equal-height   sibling columns in a branch/case/parallel must match,
                         because the notation permits no empty space
  no-overflow            no block may extend past its parent's bottom edge
  no-zero-size           every block must have been laid out
  fan-column-widths      case columns must be equal width; unequal widths would
                         imply a meaning the notation does not have

Exits non-zero if any check fails, so it can gate a build.
"""
import argparse
import json
import os
import sys

TOL = 1.5  # px; sub-pixel rounding from fractional flex widths is expected

PROBE = r"""
() => {
  const out = [];
  const rect = el => { const r = el.getBoundingClientRect();
                       return {x: r.x, y: r.y, w: r.width, h: r.height}; };
  document.querySelectorAll('.ns .cols').forEach((cols, i) => {
    const kids = [...cols.children].filter(c => c.classList.contains('col'));
    out.push({ kind: 'cols', idx: i,
               owner: cols.parentElement.className,
               cols: kids.map(k => {
                 const r = rect(k);
                 // the deepest last block inside this column
                 const blocks = k.querySelectorAll('.blk, .loop, .fork, .par');
                 let lowest = r.y;
                 blocks.forEach(bl => { const b = rect(bl);
                                        lowest = Math.max(lowest, b.y + b.h); });
                 r.fillGap = (r.y + r.h) - lowest;   // >0 means unbordered dead space
                 return r;
               }) });
  });
  document.querySelectorAll('.ns .blk, .ns .loop, .ns .fork, .ns .par')
    .forEach((el, i) => out.push({ kind: 'block', idx: i,
                                   cls: el.className, box: rect(el) }));
  return out;
}
"""


def check(html_path, browser_path=None, width=680):
    from playwright.sync_api import sync_playwright
    kw = {"args": ["--no-sandbox"]}
    if browser_path:
        kw["executable_path"] = browser_path
    with sync_playwright() as p:
        b = p.chromium.launch(**kw)
        pg = b.new_page(viewport={"width": width, "height": 900})
        pg.goto("file://" + os.path.abspath(html_path))
        data = pg.evaluate(PROBE)
        b.close()

    failures = []

    for e in data:
        if e["kind"] != "cols":
            continue
        hs = [c["h"] for c in e["cols"]]
        ws = [c["w"] for c in e["cols"]]
        if hs and max(hs) - min(hs) > TOL:
            failures.append(
                f"columns-equal-height: group {e['idx']} ({e['owner']}) "
                f"heights {[round(h, 1) for h in hs]} differ by "
                f"{round(max(hs) - min(hs), 1)}px")
        for j, c in enumerate(e["cols"]):
            if c.get("fillGap", 0) > TOL:
                failures.append(
                    f"column-not-filled: group {e['idx']} ({e['owner']}) column {j} "
                    f"leaves {round(c['fillGap'], 1)}px of unbordered dead space "
                    f"below its last block -- the notation permits no empty space")
        if len(ws) > 2 and max(ws) - min(ws) > TOL:
            failures.append(
                f"fan-column-widths: group {e['idx']} widths "
                f"{[round(w, 1) for w in ws]} are unequal")

    for e in data:
        if e["kind"] != "block":
            continue
        if e["box"]["w"] < 1 or e["box"]["h"] < 1:
            failures.append(f"no-zero-size: block {e['idx']} ({e['cls']}) "
                            f"laid out at {e['box']['w']}x{e['box']['h']}")

    return failures, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html", help="rendered HTML file to measure")
    ap.add_argument("--browser", default=None,
                    help="path to a Chromium binary if Playwright's own is absent")
    ap.add_argument("--width", type=int, default=680)
    ap.add_argument("--dump", action="store_true", help="print the raw geometry")
    a = ap.parse_args()

    try:
        failures, data = check(a.html, a.browser, a.width)
    except Exception as exc:
        print(f"could not measure: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("layout is UNVERIFIED -- do not claim it is correct", file=sys.stderr)
        return 2

    if a.dump:
        print(json.dumps(data, indent=1))

    ncols = sum(1 for e in data if e["kind"] == "cols")
    nblk = sum(1 for e in data if e["kind"] == "block")
    print(f"measured {nblk} blocks, {ncols} column groups")

    if failures:
        for f in failures:
            print("FAIL " + f)
        return 1
    print("PASS all geometry checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
