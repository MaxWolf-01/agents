#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown"]
# ///
"""Render the tracker board: one HTML page for a tracker's whole agent/tickets tree.

Reads every feature directory (spec.md, NN-<slug>.md tickets with
status/blocked-by/type frontmatter, cross-feature refs as <feature>/NN) and
every standalone ticket (*.md at the tracker root) and writes one
self-contained page beside the tracker, agent/board.html: an all-features
dependency graph with feature subgraphs and cross-feature edges, the merged
needs-human queue, and a section per feature (spec status, graph, wave lanes,
ticket rows). One switcher (floating bar or arrow keys) cycles every graph on
the page through frontier / full / lanes at once.

One board per tracker, showing what is actionable now. The tracker is read
from the repo's main checkout whatever checkout the command runs in; a feature
that has a worktree on a branch named after it (how dispatch cuts a feature
worktree) is read from that worktree instead, review pages included, so its
claims and done flips are on the board while the feature is in flight. A
worktree whose branch is already merged is ignored. A standalone ticket whose
slug names such a feature has been absorbed into it and is not shown.

A ticket row links its diffview review page when one has been rendered:
agent/diffviews mirrors agent/tickets, so <feature>/NN-*.html beside the ticket
and <slug>.html beside a standalone ticket. Those pages are gitignored, so the
link appears only on the machine that rendered them.

--watch keeps rendering: every few seconds it looks for a change under the
tracker (any worktree's copy included) and re-renders on one; it runs until
killed. Several watchers writing the same page is harmless since the render is
deterministic from disk. Per-feature orchestrator state is read from
agent/tickets/<feature>/needs-human.md: optional YAML frontmatter (worker-host),
then one `- summary :: markdown detail` bullet per pending entry.

The page polls a sidecar stamp file (written beside the HTML) every 5s and
reloads, keeping scroll position, open sections and the chosen view, only when
content actually changed: one open tab stays current across renders without
flicker. The page and its stamp file are gitignored, like agent/diffviews.

Examples:

    uv run board.py agent/tickets --watch
    uv run board.py agent/tickets --out /tmp/board.html --open never
"""

import datetime
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
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
    tickets_root: Annotated[Path, tyro.conf.Positional]
    """Tracker root, e.g. agent/tickets, in any checkout of the repo; the board renders the main checkout's copy."""
    out: Path | None = None
    """Output HTML path. Default: board.html beside the tracker (agent/board.html)."""
    repo: Path | None = None
    """Repo for the commit log. Default: the main checkout."""
    open: Literal["auto", "always", "never"] = "auto"
    """Open the result in the browser diffview pages open in ($DIFFVIEW_BROWSER, else xdg-open), so the board and the diffs it links share a window. auto = only when the output file is new."""
    watch: bool = False
    """Keep running and re-render whenever anything under the tracker changes."""


