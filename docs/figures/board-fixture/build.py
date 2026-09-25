#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright"]
# ///
"""Lay down the demo project, render its board and one review page, and shoot both.

The screenshots in the mx README are of a real render, not a mockup: this builds a
throwaway repo under /var/tmp from `fixture.py` and `tracker/`, runs `board` and
`diffview` against it, and screenshots what they produce. Re-run it whenever either
tool's output changes.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "mx" / "skills" / "tracker"))
from briefing import cache_path  # noqa: E402
from fixture import C1, C2, C3, C4, C5, C6, CONTEXT, MAKEFILE, NOTES  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE.parent
BOARD = HERE.parents[2] / "mx" / "bin" / "board"  # this checkout's board, not whichever is on PATH
REPO = Path("/var/tmp/mx-demo/ledger")
CHROMIUM = shutil.which("chromium")
WIDE = 1440  # past the board's 1400px breakpoint, where the graph panel sits beside the rows
TALL = 1400  # the side column scrolls inside the window, so a short one would cut its graph off
PAD = 24  # breathing room under the lowest element a shot is clipped to
SCHEMES = {"light": "-light", "dark": ""}  # the suffixes render.py gives the other figures
ENV = {"GIT_AUTHOR_NAME": "demo", "GIT_AUTHOR_EMAIL": "demo@example.com",
       "GIT_COMMITTER_NAME": "demo", "GIT_COMMITTER_EMAIL": "demo@example.com",
       "GIT_AUTHOR_DATE": "2026-03-02T09:12:00", "GIT_COMMITTER_DATE": "2026-03-02T09:12:00"}


def run(*args: str, cwd: Path = REPO) -> str:
    import os
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env={**os.environ, **ENV})
    if done.returncode:
        sys.exit(f"{' '.join(args)} failed ({done.returncode}):\n{done.stdout}\n{done.stderr}")
    return done.stdout.strip()


def write(files: dict[str, str]) -> None:
    for rel, body in files.items():
        path = REPO / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)


def commit(message: str) -> str:
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", message)
    return run("git", "rev-parse", "--short", "HEAD")


def build_repo() -> tuple[str, str]:
    """The repo as dispatch would have left it: csv-import landed, saved-views waiting."""
    shutil.rmtree(REPO.parent, ignore_errors=True)
    REPO.mkdir(parents=True)
    run("git", "init", "-q", "-b", "main")
    write({"CONTEXT.md": CONTEXT, "Makefile": MAKEFILE, ".gitignore": "agent/board.html\nagent/diffviews/\n.hypothesis/\n__pycache__/\n"})
    shutil.copytree(HERE / "tracker", REPO / "agent" / "tickets")
    write(C1)
    skeleton = commit("ledger: the skeleton, a Row and an importer that raises")
    write(C2)
    properties = commit("import-properties: the spec's three properties, as checks at their seams")
    write(C3)
    report = commit("upload-and-parse-report: every line the mapping could not read, with its number")
    write(C4)
    mapping = commit("map-columns-to-fields: a bank's mapping is remembered for its next statement")
    write(C5)
    commits = commit("commit-the-import: entries, after a dry run that says what will be skipped")
    write(C6)
    write({"agent/show/flaky-upload-test/rerun-under-load": RERUN})  # what the row in review offers the reader
    (REPO / "agent/show/flaky-upload-test/rerun-under-load").chmod(0o755)
    fix = commit("csv-import: the dry run's already-settled branch had no test")
    verify()
    for rel, rng in [
        ("csv-import/01-import-properties.md", f"{skeleton}..{properties}"),
        ("csv-import/02-upload-and-parse-report.md", f"{properties}..{report}"),
        ("csv-import/03-map-columns-to-fields.md", f"{report}..{mapping}"),
        ("csv-import/04-commit-the-import.md", f"{mapping}..{commits}"),
    ]:
        stamp_diff(rel, rng)
    commit(f"csv-import: 01 through 04 landed; the debrief's 06, from a survivor no test pins ({fix})")
    return properties, report


def verify() -> None:
    """Run the demo's own suite: a worked example that does not pass teaches the wrong thing."""
    run("uv", "run", "--with", "pytest", "--with", "hypothesis", "pytest", "-q")


def stamp_diff(rel: str, rng: str) -> None:
    path = REPO / "agent" / "tickets" / rel
    lines = path.read_text().splitlines()
    end = lines.index("---", 1)
    path.write_text("\n".join(lines[:end] + [f"diff: [{rng}]"] + lines[end:]) + "\n")


