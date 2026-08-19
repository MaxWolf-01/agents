#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown"]
# ///
"""Render the tracker board: one HTML page for a project's whole agent/tasks tree.

Reads every feature directory (NN-<slug>.md tickets with status/blocked-by
frontmatter, cross-feature refs as <feature>/NN) and every standalone task
(*.md at the tracker root) and writes one self-contained page: an all-features
dependency graph with feature subgraphs and cross-feature edges, the merged
needs-human queue, and a section per feature (graph, wave lanes, ticket rows).
One switcher (floating bar or arrow keys) cycles every graph on the page
through frontier / full / lanes at once.

Any agent that changes tracker state re-renders; the render is deterministic
from disk, so last-writer-wins is safe. Per-feature dispatcher state lives in
agent/tasks/<feature>/needs-human.md: optional YAML frontmatter (worker-host),
then one `- summary :: markdown detail` bullet per pending entry — an answered
entry is deleted, its answer lands in code or tickets.

The page polls a sidecar stamp file (written beside the HTML) every 30s and
reloads, preserving view state, only when content actually changed — one open
tab stays current across renders without flicker.

Examples:

    uv run dashboard.py agent/tasks
    uv run dashboard.py agent/tasks --out ~/Downloads/board.html --open never

The browser is firejailed to a home whitelist (~/Downloads, ~/Documents,
~/Pictures, ~/Music, ~/Videos, ~/repos) and a private /tmp. An --out anywhere
else renders fine and then cannot be opened.
"""

import datetime
import hashlib
import html
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Annotated, Literal

import markdown
import tyro
import yaml

STATUS_SYMBOL = {"done": "✓", "claimed": "⟳", "open": "○", "blocked": "⊘"}


@dataclass
class Args:
    tasks_root: Annotated[Path, tyro.conf.Positional]
    """Tracker root, e.g. agent/tasks — the whole board renders from here."""
    out: Path | None = None
    """Output HTML path. Default: ~/Downloads/dispatch-dashboard/<project>.html."""
    repo: Path | None = None
    """Repo for the commit log. Default: two levels above tasks_root."""
    open: Literal["auto", "always", "never"] = "auto"
    """xdg-open the result: auto = only when the output file is new."""


