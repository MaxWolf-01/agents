# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown", "markdown-it-py"]
# ///
"""The board's layout, measured in a browser. Run: uv run test_board_layout.py

The seam is the rendered page: the demo tracker on disk, rendered by board.py, measured by
render-lint. The oracle is the no-overlap Property of mx/skills/tracker/corpus/board-orients.md: at zoom
80% to 200% and window widths from 900px up, nothing on the board overlaps or escapes its box, in
either scheme.

Browser zoom scales the layout, so a window of W pixels at zoom Z lays the page out in W/Z CSS
pixels, which is what render-lint's --width takes: the Property states a range of layout widths,
that quotient over the corners of its grid. What is measured inside the range is both edges of
every band the board's own `@media` rules cut it into, read off the stylesheet board.py renders the
page with, so a new breakpoint brings its two widths here with no edit. What that gives up is a
collision that exists only mid-band, which takes a box whose size does not track the window's:
`.body` at 46rem, `main` and `.absences` at 110rem, and `.side` at 40vh of height are the ones the
board has.

A page that ignores `?theme=` would be measured twice in the same scheme, so the scheme switch the
house style prescribes is the check's precondition rather than a second check.

Each width is measured on eight pages: both schemes with every row folded, both schemes with one row
opened through its anchor, which lays out the blocks the ticket reads as and paints the dependency
graph beside it, both schemes with the graph at full size over the board, which `&graph=1` on
the address opens, and both schemes with a row folded under its parent ticket's opened through its
anchor, which opens the parent's row too and lays out the rows folded under it.
A board nobody has clicked has no graph and no open body, so without the anchors most of what the
Property covers is never laid out. Each width, and each set of pages at it, is a check of its own,
for the suite's processes to share out.

Beside the width matrix, the same widths over a board with a defect put back into it: a clean run
means nothing until the same widths have been shown reporting a defect.

What render-lint measures is text against its own box, and text drawn over other text, HTML over
HTML included; what it does not reach is text a box clips rather than spills, which every mark
that truncates does by design, and an overlap the browser paints an opaque box over, which is
what a card drawn over the page is. The Property is executable as far as that reaches; the rest
was read by eye at these widths, in both schemes (02-rows' closing comment).

Beside it, one browser run per width drives what render-lint cannot see: a mark's words on hover, a
copy button's click, and the page's own answers about the scheme, the anchor and the graph.

Every page load here answers the board's remote requests, its graph engine and its fonts, from
copies kept on this machine (show/page_cache.py), so a run after the first touches no network.
The browser checks run again with the network cut off and no copies, where the graph engine
never arrives: there they hold every view of the graph to saying it could not load, and drive
everything else the board does in full. A run online on a machine that has no network and no
copies skips, since the graph it is there to check never draws. One run more loads the engine and cuts
the network off before it draws, where every view of the graph says it could not be drawn.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

SHOW = Path(__file__).resolve().parents[1] / "show"
sys.path[:0] = [str(Path(__file__).parent), str(SHOW)]

from board import PAGE, render
from briefing import Briefing, cache_path
from demo_tracker import Demo
from page_cache import default_root

# Every check here starts a browser.
pytestmark = pytest.mark.full_path

RENDER_LINT = SHOW / "render_lint.py"
WINDOWS = (900, 2560)  # from the Property's floor to a wide monitor
ZOOMS = (0.8, 2.0)  # the Property's range
NARROWEST, WIDEST = round(min(WINDOWS) / max(ZOOMS)), round(max(WINDOWS) / min(ZOOMS))
SCHEMES = ("day", "night")
OPENED = "t-map-columns"  # the demo tracker's build in review: the row carrying every mark
FOLDED = "t-retire-legacy-exporter"  # a needs-me row the anchor leaves folded, so it keeps its question list
KIN = "t-carry-balances"  # a row folded under its parent ticket's, which its anchor opens with it
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
    """render-lint's findings on each page at `width`, the ones it reports without failing aside.
    A page it could not measure comes back as its own finding rather than as a clean run."""
    # 60s: the suite runs a browser per core, and under that load the board has taken past 20s to
    # load with nothing wrong with it.
    done = subprocess.run(
        ["uv", "run", str(RENDER_LINT), *pages, "--width", str(width), "--json", "--cache", str(default_root()),
         "--patience", "60"],
        capture_output=True, text=True,
    )
    # A run that never got as far as findings is its own failure, said here rather than left to a
    # decode error further down: the tool crashing, a browser going with it, or uv failing to start
    # it all arrive as an exit code with nothing on stdout.
    assert done.returncode in (0, 1, 2) and done.stdout.startswith("["), (
        f"render-lint at {width}px exited {done.returncode} with no findings to read: "
        f"{done.stderr.strip()[-2000:]}"
    )
    return [f for f in json.loads(done.stdout) if f["kind"] not in ("tight", "clipped")]


def band_edges(page: str) -> list[int]:
    """Both edges of every layout band the page's own `@media` rules cut the Property's range of
    layout widths into. Only a rule's prelude is read, so a width a ticket's prose or a container
    query names brings no band with it."""
    edges = {NARROWEST, WIDEST}
    for prelude in re.findall(r"@media[^{]*", page):
        for side, px in re.findall(r"\((min|max)-width:\s*(\d+)px\)", prelude):
            edges |= {int(px), int(px) - 1} if side == "min" else {int(px), int(px) + 1}
    return sorted(w for w in edges if NARROWEST <= w <= WIDEST)


# Read before any board is rendered, so that each width is a check of its own; each check holds
# the rendered board to the same widths.
WIDTHS = band_edges(PAGE.template)
# The anchors each set of pages is measured under, in both schemes: every row folded, one row
# opened, the graph over the board; and a row folded under its parent ticket's, a run of its own
# because one browser measuring all eight pages crashes a tab.
VIEWS = {"board": ("", f"#{OPENED}", f"&graph=1#{OPENED}"), "kin": (f"#{KIN}",)}


def test_a_breakpoint_added_to_the_board_brings_its_two_widths() -> None:
    added = PAGE.template.replace("<style>", "<style>\n  @media (min-width: 1700px) { main { gap: 0 } }", 1)
    assert len(WIDTHS) > 2, f"no breakpoint of the board's own falls in {NARROWEST}px..{WIDEST}px: {WIDTHS}"
    assert band_edges(added) == sorted([*WIDTHS, 1699, 1700])


def named(found: dict[int, list[dict]]) -> str:
    """What was found, by the width, the address and the element each was measured on."""
    return "\n".join(
        f"{width}px {Path(f['file']).name}: {f['kind']} on {f['el'] or '(the page)'} {f['text']!r}"
        for width, fs in sorted(found.items()) for f in fs
    )


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("width", WIDTHS)
def test_nothing_on_the_board_overlaps_or_escapes_its_box_at_any_width_in_either_scheme(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path], width: int, view: str) -> None:
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    Briefing(SAID, WRITTEN, "abc-123", WRITTEN, WRITTEN, 2).write(cache_path(out))
    render(transcribed.root, transcribed.repo, out)
    assert band_edges(out.read_text()) == WIDTHS, "the rendered board cuts bands its stylesheet does not"
    pages = [f"{out}?theme={scheme}{anchor}" for scheme in SCHEMES for anchor in VIEWS[view]]
    assert not (found := lint(pages, width)), named({width: found})


# A defect put back into the board: the brief of every folded row, in a box too narrow for the one
# unbreakable line it is set as, with nothing left to hide the rest.
DEFECT = "<style>.brief { display: block !important; width: 60px !important; overflow: visible !important }</style>"


@pytest.mark.parametrize("width", WIDTHS)
def test_a_defect_put_back_into_the_board_is_reported_at_every_band_width(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path], width: int) -> None:
    """A width where the defect goes unreported is a width the Property is not checked at, whatever
    the clean run above says. The oracle is the defect itself, named by the element it was measured
    on: any other finding, an unmeasurable page among them, leaves the width unchecked."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(transcribed.root, transcribed.repo, out)
    assert band_edges(out.read_text()) == WIDTHS, "the rendered board cuts bands its stylesheet does not"
    broken = tmp_path / "broken.html"
    broken.write_text(out.read_text().replace("</head>", f"{DEFECT}</head>", 1))
    found = lint([f"{broken}?theme=day"], width)
    assert any(f["kind"] == "escapes" and f["el"].endswith("span.brief") for f in found), (
        f"the defect went unseen at {width}px: {named({width: found})}"
    )


