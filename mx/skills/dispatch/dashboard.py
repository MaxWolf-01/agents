#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml"]
# ///
"""Render the dispatch status dashboard for a feature's ticket DAG.

Reads ticket files (NN-<slug>.md with status/blocked-by frontmatter) from a
feature's tasks directory and writes a self-contained HTML page: the dependency
DAG as a mermaid diagram (ticket number + title, colored by status), a ticket
table, the needs-human queue, and recent commits of the repo's checked-out branch.
The page auto-refreshes every 30s, so one open tab stays current across renders.

Examples:

    uv run dashboard.py agent/tasks/my-feature
    uv run dashboard.py agent/tasks/my-feature --needs-human "ticket 03: design call on retry semantics"
    uv run dashboard.py agent/tasks/my-feature --out /tmp/dash.html --open never
"""

import datetime
import html
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Annotated, Literal

import tyro
import yaml

STATUS_SYMBOL = {"done": "✓", "claimed": "⟳", "open": "○", "blocked": "⊘"}


@dataclass
class Args:
    tasks_dir: Annotated[Path, tyro.conf.Positional]
    """Feature tasks directory, e.g. agent/tasks/<feature>."""
    out: Path | None = None
    """Output HTML path. Default: ~/Downloads/dispatch-<feature>.html."""
    repo: Path | None = None
    """Repo for the commit log. Default: three levels above tasks_dir."""
    needs_human: Annotated[list[str], tyro.conf.UseAppendAction] = field(default_factory=list)
    """Needs-human queue entry; repeat the flag for multiple entries."""
    open: Literal["auto", "always", "never"] = "auto"
    """xdg-open the result: auto = only when the output file is new."""


