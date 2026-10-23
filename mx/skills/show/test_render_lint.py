# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for render-lint's reading of HTML text. Run: uv run test_render_lint.py

The seam is the command line: a page on disk in, findings and an exit code out, which is how
every caller uses it and the only place the browser's own measurements can be read. Each page
here exhibits one condition, and the oracle is what a reader sees on it: a line wider than the box
holding it escapes it and the same line in a box wide enough does not; two labels printed
over each other collide and the same two apart do not; a link in a paragraph and a span in a
button sit inside their parents' text rather than across it; a box with overflow hidden cuts
its title off, which is a finding that never fails a run; and text a clip leaves nothing of,
like the text a folded disclosure holds, is hidden on purpose. An element with no box of its own
hides its text by visibility, and not by opacity, which has no box to act on. Text the browser
renders late, or lays out below the first screen of a page that scrolls, is measured. A box cuts
off only what it is the containing block of, the page itself included. Board rows whose marks
each sit at their own offset collide wherever a long title runs under its badge, and the same marks
on a grid collide nowhere.

What the reader sees also depends on when and where the page is read: a page still moving once its
requests are done is measured once it stops and reported unmeasurable when it never does; what an
address' fragment slides under fixed chrome is no finding, while the same chrome over the top of
the page is one; and an opaque card drawn over a text hides it, where two texts nothing covers
collide in plain sight.

A page that loads a script from a server is measured with the script, and with --cache it is
measured with the script after the server stops answering: a server that hangs holds a page without
its copy unmeasurable, and one with its copy not at all. With the network cut off and no copy, the
script's request fails rather than waits.

A run launches Chromium, so these take a second or two each.
"""

import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from lint_pages import LINT, PAGE, RESTLESS

# Every check here starts a browser.
pytestmark = pytest.mark.full_path

TWO_LABELS = """
<div style="position:relative;height:60px">
  <span style="position:absolute;left:20px;top:{one}px">Row label one</span>
  <span style="position:absolute;left:20px;top:{two}px">Row label two</span>
</div>
"""


def settles(top_at_first: int, top_at_rest: int) -> str:
    """A page laying itself out for a second after the requests stop, the way a graph engine does:
    the late label finds its place only once the churn ends."""
    return """
    <div style="position:relative;height:60px">
      <span style="position:absolute;left:20px;top:10px">Row label one</span>
      <span id="late" style="position:absolute;left:20px;top:FIRSTpx">Row label two</span>
    </div>
    <div id="growing"></div>
    <script>
      let n = 0
      const tick = setInterval(() => {
        document.getElementById("growing").append(document.createElement("hr"))
        if (++n < 10) return
        clearInterval(tick)
        document.getElementById("late").style.top = "RESTpx"
      }, 100)
    </script>
    """.replace("FIRST", str(top_at_first)).replace("REST", str(top_at_rest))


# A fixed bar and a note far enough down the page for an address to scroll it under the bar. The
# bar carries no background, so what suppresses the pairing is where the page is read, not what is
# painted over what; the tail is sized in vh, so the page still scrolls once the window is the
# height the page asked for.
FIXED_CHROME = """
<style>
  #bar {{ position: fixed; top: 0; left: 0; right: 0; padding: 2px 8px; font-size: 14px }}
  .grow {{ height: 100vh }}
</style>
<div id="bar">The fixed chrome</div>
{above}
<p id="note" style="margin:0;font-size:14px">A note the chrome would cover</p>
<div class="grow"></div>
"""

# Two screens of a layout sized in vh, which grows under the viewport the run resizes: the
# labels land below the height the page first asked for.
TWO_SCREENS = """
<style>.hero { height: 100vh; position: relative }</style>
<section class="hero"><span style="position:absolute;left:40px;top:50%">The first screen</span></section>
<section class="hero">
  <span style="position:absolute;left:40px;top:50%">Row label one</span>
  <span style="position:absolute;left:40px;top:calc(50% + 2px)">Row label two</span>
