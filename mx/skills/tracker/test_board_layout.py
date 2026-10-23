# /// script
# requires-python = ">=3.14"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown", "markdown-it-py[linkify]"]
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

What render-lint measures is text against its own box, text a box cuts off, and text drawn over
other text, HTML over HTML included. Text its own `.clip` cuts off is not a finding here: that is
every mark, name and brief that truncates by design. What render-lint does not reach is an overlap
the browser paints an opaque box over, which is what a card drawn over the page is. The Property
is executable as far as that reaches; the rest was read by eye at these widths, in both schemes
(02-rows' closing comment).

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
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from board import PAGE, Failing, render, restamp
from briefing import Briefing, cache_path
from demo_tracker import Demo
from page_cache import default_root

HERE = Path(__file__).resolve().parent  # the probes, each a script a browser check runs
SHOW = HERE.parent / "show"
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
    return [f for f in json.loads(done.stdout) if not (f["kind"] == "tight" or truncates(f))]


def truncates(finding: dict) -> bool:
    """Whether a finding is text cut off only where the board means to cut it: by its own `.clip`
    (board.clipped_html), and by no box around one."""
    return finding["kind"] == "clipped" and all(c.split()[-1] == "span.clip" for c in finding["cutters"])


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


@pytest.mark.full_path
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


# Defects put back into the board, each by the kind it is reported as and the tail of the address
# of the element it is measured on: the brief of every folded row, in a box too narrow for the one
# unbreakable line it is set as, with nothing left to hide the rest; every row's time, cut off by a
# box that has no truncation of its own; and every row's name, whose `.clip` a box around it cuts.
DEFECTS = {
    ("escapes", "span.brief span.clip"): ".brief { display: block !important; width: 60px !important } .brief .clip { overflow: visible !important }",
    ("clipped", "span.time"): ".time { display: block !important; width: 4px !important; overflow: hidden !important }",
    ("clipped", "span.title span.clip"): ".titleline { height: .5rem !important; overflow: hidden !important }",
}


@pytest.mark.full_path
@pytest.mark.parametrize("width", WIDTHS)
def test_defects_put_back_into_the_board_are_reported_at_every_band_width(transcribed: Demo, tmp_path: Path, path_with: Callable[..., Path], width: int) -> None:
    """A width where a defect goes unreported is a width the Property is not checked at, whatever
    the clean run above says. The oracle is each defect itself, named by the element it was measured
    on: any other finding, an unmeasurable page among them, leaves the width unchecked."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(transcribed.root, transcribed.repo, out)
    assert band_edges(out.read_text()) == WIDTHS, "the rendered board cuts bands its stylesheet does not"
    broken = tmp_path / "broken.html"
    broken.write_text(out.read_text().replace("</head>", f"<style>{' '.join(DEFECTS.values())}</style></head>", 1))
    found = lint([f"{broken}?theme=day"], width)
    unseen = [(kind, el) for kind, el in DEFECTS if not any(f["kind"] == kind and f["el"].endswith(el) for f in found)]
    assert not unseen, f"{unseen} went unseen at {width}px: {named({width: found})}"


# a mark of the row the anchor opens, or a selector of its own for one that sits elsewhere or
# repeats within the row. An opened row lists its questions in its block rather than under its
# name, so the marks of that list are read off a row the anchor leaves folded.
MARKS = ("tree", "slug", "asks", "title", "time", "pri", "chip", "rp", "gh", "runcopy", "tick",
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
    env = dict(os.environ)
    if not offline:
        return env
    uv_cache = subprocess.run(["uv", "cache", "dir"], capture_output=True, text=True, check=True).stdout.strip()
    return env | {"MX_PAGE_CACHE_OFFLINE": "1", "XDG_CACHE_HOME": str(tmp_path / "no-copies"), "UV_CACHE_DIR": uv_cache}


def probe(page: Path, width: int, env: dict[str, str]) -> dict:
    done = subprocess.run(
        ["uv", "run", str(HERE / "board_probe_marks.py"), str(page), str(width), ",".join(MARKS), f"{OPENED},{FOLDED}"],
        capture_output=True, text=True, env=env,
    )
    assert done.returncode == 0, f"probe: {done.stderr.strip()[-2000:]}"
    return json.loads(done.stdout)


# the row beside the graph panel, the row on its own, and the row reflowed; and the first of them
# with no graph engine to draw with
@pytest.mark.full_path
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
    # the graph's name says which graph is on show, so the side column never cuts it short
    assert seen["gname"] == {"text": "csv-import", "cut": False}, f"the graph's name reads {seen['gname']}"
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
    # what the needs-me group's button counts and copies is the questions of the rows on show
    group = seen["group"]
    asked = lambda said: int(re.search(r"\d+", said["word"]).group())
    assert group["after"]["hidden"], "the saved-views pill hid no needs-me row"
    assert group["clipboard"] == group["after"]["copy"], "the click put something else on the clipboard"
    assert group["clipboard"].count("\n- [") == asked(group["after"]) < asked(group["before"]), (
        f"with saved-views hidden the button reads {group['after']['word']!r} over {group['clipboard']!r}"
    )
    assert not [path for path in group["after"]["hidden"] if path in group["clipboard"]], (
        f"the button copies the questions of a row the pill hid: {group['clipboard']!r}"
    )
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


def graph_probe(page: Path, env: dict[str, str]) -> dict:
    done = subprocess.run(
        ["uv", "run", str(HERE / "board_probe_graph.py"), str(page)],
        capture_output=True, text=True, env=env,
    )
    assert done.returncode == 0, f"graph probe: {done.stderr.strip()[-3000:]}"
    return json.loads(done.stdout)


@pytest.mark.full_path
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

    buttons = seen["buttons"]
    assert buttons["full_opened"], "the preview's full button did not open the overlay"
    assert buttons["overlay_closed"], "the overlay's window button left the overlay over the board"
    assert buttons["from_overlay"].endswith("dependencies") and buttons["from_preview"].endswith("dependencies"), (
        f"a window button opened something other than the graph's window: {buttons}"
    )

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


@pytest.mark.full_path
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
        ["uv", "run", str(HERE / "board_probe_undrawn.py"), str(out), ",".join(engine), str(tmp_path / "engine-only")],
        capture_output=True, text=True,
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


# The layout's chunks, as the page's import map pins them: the render chunk is fetched once the
# graph draws, every other one as the layout loads.
CHUNKS = [url.rsplit("/", 1)[1] for url in json.loads(
    re.search(r'<script type="importmap">(.*?)</script>', PAGE.template, re.S).group(1))["integrity"] if "/chunks/" in url]
assert any(chunk.startswith("render-") for chunk in CHUNKS), f"the import map pins no render chunk among {CHUNKS}"


@pytest.mark.full_path
@pytest.mark.parametrize(("changed", "note"), [("/mermaid.min.js", "could not load"), *(
    (f"/{chunk}", "could not be drawn" if chunk.startswith("render-") else "could not load") for chunk in CHUNKS)])
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
        ["uv", "run", str(HERE / "board_probe_tampered.py"), str(out), changed, str(tmp_path / "changed")],
        capture_output=True, text=True,
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


@pytest.mark.full_path
def test_an_open_tab_says_the_board_is_stale_while_the_watchers_passes_fail(transcribed: Demo, tmp_path: Path) -> None:
    """`board-watcher-restarts-on-new-code#P3`: the note shows in a tab already open, without
    reloading it, and goes when the stamp file drops the mark."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to render the page with")
    out = tmp_path / "board.html"
    render(transcribed.root, transcribed.repo, out)
    drawn = Path(f"{out}.stamp.js").read_text()
    since = datetime(2026, 10, 7, 9, 30).astimezone()
    restamp(out, Failing(since, "second.md:2: `flavour` is no ticket field\nsecond.md:3: and a second line"))
    stale = Path(f"{out}.stamp.js").read_text()
    Path(f"{out}.stamp.js").write_text(drawn)
    done = subprocess.run(
        ["uv", "run", str(HERE / "board_probe_stale.py"), str(out), stale],
        capture_output=True, text=True, timeout=180,
    )
    assert done.returncode == 0, f"probe: {done.stderr.strip()[-3000:]}"
    seen = json.loads(done.stdout)
    assert not seen["before"]
    assert "stale since 07 Oct 09:30" in seen["stale"] and "`flavour` is no ticket field" in seen["stale"], seen["stale"]
    assert "second line" not in seen["stale"], seen["stale"]
    assert not seen["after"]
    assert not seen["reloaded"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
