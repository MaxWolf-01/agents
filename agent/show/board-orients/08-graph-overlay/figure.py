#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright", "tyro"]
# ///
"""Write figure.html beside this file: the board's dependency graph before this slice and after it.

Four renders of one demo tracker, each a screenshot of a browser that was driven to the state it
shows, with a numbered badge sitting where each note points, placed from the box the browser
measured for that element rather than from a coordinate anyone typed. Both colour schemes are
captured and the figure's switch picks one.

The `before` render runs the board as this slice was cut from it, read out of git, so that panel
is what the board did rather than an account of it.

Examples:

    figure.py
    figure.py --before 5ced2d5 --work /tmp/board-graph-figure
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
ROW = "t-csv-import-02"  # the row the board opens on, so the preview has a feature to draw
WIDE = {"width": 1500, "height": 700}  # wide enough for the side column to sit beside the rows
PAD = 10  # the margin a clipped shot keeps around the element it is clipped to

# What each panel shows, and what its notes point at: (selector, note). A badge lands on the top
# left corner of the element named, which is why each one names the smallest element that carries
# the fact rather than the panel it sits in.
PANELS = {
    "before": (
        "the side column as it was, with the graph of the row the cursor is on",
        [
            (".side .mermaid svg g.node", "The whole feature graph, drawn to fit a 22rem column. Every label is there and none of them is readable; a tracker with more edges than this one fares worse."),
            ("#sidefold", "The one thing the head offers is folding it away. Nothing opens the graph, so the only way to a node is a click on a box a few pixels tall."),
        ],
    ),
    "preview": (
        "the same column now: the same graph, as a preview of one that opens",
        [
            (".side .mermaid svg g.node", "The preview is unchanged, and a click anywhere on it that is not a node opens the graph at full size."),
            ("#gopen", "<b>full</b> opens it over the board, and so does the <kbd>f</kbd> key or <code>#graph</code> on the address."),
            ("#gwinopen", "<b>window</b> opens the same view in a window of its own, to sit beside the board; <kbd>w</kbd> does too."),
        ],
    ),
    "overlay": (
        "the whole tracker's graph at full size, over the board",
        [
            ("#gfull .gsvg g.node", "The graph at the size mermaid drew it for: the labels are the board's body text. Wider than the window, so the box scrolls, and a drag anywhere pans it."),
            ("#gfull .seg", "The feature and whole-tracker switch, in the overlay's own head because the overlay covers the top bar. It moves the preview and the window with it."),
            ("#gfull .gsvg g.node.cur", "The row the board's cursor is on, ringed, which is how a graph this size stays a map of where you are."),
            ("#gwinfull", "From here the same graph moves into a window of its own; <b>close</b> or <kbd>Esc</kbd> goes back to the board. A click on a node closes the overlay on that ticket's row."),
        ],
    ),
    "window": (
        "the same graph in a window of its own, which sits beside the board",
        [
            (".gfbody g.node", "The same drawing, in a window the user sizes and keeps open beside the board. It follows the board's cursor, its mode and its colour scheme; what runs past the edge is scrolled to or dragged into view, as in the overlay."),
            (".seg", "The switch works here too, and moves the board's own graph with it."),
            (".gfbody g.node.cur", "A click on a node leaves this window where it is and moves the board behind it to that ticket's row."),
        ],
    ),
}


@dataclass
class Args:
    before: str = "5ced2d5"
    """The commit the `before` panel is rendered from: the board as this slice was cut from it."""
    work: Path = Path("/tmp/board-graph-figure")
    """Where the demo tracker, the two boards and the screenshots are built and left."""


def run(*args: object, **kwargs) -> subprocess.CompletedProcess:
    done = subprocess.run([str(a) for a in args], capture_output=True, **{"text": True, **kwargs})
    assert done.returncode == 0, f"{args[0]} failed: {str(done.stderr)[-2000:]}"
    return done


def board_at(ref: str, work: Path) -> Path:
    """The board as `ref` had it, with the rest of its directory, since the board imports its siblings."""
    tree = work / "before-tree"
    tree.mkdir(parents=True, exist_ok=True)
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", ref, "mx/skills/tracker"], capture_output=True)
    run("tar", "-x", "-C", str(tree), input=tar.stdout, text=False)
    return tree / "mx" / "skills" / "tracker" / "board.py"


def render(board: Path, tracker: Path, out: Path, config: Path) -> Path:
    run("uv", "run", board, tracker, "--no-watch", "--no-open", "--out", out,
        env={**os.environ, "CLAUDE_CONFIG_DIR": str(config)})
    return out


def shot(page: Page, png: Path, notes: list[tuple[str, str]], clip_to: str | None) -> dict:
    """One panel: the page as it stands, and where on it each note's badge belongs, in fractions of
    the image so the figure can scale it."""
    clip = None
    if clip_to:
        box = page.locator(clip_to).bounding_box()
        clip = {"x": box["x"] - PAD, "y": box["y"] - PAD, "width": box["width"] + 2 * PAD, "height": box["height"] + 2 * PAD}
    page.screenshot(path=png, clip=clip)
    frame = clip or {"x": 0, "y": 0, **page.viewport_size}
    badges = []
    for selector, _ in notes:
        box = page.locator(selector).first.bounding_box()
        assert box, f"nothing at {selector} to point at"
        badges.append(((box["x"] - frame["x"]) / frame["width"], (box["y"] - frame["y"]) / frame["height"]))
    return {"png": png, "badges": badges}


def capture(before: Path, after: Path, work: Path, scheme: str) -> dict:
    """The four panels in one scheme, each driven to the state it shows."""
    shots = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("chromium"))
        page = browser.new_context(viewport=WIDE).new_page()

        page.goto(f"{before.as_uri()}?theme={scheme}#{ROW}", wait_until="networkidle")
        page.wait_for_selector(".side .mermaid svg")
        shots["before"] = shot(page, work / f"before-{scheme}.png", PANELS["before"][1], ".side")

        page.goto(f"{after.as_uri()}?theme={scheme}#{ROW}", wait_until="networkidle")
        page.wait_for_selector(".side .mermaid svg")
        shots["preview"] = shot(page, work / f"preview-{scheme}.png", PANELS["preview"][1], ".side")

        page.click("#gopen")
        page.wait_for_selector("#gfull .gsvg svg")
        page.click("#gfull [data-gmode=all]")
        page.wait_for_selector("#gfull .gsvg g.node.cur")
        shots["overlay"] = shot(page, work / f"overlay-{scheme}.png", PANELS["overlay"][1], None)

        with page.expect_popup() as popped:
            page.click("#gwinfull")
        win = popped.value
        win.set_viewport_size({"width": 900, "height": 440})
        win.wait_for_selector(".gfbody g.node.cur")
        shots["window"] = shot(win, work / f"window-{scheme}.png", PANELS["window"][1], None)
        browser.close()
    return shots


def panel(key: str, schemes: dict[str, dict]) -> str:
    """One panel: both schemes' images stacked, the badges over them, and the numbered notes."""
    what, notes = PANELS[key]
    images = "".join(
        f'<img class="{scheme}" src="data:image/png;base64,{base64.b64encode(shots[key]["png"].read_bytes()).decode()}" alt="{what}">'
        for scheme, shots in schemes.items()
    )
    badges = "".join(
        f'<span class="mk over" style="left: {x:.3%}; top: {y:.3%}">{n + 1}</span>'
        for n, (x, y) in enumerate(schemes["day"][key]["badges"])
    )
    items = "".join(f'<li><span class="mk">{n + 1}</span><span>{note}</span></li>' for n, (_, note) in enumerate(notes))
    return (
        f'<figure class="panel"><figcaption><b>{key}</b> — {what}</figcaption>'
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
<title>The dependency graph on the board, before and after</title>
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
<h1>The dependency graph on the board, before and after</h1>
<p class="lead">One demo tracker, rendered by the board as this slice was cut from it and by the
board now. Each panel is a browser screenshot of the state the caption names, with a badge where
each note points.</p>
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