# Whether the graph engine arrived, read off the requests that failed rather than off the page: one
# of its two imports failing is the network's answer, save an abort, which is a navigation leaving
# the page that asked and says nothing about the network. The chunks mermaid fetches while it draws
# are not the engine.
ENGINE = r'''
def cdn(failed):
    return not any(url.endswith(("mermaid.min.js", ".esm.min.mjs")) and why != "net::ERR_ABORTED" for url, why in failed)
'''

# What the page says of itself once a browser runs it: which scheme it painted, whether the anchor
# opened a row, whether the graph beside it came back, whether the briefing is set as prose and says
# what it is, and what each mark shows on hover, a copy button's account of what it copies among
# them. The side column's own hints are `title` attributes, as the graph's buttons are: a box that
# scrolls cuts a tooltip drawn inside it, and that column is the one box on the page that scrolls. A pseudo-element has no rect of its own, so a
# tooltip's box is its host's plus the offsets the element resolves; `clipped` is the ancestor that
# would hide it, which is how two marks came to carry words no reader could see.
PROBE = ENGINE + r'''
import json, os, shutil, sys
from pathlib import Path
from playwright.sync_api import TimeoutError, sync_playwright
from page_cache import default_root, serve

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
    # the run it belongs to, as `browsers --help` defines it
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    # the clipboard is what a copy button is for, and a page reaches it only where it is granted
    context = browser.new_context(viewport={"width": width, "height": 1000},
                                  permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    serve(context, default_root())
    failed = []
    page.on("requestfailed", lambda r: failed.append((r.url, r.failure)))
    out = {"schemes": {}, "tips": {}}
    for scheme in ("day", "night"):
        page.goto(f"{page_url}?theme={scheme}#{ROW}")
        page.evaluate("document.fonts.ready")
        out["schemes"][scheme] = page.evaluate("getComputedStyle(document.body).backgroundColor")
    # the row the anchor opened asks for its graph, which is when the engine is fetched: by the end
    # of the wait it has drawn, or the panel says it could not load
    try:
        page.wait_for_selector(".side .mermaid svg, #gunloaded:not([hidden])", timeout=10_000)
    except TimeoutError:
        pass  # counted as no graph below
    out["cdn"] = cdn(failed)
    out["names"] = page.evaluate("""
      () => [...document.querySelectorAll("details.ticket")].map((row) => {
        const clip = row.querySelector(":scope > summary .title .clip"), name = clip.getBoundingClientRect()
        const links = [...row.querySelectorAll(":scope > summary .titleline > a")]
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
    out["unloaded"] = page.is_visible("#gunloaded") and page.inner_text("#gunloaded")
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
    out["unloaded_after_switch"] = page.is_visible("#gunloaded")
    out["scheme_after_switch"] = page.evaluate("document.documentElement.dataset.theme")
    browser.close()
print(json.dumps(out))
'''

