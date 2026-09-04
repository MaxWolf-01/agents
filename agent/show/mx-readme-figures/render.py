#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright"]
# ///
"""Render every figure in this directory to PNG, both color schemes, at 2x.

`<name>.html` -> `<name>-light.png` and `<name>.png` (dark). The scheme arrives as the
emulated system preference, the way a reader's does; the toggle button is hidden for the shot.
"""

import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
CHROMIUM = shutil.which("chromium")
SCHEMES = {"light": "-light.png", "dark": ".png"}


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page(viewport={"width": 1312, "height": 800}, device_scale_factor=2)
        for html in sorted(HERE.glob("*.html")):
            for scheme, suffix in SCHEMES.items():
                page.emulate_media(color_scheme=scheme)
                page.goto(html.resolve().as_uri())
                page.add_style_tag(content=".scheme{display:none}")
                page.wait_for_load_state("networkidle")
                out = html.with_name(html.stem + suffix)
                page.screenshot(path=str(out), full_page=True)
                print(out.name)
        browser.close()


if __name__ == "__main__":
    main()
