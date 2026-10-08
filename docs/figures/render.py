#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright"]
# ///
"""Render every figure the mx README embeds to PNG, both color schemes, at 2x, into mx/assets/.

`<name>.html` -> `<name>-light.png` and `<name>.png` (dark), for each `<name>` the README embeds as
`assets/<name>.png`. The scheme arrives as the emulated system preference, the way a reader's does;
the toggle button is hidden for the shot. The shot is of the body element, so the image is the
figure's own height whatever the viewport. Each PNG goes through `compress.py` once written.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
README = HERE.parents[1] / "mx" / "README.md"
ASSETS = README.parent / "assets"
CHROMIUM = shutil.which("chromium")
SCHEMES = {"light": "-light.png", "dark": ".png"}


def embedded() -> list[Path]:
    """The figures here whose render the README shows."""
    names = set(re.findall(r"assets/([\w-]+?)(?:-light)?\.png", README.read_text()))
    return sorted(html for html in HERE.glob("*.html") if html.stem in names)


def main() -> None:
    written = []
    with sync_playwright() as p:
        # the run it belongs to, as `browsers --help` defines it
        browser = p.chromium.launch(executable_path=CHROMIUM,
                                    args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
        page = browser.new_page(viewport={"width": 1312, "height": 400}, device_scale_factor=2)
        for html in embedded():
            for scheme, suffix in SCHEMES.items():
                page.emulate_media(color_scheme=scheme)
                page.goto(html.resolve().as_uri())
                page.add_style_tag(content=".scheme{display:none}")
                page.wait_for_load_state("networkidle")
                out = ASSETS / (html.stem + suffix)
                page.locator("body").screenshot(path=str(out))
                written.append(str(out))
        browser.close()
    subprocess.run([str(HERE / "compress.py"), *written], check=True)


if __name__ == "__main__":
    main()
