# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown"]
# ///
"""The board's layout, measured in a browser. Run: uv run test_board_layout.py

The seam is the rendered page: the demo tracker on disk, rendered by board.py, measured by
render-lint. The oracle is the no-overlap Property of mx/skills/tracker/corpus/board-orients.md: at zoom
80% to 200% and window widths from 900px up, nothing on the board overlaps or escapes its box, in
either scheme.

Browser zoom scales the layout, so a window of W pixels at zoom Z lays the page out in W/Z CSS
pixels, which is what render-lint's --width takes: WIDTHS is that quotient over the corners of the
matrix. A page that ignores
`?theme=` would be measured twice in the same scheme, so the scheme switch the house style
prescribes is the check's precondition rather than a second check.

Each width is measured on six pages: both schemes with every row folded, both schemes with one row
opened through its anchor, which lays out the blocks the ticket reads as and paints the dependency
graph beside it, and both schemes with the graph at full size over the board, which `&graph=1` on
the address opens.
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
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from board import render
from briefing import Briefing, cache_path
from demo_tracker import Demo

RENDER_LINT = Path(__file__).resolve().parents[1] / "show" / "render_lint.py"
WINDOWS = (900, 1280, 1920, 2560)  # from the Property's floor to a wide monitor
ZOOMS = (0.8, 1.0, 1.5, 2.0)  # the Property's range
WIDTHS = sorted({round(window / zoom) for window in WINDOWS for zoom in ZOOMS})
SCHEMES = ("day", "night")
OPENED = "t-map-columns"  # the demo tracker's build in review: the row carrying every mark
FOLDED = "t-retire-legacy-exporter"  # a needs-me row the anchor leaves folded, so it keeps its question list
# A briefing as a session writes one, so the no-overlap matrix measures the head of the column as
# prose; the hover probe below renders the other branch, the board's own count. No model runs in a
# check: the fixtures take claude off PATH.
WRITTEN = datetime.fromisoformat("2026-09-21T09:30:00+02:00")
SAID = """Two builds wait on your ruling and the frontier is three deep. The csv-import tree is the
one moving: parse-rows landed on Monday and map-columns has been in review since, with three
questions on it.

## next

- **Map columns once per bank**: the whole tree waits behind it, and its walkthrough runs.
- **Speed up the test suite**: four minutes to forty-eight seconds, two questions left.
- **The flaky upload test**: fifteen minutes, and it stops a build going red for nothing.

