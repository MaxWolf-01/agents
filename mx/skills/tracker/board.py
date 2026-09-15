#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml", "markdown"]
# ///
"""Render the tracker board: one HTML page for a tracker's whole agent/tickets tree.

Run `board` from anywhere inside the repo: it finds the tracker (the nearest
agent/tickets up from the current directory, so a worktree or a clone inside a
workspace repo both work), renders, opens the tab, and keeps re-rendering until
Ctrl-C. --no-watch --no-open is the one-shot form: render the page and exit.

Reads every feature directory (spec.md, NN-<slug>.md tickets with
status/blocked-by/type frontmatter, cross-feature refs as <feature>/NN) and
every standalone ticket (*.md at the tracker root) and writes one
self-contained page beside the tracker, agent/board.html. The page is the
tickets as rows grouped by state: needs me (the merged needs-human queue),
frontier, claimed, blocked, proposed, done folded. A row carries its feature,
expands to the ticket's text and links its review page. Feature chips in the
top bar hide and show a feature's rows; a filter box narrows the rows to a
word. Beside the rows a graph panel shows the dependency graph of the feature
of the row under the cursor with that ticket marked, or the whole tracker's
graph with its cross-feature edges. A graph draws only tickets that wait on
something or are waited on: a ticket with no edge is a row, not a node. A
proposed ticket, one the user has not ruled on, keeps its status whatever
blocks it and is drawn in its own colour.

One board per tracker, showing what is actionable now. The tracker is read
from the repo's main checkout whatever checkout the command runs in; a feature
that has a worktree on a branch named after it (how dispatch cuts a feature
worktree) is read from that worktree instead, review pages included, so its
claims and done flips are on the board while the feature is in flight. A
worktree whose branch is already merged is ignored. A standalone ticket whose
slug names such a feature has been absorbed into it and is not shown. A
standalone ticket that an unmerged worktree's branch added or changed since it
left the main branch is shown as well, tagged with the branch, provided its
frontmatter carries a ticket status and the main checkout has no file of that
slug; a copy a branch merely inherited from the main branch is not read twice.

A ticket row links its diffview review page when one has been rendered:
agent/diffviews mirrors agent/tickets, so <feature>/NN-*.html beside the ticket
and <slug>.html beside a standalone ticket. Those pages are gitignored, so the
link appears only on the machine that rendered them.

Watching means: every few seconds it looks for a change under the tracker,
any worktree's copy included, a worktree cut after the start too, and
re-renders on one. Several watchers writing the same page is harmless since the
render is deterministic from disk. Per-feature orchestrator state is read from
agent/tickets/<feature>/needs-human.md: optional YAML frontmatter (worker-host),
then one `- summary :: markdown detail` bullet per pending entry; indented lines
under a bullet continue its detail.

The page polls a sidecar stamp file (written beside the HTML) every 5s and
reloads, keeping scroll position, open sections, the cursor and the hidden
features, only when content actually changed: one open tab stays current
across renders without flicker. The page and its stamp file are gitignored,
like agent/diffviews.

Examples:

    board
    board --no-watch --no-open
    board ~/repos/workspace/agent/tickets --out /tmp/board.html
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
from typing import Annotated

import markdown
import tyro
import yaml

STATUS_SYMBOL = {"done": "✓", "claimed": "⟳", "open": "○", "blocked": "⊘", "proposed": "◌"}
TICKET_STATUSES = {"proposed", "open", "claimed", "done"}  # what a file may declare; blocked is derived
GROUPS = [("needs", "needs me"), ("open", "frontier"), ("claimed", "claimed"), ("blocked", "blocked"), ("proposed", "proposed"), ("done", "done")]


@dataclass
class Args:
    tickets_root: Annotated[Path | None, tyro.conf.Positional, tyro.conf.arg(metavar="[PATH]")] = None
    """Tracker root, e.g. agent/tickets, in any checkout of the repo; the board renders the main checkout's copy. Default: the nearest agent/tickets up from the current directory."""
    out: Path | None = None
    """Output HTML path. Default: board.html beside the tracker (agent/board.html)."""
    repo: Path | None = None
    """Repo for the commit log. Default: the main checkout."""
    open: bool = True
    """Open the result in the browser diffview pages open in ($DIFFVIEW_BROWSER, else xdg-open), so the board and the diffs it links share a window."""
    watch: bool = True
    """Keep running and re-render whenever anything under the tracker changes, until Ctrl-C."""