# a mark of the row the anchor opens, or a selector of its own for one that sits elsewhere or
# repeats within the row. An opened row lists its questions in its block rather than under its
# name, so the marks of that list are read off a row the anchor leaves folded.
MARKS = ("tree", "slug", "asks", "title", "hinge", "time", "pri", "chip", "rp", "gh", "runcopy", "tick",
         "#t-month-close .kin",
         f"#{OPENED} .asked > li:first-child .tag", f"#{OPENED} .asked > li:first-child > .copier",
         "#grp-needs .qgroup",
         f"#{OPENED} .sessions li:first-child .when", f"#{OPENED} .sessions li:first-child .resume",
         # the list under the name, which only a folded row carries
         f"#{FOLDED} .qall", f"#{FOLDED} .q:first-child .qtag",
         f"#{FOLDED} .q:first-child .qhead", f"#{FOLDED} .q:first-child .qcopy")


def cut_off(offline: bool, tmp_path: Path) -> dict[str, str]:
    """The environment a probe runs in: this machine's copies and its network, or neither. uv keeps
    the cache it runs the probe from, which would otherwise move with the copies."""
    env = os.environ | {"PYTHONPATH": str(SHOW)}
    if not offline:
        return env
    uv_cache = subprocess.run(["uv", "cache", "dir"], capture_output=True, text=True, check=True).stdout.strip()
    return env | {"MX_PAGE_CACHE_OFFLINE": "1", "XDG_CACHE_HOME": str(tmp_path / "no-copies"), "UV_CACHE_DIR": uv_cache}


def probe(page: Path, width: int, env: dict[str, str]) -> dict:
    done = subprocess.run(
        ["uv", "run", "--with", "playwright", "python", "-", str(page), str(width), ",".join(MARKS), f"{OPENED},{FOLDED}"],
        input=PROBE, capture_output=True, text=True, env=env,
    )
    assert done.returncode == 0, f"probe: {done.stderr.strip()[-2000:]}"
    return json.loads(done.stdout)


