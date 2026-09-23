#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright", "tyro"]
# ///
"""Write figure.html beside this file: an opened row's questions before this slice and after it.

Three panels off one demo tracker, each a screenshot of a browser driven to the state it shows,
with a numbered badge sitting where each note points, placed from the box the browser measured for
that element rather than from a coordinate anyone typed. Both colour schemes are captured and the
figure's switch picks one.

The `before` render runs the board as this slice was cut from it, read out of git, so that panel is
what the board did rather than an account of it.

Examples:

    figure.py
    figure.py --before 298cff2 --work /tmp/board-questions-figure
"""

import base64
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import tyro
from playwright.sync_api import Page, sync_playwright

HERE = Path(__file__).parent
ROOT = HERE.parents[3]
TRACKER = ROOT / "mx" / "skills" / "tracker"
ROW = "t-csv-import-02"  # the build in review, which asks three questions
FOLDED = "standalone-retire-legacy-exporter"  # a needs-me row the anchor leaves folded
WIDE = {"width": 1500, "height": 1700}  # tall enough for the opened row to be shot without scrolling
PAD = 10  # the margin a clipped shot keeps around the element it is clipped to

# What each panel shows, and what its notes point at: (selector, note). A badge lands on the top
# left corner of the element named, which is why each one names the smallest element that carries
# the fact rather than the panel it sits in.
PANELS = {
    "before": (
        "the opened row as it was: every question under the name, and again in the block",
        [
            (f"#{ROW} .qs", "The list a folded row carries stayed when the row opened: each question's tag and headline, its copy button, and the copy-all under them."),
            (f"#{ROW} .asked > li:first-child .head", "The same question again, twelve lines down, this time with the detail the list had no room for. Three questions, read twice each, with the tags the only thing tying the two lists together."),
        ],
    ),
    "after": (
        "the same row now: the questions once, in the block, with their detail and their buttons",
        [
            (f"#{ROW} .brief", "The list under the name is gone while the row is open. The brief stays, since it is the row's own."),
            (f"#{ROW} .asked > li:first-child .head", "Each question once: the headline the list showed, with its detail under it."),
            (f"#{ROW} .asked > li:first-child > .copier", "The button the list carried, now beside the question it copies. It copies what the list's did, the question as one line of markdown under the ticket's path, and says so on hover."),
        ],
    ),
    "folded": (
        "a folded row, unchanged: the list is what a row that is not open shows",
        [
            (f"#{FOLDED} .qs", "Both questions under the name, each with its copy button and the copy-all beside them, as before this slice."),
        ],
    ),
}


@dataclass
class Args:
    before: str = "298cff2"
    """The commit the `before` panel is rendered from: the board as this slice was cut from it."""
    work: Path = Path("/tmp/board-questions-figure")
    """Where the demo tracker, the two boards and the screenshots are built and left."""


def run(*args: object, **kwargs) -> subprocess.CompletedProcess:
    done = subprocess.run([str(a) for a in args], capture_output=True, **{"text": True, **kwargs})
    assert done.returncode == 0, f"{args[0]} failed: {str(done.stderr)[-2000:]}"
    return done


def board_at(ref: str, work: Path) -> Path:
    """The board as `ref` had it, with the rest of its directory, since the board imports its siblings."""
    tree = work / "before-tree"
    tree.mkdir(parents=True, exist_ok=True)
    tar = run("git", "-C", str(ROOT), "archive", ref, "mx/skills/tracker", text=False)
    run("tar", "-x", "-C", str(tree), input=tar.stdout, text=False)
    return tree / "mx" / "skills" / "tracker" / "board.py"


def render(board: Path, tracker: Path, out: Path, config: Path) -> Path:
    run("uv", "run", board, tracker, "--no-watch", "--no-open", "--out", out,
        env={**os.environ, "CLAUDE_CONFIG_DIR": str(config)})
    return out


def shot(page: Page, png: Path, notes: list[tuple[str, str]], clip_to: str) -> dict:
    """One panel: the row as it stands, and where on it each note's badge belongs, in fractions of
    the image so the figure can scale it."""
    box = page.locator(clip_to).bounding_box()
    clip = {"x": box["x"] - PAD, "y": box["y"] - PAD, "width": box["width"] + 2 * PAD, "height": box["height"] + 2 * PAD}
    page.screenshot(path=png, clip=clip)
    badges = []
    for selector, _ in notes:
        at = page.locator(selector).first.bounding_box()
        assert at, f"nothing at {selector} to point at"
        badges.append(((at["x"] - clip["x"]) / clip["width"], (at["y"] - clip["y"]) / clip["height"]))
    return {"png": png, "badges": badges}


def capture(before: Path, after: Path, work: Path, scheme: str) -> dict:
    """The three panels in one scheme, each driven to the state it shows."""
    shots = {}
    assert shutil.which("chromium"), "no chromium to render the board with"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("chromium"))
        page = browser.new_context(viewport=WIDE).new_page()

        page.goto(f"{before.as_uri()}?theme={scheme}#{ROW}", wait_until="networkidle")
        page.wait_for_selector(f"#{ROW}[open] .asked")
        shots["before"] = shot(page, work / f"before-{scheme}.png", PANELS["before"][1], f"#{ROW}")

        page.goto(f"{after.as_uri()}?theme={scheme}#{ROW}", wait_until="networkidle")
        page.wait_for_selector(f"#{ROW}[open] .asked")
        shots["after"] = shot(page, work / f"after-{scheme}.png", PANELS["after"][1], f"#{ROW}")
        shots["folded"] = shot(page, work / f"folded-{scheme}.png", PANELS["folded"][1], f"#{FOLDED}")
        browser.close()
    return shots


