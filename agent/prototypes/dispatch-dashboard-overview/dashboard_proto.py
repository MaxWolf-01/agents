#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown"]
# ///
"""PROTOTYPE — throwaway variant explorer for the dispatch dashboard. Not the real renderer.

Three overview variants on one page, switchable via ?variant= and a floating bar:
  a — full DAG (ELK orthogonal), done tickets ghosted
  b — frontier DAG: undone tickets + their direct blockers only
  c — wave lanes: no graph, remaining tickets in topological lanes

Shared in all variants: expandable ticket bodies, collapsed done fold, and
anchor links from graph nodes / strip cells / dep chips to the ticket row.
"""

import datetime
import html
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Annotated

import markdown
import tyro
import yaml

STATUS_SYMBOL = {"done": "✓", "claimed": "⟳", "open": "○", "blocked": "⊘"}


@dataclass
class Args:
    tasks_dir: Annotated[Path, tyro.conf.Positional]
    """Feature tasks directory, e.g. agent/tasks/<feature>."""
    out: Path | None = None
    """Output HTML path. Default: ~/Downloads/dispatch-proto-<feature>.html."""
    repo: Path | None = None
    """Repo for the commit log. Default: three levels above tasks_dir."""
    needs_human: Annotated[list[str], tyro.conf.UseAppendAction] = field(default_factory=list)
    """Needs-human queue entry; repeat the flag for multiple entries."""


def main(args: Args) -> None:
    feature = args.tasks_dir.name
    out = args.out or Path.home() / "Downloads" / f"dispatch-proto-{feature}.html"
    repo = args.repo or args.tasks_dir.parent.parent.parent
    tickets = load_tickets(args.tasks_dir)
    assert tickets, f"no NN-<slug>.md tickets in {args.tasks_dir}"
    out.write_text(render_page(feature, tickets, args.needs_human, git_log(repo)))
    print(out)


@dataclass
class Ticket:
    num: str
    title: str
    status: str  # open | claimed | done, plus derived: blocked
    blocked_by: list[str]
    body_html: str


def load_tickets(tasks_dir: Path) -> list[Ticket]:
    tickets = []
    for path in sorted(tasks_dir.glob("[0-9][0-9]-*.md")):
        meta, body = split_frontmatter(path.read_text())
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        body = body[heading.end():] if heading else body
        tickets.append(
            Ticket(
                num=path.name[:2],
                title=heading.group(1).strip() if heading else path.stem[3:].replace("-", " "),
                status=str(meta.get("status", "open")),
                blocked_by=[normalize_num(n) for n in meta.get("blocked-by") or []],
                body_html=render_body(body),
            )
        )
    done = {t.num for t in tickets if t.status == "done"}
    for t in tickets:
        if t.status == "open" and any(b not in done for b in t.blocked_by):
            t.status = "blocked"
    return tickets


def render_body(md: str) -> str:
    out = markdown.markdown(md, extensions=["fenced_code", "tables"])
    # cross-ticket links (47-event-union-v2.md) become in-page anchors
    return re.sub(r'href="(?:[\w./-]*/)?(\d\d)-[\w-]*\.md"', r'href="#t\1"', out)


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"\A---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def normalize_num(n: object) -> str:
    return f"{int(n):02d}" if isinstance(n, int) else str(n).zfill(2)