</section>
"""


# The board prototype's rows with every mark placed at its own offset, so a long title runs under
# the badge beside it, and the feature tag is cut off by its box. `?fixed` lays the same marks
# out on a grid, where each gets its own track. The badge stands far enough from the chip that a long
# title, from the narrowest face a host falls back on to a monospace one, ends between the two.
BOARD_ROWS = """
<style>
  .rows { width: 56rem; margin: 2rem }
  .row { position: relative; height: 2.2rem }
  .row > * { position: absolute; top: 0.45rem }
  .ftag { left: 0; width: 8rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
  .num { left: 9.5rem }
  .title { left: 12rem; white-space: nowrap; font-size: 0.8rem }
  .badge { right: 18rem }
  .chip { right: 0 }
  .fixed .row { height: auto; display: grid; grid-template-columns: 8rem 1.5rem 1fr 4.5rem 2rem; gap: 0.8rem; align-items: baseline; padding: 0.35rem 0 }
  .fixed .row > * { position: static }
  .fixed .title { overflow: hidden; text-overflow: ellipsis }
  .fixed .badge, .fixed .chip { justify-self: end }
  .ftag, .num, .badge, .chip { font-size: 0.8125rem }
  .ftag, .badge, .chip { border: 1px solid; padding: 0 0.4rem }
</style>
<div class="rows">
  <div class="row"><span class="ftag">board-orients</span><span class="num">02</span><span class="title">Rows</span><span class="badge">claimed</span><span class="chip">01</span></div>
  <div class="row"><span class="ftag">board-orients</span><span class="num">03</span><span class="title">Open questions on a ticket, and the needs-me group they put it into</span><span class="badge">open</span><span class="chip">01</span></div>
  <div class="row"><span class="ftag">render-lint-html-overlap</span><span class="num">—</span><span class="title">render-lint sees HTML text colliding, and says what a box cuts off</span><span class="badge">claimed</span><span class="chip">—</span></div>
</div>
<script>if (new URLSearchParams(location.search).has("fixed")) document.body.classList.add("fixed")</script>
"""


def lint(tmp_path: Path, body: str, *flags: str, crops: Path | None = None, at: str = "", env: dict | None = None) -> tuple[int, list[dict]]:
    """The tool over `body` as a page, at the address `at` appends to it. Exit code and findings."""
    page = tmp_path / "page.html"
    page.write_text(PAGE.format(body))
    run = subprocess.run(
        [str(LINT), f"{page}{at}", "--json", *flags, *(["--crops", str(crops)] if crops else [])],
        capture_output=True, text=True, env=os.environ | (env or {}),
    )
    assert run.returncode in (0, 1, 2) and run.stdout, run.stderr
    return run.returncode, json.loads(run.stdout)


def kinds(findings: list[dict]) -> list[str]:
    return [f["kind"] for f in findings]


def png_size(path: Path) -> tuple[int, int]:
    """A PNG's pixel width and height, out of the IHDR chunk its header opens with."""
    header = path.read_bytes()[16:24]
    return int.from_bytes(header[:4]), int.from_bytes(header[4:])


def test_board_row_marks_at_their_own_offsets_collide_and_the_tag_box_cuts_its_tag_off(tmp_path):
    """The page that showed render-lint seeing HTML text collide: each long title runs under the
    badge in its row, and the feature tag too long for its box is cut off."""
    code, findings = lint(tmp_path, BOARD_ROWS)
    assert {(f["kind"], frozenset(f["text"].split(" | "))) for f in findings} == {
        ("clipped", frozenset({"render-lint-html-overlap"})),
        ("overlap", frozenset({"open", "Open questions on a ticket, and the needs-me group they put it into"})),
        ("overlap", frozenset({"claimed", "render-lint sees HTML text colliding, and says what a box cuts off"})),
    }
    assert len(findings) == 3
    assert code == 1


def test_the_same_board_row_marks_on_a_grid_collide_nowhere(tmp_path):
    """What the grid cuts off, the tag and the long titles, is truncated by design and never fails a run."""
    code, findings = lint(tmp_path, BOARD_ROWS, at="?fixed")
    assert {f["kind"] for f in findings} == {"clipped"}
    assert code == 0


def test_a_line_wider_than_its_box_escapes_it(tmp_path):
    """The kind the board's no-overlap Property leans on hardest and the one nothing here read: a
    line of text wider than the box holding it, with nothing set to hide the rest. What the reader
    sees is the text drawn over whatever sits beside it."""
    code, findings = lint(tmp_path, '<div style="width:80px;white-space:nowrap">A title far too long for it</div>')
    assert kinds(findings) == ["escapes"]
    assert findings[0]["where"] == "html" and findings[0]["by"] > 0
    assert code == 1


def test_the_same_line_in_a_box_wide_enough_passes(tmp_path):
    code, findings = lint(tmp_path, '<div style="width:400px;white-space:nowrap">A title far too long for it</div>')
    assert findings == []
    assert code == 0


def test_two_labels_drawn_over_each_other_collide(tmp_path):
    code, findings = lint(tmp_path, TWO_LABELS.format(one=10, two=12))
    assert kinds(findings) == ["overlap"]
    assert findings[0]["text"] == "Row label one | Row label two"
    assert code == 1


def test_the_same_two_labels_apart_pass(tmp_path):
    code, findings = lint(tmp_path, TWO_LABELS.format(one=10, two=34))
    assert findings == []
    assert code == 0


def test_text_inside_a_parent_does_not_overlap_it(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <p style="width:150px;line-height:0.85">Tight one two <a href="#">a link here</a> and more words after it.</p>
        <button style="font-size:20px">Save <span>everything</span></button>
        """,
    )
    assert findings == []
    assert code == 0


def test_a_clipped_title_is_reported_and_the_run_still_passes(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <div style="width:80px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">An ellipsised title too long for its box</div>
        <div style="width:80px;height:20px;overflow:hidden">A plainly clipped title, several lines of it</div>
        """,
    )
    assert kinds(findings) == ["clipped", "clipped"]
    assert [f["text"][:14] for f in findings] == ["An ellipsised ", "A plainly clip"]
    assert code == 0


def test_a_clipped_text_names_every_box_that_cuts_it(tmp_path):
    """A text set to truncate in a box of its own can still be cut by a box around it, which is a
    different finding: the cutters tell the two apart, the box that cuts less included. A box
    around it counts only for what it cuts off of what the inner box left showing, so a text in a
    scroller a wider card leaves wholly showing is no finding at all, and one a narrower card cuts
    names the card."""
    _, findings = lint(
        tmp_path,
        """
        <div style="width:300px"><span class="clip" style="display:block;width:80px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">Its own ellipsis, cut where it means to be</span></div>
        <div class="card" style="height:4px;overflow:hidden"><span class="clip" style="display:block;overflow:hidden;white-space:nowrap">Short, cut by the card</span></div>
        <div class="row" style="height:12px;overflow:hidden"><span class="clip" style="display:block;width:80px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">Long and cut both ways, mostly by its own ellipsis</span></div>
        <div class="panel" style="width:200px;overflow:hidden"><span class="clip" style="display:block;width:80px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">Wider than the panel, which hides none of what its ellipsis left</span></div>
        <div class="card" style="width:200px;overflow:hidden"><div style="width:100px;overflow-x:auto;white-space:nowrap">Scrolled to, wider than the card around its scroller</div></div>
        <div class="card" style="width:60px;overflow:hidden"><div style="width:100px;overflow-x:auto;white-space:nowrap">In a scroller its card cuts</div></div>
        """,
    )
    assert [(f["text"][:5], sorted(c.split()[-1] for c in f["cutters"])) for f in findings] == [
        ("Its o", ["span.clip"]), ("Short", ["div.card"]), ("Long ", ["div.row", "span.clip"]), ("Wider", ["span.clip"]),
        ("In a ", ["div.card"]),
    ]


def test_text_a_clip_leaves_nothing_of_is_hidden_rather_than_clipped(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <button style="font-size:20px">Save</button>
        <span style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap">screen reader only</span>
        """,
    )
    assert findings == []
    assert code == 0


def test_a_folded_disclosure_holds_no_visible_text(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <details><summary>Ticket one</summary><p>The brief, folded away.</p><p>More of it.</p></details>
        <p>A paragraph after it.</p>
        <p>And another.</p>
        """,
    )
    assert findings == []
    assert code == 0


def test_an_open_disclosure_still_has_its_text_measured(tmp_path):
    code, findings = lint(tmp_path, f"<details open><summary>Ticket one</summary>{TWO_LABELS.format(one=10, two=12)}</details>")
    assert kinds(findings) == ["overlap"]
    assert code == 1


def test_text_in_a_box_that_generates_none_is_measured(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <div style="position:relative;height:80px">
          <div style="position:absolute;left:40px;top:20px"><span style="display:contents">Label A over label B</span></div>
          <span style="position:absolute;left:40px;top:22px">Label B under label A</span>
        </div>
        """,
    )
    assert kinds(findings) == ["overlap"]
    assert code == 1


def test_a_box_less_element_hides_its_text_by_visibility_and_not_by_opacity(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <div style="position:relative;height:120px">
          <div style="position:absolute;left:40px;top:20px"><span style="display:contents;visibility:hidden">A hidden label</span></div>
          <span style="position:absolute;left:40px;top:22px">The label under it</span>
          <div style="position:absolute;left:40px;top:80px"><span style="display:contents;opacity:0">A faded label</span></div>
          <span style="position:absolute;left:40px;top:82px">The label under that</span>
        </div>
        """,
    )
    assert [f["text"] for f in findings] == ["A faded label | The label under that"]
    assert code == 1


def test_a_section_the_browser_renders_late_is_measured(tmp_path):
    code, findings = lint(
        tmp_path,
        f"""
        <div style="height:3000px">A spacer taller than the first viewport.</div>
        <section style="content-visibility:auto;contain-intrinsic-size:auto 200px">{TWO_LABELS.format(one=10, two=12)}</section>
        """,
    )
    assert kinds(findings) == ["overlap"]
    assert code == 1


def test_a_static_box_does_not_clip_the_labels_absolutely_positioned_inside_it(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <div style="overflow:hidden;height:100px">
          <span style="position:absolute;left:40px;top:200px">Label A over label B</span>
          <p style="position:absolute;left:40px;top:202px;margin:0">Label B under label A</p>
        </div>
        """,
    )
    assert kinds(findings) == ["overlap"]
    assert findings[0]["text"] == "Label A over label B | Label B under label A"
    assert code == 1


def test_a_positioned_box_does_clip_what_it_holds(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <div style="position:relative;overflow:hidden;height:40px;width:120px">
          <span style="position:absolute;left:8px;top:8px;white-space:nowrap">A label the box really does cut off</span>
        </div>
        """,
    )
    assert kinds(findings) == ["clipped"]
    assert code == 0


def test_a_box_that_holds_what_it_positions_clips_it_however_it_holds_it(tmp_path):
    held = "perspective:500px", "backdrop-filter:blur(1px)", "translate:0 0", "offset-path:circle(1px)", "will-change:Transform"
    code, findings = lint(
        tmp_path,
        "".join(
            f"""
            <div style="{how};overflow:hidden;width:120px;height:40px">
              <span style="position:absolute;left:4px;top:8px;white-space:nowrap">A label the {how} box cuts off long before here</span>
            </div>
            """
            for how in held
        ),
    )
    assert kinds(findings) == ["clipped"] * len(held)
    assert code == 0


def test_the_page_itself_clips_what_it_pushes_out_of_the_viewport(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <style>body { overflow-x: hidden; min-height: 3000px; width: 3000px }</style>
        <span style="position:absolute;left:2000px;top:20px">Off to the right A</span>
        <span style="position:absolute;left:2000px;top:22px">Off to the right B</span>
        """,
    )
    assert findings == []
    assert code == 0


def test_the_page_does_not_clip_what_it_keeps_in_the_viewport(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <style>body { overflow-x: hidden }</style>
        <span style="position:absolute;left:20px;top:20px">Inside the viewport A</span>
        <span style="position:absolute;left:20px;top:22px">Inside the viewport B</span>
        """,
    )
    assert kinds(findings) == ["overlap"]
    assert code == 1


def test_a_page_that_scrolls_down_shows_what_a_viewport_sized_layout_puts_below_the_fold(tmp_path):
    code, findings = lint(tmp_path, "<style>body { overflow-x: hidden }</style>" + TWO_SCREENS)
    assert kinds(findings) == ["overlap"]
    assert code == 1


def test_a_page_that_cannot_scroll_down_hides_it(tmp_path):
    code, findings = lint(tmp_path, "<style>html { overflow: hidden }</style>" + TWO_SCREENS)
    assert findings == []
    assert code == 0


def test_a_page_that_scrolls_sideways_shows_what_stands_off_to_the_right(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <style>html { overflow-y: hidden } body { width: 3000px }</style>
        <span style="position:absolute;left:2000px;top:20px">Off to the right A</span>
        <span style="position:absolute;left:2000px;top:22px">Off to the right B</span>
        """,
    )
    assert kinds(findings) == ["overlap"]
    assert code == 1


def test_a_box_holds_what_will_change_says_it_will_position_and_not_what_merely_reads_like_it(tmp_path):
    code, findings = lint(
        tmp_path,
        """
        <div style="position:relative;height:320px">
          <div style="overflow:hidden;height:100px;will-change:transform-origin">
            <span style="position:absolute;left:40px;top:200px">A label no box holds</span>
            <span style="position:absolute;left:40px;top:202px">The label under it</span>
          </div>
          <div style="overflow:hidden;height:100px;will-change:position">
            <span style="position:absolute;left:40px;top:200px">A label its box holds</span>
            <span style="position:absolute;left:40px;top:202px">The label under that</span>
          </div>
        </div>
        """,
    )
    assert [f["text"] for f in findings] == ["A label no box holds | The label under it"]
    assert code == 1


def test_a_finding_below_the_first_screen_still_gets_its_crop(tmp_path):
    code, findings = lint(tmp_path, TWO_SCREENS, crops=tmp_path / "crops")
    assert code == 1
    crop = tmp_path / "crops" / "page-01-overlap.png"
    assert [Path(f["crop"]).name for f in findings] == [crop.name]
    # The finding's box and the 24px margin around it, to the pixel the screenshot rounds to,
    # so a crop clamped to a sliver of the first screen fails here rather than passing as a
    # file that exists.
    box, (wide, tall) = findings[0]["box"], png_size(crop)
    assert abs(wide - (box["w"] + 48)) <= 1 and abs(tall - (box["h"] + 48)) <= 1, (wide, tall, box)


def test_a_page_still_moving_once_its_requests_are_done_is_measured_once_it_stops(tmp_path):
    """The board's own failure, as one page: the labels are stacked when the requests stop and
    apart a moment later, so a run that measures once the requests stop reads a collision nobody sees."""
    code, findings = lint(tmp_path, settles(top_at_first=10, top_at_rest=34))
    assert findings == []
    assert code == 0


def test_a_page_that_settles_into_a_collision_still_reports_it(tmp_path):
    code, findings = lint(tmp_path, settles(top_at_first=34, top_at_rest=12))
    assert kinds(findings) == ["overlap"]
    assert code == 1


def test_a_page_that_never_stops_moving_is_unmeasurable(tmp_path):
    """Distinct from a finding and from the run itself failing: nothing on the page was measured,
    so a clean result would be a lie and an overlap would be an accident of timing."""
    code, findings = lint(tmp_path, RESTLESS, "--patience", "1.5")
    assert kinds(findings) == ["unmeasurable"]
    assert findings[0]["text"] == "still moving after 1.5s"
    assert code == 2


def test_what_an_address_scrolls_under_fixed_chrome_is_no_finding(tmp_path):
    """A page is read at the top, where its chrome belongs; the fragment in an address decides
    what the reader scrolls to, not what the page puts under its own bar."""
    code, findings = lint(tmp_path, FIXED_CHROME.format(above='<div style="height:300px"></div>'), at="#note")
    assert findings == []
    assert code == 0


def test_the_same_chrome_over_the_top_of_the_page_still_collides(tmp_path):
    code, findings = lint(tmp_path, FIXED_CHROME.format(above=""), at="#note")
    assert kinds(findings) == ["overlap"]
    assert set(findings[0]["text"].split(" | ")) == {"The fixed chrome", "A note the chrome would cover"}
    assert code == 1


def test_a_card_painted_over_a_text_is_no_finding_and_two_visible_texts_are(tmp_path):
    """An overlap is a collision only where the browser paints both texts. The note under the card
    is not one a reader can see crossed, so it is not one the tool reports; the pair beside it,
    with nothing over either, is."""
    code, findings = lint(
        tmp_path,
        """
        <div style="position:relative;height:170px">
          <span style="position:absolute;left:24px;top:24px">A note under the card</span>
          <div style="position:absolute;left:0;top:0;width:420px;height:120px;padding:22px 20px 0;box-sizing:border-box;background:#fff">The card's own words</div>
          <span id="over" style="position:absolute;left:24px;top:130px">Two visible labels here</span>
          <span style="position:absolute;left:24px;top:132px">And the one under them</span>
        </div>
        """,
    )
    assert [f["text"] for f in findings] == ["Two visible labels here | And the one under them"]
    assert findings[0]["el"] == "span#over | div span"
    assert code == 1


def test_a_finding_names_the_element_it_was_measured_on(tmp_path):
    code, findings = lint(
        tmp_path,
        '<main id="board"><div class="row"><span class="title" style="display:block;width:80px;white-space:nowrap">A title far too long for it</span></div></main>',
    )
    assert [f["el"] for f in findings] == ["main#board div.row span.title"]
    assert code == 1


def test_a_scrolling_box_cuts_nothing_off(tmp_path):
    code, findings = lint(
        tmp_path,
        """<div style="width:80px;overflow-x:auto;white-space:nowrap">A title too long for the box it scrolls in</div>""",
    )
    assert findings == []
    assert code == 0


class Remote:
    """A server a page loads a script from, answering until told to hang."""

    SCRIPT = b"""document.body.insertAdjacentHTML("beforeend", `
      <div style="position:relative;height:60px">
        <span style="position:absolute;left:20px;top:10px">Row label one</span>
        <span style="position:absolute;left:20px;top:12px">Row label two</span>
      </div>`)"""

    def __init__(self) -> None:
        self.hanging = threading.Event()
        self.released = threading.Event()
        remote = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if remote.hanging.is_set():
                    remote.released.wait()
                    return
                if self.path == "/moved.js":
                    self.send_response(302)
                    self.send_header("Location", "/labels.js")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript")
                self.end_headers()
                self.wfile.write(remote.SCRIPT)

            def log_message(self, *_) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.page = f'<script src="http://127.0.0.1:{self.server.server_port}/labels.js"></script>'


@pytest.fixture
def remote() -> Iterator[Remote]:
    r = Remote()
    threading.Thread(target=r.server.serve_forever, daemon=True).start()
    yield r
    r.released.set()
    r.server.shutdown()


def test_a_page_measured_from_its_copies_no_longer_waits_on_the_server_they_came_from(tmp_path, remote):
    cache = tmp_path / "cache"
    code, findings = lint(tmp_path, remote.page, "--cache", str(cache))
    assert kinds(findings) == ["overlap"] and code == 1, "the script the server answered with never ran"
    remote.hanging.set()
    code, findings = lint(tmp_path, remote.page, "--patience", "2")
    assert kinds(findings) == ["unmeasurable"] and findings[0]["text"] == "still loading after 2s"
    code, findings = lint(tmp_path, remote.page, "--cache", str(cache), "--patience", "2")
    assert kinds(findings) == ["overlap"] and code == 1


def test_a_script_behind_a_redirect_is_kept_with_the_redirect(tmp_path, remote):
    moved, cache = remote.page.replace("labels.js", "moved.js"), str(tmp_path / "cache")
    code, findings = lint(tmp_path, moved, "--cache", cache, "--patience", "5")
    assert kinds(findings) == ["overlap"] and code == 1
    code, findings = lint(tmp_path, moved, "--cache", cache, "--patience", "5", env={"MX_PAGE_CACHE_OFFLINE": "1"})
    assert kinds(findings) == ["overlap"] and code == 1, "the redirect was not kept, so the page lost its script offline"


def test_with_the_network_cut_off_a_page_without_its_copy_is_measured_without_the_script(tmp_path, remote):
    remote.hanging.set()
    code, findings = lint(tmp_path, remote.page, "--cache", str(tmp_path / "cache"), "--patience", "2",
                          env={"MX_PAGE_CACHE_OFFLINE": "1"})
    assert findings == [] and code == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