# the row beside the graph panel, the row on its own, and the row reflowed; and the first of them
# with no graph engine to draw with
@pytest.mark.parametrize(("width", "offline"), [(1500, False), (1100, False), (920, False), (1500, True)])
def test_every_mark_shows_its_words_on_hover_inside_the_viewport(transcribed: Demo, tmp_path: Path, width: int, offline: bool, path_with: Callable[..., Path]) -> None:
    """The rendered half of the spec's "Every mark explains itself on hover", and of "a copy button
    shows what it copies": that the words the markup carries (test_board.py) reach the reader. A
    mark whose box hides its overflow hides its own tooltip, and one anchored to the wrong side
    runs off the edge of the window.

    The same run says what the rest of the page did: that the name keeps its words while the links
    beside it give way, that ?theme= pinned each scheme, that the anchor opened a row, that an
    opened row shows each of its questions once, and that the graph survives the scheme switch.
    Three of those, the scheme, the anchor and the graph, are what the layout check above assumes
    of its eight pages; the fourth, that ?graph opened the overlay on a graph rather than on the
    placeholder, belongs to the graph probe below."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(transcribed.root, transcribed.repo, out)  # no briefing: the board's own count
    seen = probe(out, width, cut_off(offline, tmp_path))
    if not offline and not seen["cdn"]:
        pytest.skip("no network and no copy of the graph engine")
    assert seen["cdn"] is not offline, "with the network cut off and no copies, the graph engine arrived all the same"
    assert seen["schemes"]["day"] != seen["schemes"]["night"], f"?theme= pinned neither scheme: {seen['schemes']}"
    assert seen["opened"] == 1, "the anchor opened no row, so the layout check measures the folded page twice"
    said = seen["briefing"]
    assert said["wraps"] and said["over"] <= 0, f"the briefing is set as a row's mark rather than as prose: {said}"
    assert said["says"], "the briefing's own mark says nothing about what it is"
    if not offline:
        assert seen["graphs"] == 1, "the graph beside the rows never painted"
        assert seen["graphs_after_switch"] == 1, "the scheme switch left the graph panel empty"
        assert not seen["unloaded"], f"the graph drew, and the panel says {seen['unloaded']!r} as well"
    else:
        assert seen["unloaded"] and "could not load" in seen["unloaded"], (
            f"with no graph engine the graph panel says {seen['unloaded']!r} rather than that the graph could not load"
        )
        assert seen["unloaded_after_switch"], "the scheme switch dropped the note that the graph could not load"
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
GRAPH_PROBE = ENGINE + r'''
import json, os, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from page_cache import default_root, serve

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
    # the run it belongs to, as `browsers --help` defines it
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    page = context.new_page()
    serve(context, default_root())
    failed = []
    page.on("requestfailed", lambda r: failed.append((r.url, r.failure)))
    errors = []
    page.on("pageerror", lambda e: errors.append("board: " + str(e)))

    # ?graph on the address, beside the row's anchor: the state the layout check measures. The
    # overlay paints once the drawing is done, or once the engine has failed to arrive, and every
    # step past this one that needs a drawing runs only where it arrived.
    page.goto(f"{page_url}?theme=night&graph=1#{ROW}")
    page.evaluate("document.fonts.ready")
    page.wait_for_selector("#gfull .gsvg svg, #gfull .gnote:not([hidden])")
    out = {"cdn": cdn(failed),
           "ground": page.evaluate("getComputedStyle(document.body).backgroundColor"),
           "font": page.evaluate("getComputedStyle(document.getElementById('gname')).fontFamily"),
           "node": NODE}
    drawn = out["cdn"]
    PAINTED = ".gsvg svg" if drawn else ".gnote:not([hidden])"
    out["from_the_address"] = {"open": page.is_visible("#gfull"), "nodes": nodes(page, "#gfull .gsvg"),
                               "name": page.inner_text("#gfull .gname"), "note": page.inner_text("#gfull .gnote")}
    if drawn:
        out["preview_width"] = page.evaluate(WIDE, ".side .g:not([hidden]) .mermaid svg")

    # the whole tracker at full size, dragged to pan, then a node
    page.click("#gfull [data-gmode=all]")
    named(page, "#gfull .gname", "whole tracker")
    over = {"name": page.inner_text("#gfull .gname"), "note": page.inner_text("#gfull .gnote")}
    if drawn:
        page.wait_for_selector("#gfull .gsvg g.node.cur")
        over |= {"width": page.evaluate(WIDE, "#gfull .gsvg svg"),
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
    else:
        page.click("#gclose")
        over["open_after_close"] = page.is_visible("#gfull")
    out["overlay"] = over

    # the two keys, and Escape taking the overlay before the open row
    page.keyboard.press("f")
    page.wait_for_selector("#gfull " + PAINTED)
    keys = {"f_opened": page.is_visible("#gfull")}
    page.keyboard.press("Escape")
    keys["esc_closed"] = not page.is_visible("#gfull")
    keys["row_still_open"] = page.evaluate(f"!!document.getElementById('{ROW}')?.open")
    out["keys"] = keys

    # the preview: a click opens the full size view, a click on a node in it goes to that row
    page.click(".side .g:not([hidden]) .mermaid" if drawn else "#gunloaded", position={"x": 3, "y": 3})
    page.wait_for_selector("#gfull " + PAINTED)
    preview = {"click_opened": page.is_visible("#gfull")}
    page.keyboard.press("Escape")
    if drawn:
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
    win.wait_for_selector(".gfbody g.node.cur" if drawn else ".gfbody " + PAINTED)
    window = {"title": win.title(), "scheme": win.evaluate("document.documentElement.dataset.theme"),
              "ground": win.evaluate("getComputedStyle(document.body).backgroundColor"),
              "font": win.evaluate("getComputedStyle(document.querySelector('.gname')).fontFamily"),
              "name": win.inner_text(".gname"), "note": win.inner_text(".gfbody .gnote")}
    if drawn:
        window |= {"width": win.evaluate(WIDE, ".gfbody svg"),
                   "nodes": nodes(win, ".gfbody"), "overflow": win.evaluate(OVER, ".gfbody"),
                   "titles": win.eval_on_selector_all(".gfbody g.node title", "els => els.length"),
                   "marked": win.eval_on_selector_all(".gfbody g.node.cur", "els => els.length")}
    win.click("[data-gmode=tree]")  # the board is on the whole tracker, so this is a change in both
    named(win, ".gname", "csv-import")
    window["switched"] = win.inner_text(".gname")
    window["board_name"] = page.inner_text("#gname")
    if drawn:
        click_node(win, ".gfbody", NODE)
        page.wait_for_function(f"document.querySelector('.ticket.kcur')?.id === '{NODE[1:]}'")
        window["cursor"] = page.evaluate("document.querySelector('.ticket.kcur')?.id")
        window["still_open"] = not win.is_closed()
        # The window follows the board's cursor without redrawing: the cursor moves to another row of
        # the tree on show, so the graph is one the new row has a node in. A row of any other tree is
        # a different graph, and a standalone ticket's tree has none at all, which leaves the window
        # showing its note and no mark for this to wait on.
        drawing = win.evaluate("document.querySelector('.gfbody .gsvg svg').id")
        steps, slug = page.evaluate("""
          () => {
            const shown = [...document.querySelectorAll(".ticket")].filter((r) => r.checkVisibility())
            const at = shown.findIndex((r) => r.classList.contains("kcur"))
            const next = shown.findIndex((r, i) => i > at && r.dataset.tree === shown[at].dataset.tree)
            return [next - at, shown[next]?.dataset.slug]
          }
        """)
        assert slug, "no row of the cursor's own tree below it, so j leaves the graph on show"
        for _ in range(steps):
            page.keyboard.press("j")
        page.wait_for_function("(id) => document.querySelector('.ticket.kcur')?.id === id", arg=f"t-{slug}")
        node = "T_f_" + slug.replace("-", "_")
        win.wait_for_selector(f'.gfbody g.node.cur[id*="-{node}-"]')
        window["follows_cursor"] = win.eval_on_selector_all(".gfbody g.node.cur", "els => els.length")
        window["same_drawing"] = win.evaluate("document.querySelector('.gfbody .gsvg svg').id") == drawing
    window["html"] = win.evaluate("document.documentElement.outerHTML")
    out["window"] = window

    # the re-render every tracker change triggers, under a window that has to find the board again
    page.reload()
    page.evaluate("document.fonts.ready")
    page.keyboard.press("Escape")
    page.wait_for_selector(f"#{ROW} > summary")
    page.click(f"#{ROW} > summary")
    if drawn:
        win.wait_for_selector(".gfbody g.node.cur")
        click_node(win, ".gfbody", NEXT)
        page.wait_for_function(f"document.querySelector('.ticket.kcur')?.id === '{NEXT[1:]}'")
    else:
        win.click("[data-gmode=all]")
        named(page, "#gname", "whole tracker")
    out["after_reload"] = {"orphan": win.evaluate("document.documentElement.dataset.orphan"),
                           "cursor": page.evaluate("document.querySelector('.ticket.kcur')?.id"),
                           "board_name": page.inner_text("#gname")}

    # the board gone: a window that says so rather than one that looks live
    page.close()
    win.wait_for_function("document.documentElement.dataset.orphan === '1'", timeout=10_000)
    out["orphan_says"] = win.inner_text(".gorphan")
    out["errors"] = errors
    browser.close()
print(json.dumps(out))
'''


def graph_probe(page: Path, env: dict[str, str]) -> dict:
    done = subprocess.run(
        ["uv", "run", "--with", "playwright", "python", "-", str(page)],
        input=GRAPH_PROBE, capture_output=True, text=True, env=env,
    )
    assert done.returncode == 0, f"graph probe: {done.stderr.strip()[-3000:]}"
    return json.loads(done.stdout)


@pytest.mark.parametrize("offline", [False, True])
def test_the_preview_opens_the_graph_at_full_size_over_the_board_and_in_a_window(transcribed: Demo, tmp_path: Path, offline: bool, path_with: Callable[..., Path]) -> None:
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
    seen = graph_probe(out, cut_off(offline, tmp_path))
    assert seen["errors"] == [], seen["errors"]
    if not offline and not seen["cdn"]:
        pytest.skip("no network and no copy of the graph engine")
    assert seen["cdn"] is not offline, "with the network cut off and no copies, the graph engine arrived all the same"
    drawn = not offline
    row = seen["node"].removeprefix("#")
    # where the engine never arrived, every view that would draw says so instead
    unloaded = "could not load"

    # what the layout matrix above assumes of its two ?graph pages
    came = seen["from_the_address"]
    assert came["open"] and came["name"] == "csv-import", f"?graph did not open the overlay on the row's own graph: {came}"
    assert came["nodes"] >= 5 if drawn else unloaded in came["note"], f"?graph opened the overlay on {came}"

    over = seen["overlay"]
    assert over["name"] == "whole tracker", f"the overlay's switch left it on {over['name']!r}"
    if drawn:
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
    else:
        assert unloaded in over["note"], f"the whole tracker's overlay says {over['note']!r}"
        assert not over["open_after_close"], "the close button left the overlay over the board"

    keys = seen["keys"]
    assert keys["f_opened"] and keys["esc_closed"], f"f and Escape: {keys}"
    assert keys["row_still_open"], "Escape folded the row behind the overlay instead of closing the overlay"

    preview = seen["preview"]
    assert preview["click_opened"], "a click on the preview did not open the full size view"
    if drawn:
        assert not preview["node_opened"], "a node clicked in the preview opened the overlay instead of going to its row"
        assert preview["node_cursor"] == "t-parse-rows", f"the preview's node left the board on {preview['node_cursor']!r}"

    win = seen["window"]
    assert win["title"].endswith("dependencies"), win["title"]
    assert win["scheme"] == "night" and win["ground"] == seen["ground"], (
        f"the window is not in the board's scheme: {win['scheme']}, {win['ground']}"
    )
    assert win["font"] == seen["font"], f"the window letters its head in {win['font']}, the board in {seen['font']}"
    assert win["switched"] == "csv-import" and win["board_name"] == "csv-import", (
        f"the switch in the window left it on {win['switched']!r} and the board on {win['board_name']!r}"
    )
    if drawn:
        assert win["width"] > 2 * seen["preview_width"], f"the window draws the graph {win['width']}px wide"
        assert win["titles"] == win["nodes"], "a node in the window does not carry its full title"
        assert win["marked"] == 1 and win["follows_cursor"] == 1, (
            "the window does not mark the row the board's cursor is on, or stopped following it"
        )
        assert win["same_drawing"], "the window redrew the graph to follow a cursor move inside it"
        assert win["overflow"] > 0, "the window's graph fits its box, so nothing there is scrolled or panned"
        assert win["cursor"] == row, f"the click in the window left the board on {win['cursor']!r}"
        assert win["still_open"], "the click closed the window instead of moving the board behind it"
    else:
        assert unloaded in win["note"], f"the window says {win['note']!r}"

    # the board reloads on every tracker change, which is where a window holding the board itself
    # would go quiet: it finds the board again and goes on driving it
    after = seen["after_reload"]
    assert after["orphan"] == "", f"the window lost the board across its re-render: {after}"
    if drawn:
        assert after["cursor"] == "t-parse-rows", f"a node clicked in the window after the re-render left the board on {after['cursor']!r}"
    else:
        assert after["board_name"] == "whole tracker", f"the switch in the window after the re-render left the board on {after['board_name']!r}"
    assert "gone" in seen["orphan_says"], f"a window whose board closed says {seen['orphan_says']!r}"

    # the window is a rendered page of the board's, so the no-overlap Property is its business too
    doc = tmp_path / "graph-window.html"
    doc.write_text(re.sub(r"<script>.*?</script>", "", win["html"], flags=re.S))
    assert {width: f for width in (450, 900, 1600) if (f := lint([str(doc)], width))} == {}



# A draw that fails after the engine loaded: the engine and what it imports come from a directory of
# their own, with the network cut off, so the pieces mermaid fetches while it draws do not arrive.
# The copies of those pieces are then put in, and the board draws with them from its next load on:
# the browser keeps a failed import as failed for as long as the page lives, so nothing short of a
# load fetches it again, and the board loads again on every change to the tracker.
UNDRAWN_PROBE = r"""
import json, os, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from page_cache import copy_of, default_root, serve