def git_log(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline", "-n", "15"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"git log failed in {repo}: {result.stderr.strip()}"
    return result.stdout


# ---- overview variants ----------------------------------------------------


def mermaid_dag(tickets: list[Ticket], include: set[str], ghost: set[str]) -> str:
    lines = ["flowchart LR"]
    for t in tickets:
        if t.num not in include:
            continue
        label = f"{t.num} {t.title}".replace('"', "#quot;")
        cls = "ghost" if t.num in ghost else t.status
        lines.append(f'  T{t.num}["{STATUS_SYMBOL[t.status]} {label}"]:::{cls}')
    for t in tickets:
        if t.num not in include:
            continue
        lines.extend(f"  T{b} --> T{t.num}" for b in t.blocked_by if b in include)
    for t in tickets:
        if t.num in include:
            lines.append(f'  click T{t.num} "#t{t.num}"')
    return "\n".join(lines)


def variant_full(tickets: list[Ticket]) -> str:
    nums = {t.num for t in tickets}
    ghost = {t.num for t in tickets if t.status == "done"}
    return mermaid_dag(tickets, nums, ghost)


def variant_frontier(tickets: list[Ticket]) -> str:
    live = {t.num for t in tickets if t.status != "done"}
    by_num = {t.num: t for t in tickets}
    ghost = {b for t in tickets if t.num in live for b in t.blocked_by if by_num[b].status == "done"}
    return mermaid_dag(tickets, live | ghost, ghost)


def variant_lanes(tickets: list[Ticket]) -> str:
    by_num = {t.num: t for t in tickets}
    live = [t for t in tickets if t.status != "done"]
    depth: dict[str, int] = {}

    def wave(t: Ticket) -> int:
        if t.num not in depth:
            depth[t.num] = 0  # break cycles defensively
            pending = [by_num[b] for b in t.blocked_by if by_num[b].status != "done"]
            depth[t.num] = 1 + max((wave(p) for p in pending), default=-1)
        return depth[t.num]

    lanes: dict[int, list[Ticket]] = {}
    for t in live:
        lanes.setdefault(wave(t), []).append(t)

    def card(t: Ticket) -> str:
        chips = "".join(
            f'<a class="chip {by_num[b].status}" href="#t{b}">{b}</a>' for b in t.blocked_by
        )
        deps = f'<span class="chips">{chips}</span>' if chips else ""
        return (
            f'<div class="card {t.status}">'
            f'<a class="cardlink" href="#t{t.num}">'
            f'<span class="cardnum">{STATUS_SYMBOL[t.status]} {t.num}</span>'
            f'<span class="cardtitle">{html.escape(t.title)}</span></a>{deps}</div>'
        )

    names = {0: "now — in flight / ready"}
    sections = []
    for d in sorted(lanes):
        label = names.get(d, f"wave +{d}")
        cards = "".join(card(t) for t in sorted(lanes[d], key=lambda t: (t.status != "claimed", t.num)))
        sections.append(f'<div class="lane"><div class="lanelabel">{label}</div><div class="lanecards">{cards}</div></div>')
    return "".join(sections)


# ---- page -----------------------------------------------------------------


def render_page(feature: str, tickets: list[Ticket], needs_human: list[str], log: str) -> str:
    by_num = {t.num: t for t in tickets}
    counts = Counter(t.status for t in tickets)
    meta = f"{counts['done']}/{len(tickets)} done"
    for status in ("claimed", "open", "blocked"):
        if counts[status]:
            meta += f" · {counts[status]} {status}"
    if needs_human:
        meta += f' · <a href="#needs-human">● {len(needs_human)} need human</a>'
    meta += f" · rendered {datetime.datetime.now():%Y-%m-%d %H:%M:%S}"

    strip = "".join(
        f'<a class="cell {t.status}" href="#t{t.num}" title="{html.escape(t.num + " " + t.title)} — {t.status}">{t.num}</a>'
        for t in tickets
    )

    def row(t: Ticket) -> str:
        chips = "".join(
            f'<a class="chip {by_num[b].status}" href="#t{b}">{b}</a>' for b in t.blocked_by
        ) or '<span class="deps">—</span>'
        return (
            f'<details class="ticket row-{t.status}" id="t{t.num}"><summary>'
            f'<span class="num">{t.num}</span><span class="title">{html.escape(t.title)}</span>'
            f'<span class="badge {t.status}">{STATUS_SYMBOL[t.status]} {t.status}</span>'
            f'<span class="chips">{chips}</span></summary>'
            f'<div class="body">{t.body_html}</div></details>'
        )

    order = {"claimed": 0, "open": 1, "blocked": 2}
    active = [t for t in tickets if t.status != "done"]
    active.sort(key=lambda t: (order[t.status], t.num))
    active_rows = "".join(row(t) for t in active)
    done_rows = "".join(row(t) for t in tickets if t.status == "done")
    done_fold = (
        f'<details class="done-fold"><summary>{counts["done"]} done tickets</summary>{done_rows}</details>'
        if done_rows else ""
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
        feature=html.escape(feature), meta=meta, strip=strip,
        active_rows=active_rows, done_fold=done_fold, needs=needs, log=log_html,
        dag_full=variant_full(tickets), dag_frontier=variant_frontier(tickets),
        lanes=variant_lanes(tickets),
    )


PAGE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>dispatch proto — ${feature}</title>
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
    --ghost-bg: #f7f8fa; --ghost-br: #d4dae3; --ghost-tx: #9aa5b4;
    --human: #c03535; --human-bg: #fbe9e9; --flash: #fdf0d5;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0d1320; --panel: #151d2b; --line: #26324a; --ink: #dfe6f2; --muted: #8b96a8; --edge: #4d5c74;
      --done-bg: #12321f; --done-br: #2f9e5f; --done-tx: #7fe0a7;
      --claimed-bg: #3a2a10; --claimed-br: #c9932e; --claimed-tx: #f0c46a;
      --open-bg: #10293c; --open-br: #3e87c2; --open-tx: #86c5ee;
      --blocked-bg: #1b2230; --blocked-br: #3a4453; --blocked-tx: #7a8698;
      --ghost-bg: #131a27; --ghost-br: #26324a; --ghost-tx: #55617a;
      --human: #e25b5b; --human-bg: #3a1414; --flash: #3a2a10;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: "IBM Plex Sans", system-ui, sans-serif; font-size: 15px; line-height: 1.55;
    background: var(--bg); color: var(--ink); max-width: 64rem; margin: 2.5rem auto 6rem; padding: 0 1.25rem;
  }
  .eyebrow, h1, h2, .meta, .strip, .badge, .num, .deps, .chip, .log, .mermaid, .cardnum, .lanelabel, #switcher { font-family: "IBM Plex Mono", ui-monospace, monospace; }

  .eyebrow { text-transform: uppercase; letter-spacing: .24em; font-size: .68rem; color: var(--muted); margin: 0 0 .35rem; }
  .masthead { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem 2rem; flex-wrap: wrap; }
  h1 { font-size: 1.55rem; font-weight: 600; margin: 0; }
  .strip { display: flex; gap: 2px; flex-wrap: wrap; }
  .cell { min-width: 2em; text-align: center; font-size: .68rem; padding: .18rem .2rem; border: 1px solid; border-radius: 4px; text-decoration: none; }
  .meta { color: var(--muted); font-size: .74rem; margin: .6rem 0 0; }
  .meta a { color: var(--human); font-weight: 600; text-decoration: none; }
  .meta a:hover { text-decoration: underline; }

  h2 {
    text-transform: uppercase; letter-spacing: .2em; font-size: .7rem; font-weight: 500;
    color: var(--muted); margin: 2.4rem 0 .8rem; display: flex; align-items: center; gap: .8rem;
  }
  h2::after { content: ""; flex: 1; border-top: 1px solid var(--line); }

  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
  .board { padding: 1rem; overflow-x: auto; }
  .mermaid { margin: 0; display: flex; justify-content: center; color: var(--muted); }
  .variant { display: none; }
  .variant.active { display: block; }

  .done { background: var(--done-bg); border-color: var(--done-br); color: var(--done-tx); }
  .claimed { background: var(--claimed-bg); border-color: var(--claimed-br); color: var(--claimed-tx); }
  .open { background: var(--open-bg); border-color: var(--open-br); color: var(--open-tx); }
  .blocked { background: var(--blocked-bg); border-color: var(--blocked-br); color: var(--blocked-tx); }

  /* lanes (variant c) */
  .lane { display: flex; gap: 1rem; padding: .7rem 0; border-bottom: 1px dashed var(--line); align-items: baseline; }
  .lane:last-child { border-bottom: 0; }
  .lanelabel { flex: 0 0 9.5rem; text-transform: uppercase; letter-spacing: .14em; font-size: .64rem; color: var(--muted); padding-top: .5rem; }
  .lanecards { display: flex; flex-wrap: wrap; gap: .5rem; flex: 1; }
  .card { display: flex; flex-direction: column; gap: .15rem; border: 1px solid; border-radius: 6px; padding: .45rem .65rem; max-width: 15rem; }
  .cardlink { display: flex; flex-direction: column; gap: .15rem; text-decoration: none; color: inherit; }
  .cardnum { font-size: .68rem; opacity: .8; }
  .cardtitle { font-size: .8rem; line-height: 1.35; }
  .card .chips { margin-top: .2rem; justify-content: flex-start; min-width: 0; }

  /* ticket rows */
  .ticket { border-bottom: 1px solid var(--line); }
  .ticket summary {
    display: grid; grid-template-columns: 2.2rem 1fr auto auto; gap: .8rem; align-items: baseline;
    padding: .45rem .3rem; cursor: pointer; list-style: none;
  }
  .ticket summary::-webkit-details-marker { display: none; }
  .ticket summary:hover { background: var(--panel); }
  .ticket .num { color: var(--muted); font-size: .8rem; }
  .row-done summary .title { color: var(--muted); }
  .badge { display: inline-block; border: 1px solid; padding: .02rem .55rem; border-radius: 99px; font-size: .72rem; white-space: nowrap; }
  .chips { display: inline-flex; gap: .25rem; min-width: 5rem; justify-content: flex-end; }
  .chip { border: 1px solid; border-radius: 4px; font-size: .68rem; padding: 0 .3rem; text-decoration: none; }
  .deps { color: var(--muted); font-size: .8rem; }
  .ticket .body {
    padding: .2rem 1rem 1rem 3rem; font-size: .88rem; color: var(--ink);
    border-left: 3px solid var(--line); margin: 0 0 .8rem .6rem;
  }
  .ticket .body h2 { text-transform: none; letter-spacing: 0; font-size: .95rem; font-family: "IBM Plex Sans", sans-serif; color: var(--ink); margin: 1rem 0 .3rem; }
  .ticket .body h2::after { display: none; }
  .ticket .body code { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 0 .25rem; font-size: .82em; }
  .ticket .body pre code { display: block; padding: .6rem .8rem; overflow-x: auto; }
  .ticket .body a { color: var(--open-tx); }
  .ticket.flash > summary { background: var(--flash); transition: background .2s; }
  .done-fold > summary {
    cursor: pointer; color: var(--muted); font-family: "IBM Plex Mono", monospace; font-size: .78rem;
    text-transform: uppercase; letter-spacing: .14em; padding: .7rem .3rem;
  }

  .needs-human { padding: 0; margin: 0; }
  .needs-human li {
    list-style: none; background: var(--human-bg); border-left: 3px solid var(--human);
    border-radius: 0 6px 6px 0; padding: .45rem .8rem; margin: .4rem 0; font-size: .9rem;
  }
  .log { padding: .9rem 1.1rem; margin: 0; font-size: .8rem; line-height: 1.75; overflow-x: auto; }
  .hash { color: var(--claimed-br); }

  #switcher {
    position: fixed; bottom: 1.2rem; left: 50%; transform: translateX(-50%);
    display: flex; align-items: center; gap: .8rem; background: var(--ink); color: var(--bg);
    padding: .4rem 1rem; border-radius: 99px; font-size: .78rem; box-shadow: 0 4px 16px rgba(0,0,0,.35); z-index: 10;
  }
  #switcher button { background: none; border: 0; color: inherit; font: inherit; cursor: pointer; padding: 0 .2rem; }
