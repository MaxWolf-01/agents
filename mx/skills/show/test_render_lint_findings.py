"""Checks for what render-lint does with what a page measures: the widths it walks, when it reads
a page, and how its findings become output and an exit code.

Two seams, neither with a browser behind it. measure() takes the tab it reads, so a stand-in tab
plays the page: it says how tall it is, whether it is still moving, and what the in-page
measurement finds at each width. main() takes the function that measures the pages, so a stand-in
hands it findings. The oracle is render-lint's --help: the widths --narrow adds and the order it
walks them in, a finding made once, a page read at rest in a window as tall as it at the top, an
unmeasurable page, a crop per finding, and the exit codes. What the in-page measurement finds on a
real page is test_render_lint.py's, in Chromium.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import render_lint
from lint_pages import LINT
from render_lint import Args, main, measure


class Slow(Exception):
    """What the tab raises when the page outlasts the patience it was given to load."""


class Tab:
    """A tab holding a page `tall` pixels high, opened scrolled `scrolled` down, whose in-page
    measurement finds `found[width]` at each window width. At the widths in `moving` it never comes
    to rest, and at every width it moves for `settling` seconds after the window changes; a `slow`
    page never loads; a `pending` one starts a request that never finishes. Its clock moves only
    while render-lint waits on it."""

    def __init__(self, found: dict[int, list[dict]] | None = None, tall: int = 900, scrolled: int = 0,
                 moving: tuple[int, ...] = (), settling: float = 0, slow: bool = False, pending: bool = False) -> None:
        self.found, self.tall, self.scrolled, self.moving = found or {}, tall, scrolled, moving
        self.slow, self.pending, self.settling = slow, pending, settling
        self.resized = 0.0
        self.viewport_size: dict = {}
        self.now, self.ticks = 0.0, 0
        self.handlers: dict = {}
        self.url = ""
        self.read: list[tuple[int, int, int]] = []  # (width, height, scrolled) at each measurement
        self.crops: list[dict] = []

    def clock(self) -> float:
        return self.now

    def on(self, event: str, handler) -> None:
        self.handlers[event] = handler

    def goto(self, url: str, timeout: float) -> None:
        self.url = url
        if self.pending:
            self.handlers["request"](object())
        if self.slow:
            raise Slow

    def set_viewport_size(self, size: dict) -> None:
        self.viewport_size, self.resized = size, self.now

    def wait_for_timeout(self, ms: float) -> None:
        self.now += ms / 1000

    def screenshot(self, path: str, full_page: bool, clip: dict) -> None:
        self.crops.append({"path": path, "clip": clip})

    def evaluate(self, script: str, arg=None):
        width, height = self.viewport_size["width"], self.viewport_size["height"]
        if script == render_lint.STILL:
            self.ticks += 1
            moves = width in self.moving or self.now - self.resized < self.settling
            return f"{width}x{height}:{self.scrolled}:{self.ticks if moves else 0}"
        if script == "document.documentElement.scrollHeight":
            return self.tall
        if script == "scrollX || scrollY":
            return self.scrolled
        if script.startswith("scrollTo"):
            self.scrolled = 0
            return None
        assert script == render_lint.MEASURE
        self.read.append((width, height, self.scrolled))
        return [dict(f) for f in self.found.get(width, [])]


def finding(kind: str, el: str, text: str = "Row label") -> dict:
    """A finding as the in-page measurement reports it."""
    return {"kind": kind, "where": "html", "el": el, "text": text, "by": 3, "box": {"x": 40, "y": 600, "w": 120, "h": 18}}


def lint(tab: Tab, spec: str = "page.html", **flags) -> list[dict]:
    """measure() on the tab, opened as wide as --width says, the way chromium() opens it."""
    args = Args(files=[Path(spec)], **flags)
    tab.viewport_size = {"width": args.width, "height": 900}
    return measure(tab, Path(spec), args, Slow, tab.clock)


def widths_read(tab: Tab) -> list[int]:
    return [width for width, _, _ in tab.read]


A, B, C = finding("escapes", "div#a"), finding("overlap", "div#b"), finding("escapes", "div#c")


def test_narrow_reads_the_page_at_zoom_and_at_700px_and_reports_each_finding_at_the_first_width_it_shows():
    """1400px at 150% zoom lays out 933px."""
    tab = Tab({1400: [A], 933: [A, B], 700: [A, B, C]})
    assert [(f["el"], f["width"]) for f in lint(tab, narrow=True)] == [("div#a", 1400), ("div#b", 933), ("div#c", 700)]
    assert widths_read(tab) == [1400, 933, 700]


def test_without_narrow_only_the_given_width_is_read():
    tab = Tab({1400: [A], 933: [A, B]})
    assert [(f["el"], f["width"]) for f in lint(tab)] == [("div#a", 1400)]
    assert widths_read(tab) == [1400]


def test_a_narrower_width_that_is_not_narrower_than_the_given_one_is_skipped():
    tab = Tab()
    lint(tab, width=600, narrow=True)
    assert widths_read(tab) == [600, 400]


def test_a_query_and_a_fragment_go_on_the_address(tmp_path):
    tab = Tab()
    lint(tab, f"{tmp_path}/page.html?theme=night#row-3")
    assert tab.url == (tmp_path / "page.html").as_uri() + "?theme=night#row-3"


def test_a_page_is_read_at_rest_in_a_window_as_tall_as_it_at_the_top():
    """The fragment scrolled it 600px down; at the next width the window is still the page's height."""
    tab = Tab(tall=2400, scrolled=600)
    lint(tab, narrow=True)
    assert tab.read == [(1400, 2400, 0), (933, 2400, 0), (700, 2400, 0)]


