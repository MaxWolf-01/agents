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
from fixture import C1, C2, C3, C4, C5, C6, CONTEXT, MAKEFILE, NOTES  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE.parent
REPO = Path("/var/tmp/mx-demo/ledger")
CHROMIUM = shutil.which("chromium")
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
    fix = commit("csv-import: the dry run's already-settled branch had no test")
    verify()
    for rel, rng in [
        ("csv-import/01-import-properties.md", f"{skeleton}..{properties}"),
        ("csv-import/02-upload-and-parse-report.md", f"{properties}..{report}"),
        ("csv-import/03-map-columns-to-fields.md", f"{report}..{mapping}"),
        ("csv-import/04-commit-the-import.md", f"{mapping}..{commits}"),
    ]:
        stamp_diff(rel, rng)
    needs = REPO / "agent" / "tickets" / "csv-import" / "needs-human.md"
    needs.write_text(needs.read_text().replace("{fix_sha}", fix))
    commit("csv-import: 01 through 04 landed, and the feature's debrief")
    return properties, report


def verify() -> None:
    """Run the demo's own suite: a worked example that does not pass teaches the wrong thing."""
    run("uv", "run", "--with", "pytest", "--with", "hypothesis", "pytest", "-q")


def stamp_diff(rel: str, rng: str) -> None:
    path = REPO / "agent" / "tickets" / rel
    lines = path.read_text().splitlines()
    end = lines.index("---", 1)
    path.write_text("\n".join(lines[:end] + [f"diff: [{rng}]"] + lines[end:]) + "\n")


def render(base: str, head: str) -> tuple[Path, Path]:
    notes = REPO / "agent" / "notes.json"
    notes.write_text(json.dumps(NOTES))
    review = REPO / "agent" / "diffviews" / "csv-import" / "02-upload-and-parse-report.html"
    review.parent.mkdir(parents=True, exist_ok=True)
    run("diffview", f"{REPO}@{base}..{head}", "-o", str(review), "--no-open", "--no-auto-summary",
        "--notes", str(notes), "--title", "02 upload-and-parse-report",
        "--summary", "The upload gets a report instead of a row list: every line the mapping could "
                     "not read comes back with its number and the reason, so the human sees the whole "
                     "statement before anything is committed. Lifts the two parse properties.")
    board = REPO / "agent" / "board.html"
    run("board", str(REPO / "agent" / "tickets"), "--no-watch", "--no-open")
    return board, review


def shoot(board: Path, review: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)

        page.goto(board.resolve().as_uri())
        page.wait_for_selector(".view.active .mermaid svg", timeout=30_000)
        page.wait_for_timeout(1200)
        page.evaluate("document.querySelector('.btn[data-mode=full]').click()")
        page.wait_for_timeout(1500)
        page.evaluate("document.querySelector('#needs-human details').open = true")
        page.wait_for_timeout(300)
        band(page, "board-overview.png", "#needs-human")

        page.evaluate("document.querySelector('.btn[data-mode=lanes]').click()")
        page.evaluate("document.querySelector('#t-saved-views-05').open = true")
        page.wait_for_timeout(600)
        page.locator("#f-saved-views").screenshot(path=str(OUT / "board-feature.png"))
        print("board-feature.png")

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


def band(page, name: str, bottom: str) -> None:
    """Screenshot from the top of the page to the bottom of `bottom`, full width."""
    height = page.evaluate("b => document.querySelector(b).getBoundingClientRect().bottom + scrollY", bottom)
    page.screenshot(path=str(OUT / name), full_page=True,
                    clip={"x": 0, "y": 0, "width": 1280, "height": height})
    print(name)


if __name__ == "__main__":
    base, head = build_repo()
    board, review = render(base, head)
    shoot(board, review)
    print(f"repo: {REPO}")