def main(args: Args) -> None:
    tickets_root = args.tickets_root or find_tracker(Path.cwd())
    roots = tracker_roots(tickets_root)
    assert roots.main.is_dir() or roots.overrides, f"no tracker at {roots.main}"
    repo = (args.repo or roots.main.parent.parent).resolve()
    out = (args.out or roots.main.parent / "board.html").resolve()
    render(roots, repo, out)
    if args.open:
        browser = os.environ.get("DIFFVIEW_BROWSER") or "xdg-open"
        subprocess.Popen([browser, str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if args.watch:
        try:
            watch(tickets_root, repo, out)
        except KeyboardInterrupt:
            pass


def find_tracker(start: Path) -> Path:
    """The nearest agent/tickets at or above `start`: the repo's own tracker, or the workspace repo's when `start` is inside a clone it holds."""
    for d in (start, *start.parents):
        if (d / "agent" / "tickets").is_dir():
            return d / "agent" / "tickets"
    sys.exit(f"board: no agent/tickets at or above {start}")


def render(roots: "Roots", repo: Path, out: Path) -> None:
    project = repo.name
    root = roots.main
    diffviews = load_diffviews(root.parent / "diffviews")
    features = load_features(root, roots.overrides, diffviews)
    # a standalone ticket whose slug names an in-flight feature was absorbed into it (grilling)
    standalone = [k for k in load_standalone(roots, diffviews) if k.slug not in roots.overrides]
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
            roots = tracker_roots(tickets_root)
            dirs = [roots.main, roots.main.parent / "diffviews"]
            dirs += [d for _, o in roots.branches for d in (o, o.parent / "diffviews")]
            snapshot = (git(repo, "rev-parse", "HEAD"),) + tuple(
                (str(f), st.st_mtime_ns, st.st_size)
                for d in dirs if d.is_dir() for f in sorted(d.rglob("*")) if f.is_file() for st in [f.stat()]
            )
            if snapshot != seen:
                if seen is not None:
                    render(roots, repo, out)
                seen = snapshot
        except Exception as e:  # a file deleted mid-scan, a half-written ticket: the next pass sees the settled state
            print(f"board: {e}; retrying", file=sys.stderr)
        time.sleep(2)


# ---- which checkout's tracker ---------------------------------------------


@dataclass
class Roots:
    """Where the tracker is read from.

    `main` is the main checkout's tracker. `overrides` maps a feature name to the copy of
    its directory in a worktree on the branch of that name. `branches` lists every unmerged
    worktree's tracker root with its branch, for the standalone tickets a branch added.
    """

    main: Path
    overrides: dict[str, Path]
    branches: list[tuple[str, Path]]


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


def tracker_roots(tickets_root: Path) -> Roots:
    """The main checkout's tracker, plus the feature directories a worktree on that feature's branch overrides.

    Ticket state an orchestrator commits on its feature branch is invisible to the main
    checkout until the feature merges; the worktree on that branch is where the
    feature's current truth lives, so its copy of the feature directory wins.
    """
    here = tickets_root.resolve()
    wts = worktrees(here)
    if not wts:
        return Roots(here, {}, [])
    toplevel = subprocess.run(["git", "-C", str(here), "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    rel = here.relative_to(Path(toplevel).resolve())
    main = wts[0][0].resolve()
    landed = landed_tips(main)
    overrides: dict[str, Path] = {}
    branches: list[tuple[str, Path]] = []
    for path, branch in wts[1:]:
        if not branch or git(path, "rev-parse", branch) in landed:
            continue
        if (path / rel).is_dir():
            branches.append((branch, path.resolve() / rel))
        if (path / rel / branch).is_dir():
            overrides[branch] = path.resolve() / rel / branch
    return Roots(main / rel, overrides, branches)


def landed_tips(main: Path) -> set[str]:
    """Tips of branches merged --no-ff into the main checkout's history: the second parent of each
    first-parent merge commit. A worktree left behind on such a branch must not outvote the main
    checkout; a branch merely cut from it and idle is not landed, so ancestry alone is the wrong test."""
    parents = git(main, "log", "--first-parent", "--merges", "--format=%P", "HEAD")
    return {line.split()[1] for line in parents.splitlines() if len(line.split()) > 1}


def branch_added(tracker: Path, main: Path) -> list[Path]:
    """The *.md files at a worktree's tracker root that its branch added or changed since it left the
    main checkout's branch, untracked ones included. A file the branch merely inherited is main's to
    show; one main has since retired must not come back through a stale copy."""
    toplevel = Path(git(tracker, "rev-parse", "--show-toplevel")).resolve()
    rel = tracker.resolve().relative_to(toplevel)
    # run from the worktree root: a pathspec is relative to git's cwd, and the names come back root-relative
    base = git(toplevel, "merge-base", "HEAD", git(main, "rev-parse", "HEAD"))
    changed = git(toplevel, "diff", "--name-only", base, "--", str(rel)).splitlines()
    untracked = git(toplevel, "ls-files", "--others", "--exclude-standard", "--", str(rel)).splitlines()
    paths = {toplevel / p for p in changed + untracked if Path(p).parent == rel and p.endswith(".md")}
    return sorted(p for p in paths if p.is_file())


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
    status: str  # proposed | open | claimed | done, plus derived: blocked
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
    status: str  # proposed | open | claimed | done, plus derived: blocked
    kind: str | None
    blocked_by: list[tuple[str, str]]  # (ref "<feature>/NN" or "<slug>", status)
    body_html: str
    diffview: str | None
    source: str | None = None  # the branch whose worktree holds the file; None when the main checkout does


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


def load_standalone(roots: Roots, diffviews: Diffviews) -> list[Standalone]:
    root = roots.main
    standalone = [read_standalone(p, roots, diffviews, None) for p in (sorted(root.glob("*.md")) if root.is_dir() else [])]
    have = {k.slug for k in standalone}
    for branch, tracker in roots.branches:
        dv = load_diffviews(tracker.parent / "diffviews")
        for path in branch_added(tracker, root):
            meta, _ = split_frontmatter(path.read_text())
            if path.stem in have or str(meta.get("status")) not in TICKET_STATUSES:
                continue
            standalone.append(read_standalone(path, roots, dv, branch))
            have.add(path.stem)
    return standalone


def read_standalone(path: Path, roots: Roots, diffviews: Diffviews, source: str | None) -> Standalone:
    assert_safe_name(path.stem)
    meta, body = split_frontmatter(path.read_text())
    heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    body = body[heading.end():] if heading else body
    blocked_by = [(str(n), ref_status(roots.main, roots.overrides, str(n))) for n in meta.get("blocked-by") or []]
    status = str(meta.get("status", "open"))
    if status == "open" and any(s != "done" for _, s in blocked_by):
        status = "blocked"
    return Standalone(
        slug=path.stem,
        title=heading.group(1).strip() if heading else path.stem.replace("-", " "),
        status=status,
        kind=ticket_kind(meta),
        blocked_by=blocked_by,
        body_html=markdown.markdown(body, extensions=["fenced_code", "tables"]),
        diffview=diffviews.link(diffviews.root, f"{path.stem}.html"),
        source=source,
    )


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
    entries: list[str] = []
    for line in body.splitlines():
        if line.startswith("- "):
            entries.append(line[2:].strip())
        elif entries and (line[:1] in (" ", "\t") or not line.strip()):
            entries[-1] += "\n" + line.strip()
    entries = [e.strip() for e in entries]
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
    # a local blocker whose file is gone counts as done, as in ref_status
    present = {t.num for t in tickets}
    for t in tickets:
        t.blocked_by = [b for b in t.blocked_by if b in present]
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
        [(k.slug, k.title, k.status, k.kind, k.blocked_by, k.body_html, k.diffview, k.source) for k in standalone],
        log,
    ))
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def git_log(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline", "-n", "15"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"git log failed in {repo}: {result.stderr.strip()}"
    return result.stdout


# ---- graphs ---------------------------------------------------------------


def slug_id(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", name)


def visible(tickets: list[Ticket]) -> tuple[set[str], set[str]]:
    """(include, ghost): the live tickets plus the done ones a live ticket waits on, and those done ones."""
    by_num = {t.num: t for t in tickets}
    live = {t.num for t in tickets if t.status != "done"}
    ghost = {b for t in tickets if t.num in live for b in t.blocked_by if by_num[b].status == "done"}
    return live | ghost, ghost


def node_label(text: str) -> str:
    # a double quote ends mermaid's label string, and the #quot; entity renders literally in an SVG text label
    return text.replace('"', "”")


def node_id(ns: str, feature: str, num: str) -> str:
    # ns makes node ids unique per diagram instance: mermaid+elk contaminate across
    # diagrams on one page when two share a node id (DOM lookups hit the first SVG).
    return f"T_{ns}_{slug_id(feature)}_{num}"


def node_defs(ns: str, feature: str, tickets: list[Ticket], nums: set[str], ghost: set[str]) -> list[str]:
    lines = []
    for t in tickets:
        if t.num in nums:
            cls = "ghost" if t.num in ghost else t.status
            lines.append(f'  {node_id(ns, feature, t.num)}["{STATUS_SYMBOL[t.status]} {node_label(f"{t.num} {t.title}")}"]:::{cls}')
    lines.extend(f'  click {node_id(ns, feature, t.num)} "#t-{feature}-{t.num}"' for t in tickets if t.num in nums)
    return lines


def feature_graph(feature: Feature) -> str | None:
    """One feature's dependency graph, edges only: live tickets and the done blockers they wait on,
    minus every ticket with no edge. None when nothing in the feature waits on anything."""
    include, ghost = visible(feature.tickets)
    edges = [(b, t.num) for t in feature.tickets if t.num in include for b in t.blocked_by if b in include]
    nums = {n for e in edges for n in e}
    if not nums:
        return None
    ns = "f"
    lines = ["flowchart LR", *node_defs(ns, feature.name, feature.tickets, nums, ghost & nums)]
    lines.extend(f"  {node_id(ns, feature.name, a)} --> {node_id(ns, feature.name, b)}" for a, b in edges)
    return "\n".join(lines)


def board_graph(features: list[Feature], standalone: list[Standalone]) -> str | None:
    """The whole tracker's dependency graph: a subgraph per feature, standalone tickets in their own,
    cross-feature and standalone edges drawn where both ends are on the board; edges only, as in
    feature_graph. None when nothing waits on anything."""
    ns = "b"
    included = {f.name: visible(f.tickets) for f in features}
    shown = [k for k in standalone if k.status != "done"]
    shown_slugs = {k.slug for k in shown}
    # a done ticket a live ticket of another feature waits on is context there too, as within a feature
    by_feature = {f.name: {t.num: t for t in f.tickets} for f in features}
    waits = [ref for f in features for t in f.tickets if t.status != "done" for ref, _ in t.ext_by]
    waits += [ref for k in shown for ref, _ in k.blocked_by]
    for ref in waits:
        if "/" in ref:
            src_feat, src_num = ref.rsplit("/", 1)
            src_num = normalize_num(src_num)
            if by_feature.get(src_feat, {}).get(src_num, None) and by_feature[src_feat][src_num].status == "done":
                included[src_feat][0].add(src_num)
                included[src_feat][1].add(src_num)

    def node(ref: str) -> str | None:
        if "/" in ref:
            src_feat, src_num = ref.rsplit("/", 1)
            if normalize_num(src_num) in included.get(src_feat, (set(), set()))[0]:
                return node_id(ns, src_feat, normalize_num(src_num))
            return None
        return f"K_{ns}_{slug_id(ref)}" if ref in shown_slugs else None

    edges: list[tuple[str, str]] = []
    for f in features:
        include, _ = included[f.name]
        for t in f.tickets:
            if t.num not in include:
                continue
            edges.extend((node_id(ns, f.name, b), node_id(ns, f.name, t.num)) for b in t.blocked_by if b in include)
            edges.extend((src, node_id(ns, f.name, t.num)) for ref, _ in t.ext_by if (src := node(ref)))
    for k in shown:
        edges.extend((src, f"K_{ns}_{slug_id(k.slug)}") for ref, _ in k.blocked_by if (src := node(ref)))
    connected = {n for e in edges for n in e}
    if not connected:
        return None
    lines = ["flowchart LR"]
    for f in features:
        include, ghost = included[f.name]
        nums = {t.num for t in f.tickets if node_id(ns, f.name, t.num) in connected}
        if not nums:
            continue
        lines.append(f'  subgraph S_{ns}_{slug_id(f.name)}["{f.name}"]')
        lines.extend(node_defs(ns, f.name, f.tickets, nums, ghost & nums))
        lines.append("  end")
    ks = [k for k in shown if f"K_{ns}_{slug_id(k.slug)}" in connected]
    if ks:
        lines.append(f'  subgraph S_{ns}__standalone["standalone"]')
        for k in ks:
            lines.append(f'  K_{ns}_{slug_id(k.slug)}["{STATUS_SYMBOL[k.status]} {node_label(k.title)}"]:::{k.status}')
            lines.append(f'  click K_{ns}_{slug_id(k.slug)} "#standalone-{k.slug}"')
        lines.append("  end")
    lines.extend(f"  {a} --> {b}" for a, b in edges)
    return "\n".join(lines)


# ---- page -----------------------------------------------------------------


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


def dv_link(path: str | None) -> str:
    if not path:
        return ""
    return (f'<a class="dv" href="{html.escape(path)}" target="_blank" '
            f'onclick="event.stopPropagation()" title="{html.escape(path)}">diff</a>')


def search_text(*parts: str) -> str:
    return html.escape(re.sub(r"\s+", " ", " ".join(re.sub(r"<[^>]+>", " ", p) for p in parts)).strip().lower(), quote=True)


def row(row_id: str, feature: str, num: str, title: str, status: str, badges: str, chips: str, body: str, dv: str | None = None) -> str:
    """One ticket row: feature tag, number, title, badges, blocker chips; the body folded under it."""
    return (
        f'<details class="ticket row-{status}" id="{row_id}" data-feature="{html.escape(feature)}" data-num="{html.escape(num)}" '
        f'data-search="{search_text(num, title, body)}"><summary>'
        f'<span class="ftag">{html.escape(feature)}</span><span class="num">{html.escape(num)}</span>'
        f'<span class="title">{html.escape(title)}{dv_link(dv)}</span>'
        f'<span class="badges">{badges}</span>'
        f'<span class="chips">{chips or "<span class=deps>—</span>"}</span></summary>'
        f'<div class="body">{body}</div></details>'
    )


def ticket_row(f: Feature, t: Ticket) -> str:
    by_num = {x.num: x for x in f.tickets}
    badges = f'<span class="badge {t.status}">{STATUS_SYMBOL[t.status]} {t.status}</span>{kind_badge(t.kind)}'
    return row(f"t-{f.name}-{t.num}", f.name, t.num, t.title, t.status, badges, dep_chips(f.name, by_num, t), t.body_html, t.diffview)


def standalone_row(k: Standalone) -> str:
    badges = f'<span class="badge {k.status}">{STATUS_SYMBOL[k.status]} {k.status}</span>{kind_badge(k.kind)}'
    if k.source:
        badges += f'<span class="badge source" title="filed on branch {html.escape(k.source)}, not on the main branch">on {html.escape(k.source)}</span>'
    return row(f"standalone-{k.slug}", "standalone", "·", k.title, k.status, badges, ext_chips(k.blocked_by), k.body_html, k.diffview)


def needs_row(f: Feature, i: int, item: str) -> str:
    summary, sep, detail = item.partition(" :: ")
    body = markdown.markdown(detail, extensions=["fenced_code"]) if sep else ""
    return row(f"needs-{f.name}-{i}", f.name, "!", summary if sep else item, "needs", '<span class="badge needs">needs me</span>', "", body)


def feature_chip(f: Feature) -> str:
    counts = Counter(t.status for t in f.tickets)
    bits = [f"spec {f.spec_status}"] if f.spec_status else []
    bits += [f"{counts['done']}/{len(f.tickets) - counts['proposed']} done"] if f.tickets else ["no tickets yet"]
    bits += [f"{counts[s]} {s}" for s in ("open", "claimed", "blocked", "proposed") if counts[s]]
    if f.needs_human:
        bits.append(f"{len(f.needs_human)} need me")
    if f.worker_host:
        bits.append(f"workers on {f.worker_host}")
    dot = '<i class="dot"></i>' if f.needs_human else ""
    return (
        f'<button class="featchip" data-feature="{html.escape(f.name)}" title="{html.escape(" · ".join(bits))}">{dot}{html.escape(f.name)} '
        f'<span class="dim">{counts["done"]}/{len(f.tickets) - counts["proposed"]}</span></button>'
    )


def render_page(
    project: str, features: list[Feature], standalone: list[Standalone], log: str, stamp: str, stamp_src: str
) -> str:
    rows: dict[str, list[str]] = {state: [] for state, _ in GROUPS}
    for f in features:
        rows["needs"].extend(needs_row(f, i, item) for i, item in enumerate(f.needs_human))
    for f in features:
        for t in f.tickets:
            rows[t.status].append(ticket_row(f, t))
    for k in standalone:
        rows[k.status].append(standalone_row(k))
    groups = "".join(
        f'<details class="grp" id="grp-{state}" data-state="{state}"{"" if state == "done" else " open"}>'
        f'<summary><h2>{label} <span class="n">{len(rows[state])}</span></h2></summary>'
        f'<div class="tickets panel-b">{"".join(rows[state])}</div></details>'
        for state, label in GROUPS if rows[state]
    )

    chips = "".join(feature_chip(f) for f in features)
    if standalone:
        chips += f'<button class="featchip" data-feature="standalone" title="tickets without a spec">standalone <span class="dim">{len(standalone)}</span></button>'

    graphs = ""
    for f in features:
        src = feature_graph(f)
        inner = f'<pre class="mermaid" data-key="g:{f.name}">{src}</pre>' if src else f'<div class="gnote">nothing in {html.escape(f.name)} waits on anything</div>'
        graphs += f'<div class="g" data-feature="{html.escape(f.name)}" hidden>{inner}</div>'
    board = board_graph(features, standalone)
    graphs += '<div class="g" data-feature="*" hidden>' + (
        f'<pre class="mermaid" data-key="g:*">{board}</pre>' if board else '<div class="gnote">nothing waits on anything</div>'
    ) + "</div>"

    log_html = "\n".join(
        f'<span class="hash">{html.escape(line.split(" ")[0])}</span> {html.escape(line.partition(" ")[2])}'
        for line in log.strip().splitlines()
    )
    footmeta = f"{len(features)} feature{'s' if len(features) != 1 else ''} · {len(standalone)} standalone · rendered {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · refreshes on change"
    return PAGE.substitute(
        project=html.escape(project), chips=chips, groups=groups, graphs=graphs, log=log_html,
        footmeta=footmeta, stamp=stamp, stamp_src=html.escape(stamp_src),
    )


PAGE = Template(r"""<!doctype html>
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
    --proposed-bg: #1d1a26; --proposed-br: #5b4f7a; --proposed-tx: #a397c4;
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
  .eyebrow, .badge, .num, .deps, .chip, .log, .mermaid, .featchip, .ftag, .search, .n, .gname, .gnote, .keys { font-family: var(--mono); }

  /* ---- sticky topbar: identity, feature chips, filter, graph mode ---- */
  .top { position: sticky; top: 0; z-index: 10; display: flex; gap: 12px; align-items: center; height: var(--topbar-h);
    padding: 0 16px; background: color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter: blur(6px);
    border-bottom: 1px solid var(--border); }
  .top h1 { font-size: 14px; margin: 0; font-weight: 600; white-space: nowrap; }
  .top .eyebrow { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--ink3); }
  .featnav { display: flex; gap: 6px; overflow-x: auto; flex: 1; min-width: 0; scrollbar-width: none; }
  .featchip { font-size: 11.5px; padding: 2px 8px; border: 1px solid var(--border); border-radius: 5px; background: none;
    color: var(--ink2); white-space: nowrap; cursor: pointer; display: inline-flex; gap: .3em; align-items: center; }
  .featchip:hover { color: var(--ink); border-color: var(--border-strong); }
  .featchip.off { opacity: .45; text-decoration: line-through; }
  .dot { display: inline-block; width: .5em; height: .5em; border-radius: 50%; background: var(--human); }
  .search { background: var(--raised); border: 1px solid var(--border); color: var(--ink); font-size: 12px; padding: 3px 8px;
    border-radius: 6px; width: 15rem; }
  .search:focus { outline: 1px solid var(--accent-dim); }
  .modes { display: flex; gap: 4px; }
  .btn { background: var(--raised); border: 1px solid var(--border); border-radius: 6px; padding: 3px 10px;
    cursor: pointer; color: var(--ink2); font-size: 12.5px; white-space: nowrap; font-family: var(--sans); }
  .btn:hover { color: var(--ink); border-color: var(--border-strong); }
  .btn.on { color: var(--accent); border-color: var(--accent-dim); }

  /* ---- rows beside the graph panel; one column when the window is narrow ---- */
  main { display: grid; grid-template-columns: minmax(0, 1fr) minmax(22rem, 38%); gap: 1rem; padding: .6rem 1.25rem 6rem; align-items: start; }
  .side { position: sticky; top: calc(var(--topbar-h) + 8px); max-height: calc(100vh - var(--topbar-h) - 16px); overflow: auto;
    background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: .6rem .8rem; }
  .side.folded .gbody { display: none; }
  @media (max-width: 1100px) {
    /* half a screen: the graph above the rows, sticky, the top bar wrapping and scrolling away */
    main { grid-template-columns: 1fr; }
    .top { position: static; height: auto; flex-wrap: wrap; padding: 6px 12px; }
    .featnav { flex-basis: 100%; order: 1; }
    .search { width: 9rem; margin-left: auto; }
    .side { order: -1; top: 0; max-height: 40vh; }
  }
  .ghead { display: flex; gap: .5rem; align-items: center; margin-bottom: .4rem; }
  .gname { color: var(--ink2); font-size: 12px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .gnote { color: var(--ink3); font-size: 12px; padding: .4rem .2rem; }
  .mermaid { margin: 0; display: flex; justify-content: center; color: var(--ink3); }
  .mermaid:not(:has(svg)) { visibility: hidden; }
  .mermaid svg { max-width: 100%; height: auto; }
  .side g.node.cur rect, .side g.node.cur polygon { stroke: var(--ink) !important; stroke-width: 2.5px !important; }

  h2 { text-transform: uppercase; letter-spacing: .18em; font-size: 11px; font-weight: 600;
    color: var(--ink2); margin: 0; display: flex; align-items: baseline; gap: .8rem; font-family: var(--sans); }
  h2::after { content: ""; flex: 1; border-top: 1px solid var(--border); align-self: center; }
  h2 .n { letter-spacing: 0; font-size: 11.5px; color: var(--ink3); font-weight: 400; }
  .grp { margin-bottom: 1.2rem; }
  .grp > summary { list-style: none; cursor: pointer; padding: .5rem 0 .5rem; }
  .grp > summary::-webkit-details-marker { display: none; }
  .grp > summary::before { content: "▾"; color: var(--ink3); font-size: 11px; margin-right: .5rem; float: left; line-height: 1.6; }
  .grp:not([open]) > summary::before { content: "▸"; }
  .grp.empty { display: none; }
  .grp.kcur > summary h2 { color: var(--accent); }

  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; }
  .panel-b { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 0 .6rem; }

  .done { background: var(--done-bg); border-color: var(--done-br); color: var(--done-tx); }
  .claimed { background: var(--claimed-bg); border-color: var(--claimed-br); color: var(--claimed-tx); }
  .open { background: var(--open-bg); border-color: var(--open-br); color: var(--open-tx); }
  .blocked { background: var(--blocked-bg); border-color: var(--blocked-br); color: var(--blocked-tx); }
  .proposed { background: var(--proposed-bg); border-color: var(--proposed-br); color: var(--proposed-tx); }
  .needs { background: var(--human-bg); border-color: var(--human); color: var(--human); }
  .badge.kind { background: var(--human-bg); border-color: var(--human); color: var(--human); }
  .badge.source { border-style: dashed; border-color: var(--claimed-br); color: var(--claimed-tx); }

  /* ---- ticket rows ---- */
  .ticket { border-bottom: 1px solid var(--border); }
  .ticket:last-child { border-bottom: 0; }
  .ticket.off, .ticket.miss { display: none; }
  .ticket summary { display: grid; grid-template-columns: auto 1.6rem 1fr auto auto; gap: .8rem; align-items: baseline;
    padding: .45rem .3rem; cursor: pointer; list-style: none; }
  .ticket summary::-webkit-details-marker { display: none; }
  .ticket summary:hover { background: var(--raised); }
  .ftag { font-size: 10.5px; color: var(--ink3); border: 1px dashed var(--border); border-radius: 4px; padding: 0 .35rem; white-space: nowrap; }
  .ticket .num { color: var(--ink3); font-size: 12px; text-align: right; }
  .ticket .title { font-size: 13.5px; }
  .row-needs .title { color: var(--ink); }
  .row-open .title { color: var(--open-tx); }
  .row-claimed .title { color: var(--claimed-tx); }
  .row-done .title, .row-proposed .title, .row-blocked .title { color: var(--ink2); }
  .row-needs { border-left: 3px solid var(--human); margin-left: -.6rem; padding-left: calc(.6rem - 3px); }
  .dv { font-family: var(--mono); font-size: 10.5px; margin-left: .5rem; padding: 0 .3rem; text-decoration: none;
    color: var(--ink3); border: 1px solid var(--border); border-radius: 4px; }
  .dv:hover { color: var(--ink); border-color: var(--ink3); }
  .ticket .badges { display: inline-flex; gap: .35rem; white-space: nowrap; }
  .badge { display: inline-block; border: 1px solid; padding: .02rem .55rem; border-radius: 99px; font-size: 11px; white-space: nowrap; }
  .chips { display: inline-flex; gap: .25rem; min-width: 3rem; justify-content: flex-end; flex-wrap: wrap; }
  .chip { border: 1px solid; border-radius: 4px; font-size: 10.5px; padding: 0 .3rem; text-decoration: none; }
  .deps { color: var(--ink3); font-size: 12px; }
  .ticket .body { padding: .2rem 1rem 1rem 3rem; font-size: 13px; color: var(--ink);
    border-left: 3px solid var(--border); margin: 0 0 .8rem .6rem; max-width: 80ch; }
  .ticket .body h2 { text-transform: none; letter-spacing: 0; font-size: 13.5px; color: var(--ink); margin: 1rem 0 .3rem; }
  .ticket .body h2::after { display: none; }
  .ticket .body code { background: var(--raised); border: 1px solid var(--border); border-radius: 4px; padding: 0 .25rem; font-size: .85em; font-family: var(--mono); }
  .ticket .body pre code { display: block; padding: .6rem .8rem; overflow-x: auto; }
  .ticket.flash > summary { background: var(--flash); outline: 2px solid var(--accent); outline-offset: -2px; border-radius: 4px; }
  .ticket > summary { transition: background .6s, outline-color .6s; }
  .ticket.kcur > summary { outline: 2px solid var(--accent); outline-offset: -2px; border-radius: 4px; }
  .ticket { scroll-margin-top: calc(var(--topbar-h) + 60px); scroll-margin-bottom: 60px; }
  .grp { scroll-margin-top: calc(var(--topbar-h) + 10px); }

  .log { padding: .9rem 1.1rem; margin: 0; font-size: 12px; line-height: 1.75; overflow-x: auto; }
  .hash { color: var(--claimed-tx); }
  .footmeta { color: var(--ink3); font-size: 11.5px; font-family: var(--mono); margin-top: .8rem; }

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
  <nav class="featnav" id="featnav">${chips}</nav>
  <input class="search" id="search" type="search" placeholder="filter  (/)" autocomplete="off">
  <div class="modes" id="modes">
    <button class="btn" data-gmode="feature" title="graph of the feature under the cursor (a)">feature</button>
    <button class="btn" data-gmode="all" title="the whole tracker's graph (a)">all</button>
    <button class="btn" id="helpbtn" title="keyboard help (?)">?</button>
  </div>
</div>
<main>
<div class="rows" id="rows">
${groups}
<details class="grp" id="grp-log"><summary><h2>recent commits</h2></summary>
  <pre class="panel log">${log}</pre>
  <p class="footmeta">${footmeta}</p>
</details>
</div>
<aside class="side" id="side">
  <div class="ghead"><span class="eyebrow">dependencies</span><span class="gname" id="gname"></span>
    <button class="btn" id="sidefold" title="fold the graph panel (g)">▾</button></div>
  <div class="gbody" id="gbody">
    <div class="g" data-feature="" ><div class="gnote">expand a row or move onto one (j / k)</div></div>
    ${graphs}
  </div>
</aside>
</main>

<div id="help"><div class="card"><table>
<tr><td><kbd>j</kbd> <kbd>k</kbd></td><td>next / previous row (the graph follows)</td></tr>
<tr><td><kbd>Enter</kbd> / <kbd>Space</kbd></td><td>expand / collapse the row</td></tr>
<tr><td><kbd>c</kbd></td><td>collapse / expand the row's group</td></tr>
<tr><td><kbd>x</kbd></td><td>collapse / expand every group</td></tr>
<tr><td><kbd>h</kbd> <kbd>l</kbd></td><td>previous / next group</td></tr>
<tr><td><kbd>a</kbd></td><td>graph: the row's feature / the whole tracker</td></tr>
<tr><td><kbd>g</kbd></td><td>fold / unfold the graph panel</td></tr>
<tr><td><kbd>/</kbd></td><td>filter rows; <kbd>Esc</kbd> clears</td></tr>
<tr><td><kbd>?</kbd></td><td>this help</td></tr>
</table></div></div>

<script>
  // Synchronous state restore, before first paint. The module below waits on the
  // mermaid import; doing any of this there makes every reload visibly collapse
  // the groups and drop expanded tickets for a beat.
  (() => {
    let saved = null, cache = {};
    try {
      saved = JSON.parse(sessionStorage.getItem("board-view") ?? "null");
      cache = JSON.parse(sessionStorage.getItem("board-svg") ?? "{}");
    } catch {}
    // window.name survives navigation in every browser: the fallback carrier
    if (!saved && window.name.startsWith("board:")) {
      try { ({ saved = null, cache = {} } = JSON.parse(window.name.slice(6))); } catch {}
    }
    const off = new Set(JSON.parse(localStorage.getItem("board-off:" + document.title) ?? "[]"));
    for (const b of document.querySelectorAll(".featchip")) b.classList.toggle("off", off.has(b.dataset.feature));
    for (const t of document.querySelectorAll(".ticket")) t.classList.toggle("off", off.has(t.dataset.feature));
    // re-inject cached SVGs: an unchanged graph paints instantly instead of re-running mermaid
    for (const el of document.querySelectorAll(".mermaid")) {
      const hit = cache[el.dataset.key];
      if (hit && hit.src === el.textContent) { el.dataset.src = hit.src; el.innerHTML = hit.svg; }
    }
    if (saved) {
      for (const d of document.querySelectorAll("details.grp")) d.open = saved.groups?.includes(d.id) ?? d.open;
      for (const id of saved.open ?? []) document.getElementById(id)?.setAttribute("open", "");
      document.getElementById("side").classList.toggle("folded", !!saved.folded);
      scrollTo(0, saved.scroll ?? 0);
    }
    window.boardState = { saved, off };
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
  const classDefs = ["done", "claimed", "open", "blocked", "proposed"].map((s) =>
    "  classDef " + s + " fill:" + v("--" + s + "-bg") + ",stroke:" + v("--" + s + "-br") + ",color:" + v("--" + s + "-tx")
  ).join("\n") + "\n  classDef ghost fill:" + v("--done-bg") + ",stroke:" + v("--done-br") + ",color:" + v("--done-tx") + ",stroke-dasharray:4 3";
  // SVG text labels, not HTML ones: mermaid switches an HTML label into wrapping
  // mode only when its measured width equals the wrap width exactly, and the
  // measurement misses by a fraction of a pixel at any page zoom other than 100%
  // and at some device scale factors (1.75 and 2.225, though not 1.25 or 2), so
  // every long label stays on one line and clips (mermaid-js/mermaid#7794).
  // SVG labels wrap by mermaid's own measure.
  mermaid.initialize({
    startOnLoad: false, layout: "elk", securityLevel: "loose", theme: "base", htmlLabels: false,
    elk: { mergeEdges: false }, flowchart: { htmlLabels: false },
    themeVariables: {
      fontFamily: v("--mono"), fontSize: "13px",
      primaryColor: v("--panel"), primaryTextColor: v("--ink"),
      primaryBorderColor: v("--border"), lineColor: v("--edge"),
      clusterBkg: v("--panel"), clusterBorder: v("--border-strong"),
      titleColor: v("--ink2"),
    },
  });

  let seq = 0;
  async function renderGraphs() {
    // mermaid.render (string -> svg), never mermaid.run: run's in-DOM processing
    // contaminates across the page's many diagrams, render is hermetic per call.
    // Only the graph on show renders; the others wait for their turn.
    for (const el of document.querySelectorAll(".g:not([hidden]) .mermaid")) {
      if (el.querySelector("svg")) continue;  // already rendered, or restored from the svg cache
      el.dataset.src = el.textContent;
      const { svg } = await mermaid.render("m" + Date.now() + "_" + seq++, el.dataset.src + "\n" + classDefs);
      el.innerHTML = svg;
      nodeHover(el);
    }
    markNode();
  }

  // Every node carries its full title as a native tooltip.
  function nodeHover(root) {
    for (const n of root.querySelectorAll("g.node")) {
      const t = document.createElementNS("http://www.w3.org/2000/svg", "title");
      // each wrapped row is its own tspan with no space at the boundary, so join the rows
      const rows = [...n.querySelectorAll(".text-outer-tspan")].map((r) => r.textContent.trim());
      t.textContent = (rows.length ? rows.join(" ") : n.textContent).replace(/\s+/g, " ").trim();
      n.prepend(t);
    }
  }
  for (const el of document.querySelectorAll(".mermaid")) if (el.querySelector("svg")) nodeHover(el);

  // ---- state: hidden features, the cursor row, the graph mode ----
  const { saved, off } = window.boardState;
  const rowsEl = document.getElementById("rows"), side = document.getElementById("side");
  const search = document.getElementById("search");
  let mode = saved?.mode ?? "feature";
  let cur = saved?.cur ? document.getElementById(saved.cur) : null;
  const inField = (e) => e.target.closest("input, textarea, [contenteditable]");
  const visible = (el) => el.offsetParent !== null;
  const rows = () => [...rowsEl.querySelectorAll(".ticket")].filter(visible);
  const groups = () => [...rowsEl.querySelectorAll("details.grp")].filter(visible);

  function applyFilters() {
    const q = search.value.trim().toLowerCase();
    for (const t of rowsEl.querySelectorAll(".ticket")) {
      t.classList.toggle("off", off.has(t.dataset.feature));
      t.classList.toggle("miss", !!q && !t.dataset.search.includes(q));
    }
    for (const g of rowsEl.querySelectorAll("details.grp[data-state]")) {
      const n = g.querySelectorAll(".ticket:not(.off):not(.miss)").length;
      g.querySelector(".n").textContent = n;
      g.classList.toggle("empty", n === 0);
    }
    for (const b of document.querySelectorAll(".featchip")) b.classList.toggle("off", off.has(b.dataset.feature));
    localStorage.setItem("board-off:" + document.title, JSON.stringify([...off]));
    if (cur && !visible(cur)) setCur(null);  // a hidden feature takes its row, and its graph, with it
    showGraph();
  }

  // The graph panel shows one pre-rendered graph at a time: the cursor row's feature, or the
  // whole tracker. Switching shows another element and marks another node; nothing re-renders,
  // so moving between rows of one feature never flickers.
  function showGraph() {
    const feature = cur?.dataset.feature ?? "";
    const key = mode === "all" ? "*" : (feature === "standalone" ? "*" : feature);
    for (const g of side.querySelectorAll(".g")) g.hidden = g.dataset.feature !== key;
    document.getElementById("gname").textContent = mode === "all" ? "whole tracker" : (feature || "");
    for (const b of document.querySelectorAll("[data-gmode]")) b.classList.toggle("on", b.dataset.gmode === mode);
    renderGraphs();
  }
  function markNode() {
    for (const n of side.querySelectorAll("g.node.cur")) n.classList.remove("cur");
    if (!cur) return;
    const g = side.querySelector(".g:not([hidden])");
    const id = cur.id.startsWith("standalone-") ? "K_b_" + cur.id.slice(11).replace(/[^a-zA-Z0-9]/g, "_")
      : "T_" + (g?.dataset.feature === "*" ? "b" : "f") + "_" + cur.dataset.feature.replace(/[^a-zA-Z0-9]/g, "_") + "_" + cur.dataset.num;
    g?.querySelector('g.node[id*="-' + id + '-"]')?.classList.add("cur");
  }
  function setCur(el, scroll = true) {
    cur?.classList.remove("kcur");
    cur = el ?? null;
    if (cur) { cur.classList.add("kcur"); if (scroll) cur.scrollIntoView({ block: "nearest" }); }
    showGraph();
  }
  function moveCur(delta) {
    const list = rows();
    if (!list.length) return;
    const i = list.indexOf(cur);
    setCur(list[i < 0 ? (delta > 0 ? 0 : list.length - 1) : Math.min(Math.max(i + delta, 0), list.length - 1)]);
  }
  function jumpGroup(delta) {
    const gs = groups();
    if (!gs.length) return;
    const y = scrollY + 1;
    let i = gs.findIndex((g) => g.offsetTop > y) - 1;  // the group holding the viewport top
    if (i < -1) i = gs.length - 1;
    gs[Math.min(Math.max(i + delta, 0), gs.length - 1)].scrollIntoView({ block: "start" });
  }

  document.getElementById("featnav").addEventListener("click", (e) => {
    const b = e.target.closest(".featchip"); if (!b) return;
    off.has(b.dataset.feature) ? off.delete(b.dataset.feature) : off.add(b.dataset.feature);
    applyFilters();
  });
  for (const b of document.querySelectorAll("[data-gmode]")) b.addEventListener("click", () => { mode = b.dataset.gmode; showGraph(); });
  document.getElementById("sidefold").addEventListener("click", () => side.classList.toggle("folded"));
  search.addEventListener("input", applyFilters);
  // a click on a row's summary moves the cursor there, so the graph follows the mouse too
  rowsEl.addEventListener("click", (e) => {
    const t = e.target.closest(".ticket");
    if (t && e.target.closest("summary")) setCur(t, false);
  });

  const help = document.getElementById("help");
  document.getElementById("helpbtn").addEventListener("click", () => help.classList.toggle("open"));
  help.addEventListener("click", () => help.classList.remove("open"));

  document.addEventListener("keydown", (e) => {
    if (inField(e)) {
      if (e.key === "Escape") { search.value = ""; applyFilters(); search.blur(); }
      return;
    }
    if (e.key === "Escape") { help.classList.remove("open"); if (cur?.open) cur.open = false; else setCur(null); return; }
    if (e.key === "?") { help.classList.toggle("open"); return; }
    if (e.key === "/") { e.preventDefault(); search.focus(); search.select(); return; }
    if (e.key === "j") { e.preventDefault(); moveCur(1); return; }
    if (e.key === "k") { e.preventDefault(); moveCur(-1); return; }
    if (e.key === "h") { jumpGroup(-1); return; }
    if (e.key === "l") { jumpGroup(1); return; }
    if ((e.key === "Enter" || e.key === " ") && cur) { e.preventDefault(); cur.open = !cur.open; return; }
    if (e.key === "c") {
      const g = cur?.closest("details.grp") ?? groups()[0];
      if (g) g.open = !g.open;
      if (cur && !visible(cur)) setCur(g, false);
      return;
    }
    if (e.key === "x") {
      const anyOpen = rowsEl.querySelector("details.grp[data-state][open]");
      for (const g of rowsEl.querySelectorAll("details.grp[data-state]")) g.open = !anyOpen;
      return;
    }
    if (e.key === "a") { mode = mode === "all" ? "feature" : "all"; showGraph(); return; }
    if (e.key === "g") { side.classList.toggle("folded"); return; }
  });

  // anchor navigation: open the target ticket, move the cursor to it, flash it.
  // A click on an in-page link (a graph node, a chip) runs it directly, so the
  // flash fires again when the hash is already the target's and hashchange stays silent.
  function openTarget(hash = location.hash) {
    const el = document.getElementById(hash.slice(1));
    if (!el) return;
    for (let d = el; d; d = d.parentElement) if (d.tagName === "DETAILS") d.open = true;
    if (el.classList.contains("ticket")) setCur(el, false);
    el.scrollIntoView({ block: "start" });
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 2000);
  }
  window.addEventListener("hashchange", () => openTarget());
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a");
    const href = a && (a.getAttribute("href") || a.getAttribute("xlink:href"));
    if (href && href.startsWith("#") && href === location.hash) setTimeout(() => openTarget(href));
  });

  function saveState() {
    const state = {
      mode, cur: cur?.id ?? null, folded: side.classList.contains("folded"),
      groups: [...document.querySelectorAll("details.grp[open]")].map((d) => d.id),
      open: [...document.querySelectorAll("details.ticket[open]")].map((d) => d.id).filter(Boolean),
      scroll: scrollY,
    };
    const svgs = {};
    for (const el of document.querySelectorAll(".mermaid")) {
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

  if (cur) cur.classList.add("kcur");
  applyFilters();
  if (!saved && location.hash) openTarget();
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__, prog="board"))
