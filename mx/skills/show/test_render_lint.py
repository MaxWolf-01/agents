# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for render-lint's reading of HTML text. Run: uv run test_render_lint.py

The seam is the command line: a page on disk in, findings and an exit code out, which is how
every caller uses it and the only place the browser's own measurements can be read. Each page
here exhibits one condition, and the oracle is what a reader sees on it: two labels printed
over each other collide and the same two apart do not; a link in a paragraph and a span in a
button sit inside their parents' text rather than across it; a box with overflow hidden cuts
its title off, which is a finding that never fails a run; and text a clip leaves nothing of,
like the text a folded disclosure holds, is hidden on purpose. An element with no box of its own
hides its text by visibility, and not by opacity, which has no box to act on. Text the browser
renders late, or lays out below the first screen of a page that scrolls, is measured. A box cuts
off only what it is the containing block of, the page itself included.

A run launches Chromium, so these take a second or two each.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

LINT = Path(__file__).parent / "render_lint.py"

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>body {{ font-family: serif; margin: 0 }}</style></head>
<body>{}</body></html>
"""

TWO_LABELS = """
<div style="position:relative;height:60px">
  <span style="position:absolute;left:20px;top:{one}px">Row label one</span>
  <span style="position:absolute;left:20px;top:{two}px">Row label two</span>
</div>
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


def lint(tmp_path: Path, body: str, crops: Path | None = None) -> tuple[int, list[dict]]:
    page = tmp_path / "page.html"
    page.write_text(PAGE.format(body))
    run = subprocess.run([str(LINT), str(page), "--json", *(["--crops", str(crops)] if crops else [])], capture_output=True, text=True)
    assert run.returncode in (0, 1) and run.stdout, run.stderr
    return run.returncode, json.loads(run.stdout)


def kinds(findings: list[dict]) -> list[str]:
    return [f["kind"] for f in findings]


def png_size(path: Path) -> tuple[int, int]:
    """A PNG's pixel width and height, out of the IHDR chunk its header opens with."""
    header = path.read_bytes()[16:24]
    return int.from_bytes(header[:4]), int.from_bytes(header[4:])


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


def test_a_scrolling_box_cuts_nothing_off(tmp_path):
    code, findings = lint(
        tmp_path,
        """<div style="width:80px;overflow-x:auto;white-space:nowrap">A title too long for the box it scrolls in</div>""",
    )
    assert findings == []
    assert code == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