The first two touch nothing in common and can run as one wave."""
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


@pytest.mark.xfail(strict=False, reason="passes or fails by machine, not by code: agent/tickets/layout-check-flaky.md fixes it or retires the check")
def test_nothing_on_the_board_overlaps_or_escapes_its_box_at_any_width_in_either_scheme(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    Briefing(SAID, WRITTEN, "abc-123", WRITTEN, WRITTEN, 2).write(cache_path(out))
    render(transcribed.root, transcribed.repo, out)
    pages = [f"{out}?theme={scheme}{anchor}" for scheme in SCHEMES
             for anchor in ("", f"#{OPENED}", f"&graph=1#{OPENED}")]
    found = {width: lint(pages, width) for width in WIDTHS}
    assert {width: f for width, f in found.items() if f} == {}


# What the page says of itself once a browser runs it: which scheme it painted, whether the anchor
# opened a row, whether the graph beside it came back, whether the briefing is set as prose and says
# what it is, and what each mark shows on hover, a copy button's account of what it copies among
# them. The side column's own hints are `title` attributes, as the graph's buttons are: a box that
# scrolls cuts a tooltip drawn inside it, and that column is the one box on the page that scrolls. A pseudo-element has no rect of its own, so a
# tooltip's box is its host's plus the offsets the element resolves; `clipped` is the ancestor that
# would hide it, which is how two marks came to carry words no reader could see.
PROBE = r'''
import json, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

page_url = Path(sys.argv[1]).resolve().as_uri()
width, marks = int(sys.argv[2]), sys.argv[3].split(",")
ROW, FOLDED = sys.argv[4].split(",")
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
        page.goto(f"{page_url}?theme={scheme}#{ROW}", wait_until="networkidle")
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
    out["briefing"] = page.evaluate("""
      () => {
        const p = document.querySelector(".btext p"), box = p.getBoundingClientRect()
        return {wraps: getComputedStyle(p).whiteSpace !== "nowrap", over: p.scrollWidth - Math.ceil(box.width),
                says: document.querySelector("#briefing .bwhen").title}
      }
    """)
    out["graphs"] = page.evaluate("document.querySelectorAll('.side .mermaid svg').length")
    out["cdn"] = not any("mermaid" in url or "elk" in url for url in failed)
    for mark in marks:
        where = mark if mark.startswith("#") else f"#{ROW} .{mark}"
        page.hover(where)
        out["tips"][mark] = page.evaluate(TIP, where)
    out["questions"] = page.evaluate("""
      ([opened, folded]) => {
        const listed = (id) => {
          const list = document.getElementById(id).querySelector(".qs")
          return list ? list.getBoundingClientRect().height > 0 : null
        }
        const row = document.getElementById(opened)
        // each question of the opened row, as boxes rather than as nodes: a button the markup
        // carries and the style hides is what this run is here to tell from one the reader can click
        const asked = [...row.querySelectorAll(".asked > li")].map((li) => {
          const line = li.getBoundingClientRect()
          const button = li.querySelector(":scope > .copier")?.getBoundingClientRect()
          return {copier: button ? button.width > 0 : false,
                  at_the_end: button ? line.right - button.right < 1 : null}
        })
        return {opened_list: listed(opened), folded_list: listed(folded), asked}
      }
    """, [ROW, FOLDED])
    page.click(f"#{FOLDED} .qall")
    page.wait_for_timeout(500)
    out["copied"] = {
        "clipboard": page.evaluate("navigator.clipboard.readText()"),
        "asked": page.evaluate(f"document.querySelector('#{FOLDED} .qall').dataset.copy"),
        "note": page.inner_text("#toast"),
        "shown": page.evaluate("document.getElementById('toast').classList.contains('on')"),
        "still_folded": page.evaluate(f"!document.getElementById('{FOLDED}').open"),
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
# repeats within the row. An opened row lists its questions in its block rather than under its
# name, so the marks of that list are read off a row the anchor leaves folded.
MARKS = ("tree", "slug", "asks", "title", "time", "pri", "chip", "rp", "gh", "runcopy", "tick",
         f"#{OPENED} .asked > li:first-child .tag", f"#{OPENED} .asked > li:first-child > .copier",
         "#grp-needs .qgroup",
         f"#{OPENED} .sessions li:first-child .when", f"#{OPENED} .sessions li:first-child .resume",
         # the list under the name, which only a folded row carries
         f"#{FOLDED} .qall", f"#{FOLDED} .q:first-child .qtag",
         f"#{FOLDED} .q:first-child .qhead", f"#{FOLDED} .q:first-child .qcopy")


def probe(page: Path, width: int) -> dict:
    done = subprocess.run(
        ["uv", "run", "--with", "playwright", "python", "-", str(page), str(width), ",".join(MARKS), f"{OPENED},{FOLDED}"],
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

    The same run says what the rest of the page did: that the name keeps its words while the links
    beside it give way, that ?theme= pinned each scheme, that the anchor opened a row, that an
    opened row shows each of its questions once, and that the graph survives the scheme switch.
    Three of those, the scheme, the anchor and the graph, are what the layout check above assumes
    of its six pages; the fourth, that ?graph opened the overlay on a graph rather than on the
    placeholder, belongs to the graph probe below."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(transcribed.root, transcribed.repo, out)  # no briefing: the board's own count
    seen = probe(out, width)
    assert seen["schemes"]["day"] != seen["schemes"]["night"], f"?theme= pinned neither scheme: {seen['schemes']}"
    assert seen["opened"] == 1, "the anchor opened no row, so the layout check measures the folded page twice"
    said = seen["briefing"]
    assert said["wraps"] and said["over"] <= 0, f"the briefing is set as a row's mark rather than as prose: {said}"
    assert said["says"], "the briefing's own mark says nothing about what it is"
    if seen["cdn"]:
        assert seen["graphs"] == 1, "the graph beside the rows never painted"
        assert seen["graphs_after_switch"] == 1, "the scheme switch left the graph panel empty"
    assert seen["scheme_after_switch"] != seen["scheme_before_switch"], "the switch did not change the scheme"
    # an opened row shows each of its questions once: the list under the name goes, and the block
    # carries the same questions with a copy button on each
    asked = seen["questions"]
    assert asked["opened_list"] is False, "the opened row lists its questions under its name as well as in its block"
    assert asked["folded_list"] is True, "a folded row lost the questions under its name"
    assert [q["copier"] for q in asked["asked"]] == [True] * 3, (
        f"a question of the opened row has no button the reader can click: {asked['asked']}"
    )
    assert all(q["at_the_end"] for q in asked["asked"]), (
        f"a question's button sits among its words rather than at the end of its line: {asked['asked']}"
    )
    # a copy button is a span inside a summary, so the click it takes is the page's to handle
    copied = seen["copied"]
    assert copied["clipboard"] == copied["asked"], "the click put something else on the clipboard"
    assert copied["clipboard"].count("- [D") == 2, "the folded row's two questions, under its path"
    assert copied["shown"] and "retire-legacy-exporter.md" in copied["note"], f"the note reads {copied['note']!r}"
    assert copied["still_folded"], "the click opened the row instead of copying"
    # the name is what a row is read by, so it is never the thing that gives up its width
    for name in seen["names"]:
        assert not (name["cut"] and name["beside"]), (
            f"{name['row']}: the name is cut to {name['text']!r} while {name['beside']} link(s) beside it are whole"
        )
        assert not name["cut"], (
            f"{name['row']}: the name {name['text']!r} does not fit the column even with the row to itself"
            ", a name this long renders truncated until it is edited (the spec's Decisions), so if"
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
# column's preview, the same graph at full size over the board, and the same again in a window of
# its own. Every move a reader makes is made here, and what the board did with it is read off the
# board: the two keys, Escape's order, a click on the preview and on a node in it, a drag that pans
# and the click it ends with, the switch in each view, a node clicked in each full size view, the
# board re-rendering under the window, and the board going away.
GRAPH_PROBE = r'''
import json, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

page_url = Path(sys.argv[1]).resolve().as_uri()
ROW, NODE, NEXT = "t-map-columns", "#t-commit-import", "#t-parse-rows"
WIDE = "(sel) => document.querySelector(sel)?.getBoundingClientRect().width ?? 0"
OVER = "(sel) => { const b = document.querySelector(sel); return b.scrollWidth - b.clientWidth }"
OPEN = "document.getElementById('gfull').classList.contains('open')"

def nodes(frame, where):
    return frame.eval_on_selector_all(where + " g.node", "els => els.length")

def click_node(frame, where, which):
    """The node for `which`, clicked where the graph is drawn."""
    attr = "els => els.map((a) => a.getAttribute('href') || a.getAttribute('xlink:href'))"
    hrefs = frame.eval_on_selector_all(where + " a", attr)
    assert which in hrefs, f"no node for {which} in {where}"
    frame.locator(where + " a").nth(hrefs.index(which)).click()

def named(frame, where, name):
    frame.wait_for_function("([w, n]) => document.querySelector(w)?.textContent === n", arg=[where, name])

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"))
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    page = context.new_page()
    failed = []
    page.on("requestfailed", lambda r: failed.append(r.url))
    errors = []
    page.on("pageerror", lambda e: errors.append("board: " + str(e)))

    # ?graph on the address, beside the row's anchor: the state the layout check measures
    page.goto(f"{page_url}?theme=night&graph=1#{ROW}", wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    out = {"cdn": not any("mermaid" in url or "elk" in url for url in failed),
           "ground": page.evaluate("getComputedStyle(document.body).backgroundColor"),
           "font": page.evaluate("getComputedStyle(document.getElementById('gname')).fontFamily"),
           "node": NODE}
    if out["cdn"]:
        page.wait_for_selector("#gfull .gsvg svg")
    out["from_the_address"] = {"open": page.is_visible("#gfull"), "nodes": nodes(page, "#gfull .gsvg"),
                               "name": page.inner_text("#gfull .gname")}
    out["preview_width"] = page.evaluate(WIDE, ".side .g:not([hidden]) .mermaid svg")

    # the whole tracker at full size, dragged to pan, then a node
    page.click("#gfull [data-gmode=all]")
    named(page, "#gfull .gname", "whole tracker")
    page.wait_for_selector("#gfull .gsvg g.node.cur")
    over = {"name": page.inner_text("#gfull .gname"), "width": page.evaluate(WIDE, "#gfull .gsvg svg"),
            "nodes": nodes(page, "#gfull .gsvg"), "overflow": page.evaluate(OVER, "#gfull .gfbody"),
            "marked": page.eval_on_selector_all("#gfull .gsvg g.node.cur", "els => els.map((n) => n.id)"),
            "titles": page.eval_on_selector_all("#gfull .gsvg g.node title", "els => els.length"),
            "viewbox": page.evaluate("() => { const v = document.querySelector('#gfull .gsvg svg').viewBox.baseVal; return [v.width, v.height] }"),
            "drawn": page.evaluate("() => { const b = document.querySelector('#gfull .gsvg svg').getBoundingClientRect(); return [b.width, b.height] }")}
    # narrowed first, so the drag has something to move whatever the fixture's
    # labels are as wide as: the check is that a drag pans, not that this
    # tracker's graph happens to overflow the window this probe opens in
    page.set_viewport_size({"width": 700, "height": 950})
    page.wait_for_function("document.querySelector('#gfull .gfbody').scrollWidth > document.querySelector('#gfull .gfbody').clientWidth")
    over["overflow"] = page.evaluate(OVER, "#gfull .gfbody")
    box = page.evaluate("() => { const b = document.querySelector('#gfull .gfbody').getBoundingClientRect(); return {x: b.x, y: b.y, w: b.width, h: b.height} }")
    page.mouse.move(box["x"] + box["w"] * 0.8, box["y"] + box["h"] * 0.5)
    page.mouse.down()
    page.mouse.move(box["x"] + 3, box["y"] + box["h"] * 0.5, steps=12)  # out over the backdrop
    page.mouse.up()
    over["panned"] = page.evaluate("document.querySelector('#gfull .gfbody').scrollLeft")
    over["open_after_pan"] = page.is_visible("#gfull")
    over["grabbing"] = page.evaluate("document.querySelector('#gfull .gfbody').classList.contains('panning')")
    click_node(page, "#gfull .gsvg", NODE)
    over["open_after_node"] = page.is_visible("#gfull")
    over["cursor"] = page.evaluate("document.querySelector('.ticket.kcur')?.id")
    out["overlay"] = over

    # the two keys, and Escape taking the overlay before the open row
    page.keyboard.press("f")
    page.wait_for_selector("#gfull .gsvg svg")
    keys = {"f_opened": page.is_visible("#gfull")}
    page.keyboard.press("Escape")
    keys["esc_closed"] = not page.is_visible("#gfull")
    keys["row_still_open"] = page.evaluate(f"!!document.getElementById('{ROW}')?.open")
    out["keys"] = keys

    # the preview: a click opens the full size view, a click on a node in it goes to that row
    page.click(".side .g:not([hidden]) .mermaid", position={"x": 3, "y": 3})
    page.wait_for_selector("#gfull .gsvg svg")
    preview = {"click_opened": page.is_visible("#gfull")}
    page.keyboard.press("Escape")
    click_node(page, ".side .g:not([hidden]) .mermaid", NEXT)
    # a preview node is a link, so the board follows it through the address rather than at once
    page.wait_for_function(f"document.querySelector('.ticket.kcur')?.id === '{NEXT[1:]}'")
    preview["node_opened"] = page.is_visible("#gfull")
    preview["node_cursor"] = page.evaluate("document.querySelector('.ticket.kcur')?.id")
    out["preview"] = preview

    # the window of its own, opened with the other key
    with page.expect_popup() as popped:
        page.keyboard.press("w")
    win = popped.value
    win.on("pageerror", lambda e: errors.append("window: " + str(e)))
    win.set_viewport_size({"width": 900, "height": 620})
    win.wait_for_selector(".gfbody g.node.cur")
    window = {"title": win.title(), "scheme": win.evaluate("document.documentElement.dataset.theme"),
              "ground": win.evaluate("getComputedStyle(document.body).backgroundColor"),
              "font": win.evaluate("getComputedStyle(document.querySelector('.gname')).fontFamily"),
              "name": win.inner_text(".gname"), "width": win.evaluate(WIDE, ".gfbody svg"),
              "nodes": nodes(win, ".gfbody"), "overflow": win.evaluate(OVER, ".gfbody"),
              "titles": win.eval_on_selector_all(".gfbody g.node title", "els => els.length"),
              "marked": win.eval_on_selector_all(".gfbody g.node.cur", "els => els.length")}
    win.click("[data-gmode=tree]")  # the board is on the whole tracker, so this is a change in both
    named(win, ".gname", "csv-import")
    window["switched"] = win.inner_text(".gname")
    window["board_name"] = page.inner_text("#gname")
    click_node(win, ".gfbody", NODE)
    page.wait_for_function(f"document.querySelector('.ticket.kcur')?.id === '{NODE[1:]}'")
    window["cursor"] = page.evaluate("document.querySelector('.ticket.kcur')?.id")
    window["still_open"] = not win.is_closed()
    page.keyboard.press("j")  # the window follows the board's cursor without redrawing
    win.wait_for_selector(".gfbody g.node.cur")
    window["follows_cursor"] = win.eval_on_selector_all(".gfbody g.node.cur", "els => els.length")
    window["html"] = win.evaluate("document.documentElement.outerHTML")
    out["window"] = window

    # the re-render every tracker change triggers, under a window that has to find the board again
    page.reload(wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.keyboard.press("Escape")
    page.wait_for_selector(f"#{ROW} > summary")
    page.click(f"#{ROW} > summary")
    win.wait_for_selector(".gfbody g.node.cur")
    click_node(win, ".gfbody", NEXT)
    page.wait_for_function(f"document.querySelector('.ticket.kcur')?.id === '{NEXT[1:]}'")
    out["after_reload"] = {"orphan": win.evaluate("document.documentElement.dataset.orphan"),
                           "cursor": page.evaluate("document.querySelector('.ticket.kcur')?.id")}

    # the board gone: a window that says so rather than one that looks live
    page.close()
    win.wait_for_function("document.documentElement.dataset.orphan === '1'", timeout=10_000)
    out["orphan_says"] = win.inner_text(".gorphan")
    out["errors"] = errors
    browser.close()
print(json.dumps(out))
'''


def graph_probe(page: Path) -> dict:
    done = subprocess.run(
        ["uv", "run", "--with", "playwright", "python", "-", str(page)],
        input=GRAPH_PROBE, capture_output=True, text=True,
    )
    assert done.returncode == 0, f"graph probe: {done.stderr.strip()[-3000:]}"
    return json.loads(done.stdout)


def test_the_preview_opens_the_graph_at_full_size_over_the_board_and_in_a_window(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The ticket's acceptance criteria, which are all about what a browser does: the whole
    tracker's graph readable at full size in the overlay, a node clicked in the overlay and in the
    window bringing the board to that ticket's row, and the switch working in both.

    Readable is the size mermaid drew the graph for, which is the one its viewBox counts in and the
    one the preview's column shrinks it below. The window of its own is a page of its own, so its
    layout is handed to render-lint here rather than through the matrix above, which only reaches
    pages on disk."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    Briefing(SAID, WRITTEN, "abc-123", WRITTEN, WRITTEN, 2).write(cache_path(out))
    render(transcribed.root, transcribed.repo, out)
    seen = graph_probe(out)
    assert seen["errors"] == [], seen["errors"]
    if not seen["cdn"]:
        pytest.skip("no mermaid: the graph never painted")
    row = seen["node"].removeprefix("#")

    # what the layout matrix above assumes of its two ?graph pages
    came = seen["from_the_address"]
    assert came["open"] and came["nodes"] >= 5 and came["name"] == "csv-import", (
        f"?graph did not open the overlay on the row's own graph: {came}"
    )

    over = seen["overlay"]
    assert over["name"] == "whole tracker", f"the overlay's switch left it on {over['name']!r}"
    assert over["nodes"] >= 8, f"the whole tracker's graph drew {over['nodes']} nodes"
    assert all(abs(a - b) < 1 for a, b in zip(over["drawn"], over["viewbox"], strict=True)), (
        f"the overlay draws {over['drawn']} of a graph mermaid measured for {over['viewbox']}"
    )
    assert over["width"] > 2 * seen["preview_width"], (
        f"the overlay draws the graph {over['width']}px wide, against {seen['preview_width']}px in the preview"
    )
    assert over["titles"] == over["nodes"], "a node at full size does not carry its full title"
    assert len(over["marked"]) == 1, f"the cursor's row is marked on {len(over['marked'])} nodes"
    assert over["overflow"] > 0 and over["panned"] > 0, (
        f"a drag across the box moved it {over['panned']}px of {over['overflow']}px of graph past its edge"
    )
    assert over["open_after_pan"] and not over["grabbing"], (
        "a drag that ended on the backdrop closed the overlay or left it under the grabbing cursor"
    )
    assert not over["open_after_node"], "the click left the overlay over the board"
    assert over["cursor"] == row, f"the click left the board on {over['cursor']!r}"

    keys = seen["keys"]
    assert keys["f_opened"] and keys["esc_closed"], f"f and Escape: {keys}"
    assert keys["row_still_open"], "Escape folded the row behind the overlay instead of closing the overlay"

    preview = seen["preview"]
    assert preview["click_opened"], "a click on the preview did not open the full size view"
    assert not preview["node_opened"], "a node clicked in the preview opened the overlay instead of going to its row"
    assert preview["node_cursor"] == "t-parse-rows", f"the preview's node left the board on {preview['node_cursor']!r}"

    win = seen["window"]
    assert win["title"].endswith("dependencies"), win["title"]
    assert win["scheme"] == "night" and win["ground"] == seen["ground"], (
        f"the window is not in the board's scheme: {win['scheme']}, {win['ground']}"
    )
    assert win["font"] == seen["font"], f"the window letters its head in {win['font']}, the board in {seen['font']}"
    assert win["width"] > 2 * seen["preview_width"], f"the window draws the graph {win['width']}px wide"
    assert win["titles"] == win["nodes"], "a node in the window does not carry its full title"
    assert win["marked"] == 1 and win["follows_cursor"] == 1, (
        "the window does not mark the row the board's cursor is on, or stopped following it"
    )
    assert win["overflow"] > 0, "the window's graph fits its box, so nothing there is scrolled or panned"
    assert win["switched"] == "csv-import" and win["board_name"] == "csv-import", (
        f"the switch in the window left it on {win['switched']!r} and the board on {win['board_name']!r}"
    )
    assert win["cursor"] == row, f"the click in the window left the board on {win['cursor']!r}"
    assert win["still_open"], "the click closed the window instead of moving the board behind it"

    # the board reloads on every tracker change, which is where a window holding the board itself
    # would go quiet: it finds the board again and goes on driving it
    after = seen["after_reload"]
    assert after["orphan"] == "" and after["cursor"] == "t-parse-rows", (
        f"the window lost the board across its re-render: {after}"
    )
    assert "gone" in seen["orphan_says"], f"a window whose board closed says {seen['orphan_says']!r}"

    # the window is a rendered page of the board's, so the no-overlap Property is its business too
    doc = tmp_path / "graph-window.html"
    doc.write_text(re.sub(r"<script>.*?</script>", "", win["html"], flags=re.S))
    assert {width: f for width in (450, 900, 1600) if (f := lint([str(doc)], width))} == {}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