page_url, ENGINE = Path(sys.argv[1]).resolve().as_uri(), sys.argv[2].split(",")
own, kept = Path(sys.argv[3]), default_root()
UNDRAWN = "#gundrawn:not([hidden])"
# mermaid is a classic script, its layout a module
LOAD = '''(urls) => Promise.all(urls.map((u) => u.endsWith(".mjs") ? import(u) : new Promise((ok, no) =>
  document.head.append(Object.assign(document.createElement("script"), {src: u, onload: ok, onerror: no})))))
  .then(() => true, () => false)'''

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    # what importing the engine asks for, and nothing its drawing does
    loader = browser.new_context()
    page = loader.new_page()
    serve(loader, kept)
    asked = []
    page.on("request", lambda r: asked.append(r.url))
    if not page.evaluate(LOAD, ENGINE):
        print(json.dumps({"cdn": False}))
        sys.exit()
    own.mkdir()
    for url in asked:
        shutil.copy(copy_of(kept, url), own)
    loader.close()

    os.environ["MX_PAGE_CACHE_OFFLINE"] = "1"
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    page = context.new_page()
    serve(context, own)
    page.goto(f"{page_url}?theme=night#t-map-columns")
    page.wait_for_selector(UNDRAWN)
    out = {"cdn": True, "preview": {"note": page.inner_text("#gundrawn"), "unloaded": page.is_visible("#gunloaded"),
                       "graphs": page.evaluate("document.querySelectorAll('.side .mermaid svg').length")}}
    page.keyboard.press("f")
    page.wait_for_selector("#gfull .gnote:not([hidden])")
    out["overlay"] = page.inner_text("#gfull .gnote")
    page.keyboard.press("Escape")
    with page.expect_popup() as popped:
        page.keyboard.press("w")
    win = popped.value
    win.wait_for_selector(".gfbody .gnote:not([hidden])")
    out["window"] = win.inner_text(".gfbody .gnote")
    win.close()
    # a failed draw, in the preview or at full size, leaves no error drawing of mermaid's own behind
    out["stray"] = page.evaluate("document.querySelectorAll('body > [id^=dm], body > [id^=dgf]').length")

    shutil.copytree(kept, own, dirs_exist_ok=True)
    page.reload()
    page.wait_for_selector(".side .g:not([hidden]) .mermaid svg", timeout=20_000)
    out["next"] = {"graphs": page.evaluate("document.querySelectorAll('.side .g:not([hidden]) .mermaid svg').length"),
                   "note": page.is_visible("#gundrawn")}
    browser.close()
