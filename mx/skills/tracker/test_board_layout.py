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
spills, which every mark that truncates does by design. The Property is executable as far as that
reaches; the rest was read by eye at these widths, in both schemes (02-rows' closing comment).

Beside it, one browser run per width drives what render-lint cannot see: a mark's words on hover,
and the page's own answers about the scheme, the anchor and the graph.
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
    return [f for f in json.loads(done.stdout) if f["kind"] not in ("tight", "clipped")]


def test_nothing_on_the_board_overlaps_or_escapes_its_box_at_any_width_in_either_scheme(demo: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    pages = [f"{out}?theme={scheme}{anchor}" for scheme in SCHEMES for anchor in ("", f"#{OPENED}")]
    found = {width: lint(pages, width) for width in WIDTHS}
    assert {width: f for width, f in found.items() if f} == {}


# What the page says of itself once a browser runs it: which scheme it painted, whether the anchor
# opened a row, whether the graph beside it came back, and what each mark shows on hover. A
# pseudo-element has no rect of its own, so a tooltip's box is its host's plus the offsets the
# element resolves; `clipped` is the ancestor that would hide it, which is how two marks came to
# carry words no reader could see.
PROBE = r'''
import json, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

page_url = Path(sys.argv[1]).resolve().as_uri()
width, marks = int(sys.argv[2]), sys.argv[3].split(",")
TIP = """
(mark) => {
  const el = document.querySelector(mark)
  if (!el) return {missing: true}
  const tip = getComputedStyle(el, "::after")
  // an absolutely positioned box is laid out from the padding box of its nearest positioned
  // ancestor, which is the row, not the mark
  let cb = el
  while (cb.parentElement && getComputedStyle(cb).position === "static") cb = cb.parentElement
  const base = cb.getBoundingClientRect()
  const [w, h] = [parseFloat(tip.width), parseFloat(tip.height)]
  const left = tip.left === "auto" ? base.right - w - parseFloat(tip.right) : base.left + parseFloat(tip.left)
  // what could clip the tip: its containing block and everything under it, up to the first
  // positioned ancestor, which is where an absolutely positioned box is laid out from
  let clipped = null
  for (let a = el; a; a = a.parentElement) {
    if (getComputedStyle(a).overflow !== "visible") clipped = a.className
    if (a !== el && getComputedStyle(a).position !== "static") break
  }
  return {words: tip.content, w, h, left, right: left + w, clipped, viewport: innerWidth}
}
"""
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"))
    page = browser.new_page(viewport={"width": width, "height": 1000})
    failed = []
    page.on("requestfailed", lambda r: failed.append(r.url))
    out = {"schemes": {}, "tips": {}}
    for scheme in ("day", "night"):
        page.goto(f"{page_url}?theme={scheme}#t-csv-import-02", wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        out["schemes"][scheme] = page.evaluate("getComputedStyle(document.body).backgroundColor")
    out["names"] = page.evaluate("""
      () => [...document.querySelectorAll("details.ticket")].map((row) => {
        const clip = row.querySelector(".title .clip"), name = clip.getBoundingClientRect()
        const links = [...row.querySelectorAll(".titleline > a")]
        return {
          row: row.id, text: clip.textContent,
          cut: clip.scrollWidth > clip.clientWidth + 1,
          beside: links.filter((a) => Math.abs(a.getBoundingClientRect().top - name.top) < 4).length,
        }
      })
    """)
    out["opened"] = page.evaluate("document.querySelectorAll('details.ticket[open]').length")
    out["graphs"] = page.evaluate("document.querySelectorAll('.side .mermaid svg').length")
    out["cdn"] = not any("mermaid" in url or "elk" in url for url in failed)
    for mark in marks:
        page.hover(f"#t-csv-import-02 .{mark}" if mark != "num" else "#t-csv-import-02 .num")
        out["tips"][mark] = page.evaluate(TIP, f"#t-csv-import-02 .{mark}")
    out["scheme_before_switch"] = page.evaluate("document.documentElement.dataset.theme")
    page.click("#scheme")
    page.wait_for_timeout(2500)
    out["graphs_after_switch"] = page.evaluate("document.querySelectorAll('.side .mermaid svg').length")
    out["scheme_after_switch"] = page.evaluate("document.documentElement.dataset.theme")
    browser.close()
print(json.dumps(out))
'''

MARKS = ("ftag", "num", "asks", "title", "time", "pri", "chip", "rp", "gh")


def probe(page: Path, width: int) -> dict:
    done = subprocess.run(
        ["uv", "run", "--with", "playwright", "python", "-", str(page), str(width), ",".join(MARKS)],
        input=PROBE, capture_output=True, text=True,
    )
    assert done.returncode == 0, f"probe: {done.stderr.strip()[-2000:]}"
    return json.loads(done.stdout)


# the row beside the graph panel, the row on its own, and the row reflowed
@pytest.mark.parametrize("width", [1500, 1100, 920])
def test_every_mark_shows_its_words_on_hover_inside_the_viewport(demo: Demo, tmp_path: Path, width: int, path_with: Callable[..., Path]) -> None:
    """The rendered half of the spec's "Every mark explains itself on hover": that the words the
    markup carries (test_board.py) reach the reader. A mark whose box hides its overflow hides its
    own tooltip, and one anchored to the wrong side runs off the edge of the window.

    The same run says what the rest of the page did, since it is the only one that drives a browser:
    that the name keeps its words while the links beside it give way, that ?theme= pinned each
    scheme, that the anchor opened a row, and that the graph survives the scheme switch, which is
    what the layout check above assumes of its four pages."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(tracker_roots(demo.root), demo.repo, out)
    seen = probe(out, width)
    assert seen["schemes"]["day"] != seen["schemes"]["night"], f"?theme= pinned neither scheme: {seen['schemes']}"
    assert seen["opened"] == 1, "the anchor opened no row, so the layout check measures the folded page twice"
    if seen["cdn"]:
        assert seen["graphs"] == 1, "the graph beside the rows never painted"
        assert seen["graphs_after_switch"] == 1, "the scheme switch left the graph panel empty"
    assert seen["scheme_after_switch"] != seen["scheme_before_switch"], "the switch did not change the scheme"
    # the name is what a row is read by, so it is never the thing that gives up its width
    for name in seen["names"]:
        assert not (name["cut"] and name["beside"]), (
            f"{name['row']}: the name is cut to {name['text']!r} while {name['beside']} link(s) beside it are whole"
        )
        assert not name["cut"], (
            f"{name['row']}: the name {name['text']!r} does not fit the column even with the row to itself"
            " — a name this long renders truncated until it is edited (the spec's Decisions), so if"
            " the fixture meant it, this row wants a shorter H1"
        )
    for mark, tip in seen["tips"].items():
        assert not tip.get("missing"), f"no {mark} on the row"
        assert tip["words"] not in ("none", "normal"), f"the {mark} mark shows nothing on hover"
        assert tip["clipped"] is None, f"the {mark} mark's words are clipped away by {tip['clipped']!r}"
        assert tip["w"] > 20 and tip["h"] > 10, f"the {mark} mark's tooltip is {tip['w']}x{tip['h']}"
        assert 0 <= tip["left"] and tip["right"] <= tip["viewport"], (
            f"the {mark} mark's words run off the window: {tip['left']}..{tip['right']} of {tip['viewport']}"
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
