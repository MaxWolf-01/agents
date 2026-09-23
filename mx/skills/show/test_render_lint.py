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
its title off, which is a finding that never fails a run; text a clip leaves nothing of, and
text a folded disclosure holds, are both hidden on purpose; and a box cuts off only what it
is the containing block of.

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


def lint(tmp_path: Path, body: str) -> tuple[int, list[dict]]:
    page = tmp_path / "page.html"
    page.write_text(PAGE.format(body))
    run = subprocess.run([str(LINT), str(page), "--json"], capture_output=True, text=True)
    assert run.returncode in (0, 1), run.stderr
    return run.returncode, json.loads(run.stdout)


def kinds(findings: list[dict]) -> list[str]:
    return [f["kind"] for f in findings]


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


def test_a_scrolling_box_cuts_nothing_off(tmp_path):
    code, findings = lint(
        tmp_path,
        """<div style="width:80px;overflow-x:auto;white-space:nowrap">A title too long for the box it scrolls in</div>""",
    )
    assert findings == []
    assert code == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