def main(args: Args) -> None:
    repo = (args.repo or args.tasks_root.parent.parent).resolve()
    project = repo.name
    features = load_features(args.tasks_root)
    tasks = load_tasks(args.tasks_root)
    assert features or tasks, f"no feature dirs or task files in {args.tasks_root}"
    log = git_log(repo)
    stamp = content_stamp(project, features, tasks, log)
    out = args.out or Path.home() / "Downloads" / "dispatch-dashboard" / f"{project}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    page = render_page(project, features, tasks, log, stamp, out.name + ".stamp.js")
    existed = out.exists()
    out.write_text(page)
    Path(str(out) + ".stamp.js").write_text(f'window.__dispatchStamp = "{stamp}";\n')
    print(out)
    if args.open == "always" or (args.open == "auto" and not existed):
        subprocess.Popen(["xdg-open", str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---- tracker state --------------------------------------------------------


@dataclass
class Ticket:
    num: str
    title: str
    status: str  # open | claimed | done, plus derived: blocked
    blocked_by: list[str]
    ext_by: list[tuple[str, str]]  # cross-feature blockers: (ref "<feature>/NN", status)
    body_html: str


@dataclass
class Feature:
    name: str
    tickets: list[Ticket]
    needs_human: list[str]
    worker_host: str | None


@dataclass
class Task:
    slug: str
    title: str
    status: str
    body_html: str


def load_features(root: Path) -> list[Feature]:
    features = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        tickets = load_tickets(d)
        if not tickets:
            continue
        assert_safe_name(d.name)
        needs_human, worker_host = load_needs_human(d / "needs-human.md")
        features.append(Feature(d.name, tickets, needs_human, worker_host))
    ids = [slug_id(f.name) for f in features]
    assert len(ids) == len(set(ids)), f"feature names collide as mermaid ids: {sorted(ids)}"
    return features


def assert_safe_name(name: str) -> None:
    # names ride into HTML attributes and mermaid click strings unescaped
    assert re.fullmatch(r"[A-Za-z0-9._-]+", name), f"unsafe tracker name: {name!r}"


def load_tasks(root: Path) -> list[Task]:
    tasks = []
    for path in sorted(root.glob("*.md")):
        assert_safe_name(path.stem)
        meta, body = split_frontmatter(path.read_text())
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        body = body[heading.end():] if heading else body
        tasks.append(
            Task(
                slug=path.stem,
                title=heading.group(1).strip() if heading else path.stem.replace("-", " "),
                status=str(meta.get("status", "open")),
                body_html=markdown.markdown(body, extensions=["fenced_code", "tables"]),
            )
        )
    return tasks


def load_needs_human(path: Path) -> tuple[list[str], str | None]:
    if not path.exists():
        return [], None
    meta, body = split_frontmatter(path.read_text())
    entries = [line[2:].strip() for line in body.splitlines() if line.startswith("- ")]
    host = meta.get("worker-host")
    return entries, str(host) if host else None


def load_tickets(tasks_dir: Path) -> list[Ticket]:
    tickets = []
    for path in sorted(tasks_dir.glob("[0-9][0-9]-*.md")):
        meta, body = split_frontmatter(path.read_text())
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        body = body[heading.end():] if heading else body
        blockers = meta.get("blocked-by") or []
        tickets.append(
            Ticket(
                num=path.name[:2],
                title=heading.group(1).strip() if heading else path.stem[3:].replace("-", " "),
                status=str(meta.get("status", "open")),
                blocked_by=[normalize_num(n) for n in blockers if "/" not in str(n)],
                ext_by=[(str(n), ext_status(tasks_dir, str(n))) for n in blockers if "/" in str(n)],
                body_html=render_body(body, tasks_dir.name),
            )
        )
    done = {t.num for t in tickets if t.status == "done"}
    for t in tickets:
        if t.status == "open" and (
            any(b not in done for b in t.blocked_by) or any(s != "done" for _, s in t.ext_by)
        ):
            t.status = "blocked"
    return tickets


def ext_status(tasks_dir: Path, ref: str) -> str:
    # Cross-feature blocker "<feature>/NN". A missing file counts as done: feature dirs
    # are retired only after shipping (tracker conventions).
    feature, num = ref.rsplit("/", 1)
    matches = sorted((tasks_dir.parent / feature).glob(f"{normalize_num(num)}-*.md"))
    if not matches:
        return "done"
    meta, _ = split_frontmatter(matches[0].read_text())
    return str(meta.get("status", "open"))


def render_body(md: str, feature: str) -> str:
    out = markdown.markdown(md, extensions=["fenced_code", "tables"])
    # cross-ticket links (47-event-union-v2.md) become in-page anchors
    return re.sub(r'href="(?:[\w./-]*/)?(\d\d)-[\w-]*\.md"', rf'href="#t-{feature}-\1"', out)


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"\A---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def normalize_num(n: object) -> str:
    # YAML reads `01` as int 1; ticket ids are two-digit strings.
    return f"{int(n):02d}" if isinstance(n, int) else str(n).zfill(2)


def content_stamp(project: str, features: list[Feature], tasks: list[Task], log: str) -> str:
    # everything the page shows except the render timestamp: an unchanged board
    # keeps its stamp, so the open tab knows not to reload
    key = repr((
        project,
        [(f.name, f.needs_human, f.worker_host,
          [(t.num, t.title, t.status, t.blocked_by, t.ext_by, t.body_html) for t in f.tickets])
         for f in features],
        [(k.slug, k.title, k.status, k.body_html) for k in tasks],
        log,
    ))
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def git_log(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline", "-n", "15"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"git log failed in {repo}: {result.stderr.strip()}"
    return result.stdout


# ---- graph views ----------------------------------------------------------


def slug_id(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", name)


def visible(tickets: list[Ticket], full: bool) -> tuple[set[str], set[str]]:
    """(include, ghost) node sets for one feature at the given depth."""
    if full:
        return {t.num for t in tickets}, {t.num for t in tickets if t.status == "done"}
    by_num = {t.num: t for t in tickets}
    live = {t.num for t in tickets if t.status != "done"}
    ghost = {b for t in tickets if t.num in live for b in t.blocked_by if by_num[b].status == "done"}
    return live | ghost, ghost


def node_lines(ns: str, feature: str, tickets: list[Ticket], include: set[str], ghost: set[str]) -> list[str]:
    # ns makes node ids unique per diagram instance: mermaid+elk contaminate across
    # diagrams on one page when two share a node id (DOM lookups hit the first SVG).
    fid = f"{ns}_{slug_id(feature)}"
    lines = []
    for t in tickets:
        if t.num not in include:
            continue
        label = f"{t.num} {t.title}".replace('"', "#quot;")
        cls = "ghost" if t.num in ghost else t.status
        lines.append(f'  T_{fid}_{t.num}["{STATUS_SYMBOL[t.status]} {label}"]:::{cls}')
    for t in tickets:
        if t.num not in include:
            continue
        lines.extend(f"  T_{fid}_{b} --> T_{fid}_{t.num}" for b in t.blocked_by if b in include)
    lines.extend(f'  click T_{fid}_{t.num} "#t-{feature}-{t.num}"' for t in tickets if t.num in include)
    return lines


def feature_dag(feature: Feature, full: bool) -> str:
    include, ghost = visible(feature.tickets, full)
    ns = "f1" if full else "f0"
    return "flowchart LR\n" + "\n".join(node_lines(ns, feature.name, feature.tickets, include, ghost))


def board_dag(features: list[Feature], tasks: list[Task], full: bool) -> str:
    ns = "b1" if full else "b0"
    lines = ["flowchart LR"]
    included: dict[str, set[str]] = {}
    for f in features:
        include, ghost = visible(f.tickets, full)
        included[f.name] = include
        if not include:
            continue
        lines.append(f'  subgraph S_{ns}_{slug_id(f.name)}["{f.name}"]')
        lines.extend(node_lines(ns, f.name, f.tickets, include, ghost))
        lines.append("  end")
    show_tasks = [k for k in tasks if full or k.status != "done"]
    if show_tasks:
        lines.append(f'  subgraph S_{ns}__tasks["tasks"]')
        for k in show_tasks:
            label = k.title.replace('"', "#quot;")
            cls = "ghost" if k.status == "done" else k.status
            lines.append(f'  K_{ns}_{slug_id(k.slug)}["{STATUS_SYMBOL[k.status]} {label}"]:::{cls}')
            lines.append(f'  click K_{ns}_{slug_id(k.slug)} "#task-{k.slug}"')
        lines.append("  end")
    # cross-feature edges, drawn where both endpoints are on the board
    for f in features:
        for t in f.tickets:
            if t.num not in included[f.name]:
                continue
            for ref, _ in t.ext_by:
                src_feat, src_num = ref.rsplit("/", 1)
                if src_num in included.get(src_feat, set()):
                    lines.append(f"  T_{ns}_{slug_id(src_feat)}_{normalize_num(src_num)} --> T_{ns}_{slug_id(f.name)}_{t.num}")
    return "\n".join(lines)


def wave_lanes(feature: Feature) -> str:
    tickets = feature.tickets
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
        chips = dep_chips(feature.name, by_num, t)
        deps = f'<span class="chips">{chips}</span>' if chips else ""
        return (
            f'<div class="card {t.status}">'
            f'<a class="cardlink" href="#t-{feature.name}-{t.num}">'
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


def dep_chips(feature: str, by_num: dict[str, Ticket], t: Ticket) -> str:
    local = "".join(
        f'<a class="chip {by_num[b].status}" href="#t-{feature}-{b}">{b}</a>' for b in t.blocked_by
    )
    ext = "".join(
        f'<a class="chip {s}" href="#t-{ref.rsplit("/", 1)[0]}-{normalize_num(ref.rsplit("/", 1)[1])}" '
        f'title="cross-feature blocker">{html.escape(ref)}</a>'
        for ref, s in t.ext_by
    )
    return local + ext


# ---- page -----------------------------------------------------------------


def graph_views(sec_id: str, frontier: str, full: str, lanes: str | None) -> str:
    def view(key: str, inner: str, mermaid: bool) -> str:
        content = f'<pre class="mermaid" data-key="{sec_id}:{key}">{inner}</pre>' if mermaid else inner
        return f'<div class="view" data-view="{key}"><div class="panel board">{content}</div></div>'

    out = view("frontier", frontier, True) + view("full", full, True)
    if lanes is not None:
        out += view("lanes", lanes, False)
    return out


def render_page(
    project: str, features: list[Feature], tasks: list[Task], log: str, stamp: str, stamp_src: str
) -> str:
    total = sum(len(f.tickets) for f in features)
    total_done = sum(1 for f in features for t in f.tickets if t.status == "done")
    all_needs = [(f.name, item) for f in features for item in f.needs_human]
    meta = f"{len(features)} features · {total_done}/{total} tickets done"
    if tasks:
        n = sum(1 for k in tasks if k.status != "done")
        meta += f" · {n} standalone task{'s' if n != 1 else ''}"
    if all_needs:
        meta += f' · <a href="#needs-human">● {len(all_needs)} need human</a>'
    meta += f" · rendered {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · refreshes on change"

    nav = "".join(
        f'<a class="cell open" href="#f-{f.name}">{html.escape(f.name)} '
        f"{sum(1 for t in f.tickets if t.status == 'done')}/{len(f.tickets)}</a>"
        for f in features
    )

    board = (
        f'<section class="viewgroup" id="sec-board"><h2>Board</h2>'
        + graph_views("sec-board", board_dag(features, tasks, False), board_dag(features, tasks, True), None)
        + "</section>"
    )

    def needs_item(feature: str, item: str) -> str:
        chip = f'<a class="chip open" href="#f-{feature}">{html.escape(feature)}</a> '
        summary, sep, detail = item.partition(" :: ")
        if not sep:
            return f"<li>{chip}{html.escape(item)}</li>"
        return (
            f"<li><details><summary>{chip}{html.escape(summary)}</summary>"
            f'<div class="needs-detail">{markdown.markdown(detail, extensions=["fenced_code"])}</div>'
            "</details></li>"
        )

    needs = (
        '<section id="needs-human"><h2>Needs human</h2><ul class="needs-human">'
        + "".join(needs_item(f, item) for f, item in all_needs)
        + "</ul></section>"
        if all_needs
        else ""
    )

    sections = "".join(feature_section(f) for f in features)

    task_rows = "".join(
        f'<details class="ticket row-{k.status}" id="task-{k.slug}"><summary>'
        f'<span class="num">·</span><span class="title">{html.escape(k.title)}</span>'
        f'<span class="badge {k.status}">{STATUS_SYMBOL[k.status]} {k.status}</span>'
        f'<span class="deps">—</span></summary>'
        f'<div class="body">{k.body_html}</div></details>'
        for k in tasks
    )
    tasks_sec = f'<section><h2>Standalone tasks</h2><div class="tickets">{task_rows}</div></section>' if tasks else ""

    log_html = "\n".join(
        f'<span class="hash">{html.escape(line.split(" ")[0])}</span> {html.escape(line.partition(" ")[2])}'
        for line in log.strip().splitlines()
    )
    return PAGE.substitute(
        project=html.escape(project), meta=meta, nav=nav, board=board, needs=needs,
        sections=sections, tasks=tasks_sec, log=log_html,
        stamp=stamp, stamp_src=html.escape(stamp_src),
    )


def feature_section(f: Feature) -> str:
    by_num = {t.num: t for t in f.tickets}
    counts = Counter(t.status for t in f.tickets)
    bits = [f"{counts['done']}/{len(f.tickets)} done"]
    bits += [f"{counts[s]} {s}" for s in ("claimed", "open", "blocked") if counts[s]]
    if f.worker_host:
        bits.append(f"workers on {html.escape(f.worker_host)}")
    strip = "".join(
        f'<a class="cell {t.status}" href="#t-{f.name}-{t.num}" title="{html.escape(t.num + " " + t.title)} — {t.status}">{t.num}</a>'
        for t in f.tickets
    )

    def row(t: Ticket) -> str:
        chips = dep_chips(f.name, by_num, t) or '<span class="deps">—</span>'
        return (
            f'<details class="ticket row-{t.status}" id="t-{f.name}-{t.num}"><summary>'
            f'<span class="num">{t.num}</span><span class="title">{html.escape(t.title)}</span>'
            f'<span class="badge {t.status}">{STATUS_SYMBOL[t.status]} {t.status}</span>'
            f'<span class="chips">{chips}</span></summary>'
            f'<div class="body">{t.body_html}</div></details>'
        )

    order = {"claimed": 0, "open": 1, "blocked": 2}
    active = sorted((t for t in f.tickets if t.status != "done"), key=lambda t: (order[t.status], t.num))
    active_rows = "".join(row(t) for t in active)
    done_rows = "".join(row(t) for t in f.tickets if t.status == "done")
    done_fold = (
        f'<details class="done-fold" id="done-{f.name}"><summary>{counts["done"]} done tickets</summary>{done_rows}</details>'
        if done_rows else ""
    )
    return (
        f'<section class="viewgroup feature" id="f-{f.name}">'
        f'<h2>{html.escape(f.name)} <span class="counts">{" · ".join(bits)}</span></h2>'
        f'<div class="strip">{strip}</div>'
        + graph_views(f"f-{f.name}", feature_dag(f, False), feature_dag(f, True), wave_lanes(f))
        + f'<div class="tickets">{active_rows}{done_fold}</div>'
        "</section>"
    )


PAGE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>board — ${project}</title>
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
    --human: #c03535; --human-bg: #fbe9e9; --flash: #fdf0d5;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0d1320; --panel: #151d2b; --line: #26324a; --ink: #dfe6f2; --muted: #8b96a8; --edge: #4d5c74;
      --done-bg: #12321f; --done-br: #2f9e5f; --done-tx: #7fe0a7;
      --claimed-bg: #3a2a10; --claimed-br: #c9932e; --claimed-tx: #f0c46a;
      --open-bg: #10293c; --open-br: #3e87c2; --open-tx: #86c5ee;
      --blocked-bg: #1b2230; --blocked-br: #3a4453; --blocked-tx: #7a8698;
      --human: #e25b5b; --human-bg: #3a1414; --flash: #3a2a10;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: "IBM Plex Sans", system-ui, sans-serif; font-size: 15px; line-height: 1.55;
    background: var(--bg); color: var(--ink); max-width: 64rem; margin: 2.5rem auto 6rem; padding: 0 1.25rem;
  }
  .eyebrow, h1, h2, .meta, .strip, .badge, .num, .deps, .chip, .log, .mermaid, .cardnum, .lanelabel, .counts, #switcher { font-family: "IBM Plex Mono", ui-monospace, monospace; }

  .eyebrow { text-transform: uppercase; letter-spacing: .24em; font-size: .68rem; color: var(--muted); margin: 0 0 .35rem; }
  .masthead { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem 2rem; flex-wrap: wrap; }
  h1 { font-size: 1.55rem; font-weight: 600; margin: 0; }
  .strip { display: flex; gap: 2px; flex-wrap: wrap; margin: .3rem 0 .8rem; }
  .cell { min-width: 2em; text-align: center; font-size: .68rem; padding: .18rem .35rem; border: 1px solid; border-radius: 4px; text-decoration: none; }
  .meta { color: var(--muted); font-size: .74rem; margin: .6rem 0 0; }
  .meta a { color: var(--human); font-weight: 600; text-decoration: none; }
  .meta a:focus-visible, .meta a:hover { text-decoration: underline; }

  h2 {
    text-transform: uppercase; letter-spacing: .2em; font-size: .7rem; font-weight: 500;
    color: var(--muted); margin: 2.4rem 0 .8rem; display: flex; align-items: center; gap: .8rem;
  }
  h2::after { content: ""; flex: 1; border-top: 1px solid var(--line); }
  h2 .counts { letter-spacing: 0; text-transform: none; }

  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
  .board { padding: 1rem; overflow-x: auto; }
  .mermaid { margin: 0; display: flex; justify-content: center; color: var(--muted); }
  .mermaid:not(:has(svg)) { visibility: hidden; }
  .view { display: none; }
  .view.active { display: block; }
  .viewgroup:not(:has(.view.active)) .strip { display: none; }

  .done { background: var(--done-bg); border-color: var(--done-br); color: var(--done-tx); }
  .claimed { background: var(--claimed-bg); border-color: var(--claimed-br); color: var(--claimed-tx); }
  .open { background: var(--open-bg); border-color: var(--open-br); color: var(--open-tx); }
  .blocked { background: var(--blocked-bg); border-color: var(--blocked-br); color: var(--blocked-tx); }

  /* wave lanes */
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
  .chips { display: inline-flex; gap: .25rem; min-width: 5rem; justify-content: flex-end; flex-wrap: wrap; }
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
  .needs-human summary { cursor: pointer; }
  .needs-detail { padding: .3rem .2rem 0; font-size: .875rem; line-height: 1.55; }
  .needs-detail pre {
    background: var(--bg); border-radius: 6px; padding: .6rem .8rem;
    overflow-x: auto; font-size: .8rem; line-height: 1.5; white-space: pre-wrap;
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
<body data-stamp="${stamp}" data-stamp-src="${stamp_src}">
<header>
  <p class="eyebrow">tracker · board</p>
  <div class="masthead">
    <h1>${project}</h1>
    <div class="strip">${nav}</div>
  </div>
  <p class="meta">${meta}</p>
</header>

${board}

${needs}

${sections}

${tasks}

<section>
  <h2>Recent commits</h2>
  <pre class="panel log">${log}</pre>
</section>

<div id="switcher">
  <button id="prev" title="previous view (←)">◀</button>
  <span id="vlabel"></span>
  <button id="next" title="next view (→)">▶</button>
</div>

<script>
  // Synchronous state restore, before first paint. The module below waits on the
  // mermaid import; doing any of this there makes every 30s reload visibly
  // collapse the graphs and drop expanded tickets for a beat.
  (() => {
    const views = [["frontier", "frontier graph"], ["full", "full graph"], ["lanes", "wave lanes"]];
    // state saved by the pre-reload saveState: sessionStorage, with window.name
    // (which survives navigation in every browser) as the fallback carrier
    let saved = null, cache = {};
    try {
      saved = JSON.parse(sessionStorage.getItem("dispatch-view") ?? "null");
      cache = JSON.parse(sessionStorage.getItem("dispatch-svg") ?? "{}");
    } catch {}
    if (!saved && window.name.startsWith("dispatch:")) {
      try { ({ saved = null, cache = {} } = JSON.parse(window.name.slice(9))); } catch {}
    }
    // saved state wins over the URL: the reload keeps a stale ?view= around
    let view = saved?.view ?? new URLSearchParams(location.search).get("view") ?? "frontier";
    if (!views.some(([k]) => k === view)) view = "frontier";
    for (const s of document.querySelectorAll(".view")) s.classList.toggle("active", s.dataset.view === view);
    document.getElementById("vlabel").textContent = views.find(([k]) => k === view)[1];
    // re-inject cached SVGs: an unchanged graph paints instantly instead of re-running mermaid
    for (const el of document.querySelectorAll(".view .mermaid")) {
      const hit = cache[el.dataset.key];
      if (hit && hit.src === el.textContent) { el.dataset.src = hit.src; el.innerHTML = hit.svg; }
    }
    for (const id of saved?.open ?? []) document.getElementById(id)?.setAttribute("open", "");
    if (saved) scrollTo(0, saved.scroll ?? 0);
    window.dispatchView = { views, view, saved };
  })();
</script>

<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  import elkLayouts from "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0/dist/mermaid-layout-elk.esm.min.mjs";
  mermaid.registerLayoutLoaders(elkLayouts);

  const css = getComputedStyle(document.body);
  const v = (name) => css.getPropertyValue(name).trim();
  // Mermaid bakes colors into the SVG, so the palette is read off the CSS tokens at load time.
  // ghost = done ticket shown as context: done palette (so it never reads as
  // blocked-grey), dashed border marking it inactive
  const classDefs = ["done", "claimed", "open", "blocked"].map((s) =>
    "  classDef " + s + " fill:" + v("--" + s + "-bg") + ",stroke:" + v("--" + s + "-br") + ",color:" + v("--" + s + "-tx")
  ).join("\\n") + "\\n  classDef ghost fill:" + v("--done-bg") + ",stroke:" + v("--done-br") + ",color:" + v("--done-tx") + ",stroke-dasharray:4 3";
  mermaid.initialize({
    startOnLoad: false, layout: "elk", securityLevel: "loose", theme: "base",
    elk: { mergeEdges: false },
    themeVariables: {
      fontFamily: "'IBM Plex Mono', ui-monospace, monospace", fontSize: "13px",
      primaryColor: v("--panel"), primaryTextColor: v("--ink"),
      primaryBorderColor: v("--line"), lineColor: v("--edge"),
    },
  });

  let seq = 0;
  async function renderGraphs() {
    // mermaid.render (string -> svg), never mermaid.run: run's in-DOM processing
    // contaminates across the page's many diagrams (billing nodes appearing in
    // auth's svg), render is hermetic per call.
    for (const el of document.querySelectorAll(".view.active .mermaid")) {
      if (el.querySelector("svg")) continue;  // already rendered, or restored from the svg cache
      el.dataset.src = el.textContent;
      const { svg } = await mermaid.render("m" + Date.now() + "_" + seq++, el.dataset.src + "\\n" + classDefs);
      el.innerHTML = svg;
    }
  }

  const { views, saved } = window.dispatchView;
  let current = window.dispatchView.view;

  async function activate(key) {
    current = key;
    for (const s of document.querySelectorAll(".view"))
      s.classList.toggle("active", s.dataset.view === key);
    document.getElementById("vlabel").textContent = views.find(([k]) => k === key)[1];
    await renderGraphs();
  }
  function cycle(delta) {
    const i = views.findIndex(([k]) => k === current);
    activate(views[(i + delta + views.length) % views.length][0]);
  }
  document.getElementById("prev").addEventListener("click", () => cycle(-1));
  document.getElementById("next").addEventListener("click", () => cycle(1));
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, [contenteditable]")) return;
    if (e.key === "ArrowLeft") cycle(-1);
    if (e.key === "ArrowRight") cycle(1);
  });

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

  function saveState() {
    const state = {
      view: current,
      open: [...document.querySelectorAll("details[open]")].map((d) => d.id).filter(Boolean),
      scroll: scrollY,
    };
    const svgs = {};
    for (const el of document.querySelectorAll(".view .mermaid")) {
      if (el.querySelector("svg")) svgs[el.dataset.key] = { src: el.dataset.src, svg: el.innerHTML };
    }
    try {
      sessionStorage.setItem("dispatch-view", JSON.stringify(state));
      sessionStorage.setItem("dispatch-svg", JSON.stringify(svgs));
    } catch {}
    try { window.name = "dispatch:" + JSON.stringify({ saved: state, cache: svgs }); } catch {}
  }

  // Reload only when the renderer wrote different content. fetch() is blocked on
  // file://, but a classic script tag isn't — so poll the sidecar stamp file the
  // renderer writes beside this page.
  function poll() {
    const s = document.createElement("script");
    s.src = document.body.dataset.stampSrc + "?" + Date.now();
    s.onload = () => {
      s.remove();
      if (window.__dispatchStamp !== document.body.dataset.stamp) { saveState(); location.reload(); }
      else setTimeout(poll, 30_000);
    };
    s.onerror = () => { saveState(); location.reload(); };  // no sidecar: stay current the blunt way
    document.head.append(s);
  }
  setTimeout(poll, 30_000);

  await renderGraphs();
  if (!saved && location.hash) openTarget();
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
