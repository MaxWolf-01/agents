# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for blind-test. Run: uv run test_blind_test.py

The seam is the command line, a pairs file in and a page out, and the page in a browser, where the
reader picks. The oracle is what the reader is owed: before the reveal nothing on the page says
which side a cell is or which side the agent picked; after it, the answer line names every row's
pick by its ref, written out by hand below.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SHOW = Path(__file__).resolve().parent
SCRIPT = SHOW / "blind_test.py"

PAIRS = {
    "question": "Q4", "title": "Error message style",
    "options": {"a": "plain sentence", "b": "code first"},
    "pick": "a", "why": "a sentence reads aloud",
    "pairs": [
        {"ref": "r1", "a": "the file is missing", "b": "ENOENT: file"},
        {"ref": "r2", "a": "the port is taken", "b": "EADDRINUSE: port"},
        {"ref": "r3", "a": "the disk is full", "b": "ENOSPC: disk"},
        {"a": "access was refused", "b": "EACCES: access"},
    ],
}


def render(tmp_path: Path, data: object) -> subprocess.CompletedProcess:
    pairs = tmp_path / "blind-q4.json"
    pairs.write_text(json.dumps(data))
    return subprocess.run([str(SCRIPT), str(pairs), "--session", "0123456789abcdef"],
                          capture_output=True, text=True, timeout=120)


def test_a_pairs_file_renders_beside_itself_under_its_own_name(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("the ticket's own page")
    done = render(tmp_path, PAIRS)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == str(tmp_path / "blind-q4.html")
    assert "Q4 · Error message style" in (tmp_path / "blind-q4.html").read_text()
    assert (tmp_path / "index.html").read_text() == "the ticket's own page"


def test_a_malformed_pairs_file_is_refused_with_every_problem(tmp_path: Path) -> None:
    bad = PAIRS | {"options": {"a": "x", "c": "y"}, "pick": "c", "pairs": [{"a": "only one side"}]}
    done = render(tmp_path, bad)
    assert done.returncode == 1
    for problem in ("options holds exactly a and b", "pick is a or b", "pair 1 lacks a or b"):
        assert problem in done.stderr
    assert not (tmp_path / "blind-q4.html").exists()


PROBE = r"""
import json, os, shutil, sys
from playwright.sync_api import sync_playwright
from page_cache import default_root, serve

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    context = browser.new_context(reduced_motion="reduce")
    serve(context, default_root())
    page = context.new_page()
    page.goto(sys.argv[1])
    if sys.argv[2] == "first-column":
        print(json.dumps(page.evaluate("[...document.querySelectorAll('.row')].map((r) => r.querySelector('.cell').dataset.side)")))
        sys.exit()
    cell = lambda text: page.locator(".cell", has_text=text)
    for text in ("ENOENT: file", "EADDRINUSE: port", "the disk is full", "access was refused", "access was refused"):
        cell(text).click()
    out = {"before": page.evaluate("document.body.innerText")}
    page.click("#reveal-button")
    out["answer"] = page.text_content("#answer")
    out["labels"] = page.evaluate("[...document.querySelectorAll('.cell')].map((c) => [c.dataset.side, c.querySelector('.label').innerText])")
    print(json.dumps(out))
"""


def probe(tmp_path: Path, data: dict, scenario: str) -> object:
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to drive the page with")
    assert render(tmp_path, data).returncode == 0
    done = subprocess.run(["uv", "run", "--quiet", "--with", "playwright", "python", "-", (tmp_path / "blind-q4.html").as_uri(), scenario],
                          input=PROBE, capture_output=True, text=True, timeout=180, env=os.environ | {"PYTHONPATH": str(SHOW)})
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


@pytest.mark.full_path
def test_the_page_hides_the_sides_until_the_reveal_and_names_each_rows_pick(tmp_path: Path) -> None:
    """Rows r1 and r2 picked b, r3 picked a, and the fourth, which has no ref, picked and then
    unpicked, so it is named by its row number."""
    out = probe(tmp_path, PAIRS, "picks")
    for revealing in ("plain sentence", "code first", "my pick", "a sentence reads aloud"):
        assert revealing not in out["before"]
    assert out["answer"] == "Q4 blind: b 2/4 (r1 r2), a 1/4 (r3), unpicked 1/4 (4)"
    assert all(label == f"{side} · {PAIRS['options'][side]}" for side, label in out["labels"])



@pytest.mark.full_path
def test_the_sides_are_shuffled_per_row(tmp_path: Path) -> None:
    """A column that always held the same side would give the side away. Over 40 rows both sides
    lead some row, unless the shuffle is broken or a 2^-39 chance comes up."""
    many = PAIRS | {"pairs": [{"a": f"plain {i}", "b": f"code {i}"} for i in range(40)]}
    assert set(probe(tmp_path, many, "first-column")) == {"a", "b"}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