def main(args: Args) -> None:
    root, overrides = tracker_roots(args.tickets_root)
    assert root.is_dir() or overrides, f"no tracker at {root}"
    repo = (args.repo or root.parent.parent).resolve()
    out = (args.out or root.parent / "board.html").resolve()
    existed = out.exists()
    render(root, overrides, repo, out)
    if args.open == "always" or (args.open == "auto" and not existed):
        browser = os.environ.get("DIFFVIEW_BROWSER") or "xdg-open"
        subprocess.Popen([browser, str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if args.watch:
        watch(args.tickets_root, repo, out)


def render(root: Path, overrides: dict[str, Path], repo: Path, out: Path) -> None:
    project = repo.name
    diffviews = load_diffviews(root.parent / "diffviews")
    features = load_features(root, overrides, diffviews)
    # a standalone ticket whose slug names an in-flight feature was absorbed into it (grilling)
    standalone = [k for k in load_standalone(root, overrides, diffviews) if k.slug not in overrides]
    log = git_log(repo)
    stamp = content_stamp(project, features, standalone, log)
    out.parent.mkdir(parents=True, exist_ok=True)
    page = render_page(project, features, standalone, log, stamp, out.name + ".stamp.js")
    out.write_text(page)
    Path(str(out) + ".stamp.js").write_text(f'window.__boardStamp = "{stamp}";\n')
    print(out)


def watch(tickets_root: Path, repo: Path, out: Path) -> None:
    """Re-render on any change under the tracker, in every checkout that contributes to it."""
    seen = None
    while True:
        try:
            root, overrides = tracker_roots(tickets_root)
            dirs = [root, root.parent / "diffviews"]
            dirs += [d for o in overrides.values() for d in (o, o.parent.parent / "diffviews" / o.name)]
            snapshot = (git(repo, "rev-parse", "HEAD"),) + tuple(
                (str(f), st.st_mtime_ns, st.st_size)
                for d in dirs if d.is_dir() for f in sorted(d.rglob("*")) if f.is_file() for st in [f.stat()]
            )
            if snapshot != seen:
                if seen is not None:
                    render(root, overrides, repo, out)
                seen = snapshot
        except Exception as e:  # a file deleted mid-scan, a half-written ticket: the next pass sees the settled state
            print(f"board: {e}; retrying", file=sys.stderr)
        time.sleep(2)


# ---- which checkout's tracker ---------------------------------------------


def worktrees(path: Path) -> list[tuple[Path, str | None]]:
    """(path, branch) per worktree of the repo containing `path`, the main checkout first; [] outside git."""
    result = subprocess.run(["git", "-C", str(path), "worktree", "list", "--porcelain"], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    out: list[tuple[Path, str | None]] = []
    for block in result.stdout.strip().split("\n\n"):
        lines = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        branch = lines.get("branch")
        out.append((Path(lines["worktree"]), branch.removeprefix("refs/heads/") if branch else None))
    return out


def tracker_roots(tickets_root: Path) -> tuple[Path, dict[str, Path]]:
    """The main checkout's tracker, plus the feature directories a worktree on that feature's branch overrides.

    Ticket state an orchestrator commits on its feature branch is invisible to the main
    checkout until the feature merges; the worktree on that branch is where the
    feature's current truth lives, so its copy of the feature directory wins.
    """
    here = tickets_root.resolve()
    wts = worktrees(here)
    if not wts:
        return here, {}
    toplevel = subprocess.run(["git", "-C", str(here), "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    rel = here.relative_to(Path(toplevel).resolve())
    main = wts[0][0].resolve()
    landed = landed_tips(main)
    overrides = {}
    for path, branch in wts[1:]:
        if branch and (path / rel / branch).is_dir() and git(path, "rev-parse", branch) not in landed:
            overrides[branch] = path.resolve() / rel / branch
    return main / rel, overrides


def landed_tips(main: Path) -> set[str]:
    """Tips of branches merged --no-ff into the main checkout's history: the second parent of each
    first-parent merge commit. A worktree left behind on such a branch must not outvote the main
    checkout; a branch merely cut from it and idle is not landed, so ancestry alone is the wrong test."""
    parents = git(main, "log", "--first-parent", "--merges", "--format=%P", "HEAD")
    return {line.split()[1] for line in parents.splitlines() if len(line.split()) > 1}


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    assert result.returncode == 0, f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip()}"
    return result.stdout.strip()


# ---- tracker state --------------------------------------------------------


@dataclass
class Diffviews:
    """Where review pages live, and the server for them when one is answering.

    A served page can save comments; one opened as a file is read-only, so which
    link a ticket gets says which of the two the reader will land on.
    """

    root: Path
    base: str | None

    def link(self, directory: Path, pattern: str) -> str | None:
        matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
        if not matches:
            return None
        page = matches[-1].resolve()
        if self.base is None:
            return f"file://{page}"
        return f"{self.base}/{page.relative_to(self.root.resolve())}"


@dataclass
class Ticket:
    num: str
    title: str
    status: str  # open | claimed | done, plus derived: blocked
    kind: str | None  # a decision ticket's type (research | prototype | grilling | legwork); None on a build ticket
    blocked_by: list[str]
    ext_by: list[tuple[str, str]]  # cross-feature blockers: (ref "<feature>/NN", status)
    body_html: str
    diffview: str | None


@dataclass
class Feature:
    name: str
    tickets: list[Ticket]
    needs_human: list[str]
    worker_host: str | None
    spec_status: str | None  # spec.md's status; None when the feature has no spec


@dataclass
class Standalone:
    slug: str
    title: str
    status: str  # open | claimed | done, plus derived: blocked
    kind: str | None
    blocked_by: list[tuple[str, str]]  # (ref "<feature>/NN" or "<slug>", status)
    body_html: str
    diffview: str | None


def load_features(root: Path, overrides: dict[str, Path], diffviews: Diffviews) -> list[Feature]:
    features = []
    # the main checkout may not have the tracker yet: a first feature grilled in its own worktree
    names = sorted(({p.name for p in root.iterdir() if p.is_dir()} if root.is_dir() else set()) | set(overrides))
    for name in names:
        d = overrides.get(name, root / name)
        # an in-flight feature's review pages are rendered and served from its own worktree
        dv = load_diffviews(d.parent.parent / "diffviews") if name in overrides else diffviews
        tickets = load_tickets(d, dv, dv.root / name, root, overrides)
        spec_status = spec_state(d / "spec.md")
        # a directory with neither tickets nor a spec is not a feature (agent/tickets/done/, say)
        if not tickets and spec_status is None:
            continue
        assert_safe_name(name)
        needs_human, worker_host = load_needs_human(d / "needs-human.md")
        features.append(Feature(name, tickets, needs_human, worker_host, spec_status))
    ids = [slug_id(f.name) for f in features]
    assert len(ids) == len(set(ids)), f"feature names collide as mermaid ids: {sorted(ids)}"
    return features


def assert_safe_name(name: str) -> None:
    # names ride into HTML attributes and mermaid click strings unescaped
    assert re.fullmatch(r"[A-Za-z0-9._-]+", name), f"unsafe tracker name: {name!r}"


def load_standalone(root: Path, overrides: dict[str, Path], diffviews: Diffviews) -> list[Standalone]:
    standalone = []
    for path in sorted(root.glob("*.md")) if root.is_dir() else []:
        assert_safe_name(path.stem)
        meta, body = split_frontmatter(path.read_text())
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        body = body[heading.end():] if heading else body
        blocked_by = [(str(n), ref_status(root, overrides, str(n))) for n in meta.get("blocked-by") or []]
        status = str(meta.get("status", "open"))
        if status == "open" and any(s != "done" for _, s in blocked_by):
            status = "blocked"
        standalone.append(
            Standalone(
                slug=path.stem,
                title=heading.group(1).strip() if heading else path.stem.replace("-", " "),
                status=status,
                kind=ticket_kind(meta),
                blocked_by=blocked_by,
                body_html=markdown.markdown(body, extensions=["fenced_code", "tables"]),
                diffview=diffviews.link(diffviews.root, f"{path.stem}.html"),
            )
        )
    return standalone


def load_diffviews(root: Path) -> Diffviews:
    """Probe the marker's port: a server killed without cleanup leaves one naming nothing."""
    try:
        port = json.loads((root / ".serve.json").read_text())["port"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/.health", timeout=1) as answer:
            if json.loads(answer.read())["root"] == str(root.resolve()):
                return Diffviews(root, f"http://127.0.0.1:{port}")
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return Diffviews(root, None)


def spec_state(path: Path) -> str | None:
    if not path.exists():
        return None
    meta, _ = split_frontmatter(path.read_text())
    return str(meta.get("status", "status missing"))


def load_needs_human(path: Path) -> tuple[list[str], str | None]:
    if not path.exists():
        return [], None
    meta, body = split_frontmatter(path.read_text())
    entries = [line[2:].strip() for line in body.splitlines() if line.startswith("- ")]
    host = meta.get("worker-host")
    return entries, str(host) if host else None


def load_tickets(feature_dir: Path, diffviews: Diffviews, dv_dir: Path, root: Path, overrides: dict[str, Path]) -> list[Ticket]:
    tickets = []
    for path in sorted(feature_dir.glob("[0-9][0-9]-*.md")):
        meta, body = split_frontmatter(path.read_text())
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        body = body[heading.end():] if heading else body
        blockers = meta.get("blocked-by") or []
        tickets.append(
            Ticket(
                num=path.name[:2],
                title=heading.group(1).strip() if heading else path.stem[3:].replace("-", " "),
                status=str(meta.get("status", "open")),
                kind=ticket_kind(meta),
                blocked_by=[normalize_num(n) for n in blockers if is_local_ref(n)],
                ext_by=[(str(n), ref_status(root, overrides, str(n))) for n in blockers if not is_local_ref(n)],
                body_html=render_body(body, feature_dir.name),
                diffview=diffviews.link(dv_dir, f"{path.name[:2]}-*.html"),
            )
        )
    done = {t.num for t in tickets if t.status == "done"}
    for t in tickets:
        if t.status == "open" and (
            any(b not in done for b in t.blocked_by) or any(s != "done" for _, s in t.ext_by)
        ):
            t.status = "blocked"
    return tickets


def ticket_kind(meta: dict) -> str | None:
    kind = meta.get("type")
    return str(kind) if kind else None


def kind_badge(kind: str | None) -> str:
    return f'<span class="badge kind">{html.escape(kind)}</span>' if kind else ""


def is_local_ref(n: object) -> bool:
    # a bare ticket number within the feature; "<feature>/NN" and "<slug>" are external
    return isinstance(n, int) or str(n).isdigit()


def ref_status(root: Path, overrides: dict[str, Path], ref: str) -> str:
    # External blocker: "<feature>/NN" or a standalone ticket's "<slug>", resolved in the
    # checkout that holds the feature (an in-flight feature lives in its worktree). A
    # missing file counts as done: done work is deleted, feature dirs retired only after
    # shipping (tracker conventions).
    if "/" in ref:
        feature, num = ref.rsplit("/", 1)
        matches = sorted(overrides.get(feature, root / feature).glob(f"{normalize_num(num)}-*.md"))
    else:
        matches = [p for p in [root / f"{ref}.md"] if p.exists()]
    if not matches:
        return "done"
    meta, _ = split_frontmatter(matches[0].read_text())
    return str(meta.get("status", "open"))


def ref_anchor(ref: str) -> str:
    if "/" in ref:
        feature, num = ref.rsplit("/", 1)
        return f"#t-{feature}-{normalize_num(num)}"
    return f"#standalone-{ref}"


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


def content_stamp(project: str, features: list[Feature], standalone: list[Standalone], log: str) -> str:
    # everything the page shows except the render timestamp: an unchanged board
    # keeps its stamp, so the open tab knows not to reload
    key = repr((
        project,
        [(f.name, f.needs_human, f.worker_host, f.spec_status,
          [(t.num, t.title, t.status, t.kind, t.blocked_by, t.ext_by, t.body_html, t.diffview) for t in f.tickets])
         for f in features],
        [(k.slug, k.title, k.status, k.kind, k.blocked_by, k.body_html, k.diffview) for k in standalone],
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


def feature_dag(feature: Feature, full: bool) -> str | None:
    include, ghost = visible(feature.tickets, full)
    if not include:
        return None
    ns = "f1" if full else "f0"
    return "flowchart LR\n" + "\n".join(node_lines(ns, feature.name, feature.tickets, include, ghost))


def board_dag(features: list[Feature], standalone: list[Standalone], full: bool) -> str:
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
    shown = [k for k in standalone if full or k.status != "done"]
    if shown:
        lines.append(f'  subgraph S_{ns}__standalone["standalone"]')
        for k in shown:
            label = k.title.replace('"', "#quot;")
            cls = "ghost" if k.status == "done" else k.status
            lines.append(f'  K_{ns}_{slug_id(k.slug)}["{STATUS_SYMBOL[k.status]} {label}"]:::{cls}')
            lines.append(f'  click K_{ns}_{slug_id(k.slug)} "#standalone-{k.slug}"')
        lines.append("  end")
    # external edges (cross-feature, and standalone tickets), drawn where both endpoints are on the board
    shown_slugs = {k.slug for k in shown}

    def node(ref: str) -> str | None:
        if "/" in ref:
            src_feat, src_num = ref.rsplit("/", 1)
            if normalize_num(src_num) in included.get(src_feat, set()):
                return f"T_{ns}_{slug_id(src_feat)}_{normalize_num(src_num)}"
            return None
        return f"K_{ns}_{slug_id(ref)}" if ref in shown_slugs else None

    for f in features:
        for t in f.tickets:
            if t.num not in included[f.name]:
                continue
            for ref, _ in t.ext_by:
                if src := node(ref):
                    lines.append(f"  {src} --> T_{ns}_{slug_id(f.name)}_{t.num}")
    for k in shown:
        for ref, _ in k.blocked_by:
            if src := node(ref):
                lines.append(f"  {src} --> K_{ns}_{slug_id(k.slug)}")
    return "\n".join(lines)


def wave_lanes(feature: Feature) -> str | None:
    tickets = feature.tickets
    by_num = {t.num: t for t in tickets}
    live = [t for t in tickets if t.status != "done"]
    if not live:
        return None
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
            f'<span class="cardnum">{STATUS_SYMBOL[t.status]} {t.num}{" · " + html.escape(t.kind) if t.kind else ""}</span>'
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
    return local + ext_chips(t.ext_by)


def ext_chips(refs: list[tuple[str, str]]) -> str:
    return "".join(
        f'<a class="chip {s}" href="{ref_anchor(ref)}" title="external blocker">{html.escape(ref)}</a>'
        for ref, s in refs
    )


# ---- page -----------------------------------------------------------------


def graph_views(
    sec_id: str, frontier: str | None, full: str | None, lanes: str | None, done_note: str,
    with_lanes: bool = True,
) -> str:
    """One .view per mode; a None graph renders the done-note instead of a diagram.
    with_lanes=False omits the lanes view entirely (the section hides in lanes mode)."""
    def view(key: str, inner: str | None, mermaid: bool) -> str:
        if inner is None:
            content = f'<div class="alldone">✓ {done_note}</div>'
        elif mermaid:
            content = f'<pre class="mermaid" data-key="{sec_id}:{key}">{inner}</pre>'
        else:
            content = inner
        return f'<div class="view" data-view="{key}"><div class="panel board">{content}</div></div>'

    out = view("frontier", frontier, True) + view("full", full, True)
    if with_lanes:
        out += view("lanes", lanes, False)
    return out


def render_page(
    project: str, features: list[Feature], standalone: list[Standalone], log: str, stamp: str, stamp_src: str
) -> str:
    total = sum(len(f.tickets) for f in features)
    total_done = sum(1 for f in features for t in f.tickets if t.status == "done")
    all_needs = [(f.name, item) for f in features for item in f.needs_human]
    open_standalone = sum(1 for k in standalone if k.status != "done")

    meta = f"{total_done}/{total} done"
    if open_standalone:
        meta += f" · {open_standalone} standalone open"
    needs_badge = (
        f'<a class="needsbadge" href="#needs-human">● {len(all_needs)} need human</a>' if all_needs else ""
    )
    nav = "".join(
        f'<a class="featchip" href="#f-{f.name}">{html.escape(f.name)} '
        f"<span class=\"dim\">{sum(1 for t in f.tickets if t.status == 'done')}/{len(f.tickets)}</span></a>"
        for f in features
    )

    # the all-features graph earns its place only when more than one feature has tickets;
    # with one, it duplicates that feature's own section, with none it is an empty box
    board = ""
    if sum(1 for f in features if f.tickets) > 1:
        board = (
            '<section class="viewgroup" id="sec-board"><h2>Board</h2>'
            + graph_views(
                "sec-board",
                board_dag(features, standalone, False),
                board_dag(features, standalone, True),
                None,
                "everything done",
                with_lanes=False,
            )
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

    no_deps = '<span class="deps">—</span>'
    standalone_rows = "".join(
        f'<details class="ticket row-{k.status}" id="standalone-{k.slug}"><summary>'
        f'<span class="num">·</span><span class="title">{html.escape(k.title)}{dv_link(k.diffview)}</span>'
        f'<span class="badge {k.status}">{STATUS_SYMBOL[k.status]} {k.status}</span>{kind_badge(k.kind)}'
        f'<span class="chips">{ext_chips(k.blocked_by) or no_deps}</span></summary>'
        f'<div class="body">{k.body_html}</div></details>'
        for k in standalone
    )
    standalone_sec = f'<section><h2>Standalone tickets</h2><div class="tickets panel-b">{standalone_rows}</div></section>' if standalone else ""

    log_html = "\n".join(
        f'<span class="hash">{html.escape(line.split(" ")[0])}</span> {html.escape(line.partition(" ")[2])}'
        for line in log.strip().splitlines()
    )
    footmeta = f"{len(features)} feature{'s' if len(features) != 1 else ''} · {len(standalone)} standalone · rendered {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · refreshes on change"
    return PAGE.substitute(
        project=html.escape(project), meta=meta, needs_badge=needs_badge, nav=nav,
        board=board, needs=needs, sections=sections, standalone=standalone_sec, log=log_html,
        footmeta=footmeta, stamp=stamp, stamp_src=html.escape(stamp_src),
    )


def dv_link(path: str | None) -> str:
    if not path:
        return ""
    return (f'<a class="dv" href="{html.escape(path)}" target="_blank" '
            f'onclick="event.stopPropagation()" title="{html.escape(path)}">diff</a>')


def feature_section(f: Feature) -> str:
    counts = Counter(t.status for t in f.tickets)
    bits = [f"spec {html.escape(f.spec_status)}"] if f.spec_status else []
    bits += [f"{counts['done']}/{len(f.tickets)} done"] if f.tickets else ["no tickets yet"]
    bits += [f"{counts[s]} {s}" for s in ("claimed", "open", "blocked") if counts[s]]
    if f.worker_host:
        bits.append(f"workers on {html.escape(f.worker_host)}")
    strip = "".join(
        f'<a class="cell {t.status}" href="#t-{f.name}-{t.num}" title="{html.escape(t.num + " " + t.title)} — {t.status}">{t.num}</a>'
        for t in f.tickets
    )
    head = (
        f'<section class="viewgroup feature" id="f-{f.name}">'
        f'<div class="fhead"><h2>{html.escape(f.name)} <span class="counts">{" · ".join(bits)}</span></h2>'
        f'<div class="strip">{strip}</div></div>'
    )
    if not f.tickets:
        return head + "</section>"
    by_num = {t.num: t for t in f.tickets}

    def row(t: Ticket) -> str:
        chips = dep_chips(f.name, by_num, t) or '<span class="deps">—</span>'
        return (
            f'<details class="ticket row-{t.status}" id="t-{f.name}-{t.num}"><summary>'
            f'<span class="num">{t.num}</span><span class="title">{html.escape(t.title)}{dv_link(t.diffview)}</span>'
            f'<span class="badge {t.status}">{STATUS_SYMBOL[t.status]} {t.status}</span>{kind_badge(t.kind)}'
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
    done_note = f"all {len(f.tickets)} tickets done"
    return (
        head
        + graph_views(f"f-{f.name}", feature_dag(f, False), feature_dag(f, True), wave_lanes(f), done_note)
        + f'<div class="tickets panel-b">{active_rows}{done_fold}</div>'
        "</section>"
    )


PAGE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>board — ${project}</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #141519; --panel: #1b1d23; --raised: #22252c; --border: #2c303a; --border-strong: #3a4050;
    --ink: #d6dae2; --ink2: #9aa1af; --ink3: #6a7180; --edge: #4d5665;
    --accent: #7aa2f7; --accent-dim: #4b689f;
    --done-bg: #17251a; --done-br: #3f7a44; --done-tx: #85d18d;
    --claimed-bg: #2a2214; --claimed-br: #9a7a34; --claimed-tx: #e2bc66;
    --open-bg: #16202f; --open-br: #4b689f; --open-tx: #9dbcf9;
    --blocked-bg: #1e2026; --blocked-br: #3a4050; --blocked-tx: #8b93a1;
    --human: #e5534b; --human-bg: #291414; --flash: #2a2214;
    --mono: ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", Menlo, Consolas, monospace;
    --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    --topbar-h: 46px;
  }
  * { box-sizing: border-box; }
  html { scrollbar-color: #3a3f4b var(--bg); }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.5 var(--sans); }
  a { color: var(--accent); text-decoration: none; }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
  .dim { color: var(--ink3); font-weight: 400; }
  .eyebrow, .meta, .strip, .badge, .num, .deps, .chip, .log, .mermaid, .cardnum, .lanelabel, .counts, .featchip, .cell { font-family: var(--mono); }

  /* ---- sticky topbar: identity left, controls right ---- */
  .top { position: sticky; top: 0; z-index: 10; display: flex; gap: 12px; align-items: center; height: var(--topbar-h);
    padding: 0 16px; background: color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter: blur(6px);
    border-bottom: 1px solid var(--border); }
  .top h1 { font-size: 14px; margin: 0; font-weight: 600; white-space: nowrap; }
  .top .eyebrow { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--ink3); }
  .top .meta { color: var(--ink2); font-size: 12px; white-space: nowrap; }
  .needsbadge { color: var(--human); font-weight: 600; font-size: 12px; white-space: nowrap; }
  .featnav { display: flex; gap: 6px; overflow-x: auto; flex: 1; min-width: 0; scrollbar-width: none; }
  .featchip { font-size: 11.5px; padding: 2px 8px; border: 1px solid var(--border); border-radius: 5px;
    color: var(--ink2); white-space: nowrap; }
  .featchip:hover { color: var(--ink); border-color: var(--border-strong); }
  .modes { display: flex; gap: 4px; margin-left: auto; }
  .btn { background: var(--raised); border: 1px solid var(--border); border-radius: 6px; padding: 3px 10px;
    cursor: pointer; color: var(--ink2); font-size: 12.5px; white-space: nowrap; font-family: var(--sans); }
  .btn:hover { color: var(--ink); border-color: var(--border-strong); }
  .btn.on { color: var(--accent); border-color: var(--accent-dim); }
  .modes kbd { font-family: var(--mono); font-size: 10px; color: var(--ink3); align-self: center; }

  main { max-width: 72rem; margin: 0 auto 6rem; padding: 0 1.25rem; }

  h2 { text-transform: uppercase; letter-spacing: .18em; font-size: 11px; font-weight: 600;
    color: var(--ink2); margin: 2.2rem 0 .7rem; display: flex; align-items: baseline; gap: .8rem; font-family: var(--sans); }
  h2::after { content: ""; flex: 1; border-top: 1px solid var(--border); align-self: center; }
  h2 .counts { letter-spacing: 0; text-transform: none; font-size: 11.5px; color: var(--ink3); font-weight: 400; }

  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; }
  .panel-b { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 0 .6rem; }
  .board { padding: 1rem; overflow-x: auto; }
  .alldone { color: var(--ink3); font-size: 12.5px; padding: .2rem .4rem; }
  .mermaid { margin: 0; display: flex; justify-content: center; color: var(--ink3); }
  .mermaid:not(:has(svg)) { visibility: hidden; }
  .view { display: none; }
  .view.active { display: block; }
  section.viewgroup:not(.feature):not(:has(.view.active)) { display: none; }

  .done { background: var(--done-bg); border-color: var(--done-br); color: var(--done-tx); }
  .claimed { background: var(--claimed-bg); border-color: var(--claimed-br); color: var(--claimed-tx); }
  .open { background: var(--open-bg); border-color: var(--open-br); color: var(--open-tx); }
  .blocked { background: var(--blocked-bg); border-color: var(--blocked-br); color: var(--blocked-tx); }
  .badge.kind { background: var(--human-bg); border-color: var(--human); color: var(--human); margin-left: .35rem; }

  /* ---- feature header: sticky under the topbar ---- */
  .fhead { position: sticky; top: var(--topbar-h); z-index: 5; padding: .3rem 0 .5rem;
    background: color-mix(in srgb, var(--bg) 92%, transparent); backdrop-filter: blur(6px); }
  .fhead h2 { margin: 0 0 .45rem; }
  .strip { display: flex; gap: 2px; flex-wrap: wrap; }
  .cell { min-width: 2em; text-align: center; font-size: 10.5px; padding: .14rem .3rem; border: 1px solid; border-radius: 4px; text-decoration: none; }

  /* ---- wave lanes ---- */
  .lane { display: flex; gap: 1rem; padding: .7rem 0; border-bottom: 1px dashed var(--border); align-items: baseline; }
  .lane:last-child { border-bottom: 0; }
  .lanelabel { flex: 0 0 9.5rem; text-transform: uppercase; letter-spacing: .14em; font-size: 10px; color: var(--ink3); padding-top: .5rem; }
  .lanecards { display: flex; flex-wrap: wrap; gap: .5rem; flex: 1; }
  .card { display: flex; flex-direction: column; gap: .15rem; border: 1px solid; border-radius: 6px; padding: .45rem .65rem; max-width: 15rem; }
  .cardlink { display: flex; flex-direction: column; gap: .15rem; text-decoration: none; color: inherit; }
  .cardnum { font-size: 10.5px; opacity: .8; }
  .cardtitle { font-size: 12px; line-height: 1.35; }
  .card .chips { margin-top: .2rem; justify-content: flex-start; min-width: 0; }

  /* ---- ticket rows ---- */
  .ticket { border-bottom: 1px solid var(--border); }
  .ticket:last-child, .done-fold .ticket:last-child { border-bottom: 0; }
  .ticket summary { display: grid; grid-template-columns: 2.2rem 1fr auto auto; gap: .8rem; align-items: baseline;
    padding: .45rem .3rem; cursor: pointer; list-style: none; }
  .ticket summary::-webkit-details-marker { display: none; }
  .ticket summary:hover { background: var(--raised); }
  .ticket .num { color: var(--ink3); font-size: 12px; }
  .ticket .title { font-size: 13.5px; }
  .dv { font-family: var(--mono); font-size: 10.5px; margin-left: .5rem; padding: 0 .3rem; text-decoration: none;
    color: var(--ink3); border: 1px solid var(--border); border-radius: 4px; }
  .dv:hover { color: var(--ink); border-color: var(--ink3); }
  .row-done summary .title { color: var(--ink2); }
  .badge { display: inline-block; border: 1px solid; padding: .02rem .55rem; border-radius: 99px; font-size: 11px; white-space: nowrap; }
  .chips { display: inline-flex; gap: .25rem; min-width: 5rem; justify-content: flex-end; flex-wrap: wrap; }
  .chip { border: 1px solid; border-radius: 4px; font-size: 10.5px; padding: 0 .3rem; text-decoration: none; }
  .deps { color: var(--ink3); font-size: 12px; }
  .ticket .body { padding: .2rem 1rem 1rem 3rem; font-size: 13px; color: var(--ink);
    border-left: 3px solid var(--border); margin: 0 0 .8rem .6rem; }
  .ticket .body h2 { text-transform: none; letter-spacing: 0; font-size: 13.5px; color: var(--ink); margin: 1rem 0 .3rem; }
  .ticket .body h2::after { display: none; }
  .ticket .body code { background: var(--raised); border: 1px solid var(--border); border-radius: 4px; padding: 0 .25rem; font-size: .85em; font-family: var(--mono); }
  .ticket .body pre code { display: block; padding: .6rem .8rem; overflow-x: auto; }
  .ticket.flash > summary { background: var(--flash); transition: background .2s; }
  .done-fold > summary { cursor: pointer; color: var(--ink3); font-family: var(--mono); font-size: 11px;
    text-transform: uppercase; letter-spacing: .14em; padding: .7rem .3rem; }

  .needs-human { padding: 0; margin: 0; }
  .needs-human li { list-style: none; background: var(--human-bg); border-left: 3px solid var(--human);
    border-radius: 0 6px 6px 0; padding: .45rem .8rem; margin: .4rem 0; font-size: 13px; }
  .needs-human summary { cursor: pointer; }
  .needs-detail { padding: .3rem .2rem 0; font-size: 12.5px; line-height: 1.55; }
  .needs-detail pre { background: var(--bg); border-radius: 6px; padding: .6rem .8rem;
    overflow-x: auto; font-size: 11.5px; line-height: 1.5; white-space: pre-wrap; }
  .log { padding: .9rem 1.1rem; margin: 0; font-size: 12px; line-height: 1.75; overflow-x: auto; }
  .hash { color: var(--claimed-tx); }
  .footmeta { color: var(--ink3); font-size: 11.5px; font-family: var(--mono); margin-top: .8rem; }

  .kcur > summary, li.kcur { outline: 2px solid var(--accent); outline-offset: -2px; border-radius: 4px; }
  main > section { scroll-margin-top: calc(var(--topbar-h) + 10px); }
  .ticket, .done-fold, .needs-human li { scroll-margin-top: calc(var(--topbar-h) + 100px); scroll-margin-bottom: 60px; }

  #help { position: fixed; inset: 0; z-index: 100; background: rgba(10,11,13,.7); display: none; align-items: center; justify-content: center; }
  #help.open { display: flex; }
  #help .card { background: var(--panel); border: 1px solid var(--border-strong); border-radius: 10px; padding: 20px 26px; box-shadow: 0 10px 40px rgba(0,0,0,.6); }
  #help table { border-collapse: collapse; font-size: 13px; }
  #help td { padding: 3px 14px 3px 0; }
  #help kbd { font-family: var(--mono); background: var(--raised); border: 1px solid var(--border); border-radius: 4px; padding: 1px 7px; font-size: 12px; }
</style>
</head>
<body data-stamp="${stamp}" data-stamp-src="${stamp_src}">
<div class="top">
  <span class="eyebrow">board</span>
  <h1>${project}</h1>
  <span class="meta">${meta}</span>
  ${needs_badge}
  <nav class="featnav">${nav}</nav>
  <div class="modes" id="modes">
    <button class="btn" data-mode="frontier">frontier</button>
    <button class="btn" data-mode="full">full</button>
    <button class="btn" data-mode="lanes">lanes</button>
    <button class="btn" id="helpbtn" title="keyboard help (?)">?</button>
  </div>
</div>
<main>

${board}

${needs}

${sections}

${standalone}

<section>
  <h2>Recent commits</h2>
  <pre class="panel log">${log}</pre>
  <p class="footmeta">${footmeta}</p>
</section>

</main>

<div id="help"><div class="card"><table>
<tr><td><kbd>←</kbd> <kbd>→</kbd></td><td>cycle view: frontier / full / lanes</td></tr>
<tr><td><kbd>h</kbd> <kbd>l</kbd> or <kbd>Shift</kbd>+<kbd>←</kbd><kbd>→</kbd></td><td>previous / next section</td></tr>
<tr><td><kbd>j</kbd> <kbd>k</kbd></td><td>next / previous row</td></tr>
<tr><td><kbd>Enter</kbd> / <kbd>Space</kbd></td><td>expand / collapse row</td></tr>
<tr><td><kbd>x</kbd></td><td>expand / collapse all tickets</td></tr>
<tr><td><kbd>?</kbd></td><td>this help</td></tr>
</table></div></div>

<script>
  // Synchronous state restore, before first paint. The module below waits on the
  // mermaid import; doing any of this there makes every 30s reload visibly
  // collapse the graphs and drop expanded tickets for a beat.
  (() => {
    const MODES = ["frontier", "full", "lanes"];
    // state saved by the pre-reload saveState: sessionStorage, with window.name
    // (which survives navigation in every browser) as the fallback carrier
    let saved = null, cache = {};
    try {
      saved = JSON.parse(sessionStorage.getItem("board-view") ?? "null");
      cache = JSON.parse(sessionStorage.getItem("board-svg") ?? "{}");
    } catch {}
    if (!saved && window.name.startsWith("board:")) {
      try { ({ saved = null, cache = {} } = JSON.parse(window.name.slice(6))); } catch {}
    }
    // saved state wins over the URL: the reload keeps a stale ?view= around
    let view = saved?.view ?? new URLSearchParams(location.search).get("view") ?? "frontier";
    if (!MODES.includes(view)) view = "frontier";
    for (const s of document.querySelectorAll(".view")) s.classList.toggle("active", s.dataset.view === view);
    for (const b of document.querySelectorAll("#modes .btn")) b.classList.toggle("on", b.dataset.mode === view);
    // re-inject cached SVGs: an unchanged graph paints instantly instead of re-running mermaid
    for (const el of document.querySelectorAll(".view .mermaid")) {
      const hit = cache[el.dataset.key];
      if (hit && hit.src === el.textContent) { el.dataset.src = hit.src; el.innerHTML = hit.svg; }
    }
    for (const id of saved?.open ?? []) document.getElementById(id)?.setAttribute("open", "");
    if (saved) scrollTo(0, saved.scroll ?? 0);
    window.boardView = { MODES, view, saved };
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
      fontFamily: "ui-monospace, monospace", fontSize: "13px",
      primaryColor: v("--panel"), primaryTextColor: v("--ink"),
      primaryBorderColor: v("--border"), lineColor: v("--edge"),
      clusterBkg: v("--panel"), clusterBorder: v("--border-strong"),
      titleColor: v("--ink2"),
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

  const { MODES, saved } = window.boardView;
  let current = window.boardView.view;

  async function activate(key) {
    current = key;
    for (const s of document.querySelectorAll(".view"))
      s.classList.toggle("active", s.dataset.view === key);
    for (const b of document.querySelectorAll("#modes .btn"))
      b.classList.toggle("on", b.dataset.mode === key);
    await renderGraphs();
  }
  for (const b of document.querySelectorAll("#modes .btn"))
    b.addEventListener("click", () => activate(b.dataset.mode));
  // ---- keyboard: view cycling, section jumps, row cursor ----
  let cur = null;
  const visible = (el) => el.offsetParent !== null;
  const rows = () => [...document.querySelectorAll("main details, .needs-human li:not(:has(details))")].filter(visible);
  function setCur(el) {
    cur?.classList.remove("kcur");
    cur = el ?? null;
    if (cur) { cur.classList.add("kcur"); cur.scrollIntoView({ block: "nearest" }); }
  }
  function moveCur(delta) {
    const list = rows();
    if (!list.length) return;
    const i = list.indexOf(cur);
    setCur(list[i < 0 ? (delta > 0 ? 0 : list.length - 1) : Math.min(Math.max(i + delta, 0), list.length - 1)]);
  }
  function jumpSection(delta) {
    const secs = [...document.querySelectorAll("main > section")].filter(visible);
    if (!secs.length) return;
    const y = scrollY + 1;
    let i = secs.findIndex((s) => s.offsetTop > y) - 1;  // section containing the viewport top
    if (i < -1) i = secs.length - 1;
    const next = secs[Math.min(Math.max(i + delta, 0), secs.length - 1)];
    next.scrollIntoView({ block: "start" });
  }
  const help = document.getElementById("help");
  document.getElementById("helpbtn").addEventListener("click", () => help.classList.toggle("open"));
  help.addEventListener("click", () => help.classList.remove("open"));

  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, [contenteditable]")) return;
    if (e.key === "Escape") { help.classList.remove("open"); setCur(null); return; }
    if (e.key === "?") { help.classList.toggle("open"); return; }
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      if (e.shiftKey) { jumpSection(e.key === "ArrowRight" ? 1 : -1); return; }
      const i = MODES.indexOf(current);
      activate(MODES[(i + (e.key === "ArrowRight" ? 1 : MODES.length - 1)) % MODES.length]);
      return;
    }
    if (e.key === "h") { jumpSection(-1); return; }
    if (e.key === "l") { jumpSection(1); return; }
    if (e.key === "j") { e.preventDefault(); moveCur(1); return; }
    if (e.key === "k") { e.preventDefault(); moveCur(-1); return; }
    if ((e.key === "Enter" || e.key === " ") && cur) {
      e.preventDefault();
      const d = cur.tagName === "DETAILS" ? cur : cur.querySelector("details");
      if (d) d.open = !d.open;
      return;
    }
    if (e.key === "x") {
      const anyOpen = document.querySelector("main details.ticket[open], main .done-fold[open]");
      for (const d of document.querySelectorAll("main details.ticket, main .done-fold")) d.open = !anyOpen;
    }
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
      sessionStorage.setItem("board-view", JSON.stringify(state));
      sessionStorage.setItem("board-svg", JSON.stringify(svgs));
    } catch {}
    try { window.name = "board:" + JSON.stringify({ saved: state, cache: svgs }); } catch {}
  }

  // Reload only when the renderer wrote different content. fetch() is blocked on
  // file://, but a classic script tag isn't — so poll the sidecar stamp file the
  // renderer writes beside this page.
  function poll() {
    const s = document.createElement("script");
    s.src = document.body.dataset.stampSrc + "?" + Date.now();
    s.onload = () => {
      s.remove();
      if (window.__boardStamp !== document.body.dataset.stamp) { saveState(); location.reload(); }
      else setTimeout(poll, 5_000);
    };
    s.onerror = () => { saveState(); location.reload(); };  // no sidecar: stay current the blunt way
    document.head.append(s);
  }
  setTimeout(poll, 5_000);

  await renderGraphs();
  if (!saved && location.hash) openTarget();
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
