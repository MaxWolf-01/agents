#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["pyoxipng", "tyro"]
# ///
"""Compress PNGs in place, losslessly, with oxipng: the pixels stay the same and the file shrinks.

Every script that writes an image for the README runs this on what it wrote. Python stops at 3.13
because pyoxipng ships no wheel for 3.14 yet, and building one needs a Rust toolchain.

Examples:

    compress.py mx/assets/workflow-map.png mx/assets/workflow-map-light.png
    compress.py mx/assets/*.png
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import oxipng
import tyro


@dataclass
class Args:
    pngs: Annotated[list[Path], tyro.conf.Positional]
    """The PNG files to compress, each rewritten in place."""


def main(args: Args) -> None:
    for png in args.pngs:
        before = png.stat().st_size
        # past level 4, oxipng takes longer for no gain on these figures
        oxipng.optimize(png, level=4, strip=oxipng.StripChunks.safe())
        print(f"{png.name}: {before // 1024} KB -> {os.path.getsize(png) // 1024} KB")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