def panel(key: str, schemes: dict[str, dict]) -> str:
    """One panel: both schemes' images stacked, the badges over them, and the numbered notes."""
    what, notes = PANELS[key]
    images = "".join(
        f'<img class="{scheme}" src="data:image/png;base64,{base64.b64encode(shots[key]["png"].read_bytes()).decode()}" alt="{what}">'
        for scheme, shots in schemes.items()
    )
    # the two schemes differ in ink alone, so one set of badges serves both images; the check is
    # that they were measured to the same places, rather than an assumption that they would be
    places = [shots[key]["badges"] for shots in schemes.values()]
    assert all(abs(a - b) < 0.002 for one, other in zip(*places) for a, b in zip(one, other)), (
        f"the {key} panel lays out differently in the two schemes: {places}"
    )
    badges = "".join(
        f'<span class="mk over" style="left: {x:.3%}; top: {y:.3%}">{n + 1}</span>'
        for n, (x, y) in enumerate(places[0])
    )
    items = "".join(f'<li><span class="mk">{n + 1}</span><span>{note}</span></li>' for n, (_, note) in enumerate(notes))
    return (
        f'<figure class="panel"><figcaption><b>{key}</b> {what}</figcaption>'
        f'<div class="shot">{images}{badges}</div><ol class="notes">{items}</ol></figure>'
    )


def build(args: Args) -> str:
    work = args.work
    work.mkdir(parents=True, exist_ok=True)
    demo = work / "demo"
    run("uv", "run", TRACKER / "demo_tracker.py", demo)
    tracker, config = demo / "agent" / "tickets", demo / "claude"
    before = render(board_at(args.before, work), tracker, work / "before.html", config)
    after = render(TRACKER / "board.py", tracker, work / "after.html", config)
    schemes = {scheme: capture(before, after, work, scheme) for scheme in ("day", "night")}
    style = after.read_text().split("<style>", 1)[1].split("</style>", 1)[0]
    panels = "".join(panel(key, schemes) for key in PANELS)
    return PAGE.replace("${style}", style).replace("${panels}", panels)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>An opened row's questions, before and after</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<script>
  (() => {
    const asked = new URLSearchParams(location.search).get("theme");
    const night = asked ? asked === "night" : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = night ? "night" : "day";
  })();
</script>
<style>
/* the board's own stylesheet, so this page is in the same ink as the renders below */
${style}

/* the figure around them */
  body { padding: 0 0 4rem; }
  .page { max-width: 82rem; margin: 0 auto; padding: 0 1.5rem; }
  h1 { font-size: 1.6rem; font-weight: 600; margin: 2.5rem 0 .75rem; color: var(--strong); }
  .lead { color: var(--muted); max-width: 46rem; }
  .lead + .lead { margin-top: .75rem; }
  .switch { margin-top: 1.5rem; font-family: var(--font-mono); font-size: .78rem; color: var(--muted);
    background: none; border: 1px solid var(--edge); border-radius: 4px; padding: .2rem .5rem; cursor: pointer; }
  .switch:hover { color: var(--accent); border-color: var(--accent); }
  .panel { margin: 2.75rem 0 0; }
  figcaption { color: var(--muted); margin-bottom: .6rem; }
  figcaption b { color: var(--strong); font-weight: 600; font-family: var(--font-mono); font-size: .9rem; }
  .shot { position: relative; display: inline-block; max-width: 100%;
    border: 1px solid var(--edge); border-radius: var(--radius); overflow: hidden; }
  .shot img { display: block; max-width: 100%; height: auto; }
  [data-theme="day"] .shot img.night, [data-theme="night"] .shot img.day { display: none; }
  .notes { margin: .9rem 0 0; padding: 0; list-style: none; max-width: 56rem; }
  .notes li { display: flex; gap: .5rem; align-items: baseline; margin-top: .45rem; color: var(--muted); }
  .notes b { color: var(--strong); font-weight: 600; font-family: var(--font-mono); font-size: .88rem; }
  .mk { flex: none; display: inline-grid; place-items: center; width: 1.25rem; height: 1.25rem;
    border-radius: 50%; background: var(--accent); color: var(--ground); font-family: var(--font-mono); font-size: .7rem; }
  /* a badge sits on the corner of the element its note is about, so it points without covering */
  .mk.over { position: absolute; transform: translate(-60%, -60%); box-shadow: 0 0 0 2px var(--ground); }
</style>
</head>
<body>
<div class="page">
<h1>An opened row's questions, before and after</h1>
<p class="lead">One demo tracker, rendered by the board as this slice was cut from it and by the
board now, opened on the same row: the build in review that asks three questions. Each panel is a
browser screenshot of the state the caption names, with a badge where each note points.</p>
<p class="lead">The <b>folded</b> panel is from the board now, and is what the board did before as
well: a row that is not open still lists its questions under its name.</p>
<p class="lead">Built by <code>figure.py</code> beside this file. The walkthrough of the state it
leaves is <code>demo</code>, beside it.</p>
<button class="switch" onclick="document.documentElement.dataset.theme = document.documentElement.dataset.theme === 'night' ? 'day' : 'night'">day / night</button>
${panels}
</div>
</body>
</html>
"""


def main(args: Args) -> None:
    (HERE / "figure.html").write_text(build(args))
    print(HERE / "figure.html")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
