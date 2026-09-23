#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["tyro"]
# ///
"""Write figure.html beside this file: what forty minutes of a tracker cost the briefing, before and after.

One run of events -- a build ruled on, a ticket reworded, a ticket claimed, then a closing comment
written over twenty minutes -- driven through each version of the schedule and drawn as two lanes.
The `before` lane is the rule as this branch was cut from it, read out of git and run, so it is what
the board did rather than an account of it; the `after` lane is the rule the user ruled on
2026-09-23. Every mark on either lane is a run of the model.

Examples:

    figure.py
    figure.py --before 298cff2
"""

import datetime
import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import tyro

HERE = Path(__file__).resolve().parent
TRACKER = HERE.parents[3] / "mx" / "skills" / "tracker"
sys.path.insert(0, str(TRACKER))

import briefing as ruled  # noqa: E402

START = datetime.datetime.fromisoformat("2026-09-23T09:00:00+02:00")
SPAN = 40  # minutes drawn

# What happens to the tracker, and what each thing is: a status moving, or prose being rewritten.
EVENTS = {2: ("status", "02 accepted"), 4: ("prose", "04 reworded"), 11: ("status", "04 claimed")}
COMMENT = range(16, 40, 4)  # a worker writing its closing comment: an edit every four minutes
COMMENT_SAID = "a closing comment written: an edit every four minutes, no status moving"

X0, PER, TOP = 240, 20, 112  # the axis: where minute 0 sits, a minute's width, the axis line
LANES = {"before": 200, "after": 292}  # where each lane's line sits
WIDE, HIGH = 1100, 436


@dataclass
class Args:
    before: str = "298cff2"
    """The commit the `before` lane's schedule is read from: the rule as this branch was cut from it."""
    out: Path = HERE / "figure.html"
    """Where the figure is written."""


def main(args: Args) -> None:
    was = schedule_at(args.before)
    lanes = {"before": drive(was, prose_counts=True), "after": drive(ruled, prose_counts=False)}
    args.out.write_text(page(lanes, args.before))
    print(args.out)


# ---- the two schedules, driven ---------------------------------------------