def main(args: Args) -> None:
    feature = args.tasks_dir.name
    out = args.out or Path.home() / "Downloads" / f"dispatch-{feature}.html"
    repo = args.repo or args.tasks_dir.parent.parent.parent
    tickets = load_tickets(args.tasks_dir)
    assert tickets, f"no NN-<slug>.md tickets in {args.tasks_dir}"
    page = render_page(feature, tickets, args.needs_human, git_log(repo))
    existed = out.exists()
    out.write_text(page)
    print(out)
    if args.open == "always" or (args.open == "auto" and not existed):
        subprocess.Popen(["xdg-open", str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@dataclass
class Ticket:
    num: str
    title: str
    status: str  # open | claimed | done, plus derived: blocked
    blocked_by: list[str]


def load_tickets(tasks_dir: Path) -> list[Ticket]:
    tickets = []
    for path in sorted(tasks_dir.glob("[0-9][0-9]-*.md")):
        meta, body = split_frontmatter(path.read_text())
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        tickets.append(
            Ticket(
                num=path.name[:2],
                title=heading.group(1).strip() if heading else path.stem[3:].replace("-", " "),
                status=str(meta.get("status", "open")),
                blocked_by=[normalize_num(n) for n in meta.get("blocked-by") or []],
            )
        )
    done = {t.num for t in tickets if t.status == "done"}
    for t in tickets:
        if t.status == "open" and any(b not in done for b in t.blocked_by):
            t.status = "blocked"
    return tickets


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"\A---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def normalize_num(n: object) -> str:
    # YAML reads `01` as int 1; ticket ids are two-digit strings.
    return f"{int(n):02d}" if isinstance(n, int) else str(n).zfill(2)


def git_log(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline", "-n", "15"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"git log failed in {repo}: {result.stderr.strip()}"
    return result.stdout


def render_page(feature: str, tickets: list[Ticket], needs_human: list[str], log: str) -> str:
    counts = Counter(t.status for t in tickets)
    meta = f"{counts['done']}/{len(tickets)} done"
    for status in ("claimed", "open", "blocked"):
        if counts[status]:
            meta += f" · {counts[status]} {status}"
    if needs_human:
        meta += f' · <a href="#needs-human">● {len(needs_human)} need human</a>'
    meta += f" · rendered {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · auto-refresh 30s"
    strip = "".join(
        f'<span class="cell {t.status}" title="{html.escape(t.num + " " + t.title)} — {t.status}">{t.num}</span>'
        for t in tickets
    )
    rows = "".join(
        f'<tr class="row-{t.status}"><td class="num">{t.num}</td><td class="title">{html.escape(t.title)}</td>'
        f'<td><span class="badge {t.status}">{STATUS_SYMBOL[t.status]} {t.status}</span></td>'
        f'<td class="deps">{", ".join(t.blocked_by) or "—"}</td></tr>'
        for t in tickets
    )
    needs = (
        '<section id="needs-human"><h2>Needs human</h2><ul class="needs-human">'
        + "".join(f"<li>{html.escape(item)}</li>" for item in needs_human)
        + "</ul></section>"
        if needs_human
        else ""
    )
    log_html = "\n".join(
        f'<span class="hash">{html.escape(line.split(" ")[0])}</span> {html.escape(line.partition(" ")[2])}'
        for line in log.strip().splitlines()
    )
    return PAGE.substitute(
        feature=html.escape(feature), meta=meta, strip=strip, rows=rows, needs=needs,
        log=log_html, dag=mermaid_dag(tickets),
    )


def mermaid_dag(tickets: list[Ticket]) -> str:
    lines = ["flowchart LR"]
    for t in tickets:
        label = f"{t.num} {t.title}".replace('"', "#quot;")
        lines.append(f'  T{t.num}["{STATUS_SYMBOL[t.status]} {label}"]:::{t.status}')
    for t in tickets:
        lines.extend(f"  T{b} --> T{t.num}" for b in t.blocked_by)
    # classDefs are appended in the page's JS — the palette lives in the CSS custom properties.
    return "\n".join(lines)


PAGE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>dispatch — ${feature}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root {
    color-scheme: light dark;
    --bg: #f3f5f8; --panel: #ffffff; --line: #dfe4ec; --ink: #1a2432; --muted: #5d6a7d; --edge: #8fa0b5;
    --done-bg: #e2f6e9; --done-br: #2c9257; --done-tx: #1e6b40;
    --claimed-bg: #fdf0d5; --claimed-br: #c08a1e; --claimed-tx: #7d5a11;
    --open-bg: #e2f0fb; --open-br: #2e79b5; --open-tx: #1d5c8f;
    --blocked-bg: #edf0f4; --blocked-br: #97a2b1; --blocked-tx: #5d6a7d;
    --human: #c03535; --human-bg: #fbe9e9;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0d1320; --panel: #151d2b; --line: #26324a; --ink: #dfe6f2; --muted: #8b96a8; --edge: #4d5c74;
      --done-bg: #12321f; --done-br: #2f9e5f; --done-tx: #7fe0a7;
      --claimed-bg: #3a2a10; --claimed-br: #c9932e; --claimed-tx: #f0c46a;
      --open-bg: #10293c; --open-br: #3e87c2; --open-tx: #86c5ee;
      --blocked-bg: #1b2230; --blocked-br: #3a4453; --blocked-tx: #7a8698;
      --human: #e25b5b; --human-bg: #3a1414;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: "IBM Plex Sans", system-ui, sans-serif; font-size: 15px; line-height: 1.55;
    background: var(--bg); color: var(--ink); max-width: 64rem; margin: 2.5rem auto 4rem; padding: 0 1.25rem;
  }
  .eyebrow, h1, h2, .meta, .strip, .badge, .num, .deps, .log, .mermaid { font-family: "IBM Plex Mono", ui-monospace, monospace; }

  .eyebrow { text-transform: uppercase; letter-spacing: .24em; font-size: .68rem; color: var(--muted); margin: 0 0 .35rem; }
  .masthead { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem 2rem; flex-wrap: wrap; }
  h1 { font-size: 1.55rem; font-weight: 600; margin: 0; }
  .strip { display: flex; gap: 2px; flex-wrap: wrap; }
  .cell { min-width: 2em; text-align: center; font-size: .68rem; padding: .18rem .2rem; border: 1px solid; border-radius: 4px; }
  .meta { color: var(--muted); font-size: .74rem; margin: .6rem 0 0; }
  .meta a { color: var(--human); font-weight: 600; text-decoration: none; }
  .meta a:focus-visible, .meta a:hover { text-decoration: underline; }

  h2 {
    text-transform: uppercase; letter-spacing: .2em; font-size: .7rem; font-weight: 500;
    color: var(--muted); margin: 2.4rem 0 .8rem; display: flex; align-items: center; gap: .8rem;
  }
  h2::after { content: ""; flex: 1; border-top: 1px solid var(--line); }

  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
  .board { padding: 1rem; overflow-x: auto; }
  .mermaid { margin: 0; display: flex; justify-content: center; color: var(--muted); }

  .done { background: var(--done-bg); border-color: var(--done-br); color: var(--done-tx); }
  .claimed { background: var(--claimed-bg); border-color: var(--claimed-br); color: var(--claimed-tx); }
  .open { background: var(--open-bg); border-color: var(--open-br); color: var(--open-tx); }
  .blocked { background: var(--blocked-bg); border-color: var(--blocked-br); color: var(--blocked-tx); }

  table { border-collapse: collapse; width: 100%; font-size: .9rem; }
  th, td { text-align: left; padding: .45rem 1rem .45rem 0; border-bottom: 1px solid var(--line); }
  th { font-family: "IBM Plex Mono", monospace; text-transform: uppercase; letter-spacing: .14em; font-size: .62rem; font-weight: 500; color: var(--muted); }
  .num, .deps { color: var(--muted); font-size: .8rem; }
  .row-done .title { color: var(--muted); }
  .badge { display: inline-block; border: 1px solid; padding: .02rem .55rem; border-radius: 99px; font-size: .72rem; white-space: nowrap; }

  .needs-human { padding: 0; margin: 0; }
  .needs-human li {
    list-style: none; background: var(--human-bg); border-left: 3px solid var(--human);
    border-radius: 0 6px 6px 0; padding: .45rem .8rem; margin: .4rem 0; font-size: .9rem;
  }
  .log { padding: .9rem 1.1rem; margin: 0; font-size: .8rem; line-height: 1.75; overflow-x: auto; }
  .hash { color: var(--claimed-br); }
</style>
</head>
<body>
<header>
  <p class="eyebrow">dispatch · wave board</p>
  <div class="masthead">
    <h1>${feature}</h1>
    <div class="strip">${strip}</div>
  </div>
  <p class="meta">${meta}</p>
</header>

<section>
  <h2>Dependency graph</h2>
  <div class="panel board"><pre class="mermaid">${dag}</pre></div>
</section>

<section>
  <h2>Tickets</h2>
  <table>
  <tr><th>#</th><th>Title</th><th>Status</th><th>Blocked by</th></tr>
  ${rows}
  </table>
</section>

${needs}

<section>
  <h2>Recent commits</h2>
  <pre class="panel log">${log}</pre>
</section>

<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  // Mermaid bakes colors into the SVG, so the palette is read off the CSS tokens at load time.
  const css = getComputedStyle(document.body);
  const v = (name) => css.getPropertyValue(name).trim();
  const classDefs = ["done", "claimed", "open", "blocked"].map((s) =>
    "  classDef " + s + " fill:" + v("--" + s + "-bg") + ",stroke:" + v("--" + s + "-br") + ",color:" + v("--" + s + "-tx")
  ).join("\\n");
  const el = document.querySelector(".mermaid");
  el.textContent += "\\n" + classDefs;
  mermaid.initialize({
    startOnLoad: false,
    theme: "base",
    themeVariables: {
      fontFamily: "'IBM Plex Mono', ui-monospace, monospace",
      fontSize: "13px",
      primaryColor: v("--panel"),
      primaryTextColor: v("--ink"),
      primaryBorderColor: v("--line"),
      lineColor: v("--edge"),
    },
  });
  mermaid.run({ nodes: [el] });
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