def test_a_page_that_never_loads_is_unmeasurable():
    found = lint(Tab(slow=True), patience=2)
    assert [(f["kind"], f["width"], f["text"]) for f in found] == [("unmeasurable", 1400, "still loading after 2s")]


def test_a_page_with_a_request_that_never_finishes_is_unmeasurable_and_never_read():
    tab = Tab(pending=True)
    found = lint(tab, patience=2)
    assert [(f["kind"], f["text"]) for f in found] == [("unmeasurable", "still loading after 2s")]
    assert tab.read == []


def test_a_page_that_never_comes_to_rest_at_a_narrower_width_keeps_what_the_wider_ones_found():
    tab = Tab({1400: [A], 933: [A, B]}, moving=(933,))
    found = lint(tab, narrow=True, patience=5)
    assert [(f["kind"], f["width"]) for f in found] == [("escapes", 1400), ("unmeasurable", 933)]
    assert found[1]["text"] == "still moving after 5s"
    assert widths_read(tab) == [1400]
    assert tab.now > 5, "it gave up before its patience ran out"


def test_each_width_gets_the_whole_patience_to_come_to_rest():
    """The page takes 4s of the 5s patience to settle at every width."""
    tab = Tab({1400: [A], 933: [B], 700: [C]}, settling=4)
    assert [(f["el"], f["width"]) for f in lint(tab, narrow=True, patience=5)] == [("div#a", 1400), ("div#b", 933), ("div#c", 700)]


def test_each_finding_gets_a_crop_of_its_box_with_a_margin_around_it(tmp_path):
    tab = Tab({1400: [A, B]})
    found = lint(tab, crops=tmp_path)
    assert [f["crop"] for f in found] == [c["path"] for c in tab.crops]
    assert len({f["crop"] for f in found}) == 2 and all(Path(f["crop"]).parent == tmp_path for f in found)
    for crop in tab.crops:
        clip, box = crop["clip"], A["box"]
        assert clip["x"] < box["x"] and clip["y"] < box["y"]
        assert clip["x"] + clip["width"] > box["x"] + box["w"] and clip["y"] + clip["height"] > box["y"] + box["h"]


def found_in(*kinds: str) -> list[dict]:
    """The findings of one page, with what chromium() adds to each."""
    return [{"file": "page.html", "width": 1400, "crop": None} | finding(kind, f"span#{n}") for n, kind in enumerate(kinds)]


@pytest.mark.parametrize("kinds, code", [
    ((), 0),
    (("tight", "clipped"), 0),
    (("escapes",), 1),
    (("clipped", "overlap"), 1),
    (("overlap", "unmeasurable"), 2),
], ids=["nothing found", "only soft findings", "an escape", "an overlap", "a page that could not be measured outranks a finding"])
def test_the_exit_code_says_the_worst_of_what_was_found(kinds, code):
    assert main(Args(files=[Path("page.html")]), lambda args: found_in(*kinds)) == code


def test_every_finding_is_printed_with_where_it_was_found_and_the_tally_names_the_fatal_ones(capsys):
    findings = found_in("tight", "escapes")
    assert main(Args(files=[Path("page.html")]), lambda args: findings) == 1
    out, err = capsys.readouterr()
    lines = out.splitlines()
    assert len(lines) == 2
    for line, f in zip(lines, findings):
        assert all(part in line for part in ("page.html", "1400px", f["kind"], f["el"], f["text"]))
    assert "2 findings, 1 fatal" in err


def test_json_emits_the_findings_as_an_array_and_still_exits_by_them(capsys):
    findings = found_in("overlap", "clipped")
    assert main(Args(files=[Path("page.html")], json=True), lambda args: findings) == 1
    assert json.loads(capsys.readouterr().out) == findings


def run(*args: str) -> subprocess.CompletedProcess:
    """render-lint run as a caller runs it, by a Python that has its dependencies."""
    return subprocess.run([sys.executable, str(LINT), *args], capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("args, code", [((), 3), (("page.html", "--width", "wide"), 3), (("--help",), 0)],
                         ids=["no page", "a width that is no number", "help"])
def test_a_usage_error_is_the_run_failing_and_help_is_not(args, code):
    assert run(*args).returncode == code


def test_a_run_that_fails_exits_3_saying_why(tmp_path):
    """The crops directory cannot be made under a file."""
    (tmp_path / "file").write_text("")
    done = run(str(tmp_path / "page.html"), "--crops", str(tmp_path / "file" / "crops"))
    assert done.returncode == 3
    assert "NotADirectoryError" in done.stderr
