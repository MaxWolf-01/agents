# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown"]
# ///
"""The board's layout, measured in a browser. Run: uv run test_board_layout.py

The seam is the rendered page: the demo tracker on disk, rendered by board.py, measured by
render-lint. The oracle is the no-overlap Property of agent/tickets/board-orients/spec.md: at zoom
80% to 200% and window widths from 900px up, nothing on the board overlaps or escapes its box, in
either scheme.

Browser zoom scales the layout, so a window of W pixels at zoom Z lays the page out in W/Z CSS
pixels, which is what render-lint's --width takes: WIDTHS is that quotient over the corners of the
matrix. A page that ignores
`?theme=` would be measured twice in the same scheme, so the scheme switch the house style
prescribes is the check's precondition rather than a second check.

Each width is measured on four pages: both schemes with every row folded, and both schemes with
one row opened through its anchor, which is also what paints the dependency graph beside it. A
board nobody has clicked has no graph and no open body, so without the anchor half of what the
Property covers is never laid out.

Fourteen widths, two schemes, folded and open is fourteen browser runs of four pages, a minute of
the suite: the matrix the Property states, rather than a sample of it.

What render-lint measures is text against its own box, and SVG text against other SVG text: two
HTML marks overlapping each other are outside its reach, and so is text a box clips rather than
spills. The Property is executable as far as that reaches.
"""

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from board import render, tracker_roots
from demo_tracker import Demo

RENDER_LINT = Path(__file__).resolve().parents[1] / "show" / "render_lint.py"
WINDOWS = (900, 1280, 1920, 2560)  # from the Property's floor to a wide monitor
ZOOMS = (0.8, 1.0, 1.5, 2.0)  # the Property's range
WIDTHS = sorted({round(window / zoom) for window in WINDOWS for zoom in ZOOMS})
SCHEMES = ("day", "night")
OPENED = "t-csv-import-02"  # the demo tracker's build in review: the row carrying every mark


def lint(pages: list[str], width: int) -> list[dict]:
    """render-lint's findings on each page at `width`, the ones it reports without failing aside."""
    done = subprocess.run(
        ["uv", "run", str(RENDER_LINT), *pages, "--width", str(width), "--json"],
        capture_output=True, text=True,
    )
    assert done.returncode in (0, 1), f"render-lint: {done.stderr.strip()}"
    return [f for f in json.loads(done.stdout) if f["kind"] != "tight"]


def test_nothing_on_the_board_overlaps_or_escapes_its_box_at_any_width_in_either_scheme(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    page = out.read_text()
    assert "data-theme" in page and "light-dark(" in page, "the page carries no scheme switch, so neither scheme can be measured"
    pages = [f"{out}?theme={scheme}{anchor}" for scheme in SCHEMES for anchor in ("", f"#{OPENED}")]
    for width in WIDTHS:
        assert lint(pages, width) == [], f"at {width}px"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