print(json.dumps(out))
"""


def test_a_graph_that_fails_to_draw_after_the_engine_loaded_says_so_in_every_view(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path]) -> None:
    """The ticket's acceptance criterion: the preview and both full size views say the graph could
    not be drawn, and the graph draws on the board's next load once its pieces arrive. The engine
    and its drawing pieces come from this machine's copies, or from the network where it holds none."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(transcribed.root, transcribed.repo, out)
    engine = sorted(set(re.findall(r'"(https://cdn\.jsdelivr\.net/[^"]+(?:\.esm\.min\.mjs|/mermaid\.min\.js))"', out.read_text())))
    assert len(engine) == 2, f"the page names {engine} as its engine"
    done = subprocess.run(
        ["uv", "run", "--with", "playwright", "python", "-", str(out), ",".join(engine), str(tmp_path / "engine-only")],
        input=UNDRAWN_PROBE, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(SHOW)},
    )
    assert done.returncode == 0, f"probe: {done.stderr.strip()[-3000:]}"
    seen = json.loads(done.stdout)
    if not seen["cdn"]:
        pytest.skip("no network and no copy of the graph engine")
    undrawn = "could not be drawn"
    preview = seen["preview"]
    assert undrawn in preview["note"] and not preview["unloaded"] and preview["graphs"] == 0, (
        f"a draw that failed after the engine loaded leaves the preview as {preview}"
    )
    assert seen["stray"] == 0, "mermaid left its error drawing on the page"
    assert undrawn in seen["overlay"], f"the overlay says {seen['overlay']!r}"
    assert undrawn in seen["window"], f"the window of its own says {seen['window']!r}"
    assert seen["next"] == {"graphs": 1, "note": False}, f"the board's next load, once the pieces arrive: {seen['next']}"



