#!/usr/bin/env python3
"""Render a Struktogramm and screenshot it, so you can look at your own output.

Struktogramm layout depends on flexbox height propagation and CSS gradient
geometry. Both are things you cannot verify by reading the markup -- a column
that fails to stretch, or a fan of diagonals that lands as a sawtooth, looks
completely fine in source. Screenshot and view the PNG.

Degrades gracefully: if no headless browser is present it still writes the HTML
and tells you so, rather than failing.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from struktogramm import page  # noqa: E402

CANDIDATES = [
    "/opt/google/chrome/chrome",
    "chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome",
]


def find_browser():
    for c in CANDIDATES:
        p = c if os.path.isfile(c) and os.access(c, os.X_OK) else shutil.which(c)
        if p:
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="JSON file containing the node list")
    ap.add_argument("-o", "--out", default="preview", help="output basename (default: preview)")
    ap.add_argument("--width", type=int, default=680)
    ap.add_argument("--height", type=int, default=1400, help="viewport height; make it taller than the diagram")
    ap.add_argument("--dark", action="store_true")
    ap.add_argument("--scale", type=float, default=2.0, help="device pixel ratio; 2 makes hairlines legible")
    a = ap.parse_args()

    with open(a.input) as f:
        nodes = json.load(f)

    html = os.path.abspath(a.out + ".html")
    with open(html, "w") as f:
        f.write(page(nodes, dark=a.dark))
    print(f"html: {html}")

    browser = find_browser()
    if not browser:
        print("no headless browser found -- open the HTML manually to check the layout",
              file=sys.stderr)
        return 0

    png = os.path.abspath(a.out + ".png")
    cmd = [browser, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
           f"--force-device-scale-factor={a.scale}",
           f"--window-size={a.width},{a.height}",
           f"--screenshot={png}", html]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(png):
        print(f"screenshot failed:\n{r.stderr[-800:]}", file=sys.stderr)
        return 1
    print(f"png:  {png}")
    print("Now view the PNG. Check: columns stretch to equal height, diagonals meet the "
          "corners cleanly, no doubled borders, nothing clipped at the bottom.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