def render(base: str, head: str) -> tuple[Path, Path | None]:
    """The board, and the review page where `diffview` is installed: without it the board shots
    still build, and review-page.png stays as whichever run last had it."""
    review = None
    if shutil.which("diffview"):
        notes = REPO / "agent" / "notes.json"
        notes.write_text(json.dumps(NOTES))
        review = REPO / "agent" / "diffviews" / "csv-import" / "02-upload-and-parse-report.html"
        review.parent.mkdir(parents=True, exist_ok=True)
        run("diffview", f"{REPO}@{base}..{head}", "-o", str(review), "--no-open", "--no-auto-summary",
            "--notes", str(notes), "--title", "02 upload-and-parse-report",
            "--summary", "The upload gets a report instead of a row list: every line the mapping could "
                         "not read comes back with its number and the reason, so the human sees the whole "
                         "statement before anything is committed. Lifts the two parse properties.")
    else:
        (OUT / "review-page.png").unlink(missing_ok=True)  # gone reads as not shot; stale reads as fresh
        print("no diffview on PATH: skipping review-page.png, and the board's review links stay bare")
    board = REPO / "agent" / "board.html"
    # one render, so no briefing session runs: the answer one really gave on this tracker stands in
    # for it, which is the column a reader's own board has and the README's prose describes
    shutil.copy(HERE / "briefing.json", cache_path(board))
    run(str(BOARD), str(REPO / "agent" / "tickets"), "--no-watch", "--no-open")
    return board, review


def shoot(board: Path, review: Path | None) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page(viewport={"width": WIDE, "height": TALL}, device_scale_factor=2)

        for scheme, suffix in SCHEMES.items():
            # the reader's system setting decides which the README shows, as it does for every
            # other figure here; the board reads it when nothing is stored, so each pass starts clean
            page.emulate_media(color_scheme=scheme)
            page.goto(board.resolve().as_uri())
            page.evaluate("localStorage.clear()")
            page.reload()
            page.wait_for_selector(".btn[data-gmode].on", timeout=30_000)  # the module script has its listeners
            absent = page.eval_on_selector_all(".absences .absent", "notes => notes.map(n => n.textContent)")
            # the board says each missing optional source in a line above the rows, inside the clip
            # band: a shot taken on a host short of one would carry that line into the README
            assert not absent, "the board rendered without an optional source:\n  " + "\n  ".join(absent)

            # the whole tracker's graph beside the groups, needs me with its questions at the top
            page.evaluate("document.querySelector('.btn[data-gmode=all]').click()")
            page.wait_for_selector(".g:not([hidden]) .mermaid svg", timeout=30_000)
            page.wait_for_timeout(600)
            band(page, f"board-overview{suffix}", "#grp-open", "#side")

            # one feature: the other hidden by its chip, a ticket opened to its blocks, its graph marked
            page.evaluate("document.querySelector('.featchip[data-feature=csv-import]').click()")
            page.evaluate("document.querySelector('.btn[data-gmode=feature]').click()")
            page.evaluate("document.querySelector('#t-saved-views-03 > summary').click()")
            page.wait_for_selector(".g:not([hidden]) .mermaid svg", timeout=30_000)
            page.wait_for_timeout(600)
            band(page, f"board-feature{suffix}", "#grp-proposed")

        if review:
            page.emulate_media(color_scheme="dark")
            page.goto(review.resolve().as_uri())
            page.wait_for_timeout(1500)
            page.evaluate(DISMISS_BANNER)
            page.wait_for_timeout(300)
            page.set_viewport_size({"width": 1280, "height": 1020})
            page.evaluate(SCROLL_TO_NOTE)
            page.wait_for_timeout(600)
            page.screenshot(path=str(OUT / "review-page.png"))
            print("review-page.png")
        browser.close()


# The one ticket the fixture leaves in review, so the row that says "to rule on" has something to run.
RERUN = """#!/usr/bin/env bash
# The report test, a hundred times over, against a disk kept busy: the flake it used to show is
# gone because nothing in the test opens a file any more.
set -euo pipefail
dd if=/dev/zero of=/tmp/ledger-load bs=1M count=512 oflag=direct status=none &
uv run --with pytest pytest tests/test_importer.py -q --count 100
wait
"""


DISMISS_BANNER = """() => document.querySelector("div.readonly")?.remove()"""

# The agent's notes are painted into the diff body once it renders; find one by its own words.
SCROLL_TO_NOTE = """() => {
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) {
    if (!/cannot read is shown/.test(walk.currentNode.nodeValue)) continue;
    walk.currentNode.parentElement.scrollIntoView({block: "center"});
    window.scrollBy(0, -160);
    return;
  }
  throw new Error("note not found");
}"""


def band(page, name: str, *bottoms: str) -> None:
    """Screenshot from the top of the page down past every element named, full width.

    The side column is one of them wherever the rows above it are the shorter side, so a briefing
    the model wrote long never costs the shot the graph preview under it."""
    height = PAD + max(page.evaluate("b => document.querySelector(b).getBoundingClientRect().bottom + scrollY", b)
                       for b in bottoms)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True,
                    clip={"x": 0, "y": 0, "width": WIDE, "height": height})
    print(f"{name}.png")


if __name__ == "__main__":
    base, head = build_repo()
    board, review = render(base, head)
    shoot(board, review)
    print(f"repo: {REPO}")
