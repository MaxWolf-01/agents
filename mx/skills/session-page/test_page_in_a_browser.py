# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown-it-py"]
# ///
"""The session page running in a browser. Run: uv run test_page_in_a_browser.py

The seam is the rendered page: the worked example (conftest.py) rendered by `render_session`, its
artefacts written where its links point, and the page driven in headless Chromium. The oracle is
the Brief of agent/tickets/session-page-lists-its-artefacts.md: the artefact column stays in view
beside the turns while they scroll, a collapsed turn shows its artefacts as chips, j and k move
between turns, and 1 to 9 open the focused turn's artefacts. test_session_page.py checks what the
column and the chips list; this checks what the reader sees of them and what the keys do.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from session_page import PAGE, render_session

ARTEFACTS = (
    "agent/show/session-page/round-1/index.html",
    "agent/show/session-page/round-2/index.html",
    "agent/show/session-page/round-3/pages.html",
    "agent/show/session-page/round-3/spec.html",
)

PROBE = r"""
import json, os, shutil, sys
from playwright.sync_api import sync_playwright

page_url, width = sys.argv[1], int(sys.argv[2])
BOX = "(el) => { const r = el.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right} }"
with sync_playwright() as pw:
    # the run it belongs to, as `browsers --help` defines it
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    context = browser.new_context(viewport={"width": width, "height": 800})
    page = context.new_page()
    page.goto(page_url)
    out = {"height": page.evaluate("innerHeight")}
    out["top"] = {"column": page.eval_on_selector("#artefacts", BOX), "turns": page.eval_on_selector(".turns", BOX)}
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    out["bottom"] = {"column": page.eval_on_selector("#artefacts", BOX), "turns": page.eval_on_selector(".turns", BOX)}
    page.evaluate("window.scrollTo(0, 0)")
    out["chips"] = page.evaluate('''[...document.querySelectorAll("details.turn")].map((t) => [t.id,
        [...t.querySelectorAll(":scope > summary .chip-link")].filter((a) => a.checkVisibility()).map((a) => a.textContent)])''')

    def where():
        return page.evaluate('''[document.querySelector(".blk.cur")?.id ?? null,
                                 document.querySelector("#artefacts .group.cur")?.id ?? null]''')

    def opened(key):
        with context.expect_page(timeout=5000) as tab:
            page.keyboard.press(key)
        tab.value.wait_for_load_state()
        url = tab.value.url
        tab.value.close()
        return url

    out["walk"] = []
    for key in ("j", "j", "j", "k"):
        page.keyboard.press(key)
        out["walk"].append([key, *where()])
    out["opened"] = {"t04 1": opened("1"), "t04 2": opened("2")}
    page.keyboard.press("j")
    out["opened"]["t03 1"] = opened("1")
    page.keyboard.press("2")
    page.wait_for_timeout(100)
    out["toast"] = page.text_content("#toast")
    # a window too short for the column to show every group: focusing the oldest turn scrolls its
    # group into the column's view
    short = browser.new_context(viewport={"width": width, "height": 240}).new_page()
    short.goto(page_url)
    for _ in range(4):
        short.keyboard.press("j")
    short.wait_for_timeout(800)
    out["short"] = {"column": short.eval_on_selector("#artefacts", BOX), "group": short.eval_on_selector("#a02", BOX),
                    "overflows": short.eval_on_selector("#artefacts", "(el) => el.scrollHeight > el.clientHeight")}
    browser.close()
print(json.dumps(out))
"""


@pytest.fixture
def rendered(worked_example: Path, transcript: Path) -> tuple[Path, Path]:
    """The worked example's page written beside its records, and the repo root its links resolve
    from, which holds every artefact the records link."""
    root = worked_example.parents[2]
    for path in ARTEFACTS:
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(f"<title>{path}</title>")
    (worked_example / PAGE).write_text(render_session(worked_example, transcript))
    return worked_example / PAGE, root


def probe(page: Path, width: int) -> dict:
    done = subprocess.run(
        ["uv", "run", "--quiet", "--with", "playwright", "python", "-", page.as_uri(), str(width)],
        input=PROBE, capture_output=True, text=True, timeout=120,
    )
    assert done.returncode == 0, f"probe: {done.stderr.strip()[-2000:]}"
    return json.loads(done.stdout)


def test_the_column_chips_and_keys_work_in_a_browser(rendered: tuple[Path, Path]) -> None:
    """At a laptop's width: the column sits right of the turns and is still in the window once
    they have scrolled to their end; the newest turn, open, shows no chips and each collapsed turn
    shows its artefacts as chips; j and k walk the open question and then the turns, marking the
    focused turn's group in the column; 1 and 2 open the focused turn's first and second artefact,
    and a number the turn has no artefact for opens nothing and says so. In a window too short for
    the column, focusing a turn scrolls its group into the column's view."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to drive the page with")
    page, root = rendered
    seen = probe(page, 1280)
    for moment in ("top", "bottom"):
        column, turns = seen[moment]["column"], seen[moment]["turns"]
        assert column["left"] >= turns["right"], f"at the {moment}, the column is not beside the turns: {seen[moment]}"
    assert seen["bottom"]["turns"]["bottom"] <= seen["height"], "the turns never scrolled to their end"
    column = seen["bottom"]["column"]
    assert 0 <= column["top"] < seen["height"] and column["bottom"] > 0, f"the column scrolled away: {column}"
    assert seen["chips"] == [
        ["t04", []],
        ["t03", ["Round 2 as a hand-built session page"]],
        ["t02", ["The grid, the session page sketch and Q1 to Q3"]],
        ["t01", []],
    ]
    assert seen["walk"] == [["j", "q7", None], ["j", "t04", "a04"], ["j", "t03", "a03"], ["k", "t04", "a04"]]
    url = lambda path: (root / path).as_uri()
    assert seen["opened"] == {"t04 1": url(ARTEFACTS[2]), "t04 2": url(ARTEFACTS[3]), "t03 1": url(ARTEFACTS[1])}
    assert seen["toast"] == "turn 03 has no artefact 2"
    short = seen["short"]
    assert short["overflows"], "the column fits the short window, so nothing there needs scrolling"
    assert short["column"]["top"] <= short["group"]["top"] and short["group"]["bottom"] <= short["column"]["bottom"], short


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