# A file of the engine changed at the CDN: the board draws once from this machine's copies, so they
# hold every file it fetches, then loads again from a copy of them in which one file carries a
# byte more than the one its hash was taken of.
TAMPERED_PROBE = r"""
import json, os, re, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from page_cache import copy_of, default_root, serve

page = Path(sys.argv[1])
page_url, changed, own, kept = page.resolve().as_uri(), sys.argv[2], Path(sys.argv[3]), default_root()
pinned = sorted(set(re.findall(r'"(https://cdn\.jsdelivr\.net/[^"]+\.m?js)"', page.read_text())))

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    loader = browser.new_context()
    tab = loader.new_page()
    serve(loader, kept)
    tab.goto(f"{page_url}#t-map-columns")
    tab.wait_for_selector(".side .mermaid svg, .gnote[id^=gun]:not([hidden])")
    if not tab.is_visible(".side .mermaid svg"):
        print(json.dumps({"cdn": False}))
        sys.exit()
    loader.close()
    own.mkdir()
    for url in pinned:
        shutil.copy(copy_of(kept, url), own)
    [target] = [url for url in pinned if url.endswith(changed)]
    with copy_of(own, target).open("ab") as f:
        f.write(b"\n;")

    os.environ["MX_PAGE_CACHE_OFFLINE"] = "1"
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    tab = context.new_page()
    serve(context, own)
    errors = []
    tab.on("pageerror", lambda e: errors.append(str(e)))
    tab.goto(f"{page_url}?theme=day#t-map-columns")
    tab.wait_for_selector("#gunloaded:not([hidden]), #gundrawn:not([hidden]), .side .mermaid svg")
    out = {"cdn": True, "pinned": pinned, "graphs": tab.eval_on_selector_all(".mermaid svg", "els => els.length"),
           "notes": [tab.inner_text(n) for n in ("#gunloaded", "#gundrawn") if tab.is_visible(n)]}
    # the rest of the board: the open row folds, and the scheme switches
    tab.click("#t-map-columns > summary")
    tab.keyboard.press("t")
    out["rest"] = {"folded": not tab.evaluate("document.getElementById('t-map-columns').open"),
                   "scheme": tab.evaluate("document.documentElement.dataset.theme"), "errors": errors}
    browser.close()
print(json.dumps(out))
"""


