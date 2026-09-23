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

Each width is measured on six pages: both schemes with every row folded, both schemes with one row
opened through its anchor, which lays out the blocks the ticket reads as and paints the dependency
graph beside it, and both schemes with the graph at full size over the board, which #graph opens.
A board nobody has clicked has no graph and no open body, so without the anchors most of what the
Property covers is never laid out.

Fourteen widths, two schemes, folded, open and the full size graph is fourteen browser runs of six
pages, a minute of the suite: the matrix the Property states, rather than a sample of it.

What render-lint measures is text against its own box, and SVG text against other SVG text: two
HTML marks overlapping each other are outside its reach, and so is text a box clips rather than
spills, which every mark that truncates does by design. The Property is executable as far as that
reaches; the rest was read by eye at these widths, in both schemes (02-rows' closing comment).

Beside it, one browser run per width drives what render-lint cannot see: a mark's words on hover, a
copy button's click, and the page's own answers about the scheme, the anchor and the graph.
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
# The demo's own transcripts (the `transcribed` fixture), so the sessions on its commits are ones
# this machine can name and the opened row carries the block that lists them.


def lint(pages: list[str], width: int) -> list[dict]:
    """render-lint's findings on each page at `width`, the ones it reports without failing aside."""
    done = subprocess.run(
        ["uv", "run", str(RENDER_LINT), *pages, "--width", str(width), "--json"],
        capture_output=True, text=True,
    )
    assert done.returncode in (0, 1), f"render-lint: {done.stderr.strip()}"
    return [f for f in json.loads(done.stdout) if f["kind"] not in ("tight", "clipped")]


def test_nothing_on_the_board_overlaps_or_escapes_its_box_at_any_width_in_either_scheme(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(tracker_roots(transcribed.root), transcribed.repo, out)
    pages = [f"{out}?theme={scheme}{anchor}" for scheme in SCHEMES for anchor in ("", f"#{OPENED}", "#graph")]
    found = {width: lint(pages, width) for width in WIDTHS}
    assert {width: f for width, f in found.items() if f} == {}


# What the page says of itself once a browser runs it: which scheme it painted, whether the anchor
# opened a row, whether the graph beside it came back, and what each mark shows on hover, a copy
# button's account of what it copies among them. A pseudo-element has no rect of its own, so a
# tooltip's box is its host's plus the offsets the element resolves; `clipped` is the ancestor that
# would hide it, which is how two marks came to carry words no reader could see.
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
    # the clipboard is what a copy button is for, and a page reaches it only where it is granted
    context = browser.new_context(viewport={"width": width, "height": 1000},
                                  permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
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
        where = mark if mark.startswith("#") else f"#t-csv-import-02 .{mark}"
        page.hover(where)
        out["tips"][mark] = page.evaluate(TIP, where)
    page.click("#t-csv-import-02 .qall")
    page.wait_for_timeout(500)
    out["copied"] = {
        "clipboard": page.evaluate("navigator.clipboard.readText()"),
        "asked": page.evaluate("document.querySelector('#t-csv-import-02 .qall').dataset.copy"),
        "note": page.inner_text("#toast"),
        "shown": page.evaluate("document.getElementById('toast').classList.contains('on')"),
        "still_open": page.evaluate("!!document.getElementById('t-csv-import-02').open"),
    }
    out["scheme_before_switch"] = page.evaluate("document.documentElement.dataset.theme")
    page.click("#scheme")
    page.wait_for_timeout(2500)
    out["graphs_after_switch"] = page.evaluate("document.querySelectorAll('.side .mermaid svg').length")
    out["scheme_after_switch"] = page.evaluate("document.documentElement.dataset.theme")
    browser.close()
print(json.dumps(out))
'''

# a mark of the row the anchor opens, or a selector of its own for one that sits elsewhere or
# repeats within the row
MARKS = ("ftag", "num", "asks", "title", "time", "pri", "chip", "rp", "gh", "qall", "democopy", "tick",
         "#t-csv-import-02 .q:first-child .qtag", "#t-csv-import-02 .q:first-child .qhead",
         "#t-csv-import-02 .q:first-child .qcopy", "#t-csv-import-02 .asked .tag", "#grp-needs .qgroup",
         "#t-csv-import-02 .sessions li:first-child .when", "#t-csv-import-02 .sessions li:first-child .resume")


def probe(page: Path, width: int) -> dict:
    done = subprocess.run(
        ["uv", "run", "--with", "playwright", "python", "-", str(page), str(width), ",".join(MARKS)],
        input=PROBE, capture_output=True, text=True,
    )
    assert done.returncode == 0, f"probe: {done.stderr.strip()[-2000:]}"
    return json.loads(done.stdout)


# the row beside the graph panel, the row on its own, and the row reflowed
@pytest.mark.parametrize("width", [1500, 1100, 920])
def test_every_mark_shows_its_words_on_hover_inside_the_viewport(transcribed: Demo, tmp_path: Path, width: int, path_with: Callable[..., Path]) -> None:
    """The rendered half of the spec's "Every mark explains itself on hover", and of "a copy button
    shows what it copies": that the words the markup carries (test_board.py) reach the reader. A
    mark whose box hides its overflow hides its own tooltip, and one anchored to the wrong side
    runs off the edge of the window.

    The same run says what the rest of the page did, since it is the only one that drives a browser:
    that the name keeps its words while the links beside it give way, that ?theme= pinned each
    scheme, that the anchor opened a row, and that the graph survives the scheme switch, which is
    what the layout check above assumes of its four pages."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(tracker_roots(transcribed.root), transcribed.repo, out)
    seen = probe(out, width)
    assert seen["schemes"]["day"] != seen["schemes"]["night"], f"?theme= pinned neither scheme: {seen['schemes']}"
    assert seen["opened"] == 1, "the anchor opened no row, so the layout check measures the folded page twice"
    if seen["cdn"]:
        assert seen["graphs"] == 1, "the graph beside the rows never painted"
        assert seen["graphs_after_switch"] == 1, "the scheme switch left the graph panel empty"
    assert seen["scheme_after_switch"] != seen["scheme_before_switch"], "the switch did not change the scheme"
    # a copy button is a span inside a summary, so the click it takes is the page's to handle
    copied = seen["copied"]
    assert copied["clipboard"] == copied["asked"], "the click put something else on the clipboard"
    assert copied["clipboard"].count("- [D") == 3, "the ticket's three questions, under its path"
    assert copied["shown"] and "02-map-columns.md" in copied["note"], f"the note reads {copied['note']!r}"
    assert copied["still_open"], "the click folded the row instead of copying"
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


# What the graph does once a browser runs it, which is the only place it does anything: the side
# column's preview, the same graph opened at full size over the board, and the same again in a
# window of its own. A node is clicked in each full size view, and what the board did with the
# click is read off the board.
GRAPH_PROBE = r'''
import json, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

page_url = Path(sys.argv[1]).resolve().as_uri()
NODE = "#t-csv-import-04"  # a ticket with an edge, so it is a node in both graphs

def click_node(frame, where):
    hrefs = frame.eval_on_selector_all(where + " a", "els => els.map((a) => a.getAttribute('href') || a.getAttribute('xlink:href'))")
    frame.locator(where + " a").nth(hrefs.index(NODE)).click()

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"))
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    page = context.new_page()
    failed = []
    page.on("requestfailed", lambda r: failed.append(r.url))
    page.goto(f"{page_url}?theme=night#t-csv-import-02", wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    out = {"cdn": not any("mermaid" in url or "elk" in url for url in failed),
           "ground": page.evaluate("getComputedStyle(document.body).backgroundColor")}
    wide = "(sel) => document.querySelector(sel)?.getBoundingClientRect().width ?? 0"
    out["preview_width"] = page.evaluate(wide, ".side .mermaid svg")

    # the overlay: the whole tracker at full size, a node in it, and where the board landed
    page.click("#gopen")
    page.wait_for_selector("#gfull .gsvg svg")
    page.click("#gfull [data-gmode=all]")
    page.wait_for_timeout(1500)
    out["overlay"] = {
        "name": page.inner_text("#gfull .gname"),
        "width": page.evaluate(wide, "#gfull .gsvg svg"),
        "nodes": page.eval_on_selector_all("#gfull .gsvg g.node", "els => els.length"),
        "marked": page.eval_on_selector_all("#gfull .gsvg g.node.cur", "els => els.map((n) => n.id)"),
        "titles": page.eval_on_selector_all("#gfull .gsvg g.node title", "els => els.length"),
        "pannable": page.evaluate("(() => { const b = document.querySelector('#gfull .gfbody'); return b.scrollWidth > b.clientWidth })()"),
    }
    click_node(page, "#gfull .gsvg")
    page.wait_for_timeout(400)
    out["overlay"]["still_open"] = page.evaluate("document.getElementById('gfull').classList.contains('open')")
    out["overlay"]["cursor"] = page.evaluate("document.querySelector('.ticket.kcur')?.id")

    # the window of its own, which the board goes on driving and which goes on driving the board
    with page.expect_popup() as popped:
        page.click("#gwinopen")
    win = popped.value
    win.wait_for_selector(".gfbody svg")
    out["window"] = {
        "title": win.title(),
        "scheme": win.evaluate("document.documentElement.dataset.theme"),
        "ground": win.evaluate("getComputedStyle(document.body).backgroundColor"),
        "name": win.inner_text(".gname"),
        "width": win.evaluate(wide, ".gfbody svg"),
        "titles": win.eval_on_selector_all(".gfbody g.node title", "els => els.length"),
    }
    win.click("[data-gmode=all]")  # the switch in the window moves the board's graph too
    win.wait_for_timeout(1500)
    out["window"]["name_all"] = win.inner_text(".gname")
    out["window"]["board_name"] = page.inner_text("#gname")
    click_node(win, ".gfbody")
    page.wait_for_timeout(400)
    out["window"]["cursor"] = page.evaluate("document.querySelector('.ticket.kcur')?.id")
    out["window"]["still_open"] = not win.is_closed()
    page.click("#scheme")  # the board's scheme switch reaches the window
    win.wait_for_timeout(1500)
    out["window"]["scheme_after"] = win.evaluate("document.documentElement.dataset.theme")
    out["node"] = NODE
    browser.close()
print(json.dumps(out))
'''


def graph_probe(page: Path) -> dict:
    done = subprocess.run(
        ["uv", "run", "--with", "playwright", "python", "-", str(page)],
        input=GRAPH_PROBE, capture_output=True, text=True,
    )
    assert done.returncode == 0, f"graph probe: {done.stderr.strip()[-2000:]}"
    return json.loads(done.stdout)


def test_the_preview_opens_the_graph_at_full_size_over_the_board_and_in_a_window(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The ticket's acceptance criteria, which are all about what a browser does: the whole
    tracker's graph readable at full size in the overlay, a node clicked in the overlay and in the
    window bringing the board to that ticket's row, and the switch working in both.

    Readable is measured as the size mermaid drew the graph at, which is what the preview's column
    shrinks it below: the same graph, several times wider than the preview shows it."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(tracker_roots(transcribed.root), transcribed.repo, out)
    seen = graph_probe(out)
    if not seen["cdn"]:
        pytest.skip("no mermaid: the graph never painted")
    row = seen["node"].removeprefix("#")

    over = seen["overlay"]
    assert over["name"] == "whole tracker", f"the overlay's switch left it on {over['name']!r}"
    assert over["nodes"] >= 8, f"the whole tracker's graph drew {over['nodes']} nodes"
    assert over["width"] > 2 * seen["preview_width"], (
        f"the overlay draws the graph {over['width']}px wide, against {seen['preview_width']}px in the preview"
    )
    assert over["pannable"], "the whole tracker at full size fits the overlay, so nothing is being panned"
    assert over["titles"] == over["nodes"], "a node at full size does not carry its full title"
    assert len(over["marked"]) == 1, f"the cursor's row is marked on {len(over['marked'])} nodes"
    assert not over["still_open"], "the click left the overlay over the board"
    assert over["cursor"] == row, f"the click left the board on {over['cursor']!r}"

    win = seen["window"]
    assert win["title"].startswith("dependencies"), win["title"]
    assert win["scheme"] == "night" and win["scheme_after"] == "day", "the window did not follow the board's scheme"
    assert win["ground"] == seen["ground"], f"the window is not on the board's ground: {win['ground']}"
    assert win["width"] > 2 * seen["preview_width"], f"the window draws the graph {win['width']}px wide"
    assert win["titles"] > 0, "a node in the window carries no title"
    assert win["name_all"] == "whole tracker" and win["board_name"] == "whole tracker", (
        f"the switch in the window left it on {win['name_all']!r} and the board on {win['board_name']!r}"
    )
    assert win["cursor"] == row, f"the click in the window left the board on {win['cursor']!r}"
    assert win["still_open"], "the click closed the window instead of moving the board behind it"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