def schedule_at(commit: str) -> object:
    """The briefing's schedule as `commit` had it, imported from git rather than described."""
    src = subprocess.run(["git", "-C", str(HERE), "show", f"{commit}:mx/skills/tracker/briefing.py"],
                         capture_output=True, text=True, check=True).stdout
    spec = importlib.util.spec_from_loader("briefing_before", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(src, module.__dict__)  # noqa: S102 -- the repo's own file, at a commit this repo holds
    return module


def drive(schedule: object, prose_counts: bool) -> list[int]:
    """The minutes this schedule wrote a briefing in, over the run of events above.

    The board opens on a tracker with no briefing, which is a change either way, and every later
    minute asks the schedule what it owes the session, as the watcher's pass does."""
    cached, changed_at, runs = None, START, []
    for minute in range(SPAN + 1):
        now = START + timedelta(minutes=minute)
        kind = EVENTS.get(minute, ("prose", ""))[0] if minute in EVENTS or minute in COMMENT else None
        if kind and (prose_counts or kind == "status"):
            changed_at = now
        verb = schedule.on_change(cached, changed_at, now)
        if verb in ("fresh", "ping"):
            runs.append(minute)
            cached = schedule.Briefing("where things stand", now, "s", now, now, 0 if verb == "fresh" else cached.pings + 1)
    return runs


# ---- the drawing -----------------------------------------------------------


def x(minute: float) -> float:
    return X0 + PER * minute


def page(lanes: dict[str, list[int]], commit: str) -> str:
    return TEMPLATE.format(figure=svg(lanes), commit=commit,
                           before=len(lanes["before"]), after=len(lanes["after"]))


def svg(lanes: dict[str, list[int]]) -> str:
    marks = [
        *ticks(),          # connectors first: the event lines run under everything
        *lane_lines(),
        *runs(lanes),      # then the marks a lane carries
        *labels(lanes),    # then every label, whatever it belongs to
        *legend(),
    ]
    return (
        f'<svg viewBox="0 0 {WIDE} {HIGH}" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="the briefing\'s runs over forty minutes, before and after the ruling">\n  '
        + "\n  ".join(marks) + "\n</svg>"
    )


def ticks() -> list[str]:
    """One hairline per event, dropped through both lanes: solid where a status moved, dashed where
    prose was rewritten."""
    drawn = []
    for minute in sorted({*EVENTS, *COMMENT}):
        kind = EVENTS.get(minute, ("prose", ""))[0]
        dash = '' if kind == "status" else ' stroke-dasharray="4,4"'
        stroke = "var(--body)" if kind == "status" else "var(--edge)"
        drawn.append(f'<line x1="{x(minute)}" y1="{TOP - 16}" x2="{x(minute)}" y2="{LANES["after"] + 24}" '
                     f'stroke="{stroke}" stroke-width="1"{dash}/>')
    return drawn


def lane_lines() -> list[str]:
    drawn = [f'<line x1="{x(0)}" y1="{TOP}" x2="{x(SPAN)}" y2="{TOP}" stroke="var(--edge)" stroke-width="1"/>']
    for y in LANES.values():
        drawn.append(f'<line x1="{x(0)}" y1="{y}" x2="{x(SPAN)}" y2="{y}" stroke="var(--muted)" stroke-width="1.2"/>')
    return drawn


def runs(lanes: dict[str, list[int]]) -> list[str]:
    """A run of the model, which is what a briefing costs: the one thing the accent means here."""
    drawn = []
    for name, minutes in lanes.items():
        for minute in minutes:
            drawn.append(f'<circle cx="{x(minute)}" cy="{LANES[name]}" r="7" fill="var(--wash)" '
                         f'stroke="var(--accent)" stroke-width="1.2"/>')
    return drawn


def labels(lanes: dict[str, list[int]]) -> list[str]:
    """Every label in the figure, drawn after every line, so nothing is painted over."""
    drawn = []
    for minute in range(0, SPAN + 1, 4):  # the axis, in minutes
        drawn.append(text(x(minute), TOP + 24, str(minute), "meta", anchor="middle"))
    drawn.append(text(x(0) - 24, TOP + 24, "minutes", "meta", anchor="end"))
    for minute, (kind, said) in EVENTS.items():
        drawn.append(text(x(minute), TOP - 28 if kind == "status" else TOP - 52, said,
                          "event" if kind == "status" else "quiet"))
    drawn.append(text(x(COMMENT[0]), TOP - 28, COMMENT_SAID, "quiet"))
    for name, minutes in lanes.items():
        y = LANES[name]
        drawn.append(text(24, y - 16, name, "name"))
        drawn.append(text(24, y + 4, SAID[name], "role"))
        drawn.append(text(24, y + 24, UNDER[name], "role"))
        drawn.append(text(24, y + 46, f"{len(minutes)} runs of the model", "meta"))
    return drawn


SAID = {
    "before": "any edit under the tracker,",
    "after": "a status moving, five quiet",
}
UNDER = {  # the second line of a lane's role, which does not fit on one
    "before": "five minutes apart",
    "after": "minutes and ten apart",
}


def legend() -> list[str]:
    y = HIGH - 40
    drawn = [f'<line x1="24" y1="{y - 28}" x2="{WIDE - 24}" y2="{y - 28}" stroke="var(--edge)" stroke-width="1"/>']
    drawn.append(f'<circle cx="32" cy="{y - 4}" r="7" fill="var(--wash)" stroke="var(--accent)" stroke-width="1.2"/>')
    drawn.append(text(48, y, "a run of the model", "meta"))
    drawn.append(f'<line x1="228" y1="{y - 14}" x2="228" y2="{y + 6}" stroke="var(--body)" stroke-width="1"/>')
    drawn.append(text(240, y, "a ticket's status moved", "meta"))
    drawn.append(f'<line x1="468" y1="{y - 14}" x2="468" y2="{y + 6}" stroke="var(--edge)" stroke-width="1" stroke-dasharray="4,4"/>')
    drawn.append(text(480, y, "a ticket's prose edited", "meta"))
    return drawn


def text(at_x: float, at_y: float, said: str, role: str, anchor: str = "start") -> str:
    return f'<text x="{at_x}" y="{at_y}" class="{role}" text-anchor="{anchor}">{said}</text>'


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>the briefing's cadence, before and after</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
  <style>
    :root {{
      color-scheme: light dark;
      --ground: light-dark(#f4e4cd, #1a1714);
      --ground-2: light-dark(#eddabe, #201c18);
      --edge: light-dark(#cfbca3, #4a433b);
      --muted: light-dark(#5e5650, #b0a89e);
      --body: light-dark(#37261d, #ede3d2);
      --strong: light-dark(#22140b, #faf2dc);
      --accent: light-dark(#426724, #6ea444);
      --wash: light-dark(rgb(66 103 36 / 0.16), rgb(110 164 68 / 0.22));
      --font-body: "Newsreader", Georgia, serif;
      --font-mono: "IBM Plex Mono", ui-monospace, monospace;
    }}
    [data-theme="day"] {{ color-scheme: light; }}
    [data-theme="night"] {{ color-scheme: dark; }}
    body {{ margin: 0; background: var(--ground); color: var(--body);
           font: 400 19px/1.62 var(--font-body); -webkit-font-smoothing: antialiased; }}
    .page {{ max-width: 76rem; margin: 0 auto; padding: 2.5rem 2rem 4rem; }}
    .top {{ display: flex; align-items: baseline; gap: 2rem; }}
    h1 {{ font-weight: 600; font-size: 2rem; line-height: 1.12; letter-spacing: -0.022em;
         color: var(--strong); margin: 0; }}
    .lead {{ font-size: 1.14em; line-height: 1.55; margin: 1rem 0 0; max-width: 53rem; }}
    .meta {{ font-family: var(--font-mono); font-size: 0.8125rem; line-height: 1.5; color: var(--muted);
            margin: 0.75rem 0 0; }}
    .scheme {{ margin-left: auto; display: inline-flex; padding: 0.25rem; border: 0; background: none;
              color: var(--muted); cursor: pointer; transition: color 150ms; }}
    .scheme:hover {{ color: var(--accent); }}
    [data-theme="night"] .sun, [data-theme="day"] .moon {{ display: none; }}
    svg {{ width: 100%; height: auto; margin-top: 2.5rem; }}
    text {{ font-family: var(--font-body); }}
    .name {{ font-weight: 600; font-size: 15px; fill: var(--strong); }}
    .role {{ font-size: 13px; fill: var(--body); }}
    .event {{ font-size: 13px; fill: var(--body); }}
    .quiet {{ font-size: 13px; fill: var(--muted); }}
    .meta, text.meta {{ font-family: var(--font-mono); font-size: 12px; fill: var(--muted); }}
  </style>
</head>
<body>
  <div class="page">
    <div class="top">
      <h1>The briefing's cadence, before and after</h1>
      <button class="scheme" id="scheme" aria-label="switch to night">
        <svg class="sun" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
        <svg class="moon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>
      </button>
    </div>
    <p class="lead">Forty minutes of one tracker, driven through both schedules: two tickets change
      status, a brief is reworded, and a worker writes a closing comment. The briefing was rewritten
      {before} times under the rule as it was, and {after} under the one ruled on 2026-09-23.</p>
    <p class="meta">the before lane is mx/skills/tracker/briefing.py at {commit}, imported from git and run;
      the after lane is the same file on this branch</p>
    {figure}
  </div>
  <script>
    const root = document.documentElement
    const asked = new URLSearchParams(location.search).get("theme")
    const set = (night) => {{
      root.dataset.theme = night ? "night" : "day"
      document.getElementById("scheme").setAttribute("aria-label", night ? "switch to day" : "switch to night")
    }}
    document.getElementById("scheme").addEventListener("click", () => set(root.dataset.theme !== "night"))
    set(asked ? asked === "night" : matchMedia("(prefers-color-scheme: dark)").matches)
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