@pytest.mark.parametrize(("changed", "note"), [("/mermaid.min.js", "could not load"), ("/chunk-SP2CHFBE.mjs", "could not load"),
                                               ("/render-FL5BWEWF.mjs", "could not be drawn")])
def test_an_engine_file_changed_from_its_pin_is_refused_and_the_board_says_the_engine_did_not_load(transcribed: Demo, tmp_path: Path, changed: str, note: str) -> None:
    """The ticket's acceptance criterion: a file whose bytes differ from its pinned hash is refused,
    the graph does not draw, the board says so the way it says the engine did not load, and the rest
    of the board works. mermaid is pinned by its script's own hash, the layout's chunks only through
    the import map; the layout fetches its render chunk only once it draws, so that one is refused
    as a piece the draw did not get."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(transcribed.root, transcribed.repo, out)
    done = subprocess.run(
        ["uv", "run", "--with", "playwright", "python", "-", str(out), changed, str(tmp_path / "changed")],
        input=TAMPERED_PROBE, capture_output=True, text=True, env=os.environ | {"PYTHONPATH": str(SHOW)},
    )
    assert done.returncode == 0, f"probe: {done.stderr.strip()[-3000:]}"
    seen = json.loads(done.stdout)
    if not seen["cdn"]:
        pytest.skip("no network and no copy of the graph engine")
    assert all(re.search(r"@\d+\.\d+\.\d+/", url) for url in seen["pinned"]), f"a script not at an exact version: {seen['pinned']}"
    [said] = seen["notes"] or [""]
    assert len(seen["notes"]) == 1 and note in said and "pinned" in said, f"the panel says {seen['notes']}"
    assert seen["graphs"] == 0, f"a changed engine drew {seen['graphs']} graphs"
    assert seen["rest"] == {"folded": True, "scheme": "night", "errors": []}, f"the rest of the board: {seen['rest']}"

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
