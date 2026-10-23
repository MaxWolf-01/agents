#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright", "tyro"]
# ///
"""Render every figure the mx README embeds to PNG, both color schemes, at 2x, into mx/assets/.

`<name>.html` -> `<name>-light.png` and `<name>.png` (dark), for each `<name>` the README embeds as
`assets/<name>.png`. The scheme arrives as the emulated system preference, the way a reader's does;
the toggle button is hidden for the shot. The shot is of the body element, so the image is the
figure's own height whatever the viewport. Each PNG goes through `compress.py` once written, and
each figure's HTML is recorded beside its PNGs (`rendered_from.py`).

Examples:

    docs/figures/render.py
    docs/figures/render.py --check
"""

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import tyro
from playwright.sync_api import sync_playwright

import rendered_from

HERE = Path(__file__).parent
README = HERE.parents[1] / "mx" / "README.md"
ASSETS = README.parent / "assets"
CHROMIUM = shutil.which("chromium")
SCHEMES = {"light": "-light.png", "dark": ".png"}


def embedded() -> list[Path]:
    """The figures here whose render the README shows."""
    names = set(re.findall(r"assets/([\w-]+?)(?:-light)?\.png", README.read_text()))
    return sorted(html for html in HERE.glob("*.html") if html.stem in names)


@dataclass
class Args:
    check: bool = False
    """Render nothing: exit 1, naming each image under mx/assets/ whose sources changed since its render or
    that has no record of them, and each figure here with one color scheme's PNG under mx/assets/ and not
    the other's."""


def check() -> list[str]:
    problems = rendered_from.stale()
    for html in sorted(HERE.glob("*.html")):
        light, dark = (ASSETS / (html.stem + suffix) for suffix in SCHEMES.values())
        if light.is_file() != dark.is_file():
            have, lack = (light, dark) if light.is_file() else (dark, light)
            problems.append(f"docs/figures/{html.name}: mx/assets/{have.name} is there and {lack.name} is not")
    return problems


def render() -> None:
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
            rendered_from.record(html.stem, Path(__file__), html)
        browser.close()
    subprocess.run([str(HERE / "compress.py"), *written], check=True)


if __name__ == "__main__":
    if not tyro.cli(Args, description=__doc__).check:
        render()
    elif problems := check():
        sys.exit("\n".join(problems))