</style>
</head>
<body>
<header>
  <p class="eyebrow">dispatch · wave board · PROTOTYPE</p>
  <div class="masthead">
    <h1>${feature}</h1>
    <div class="strip">${strip}</div>
  </div>
  <p class="meta">${meta}</p>
</header>

<section class="variant" data-variant="a">
  <h2>Dependency graph — full</h2>
  <div class="panel board"><pre class="mermaid">${dag_full}</pre></div>
</section>
<section class="variant" data-variant="b">
  <h2>Dependency graph — frontier</h2>
  <div class="panel board"><pre class="mermaid">${dag_frontier}</pre></div>
</section>
<section class="variant" data-variant="c">
  <h2>Waves</h2>
  <div class="panel board">${lanes}</div>
</section>

${needs}

<section>
  <h2>Tickets</h2>
  <div class="tickets">
  ${active_rows}
  ${done_fold}
  </div>
</section>

<section>
  <h2>Recent commits</h2>
  <pre class="panel log">${log}</pre>
</section>

<div id="switcher">
  <button id="prev">◀</button>
  <span id="vlabel"></span>
  <button id="next">▶</button>
</div>

<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  import elkLayouts from "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0/dist/mermaid-layout-elk.esm.min.mjs";
  mermaid.registerLayoutLoaders(elkLayouts);

  const css = getComputedStyle(document.body);
  const v = (name) => css.getPropertyValue(name).trim();
  const classDefs = ["done", "claimed", "open", "blocked", "ghost"].map((s) =>
    "  classDef " + s + " fill:" + v("--" + s + "-bg") + ",stroke:" + v("--" + s + "-br") + ",color:" + v("--" + s + "-tx")
  ).join("\\n") + "\\n  classDef ghost stroke-dasharray:4 3";
  mermaid.initialize({
    startOnLoad: false, layout: "elk", securityLevel: "loose", theme: "base",
    elk: { mergeEdges: false },
    themeVariables: {
      fontFamily: "'IBM Plex Mono', ui-monospace, monospace", fontSize: "13px",
      primaryColor: v("--panel"), primaryTextColor: v("--ink"),
      primaryBorderColor: v("--line"), lineColor: v("--edge"),
    },
  });

  const rendered = new Set();
  async function renderGraphs(section) {
    for (const el of section.querySelectorAll(".mermaid")) {
      if (rendered.has(el)) continue;
      rendered.add(el);
      el.textContent += "\\n" + classDefs;
      await mermaid.run({ nodes: [el] });
    }
  }

  const variants = [["a", "full graph"], ["b", "frontier graph"], ["c", "wave lanes"]];
  let current = new URLSearchParams(location.search).get("variant") ?? "b";
  if (!variants.some(([k]) => k === current)) current = "b";
  async function activate(key) {
    current = key;
    for (const s of document.querySelectorAll(".variant"))
      s.classList.toggle("active", s.dataset.variant === key);
    const section = document.querySelector('.variant[data-variant="' + key + '"]');
    document.getElementById("vlabel").textContent = key + " — " + variants.find(([k]) => k === key)[1];
    try { history.replaceState(null, "", "?variant=" + key + location.hash); } catch {}
    await renderGraphs(section);
  }
  function cycle(delta) {
    const i = variants.findIndex(([k]) => k === current);
    activate(variants[(i + delta + variants.length) % variants.length][0]);
  }
  document.getElementById("prev").addEventListener("click", () => cycle(-1));
  document.getElementById("next").addEventListener("click", () => cycle(1));
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, [contenteditable]")) return;
    if (e.key === "ArrowLeft") cycle(-1);
    if (e.key === "ArrowRight") cycle(1);
  });
  activate(current);

  // anchor navigation: open the target ticket (and any enclosing fold), flash it
  function openTarget() {
    const el = document.getElementById(location.hash.slice(1));
    if (!el) return;
    for (let d = el; d; d = d.parentElement) if (d.tagName === "DETAILS") d.open = true;
    el.scrollIntoView({ block: "start" });
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 1200);
  }
  window.addEventListener("hashchange", openTarget);
  if (location.hash) openTarget();
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
