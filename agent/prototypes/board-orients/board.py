#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.14"
# dependencies = ["tyro", "pyyaml", "markdown"]
# ///
"""PROTOTYPE, throwaway (board-orients): the board a returning user reads.

Three variants of the "needs me" shape, one page each (board-A.html, -B, -C), with a
floating switcher. Briefs, priority and size come from fixture.yaml beside this file;
sessions from /var/tmp/board-orients-proto/sessions.json (a transcript scan standing in
for the `Session:` commit trailer). Output goes to /var/tmp/board-orients-proto/.

    uv run agent/prototypes/board-orients/board.py

Render the tracker board: one HTML page for a tracker's whole agent/tickets tree.

Run `board` from anywhere inside the repo: it finds the tracker (the nearest
agent/tickets up from the current directory, so a worktree or a clone inside a
workspace repo both work), renders, opens the tab, and keeps re-rendering until
Ctrl-C. --no-watch --no-open is the one-shot form: render the page and exit.

Reads every feature directory (spec.md, NN-<slug>.md tickets with
status/blocked-by/type frontmatter, cross-feature refs as <feature>/NN) and
every standalone ticket (*.md at the tracker root, the queue file aside) and writes one
self-contained page beside the tracker, agent/board.html. The page is the
tickets as rows grouped by state: needs me (the merged needs-human queue),
needs my review (work waiting for the user's ruling), frontier, claimed,
blocked, proposed, done folded. A row carries its feature, expands to the
ticket's text, and links its review page and the pull requests and issues
its `gh` list names. A click on a row's number copies the absolute path of
the file the row was read from: the ticket, or for a needs-me entry its
needs-human.md. Feature chips in the top bar hide and show a feature's
rows; a filter box narrows the rows to a word. Beside the rows a graph panel shows the dependency graph of the feature
of the row under the cursor with that ticket marked, or the whole tracker's
graph with its cross-feature edges, hidden features left out. A graph draws only tickets that wait on
something or are waited on: a ticket with no edge is a row, not a node. A
proposed ticket, one the user has not ruled on, keeps its status whatever
blocks it and is drawn in its own colour.

One board per tracker, showing what is actionable now. The tracker is read
from the repo's main checkout whatever checkout the command runs in; a feature
that has a worktree on a branch named after it (how dispatch cuts a feature
worktree) is read from that worktree instead, review pages included, so its
claims and review flips are on the board while the feature is in flight. A
worktree whose branch is already merged is ignored. A standalone ticket whose
slug names such a feature has been absorbed into it and is not shown. A
standalone ticket that an unmerged worktree's branch added or changed since it
left the main branch is shown as well, tagged with the branch, provided its
frontmatter carries a ticket status and the main checkout has no file of that
slug; a copy a branch merely inherited from the main branch is not read twice.

A ticket row links its diffview review page when one has been rendered:
agent/diffviews mirrors agent/tickets, so <feature>/NN-*.html beside the ticket
and <slug>.html beside a standalone ticket. Those pages are gitignored, so the
link appears only on the machine that rendered them. Every render asks
`diffview --serve` for the address the pages answer on, so a click from the
board opens a page that saves comments. A server exiting is itself a change to
re-render on, so a watching board keeps its links live; where the pages cannot
be served the link is the file, which the page itself says is read-only.

Watching means: every few seconds it looks for a change under the tracker,
any worktree's copy included, a worktree cut after the start too, and
re-renders on one. Several watchers writing the same page is harmless since the
render is deterministic from disk. The queue is read from the needs-human.md
beside the tickets it belongs to, agent/tickets/<feature>/ for a feature and the
tracker root for the standalone ones: one `- summary :: markdown detail` bullet
per pending entry; indented lines under a bullet continue its detail.

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
import functools
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Annotated

import markdown
import tyro
import yaml

STATUS_SYMBOL = {"done": "✓", "review": "◉", "claimed": "⟳", "open": "○", "blocked": "⊘", "proposed": "◌"}
TICKET_STATUSES = {"proposed", "open", "claimed", "review", "done"}  # what a file may declare; blocked is derived
GROUPS = [
    ("needs", "needs me"), ("review", "needs my review"), ("open", "frontier"), ("claimed", "claimed"),
    ("blocked", "blocked"), ("proposed", "proposed"), ("done", "done"),
]

# ---- PROTOTYPE additions ----
PROTO = Path(__file__).resolve().parent
SCRATCH = Path("/var/tmp/board-orients-proto")
FIX = yaml.safe_load((PROTO / "fixture.yaml").read_text())["tickets"]
SESSIONS = json.loads((SCRATCH / "sessions.json").read_text()) if (SCRATCH / "sessions.json").exists() else {}
SIZE_RANK = {"XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4}
HITL = {"grilling", "prototype"}
VARIANTS = {
    "A": "one queue: everything waiting on you in one group",
    "B": "calls as rows: each question its own row, reviews separate",
    "C": "by priority: bands P1 to P5, what needs you marked",
}


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
    out = (args.out or SCRATCH / "board.html").resolve()
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
    serve_diffviews.cache_clear()  # once per directory per render; the next render asks again, which is what revives a server
    diffviews = serve_diffviews(root.parent / "diffviews")
    features = load_features(root, roots.overrides, diffviews)
    # a standalone ticket whose slug names an in-flight feature was absorbed into it (grilling)
    standalone = [k for k in load_standalone(roots, diffviews) if k.slug not in roots.overrides]
    standalone += [read_standalone(p, roots, diffviews, "sample") for p in sorted((PROTO / "fixtures").glob("*.md"))]
    for f in features:
        for t in f.tickets:
            enrich(t, f"{f.name}/{t.num}", t.path.parent.parent.parent / "show" / f.name / t.path.stem)
    for k in standalone:
        enrich(k, k.slug, root.parent / "show" / k.slug)
    queue = load_needs_human(root / "needs-human.md")
    log = git_log(repo)
    stamp = content_stamp(project, features, standalone, queue, log)
    out.parent.mkdir(parents=True, exist_ok=True)
    for v in VARIANTS:
        page_out = out.with_name(f"{out.stem}-{v}.html")
        page = render_page(project, features, standalone, queue, log, stamp, page_out.name + ".stamp.js", v)
        page_out.write_text(page)
        Path(str(page_out) + ".stamp.js").write_text(f'window.__boardStamp = "{stamp}";\n')
        print(page_out)


def enrich(t: "Ticket | Standalone", tid: str, show: Path) -> None:
    """PROTOTYPE: what the build reads from the ticket file, git log and the show directory."""
    fx = FIX.get(tid) or FIX.get(t.path.stem) or {}
    t.priority, t.size, t.brief = fx.get("priority"), fx.get("size"), fx.get("brief")
    t.sessions = [s for s in SESSIONS.get(tid, SESSIONS.get(t.path.stem, [])) if s.get("cwd")]
    t.show = sorted(p for p in show.rglob("*") if p.is_file() and "/out/" not in str(p)) if show.is_dir() else []
    t.demo = show / "demo" if (show / "demo").is_file() else None
    t.calls = need_calls(branch_text(t, tid)) if t.status == "review" else []
    t.tid = tid


def branch_text(t: "Ticket | Standalone", tid: str) -> str:
    """The ticket as its own branch has it: a worker's closing comment lands there, and the branch
    the board reads carries only the status flip until the build merges."""
    repo = Path(git(t.path.parent, "rev-parse", "--show-toplevel"))
    base = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    branch = f"ticket/{base}/{t.path.stem}"
    done = subprocess.run(["git", "-C", str(repo), "show", f"{branch}:{t.path.relative_to(repo)}"], capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else t.path.read_text()


def need_calls(text: str) -> list[tuple[str, str]]:
    """The tagged calls under the last "I need from you" heading of the ticket's comments."""
    block = text.rsplit("**I need from you**", 1)
    if len(block) < 2:
        return []
    body = re.split(r"\n\*\*[A-Z][^*]*\*\*", block[1], maxsplit=1)[0]
    return [(m.group(1), m.group(2).strip()) for m in re.finditer(r"^\s*-\s*\[(D\d+)\]\s*(.+)$", body, re.MULTILINE)]


def watch(tickets_root: Path, repo: Path, out: Path) -> None:
    """Re-render on any change under the tracker, in every checkout that contributes to it."""
    seen = None
    while True:
        try:
            roots = tracker_roots(tickets_root)
            snapshot = tracker_snapshot(roots, repo)
            if snapshot != seen:
                if seen is not None:
                    render(roots, repo, out)
                seen = snapshot
        except Exception as e:  # a file deleted mid-scan, a half-written ticket: the next pass sees the settled state
            print(f"board: {e}; retrying", file=sys.stderr)
        time.sleep(2)


def tracker_snapshot(roots: "Roots", repo: Path) -> tuple:
    """What the board read last, as a value to compare: the tracker's files in every checkout that
    contributes to it, the review pages beside them, and the commit the log comes from.

    A page server's own bookkeeping counts too, hidden as it is: its exit moves those files, and
    the render that follows is what puts the pages back on an address that answers.
    """
    dirs = [roots.main, roots.main.parent / "diffviews"]
    dirs += [d for _, o in roots.branches for d in (o, o.parent / "diffviews")]
    return (git(repo, "rev-parse", "HEAD"),) + tuple(
        (str(f), st.st_mtime_ns, st.st_size)
        for d in dirs if d.is_dir() for f in sorted(d.rglob("*")) if f.is_file() for st in [f.stat()]
    )


# ---- which checkout's tracker ---------------------------------------------


@dataclass
class Roots:
    """Where the tracker is read from.

    `main` is the main checkout's tracker and `repo` that checkout's root. `branches` lists
    every unmerged worktree's tracker root with its branch: the standalone tickets a branch
    added are read there, and a feature directory in the worktree on the branch of its own
    name overrides the main checkout's copy.
    """

    main: Path
    branches: list[tuple[str, Path]]
    repo: Path | None = None

    @property
    def overrides(self) -> dict[str, Path]:
        return {branch: tracker / branch for branch, tracker in self.branches if (tracker / branch).is_dir()}


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
        return Roots(here, [])
    toplevel = subprocess.run(["git", "-C", str(here), "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    rel = here.relative_to(Path(toplevel).resolve())
    main = wts[0][0].resolve()
    landed = landed_tips(main)
    branches = [
        (branch, path.resolve() / rel)
        for path, branch in wts[1:]
        if branch and (path / rel).is_dir() and git(path, "rev-parse", branch) not in landed
    ]
    return Roots(main / rel, branches, main)


def landed_tips(main: Path) -> set[str]:
    """Tips of branches merged --no-ff into the main checkout's history: the second parent of each
    first-parent merge commit. A worktree left behind on such a branch must not outvote the main
    checkout; a branch merely cut from it and idle is not landed, so ancestry alone is the wrong test."""
    parents = git(main, "log", "--first-parent", "--merges", "--format=%P", "HEAD")
    return {line.split()[1] for line in parents.splitlines() if len(line.split()) > 1}


def branch_added(tracker: Path, repo: Path) -> list[Path]:
    """The *.md files at a worktree's tracker root that its branch added or changed since it left the
    main checkout's branch (`repo` is that checkout's root), untracked ones included. A file the
    branch merely inherited is main's to show; one main has since retired must not come back through
    a stale copy."""
    toplevel = Path(git(tracker, "rev-parse", "--show-toplevel")).resolve()
    rel = tracker.resolve().relative_to(toplevel)
    # run from the worktree root: a pathspec is relative to git's cwd, and the names come back root-relative
    base = git(toplevel, "merge-base", "HEAD", git(repo, "rev-parse", "HEAD"))
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
    status: str  # proposed | open | claimed | review | done, plus derived: blocked
    kind: str | None  # a decision ticket's type (research | prototype | grilling | legwork); None on a build ticket
    blocked_by: list[str]
    ext_by: list[tuple[str, str]]  # cross-feature blockers: (ref "<feature>/NN", status)
    gh: list[str]  # the pull requests and issues the ticket names, as owner/repo#number
    body_html: str
    diffview: str | None
    path: Path  # the file read, in whichever checkout holds the feature
    # PROTOTYPE additions, filled by enrich()
    priority: int | None = None
    size: str | None = None
    brief: str | None = None
    sessions: list = None
    show: list = None
    demo: Path | None = None
    calls: list = None
    tid: str = ""


@dataclass
class Queue:
    """A needs-human.md: where it is, and its pending entries."""

    path: Path
    entries: list[str]


@dataclass
class Feature:
    name: str
    tickets: list[Ticket]
    needs_human: Queue
    spec_status: str | None  # spec.md's status; None when the feature has no spec


@dataclass
class Standalone:
    slug: str
    title: str
    status: str  # proposed | open | claimed | review | done, plus derived: blocked
    kind: str | None
    blocked_by: list[tuple[str, str]]  # (ref "<feature>/NN" or "<slug>", status)
    gh: list[str]
    body_html: str
    diffview: str | None
    path: Path
    source: str | None = None  # the branch whose worktree holds the file; None when the main checkout does
    # PROTOTYPE additions, filled by enrich()
    priority: int | None = None
    size: str | None = None
    brief: str | None = None
    sessions: list = None
    show: list = None
    demo: Path | None = None
    calls: list = None
    tid: str = ""


def load_features(root: Path, overrides: dict[str, Path], diffviews: Diffviews) -> list[Feature]:
    features = []
    # the main checkout may not have the tracker yet: a first feature grilled in its own worktree
    names = sorted(({p.name for p in root.iterdir() if p.is_dir()} if root.is_dir() else set()) | set(overrides))
    for name in names:
        d = overrides.get(name, root / name)
        # an in-flight feature's review pages are rendered and served from its own worktree
        dv = serve_diffviews(d.parent.parent / "diffviews") if name in overrides else diffviews
        tickets = load_tickets(d, dv, dv.root / name, root, overrides)
        spec_status = spec_state(d / "spec.md")
        # a directory with neither tickets nor a spec is not a feature (agent/tickets/done/, say)
        if not tickets and spec_status is None:
            continue
        assert_safe_name(name)
        features.append(Feature(name, tickets, load_needs_human(d / "needs-human.md"), spec_status))
    ids = [slug_id(f.name) for f in features]
    assert len(ids) == len(set(ids)), f"feature names collide as mermaid ids: {sorted(ids)}"
    return features


def assert_safe_name(name: str) -> None:
    # names ride into HTML attributes and mermaid click strings unescaped
    assert re.fullmatch(r"[A-Za-z0-9._-]+", name), f"unsafe tracker name: {name!r}"


def load_standalone(roots: Roots, diffviews: Diffviews) -> list[Standalone]:
    root = roots.main
    standalone = [
        read_standalone(p, roots, diffviews, None)
        for p in (sorted(root.glob("*.md")) if root.is_dir() else [])
        if p.name != "needs-human.md"  # the standalone tickets' queue, beside them as a feature's is
    ]
    have = {k.slug for k in standalone}
    for branch, tracker in roots.branches:
        dv = serve_diffviews(tracker.parent / "diffviews")
        for path in branch_added(tracker, roots.repo):
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
    status = declared_status(meta, path)
    if status == "open" and any(s != "done" for _, s in blocked_by):
        status = "blocked"
    return Standalone(
        slug=path.stem,
        title=heading.group(1).strip() if heading else path.stem.replace("-", " "),
        status=status,
        kind=ticket_kind(meta),
        blocked_by=blocked_by,
        gh=gh_refs(meta, path),
        body_html=markdown.markdown(body, extensions=["fenced_code", "tables"]),
        diffview=diffviews.link(diffviews.root, f"{path.stem}.html"),
        path=path,
        source=source,
    )


@functools.cache
def serve_diffviews(root: Path) -> Diffviews:
    """The review pages under `root`, on the address diffview answers for them.

    `diffview --serve` is idempotent and prints that address, so the port stays diffview's
    to decide; asking on every render is also what brings back a server that has idled out
    since the last one.
    """
    if not root.is_dir():
        return Diffviews(root, None)
    try:
        done = subprocess.run(["diffview", "--serve", str(root)], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:  # no diffview on this machine, so no server for its pages either
        return Diffviews(root, None)
    except subprocess.TimeoutExpired:
        print(f"board: diffview --serve {root} did not come back; linking the pages as files", file=sys.stderr)
        return Diffviews(root, None)
    address = re.search(r"https?://\S+", done.stdout) if done.returncode == 0 else None
    if not address:
        print(f"board: diffview left {root} unserved, so its pages are read-only: {(done.stderr or done.stdout).strip()}", file=sys.stderr)
        return Diffviews(root, None)
    return Diffviews(root, address.group().rstrip("/"))


def spec_state(path: Path) -> str | None:
    if not path.exists():
        return None
    meta, _ = split_frontmatter(path.read_text())
    return str(meta.get("status", "status missing"))


def load_needs_human(path: Path) -> Queue:
    if not path.exists():
        return Queue(path, [])
    entries: list[str] = []
    for line in path.read_text().splitlines():
        if line.startswith("- "):
            entries.append(line[2:].strip())
        elif entries and (line[:1] in (" ", "\t") or not line.strip()):
            entries[-1] += "\n" + line.strip()
    return Queue(path, [e.strip() for e in entries])


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
                status=declared_status(meta, path),
                kind=ticket_kind(meta),
                blocked_by=[normalize_num(n) for n in blockers if is_local_ref(n)],
                ext_by=[(str(n), ref_status(root, overrides, str(n))) for n in blockers if not is_local_ref(n)],
                gh=gh_refs(meta, path),
                body_html=render_body(body, feature_dir.name),
                diffview=diffviews.link(dv_dir, f"{path.name[:2]}-*.html"),
                path=path,
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


def declared_status(meta: dict, path: Path) -> str:
    status = str(meta.get("status", "open"))
    assert status in TICKET_STATUSES, f"{path}: status {status!r}; a ticket declares one of {sorted(TICKET_STATUSES)}"
    return status


def ticket_kind(meta: dict) -> str | None:
    kind = meta.get("type")
    return str(kind) if kind else None


GH_REF = re.compile(r"[\w.-]+/[\w.-]+#\d+")


def gh_refs(meta: dict, path: Path) -> list[str]:
    refs = [str(r) for r in meta.get("gh") or []]
    for ref in refs:
        assert GH_REF.fullmatch(ref), f"{path}: gh reference {ref!r}; a reference is owner/repo#number"
    return refs


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


def content_stamp(project: str, features: list[Feature], standalone: list[Standalone], queue: Queue, log: str) -> str:
    # everything the page shows except the render timestamp: an unchanged board
    # keeps its stamp, so the open tab knows not to reload
    key = repr((
        project,
        [(f.name, f.needs_human, f.spec_status,
          [(t.num, t.title, t.status, t.kind, t.blocked_by, t.ext_by, t.gh, t.body_html, t.diffview, t.path) for t in f.tickets])
         for f in features],
        [(k.slug, k.title, k.status, k.kind, k.blocked_by, k.gh, k.body_html, k.diffview, k.path, k.source) for k in standalone],
        queue,
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


def standalone_id(ns: str, slug: str) -> str:
    return f"K_{ns}_{slug_id(slug)}"


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


def board_graph(features: list[Feature], standalone: list[Standalone]) -> dict | None:
    """The whole tracker's dependency graph, as the parts the page composes for whichever features
    are shown: per feature, and for the standalone tickets as one more, its nodes with their lines;
    every edge with the two features it joins. Edges only, as in feature_graph; a cross-feature or
    standalone edge is drawn where both ends are on the board, and a done ticket another feature's
    live ticket waits on is its dashed context there too. None when nothing waits on anything."""
    ns = "b"
    include = {f.name: visible(f.tickets)[0] for f in features}
    ghost = {f.name: visible(f.tickets)[1] for f in features}
    shown = [k for k in standalone if k.status != "done"]
    shown_slugs = {k.slug for k in shown}
    by_feature = {f.name: {t.num: t for t in f.tickets} for f in features}
    waits = [ref for f in features for t in f.tickets if t.status != "done" for ref, _ in t.ext_by]
    waits += [ref for k in shown for ref, _ in k.blocked_by]
    for ref in waits:
        if "/" in ref:
            src_feat, src_num = ref.rsplit("/", 1)
            src_num = normalize_num(src_num)
            if (src := by_feature.get(src_feat, {}).get(src_num)) and src.status == "done":
                include[src_feat].add(src_num)
                ghost[src_feat].add(src_num)

    def node(ref: str) -> tuple[str, str] | None:
        """(feature, node id) of a blocker that is on the board."""
        if "/" in ref:
            src_feat, src_num = ref.rsplit("/", 1)
            src_num = normalize_num(src_num)
            return (src_feat, node_id(ns, src_feat, src_num)) if src_num in include.get(src_feat, set()) else None
        return ("standalone", standalone_id(ns, ref)) if ref in shown_slugs else None

    edges: list[tuple[str, str, str, str]] = []  # (feature, node) --> (feature, node)
    for f in features:
        for t in f.tickets:
            if t.num not in include[f.name]:
                continue
            to = (f.name, node_id(ns, f.name, t.num))
            edges += [(f.name, node_id(ns, f.name, b), *to) for b in t.blocked_by if b in include[f.name]]
            edges += [(*src, *to) for ref, _ in t.ext_by if (src := node(ref))]
    for k in shown:
        edges += [(*src, "standalone", standalone_id(ns, k.slug)) for ref, _ in k.blocked_by if (src := node(ref))]
    if not edges:
        return None
    connected = {n for _, a, _, b in edges for n in (a, b)}
    parts: dict = {"features": [], "edges": [{"a": fa, "from": a, "b": fb, "to": b, "line": f"  {a} --> {b}"} for fa, a, fb, b in edges]}
    for f in features:
        nodes = [
            {"id": node_id(ns, f.name, t.num), "lines": node_defs(ns, f.name, f.tickets, {t.num}, ghost[f.name] & {t.num})}
            for t in f.tickets if node_id(ns, f.name, t.num) in connected
        ]
        if nodes:
            parts["features"].append({"name": f.name, "nodes": nodes})
    nodes = [
        {"id": standalone_id(ns, k.slug), "lines": [
            f'  {standalone_id(ns, k.slug)}["{STATUS_SYMBOL[k.status]} {node_label(k.title)}"]:::{k.status}',
            f'  click {standalone_id(ns, k.slug)} "#standalone-{k.slug}"',
        ]}
        for k in shown if standalone_id(ns, k.slug) in connected
    ]
    if nodes:
        parts["features"].append({"name": "standalone", "nodes": nodes})
    return parts


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


def dv_link(path: str | None, label: str = "diff") -> str:
    if not path:
        return ""
    return (f'<a class="dv" href="{html.escape(path)}" target="_blank" '
            f'onclick="event.stopPropagation()" title="{html.escape(path)}">{label}</a>')


def gh_links(refs: Sequence[str]) -> str:
    # the issues URL serves a pull request too: GitHub redirects it to the pull page
    return "".join(
        f'<a class="dv gh" href="https://github.com/{repo}/issues/{num}" target="_blank" '
        f'onclick="event.stopPropagation()" title="on GitHub">{html.escape(ref)}</a>'
        for ref in refs for repo, num in [ref.split("#")]
    )


def search_text(*parts: str) -> str:
    return html.escape(re.sub(r"\s+", " ", " ".join(re.sub(r"<[^>]+>", " ", p) for p in parts)).strip().lower(), quote=True)


def inline_md(text: str) -> str:
    return re.sub(r"^<p>|</p>$", "", markdown.markdown(text).strip())


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inline_md(text))).strip()


def copy_btn(label: str, payload: str, title: str, cls: str = "") -> str:
    return (f'<button class="cp {cls}" data-copy="{html.escape(payload, quote=True)}" '
            f'onclick="event.stopPropagation(); event.preventDefault()" title="{html.escape(title)}">{label}</button>')


def call_line(t, tag: str, text: str) -> str:
    """What a copy of one call yields: the tag and the question, so a fresh session knows what is being answered."""
    return f"{t.tid} {tag} ({t.path}): {plain(text)}\nMy ruling: "


def calls_html(t) -> str:
    items = "".join(
        f'<li>{copy_btn(html.escape(f"{t.tid} {tag}"), call_line(t, tag, text), "copy the call with its question, to paste into any session", "tag")} {inline_md(text)}</li>'
        for tag, text in t.calls
    )
    return f'<ul class="calls">{items}</ul>'


def pri_badges(t) -> str:
    out = f'<span class="badge pri p{t.priority}" title="priority, the agent\'s reading">P{t.priority}</span>' if t.priority else '<span class="badge pri none" title="no priority yet">P?</span>'
    if t.size:
        out += f'<span class="badge size" title="your time on it: XS under 15 min, S half an hour, M an hour or two, L half a day, XL several sessions">{t.size}</span>'
    return out


def when(ts: str | None) -> str:
    return ts[5:16].replace("T", " ") if ts else "?"


def extras_body(t) -> str:
    parts = []
    if t.sessions:
        lis = "".join(
            f'<li>{copy_btn("resume", f"cd {s["cwd"]} && claude --resume {s["id"]}", "copy the resume command")}'
            f' <b>{html.escape(s["title"])}</b> <span class="dim">{when(s["first"])} → {when(s["last"])} · {html.escape(Path(s["cwd"]).name)}</span></li>'
            for s in reversed(t.sessions)
        )
        parts.append(f'<div class="xblock"><h4>sessions on this machine</h4><ul>{lis}</ul></div>')
    if t.demo or t.show:
        demo = (f'<p>{copy_btn("copy", str(t.demo), "copy the demo path")} demo <code>{html.escape(str(t.demo))}</code></p>' if t.demo else "")
        files = "".join(f'<a class="dv" href="file://{html.escape(str(p))}" target="_blank" onclick="event.stopPropagation()">{html.escape(p.name)}</a>' for p in t.show if p.name != "demo")
        parts.append(f'<div class="xblock"><h4>artefacts</h4>{demo}{f"<p>{files}</p>" if files else ""}</div>')
    return "".join(parts)


def row(
    row_id: str, feature: str, num: str, title: str, status: str, badges: str, chips: str, body: str, path: Path,
    dv: str | None = None, gh: Sequence[str] = (), t=None, show_calls: bool = False, cls: str = "", title_html: str | None = None,
) -> str:
    """One ticket row: feature tag, number (a click copies `path`), title with its links, badges, blocker chips,
    then the brief (and, where asked, the open calls) under the title; the body folded under it."""
    under = ""
    if t is not None and t.brief:
        under += f'<span class="brief">{html.escape(t.brief)}</span>'
    if t is not None and show_calls and t.calls:
        under += calls_html(t)
    extra = extras_body(t) if t is not None else ""
    return (
        f'<details class="ticket row-{status} {cls}" id="{row_id}" data-feature="{html.escape(feature)}" data-num="{html.escape(num)}" '
        f'data-search="{search_text(num, title, body, *gh, (t.brief or "") if t is not None else "")}" data-path="{html.escape(str(path))}"><summary>'
        f'<span class="ftag">{html.escape(feature)}</span><span class="num" title="copy {html.escape(str(path))} (y)">{html.escape(num)}</span>'
        f'<span class="title">{title_html or html.escape(title)}{dv_link(dv)}{gh_links(gh)}</span>'
        f'<span class="badges">{badges}</span>'
        f'<span class="chips">{chips or "<span class=deps>—</span>"}</span>{under}</summary>'
        f'<div class="body">{f"<p class=dvline>{dv_link(dv, 'open the review page')}</p>" if dv else ""}{extra}{body}</div></details>'
    )


STATE_BADGE = {"review": "to rule on", "open": "frontier", "claimed": "in progress", "blocked": "blocked", "proposed": "proposed", "done": "done"}


def ticket_badges(t, state_badge: bool) -> str:
    out = pri_badges(t) + kind_badge(t.kind)
    if state_badge:
        label = "session with you" if t.kind in HITL and t.status in ("open", "proposed") else STATE_BADGE.get(t.status, t.status)
        out += f'<span class="badge st {t.status}">{label}</span>'
    if getattr(t, "source", None) == "sample":
        out += '<span class="badge source" title="a real ticket as it stood in review, loaded from the prototype\'s fixtures">sample</span>'
    elif getattr(t, "source", None):
        out += f'<span class="badge source" title="filed on branch {html.escape(t.source)}, not on the main branch">on {html.escape(t.source)}</span>'
    return out


def ticket_row(f: Feature, t: Ticket, show_calls: bool = False, state_badge: bool = False, cls: str = "") -> str:
    by_num = {x.num: x for x in f.tickets}
    return row(f"t-{f.name}-{t.num}", f.name, t.num, t.title, t.status, ticket_badges(t, state_badge), dep_chips(f.name, by_num, t),
               t.body_html, t.path, t.diffview, t.gh, t, show_calls, cls)


def standalone_row(k: Standalone, show_calls: bool = False, state_badge: bool = False, cls: str = "") -> str:
    return row(f"standalone-{k.slug}", "standalone", "--", k.title, k.status, ticket_badges(k, state_badge), ext_chips(k.blocked_by),
               k.body_html, k.path, k.diffview, k.gh, k, show_calls, cls)


def call_row(feature: str, t, tag: str, text: str, anchor: str) -> str:
    """Variant B: one question as its own row; the ticket it belongs to is one click away."""
    title_html = f'{copy_btn(html.escape(f"{t.tid} {tag}"), call_line(t, tag, text), "copy the call with its question, to paste into any session", "tag")} {inline_md(text)}'
    body = f'<p><a href="#{anchor}">{html.escape(t.title)}</a></p>' + (f"<p>{html.escape(t.brief)}</p>" if t.brief else "")
    return row(f"call-{slug_id(t.tid)}-{tag}", feature, tag, plain(text), "needs", pri_badges(t), "", body, t.path, t.diffview, (), None, False, "", title_html)


def needs_row(owner: str, i: int, item: str, queue: Path) -> str:
    summary, sep, detail = item.partition(" :: ")
    body = markdown.markdown(detail, extensions=["fenced_code"]) if sep else ""
    return row(f"needs-{owner}-{i}", owner, "!", summary if sep else item, "needs", '<span class="badge needs">needs me</span>', "", body, queue)


def feature_chip(f: Feature) -> str:
    counts = Counter(t.status for t in f.tickets)
    bits = [f"spec {f.spec_status}"] if f.spec_status else []
    bits += [f"{counts['done']}/{len(f.tickets)} done"] if f.tickets else ["no tickets yet"]
    bits += [f"{counts[s]} {s}" for s in ("open", "claimed", "review", "blocked", "proposed") if counts[s]]
    if f.needs_human.entries:
        bits.append(f"{len(f.needs_human.entries)} need me")
    dot = '<i class="dot"></i>' if f.needs_human.entries or counts["review"] else ""
    return (
        f'<button class="featchip" data-feature="{html.escape(f.name)}" title="{html.escape(" · ".join(bits))}">{dot}{html.escape(f.name)} '
        f'<span class="dim">{counts["done"]}/{len(f.tickets)}</span></button>'
    )


def needs_me(t) -> bool:
    """Waiting on the user: a build to rule on, or a decision ticket that needs a session with them."""
    return t.status == "review" or (t.kind in HITL and t.status in ("open", "proposed"))


def sort_key(t) -> tuple:
    return (t.priority or 9, SIZE_RANK.get(t.size or "", 9), t.title.lower())


def variant_groups(variant: str) -> list[tuple[str, str]]:
    if variant == "A":
        return [("needs", "needs me"), ("open", "frontier"), ("claimed", "in progress"), ("blocked", "blocked"), ("proposed", "proposed"), ("done", "done")]
    if variant == "B":
        return [("needs", "needs me: one row per question"), ("review", "needs my review"), ("open", "frontier"), ("claimed", "in progress"),
                ("blocked", "blocked"), ("proposed", "proposed"), ("done", "done")]
    return [("p1", "P1 · now"), ("p2", "P2 · next"), ("p3", "P3 · soon"), ("p4", "P4 · later"), ("p5", "P5 · someday"),
            ("p9", "no priority yet"), ("done", "done")]


def render_page(
    project: str, features: list[Feature], standalone: list[Standalone], queue: Queue,
    log: str, stamp: str, stamp_src: str, variant: str = "A",
) -> str:
    groups_def = variant_groups(variant)
    items: dict[str, list[tuple[tuple, str]]] = {state: [] for state, _ in groups_def}
    top = (-1,)
    for f in features:
        items["needs" if variant != "C" else "p1"].extend((top, needs_row(f.name, i, item, f.needs_human.path)) for i, item in enumerate(f.needs_human.entries))
    items["needs" if variant != "C" else "p1"].extend((top, needs_row("standalone", i, item, queue.path)) for i, item in enumerate(queue.entries))
    everything = [(f, t) for f in features for t in f.tickets] + [(None, k) for k in standalone]
    for f, t in everything:
        render_one = (lambda **kw: ticket_row(f, t, **kw)) if f is not None else (lambda **kw: standalone_row(t, **kw))
        anchor = f"t-{f.name}-{t.num}" if f is not None else f"standalone-{t.slug}"
        feature = f.name if f is not None else "standalone"
        if variant == "A":
            group = "needs" if needs_me(t) else t.status
            items[group].append((sort_key(t), render_one(show_calls=True, state_badge=group == "needs")))
        elif variant == "B":
            if t.status == "review":
                items["review"].append((sort_key(t), render_one()))
                items["needs"].extend((sort_key(t) + (tag,), call_row(feature, t, tag, text, anchor)) for tag, text in t.calls)
            elif needs_me(t):
                items["needs"].append((sort_key(t), render_one(state_badge=True)))
            else:
                items[t.status].append((sort_key(t), render_one()))
        else:
            group = "done" if t.status == "done" else f"p{t.priority or 9}"
            mine = needs_me(t)
            items[group].append(((0 if mine else 1,) + sort_key(t), render_one(show_calls=True, state_badge=True, cls="mine" if mine else "")))
    rows = {state: [h for _, h in sorted(v, key=lambda x: x[0])] for state, v in items.items()}
    groups = "".join(
        f'<details class="grp" id="grp-{state}" data-state="{state}"{"" if state == "done" else " open"}>'
        f'<summary><h2>{label} <span class="n">{len(rows[state])}</span></h2></summary>'
        f'<div class="tickets panel-b">{"".join(rows[state])}</div></details>'
        for state, label in groups_def if rows[state]
    )

    chips = "".join(feature_chip(f) for f in features)
    if standalone or queue.entries:
        chips += f'<button class="featchip" data-feature="standalone" title="tickets without a spec">standalone <span class="dim">{len(standalone)}</span></button>'

    graphs = ""
    for f in features:
        src = feature_graph(f)
        inner = f'<pre class="mermaid" data-key="g:{f.name}">{src}</pre>' if src else f'<div class="gnote">nothing in {html.escape(f.name)} waits on anything</div>'
        graphs += f'<div class="g" data-feature="{html.escape(f.name)}" hidden>{inner}</div>'
    board = board_graph(features, standalone)
    graphs += '<div class="g" data-feature="*" hidden>' + (
        f'<pre class="mermaid" data-key="g:*"></pre><div class="gnote" hidden>every ticket with an edge is in a hidden feature</div>'
        f'<script type="application/json" class="parts">{json.dumps(board).replace("</", "<\\/")}</script>'
        if board else '<div class="gnote">nothing waits on anything</div>'
    ) + "</div>"

    log_html = "\n".join(
        f'<span class="hash">{html.escape(line.split(" ")[0])}</span> {html.escape(line.partition(" ")[2])}'
        for line in log.strip().splitlines()
    )
    footmeta = f"{len(features)} feature{'s' if len(features) != 1 else ''} · {len(standalone)} standalone · rendered {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · refreshes on change"
    keys = list(VARIANTS)
    i = keys.index(variant)
    switcher = (
        f'<div id="proto-switch"><a href="board-{keys[i - 1]}.html" id="proto-prev">←</a>'
        f'<span><b>{variant}</b> · {html.escape(VARIANTS[variant])}</span>'
        f'<a href="board-{keys[(i + 1) % len(keys)]}.html" id="proto-next">→</a></div>'
    )
    return PAGE.substitute(
        project=html.escape(project), chips=chips, groups=groups, graphs=graphs, log=log_html,
        footmeta=footmeta, stamp=stamp, stamp_src=html.escape(stamp_src), switcher=switcher,
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
    --review-bg: #2a1622; --review-br: #9c4d78; --review-tx: #ee9ccb;
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
    .top { height: auto; flex-wrap: wrap; padding: 6px 12px; }
    .featnav { flex-basis: 100%; order: 1; }
    .search { width: 9rem; margin-left: auto; }
    .side { order: -1; top: var(--topbar-h); max-height: 40vh; }
  }
  .ghead { display: flex; gap: .5rem; align-items: center; margin-bottom: .4rem; }
  .gname { color: var(--ink2); font-size: 12px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .gnote { color: var(--ink3); font-size: 12px; padding: .4rem .2rem; }
  .mermaid { margin: 0; display: flex; justify-content: center; color: var(--ink3); }
  .mermaid:not(:has(svg)) { visibility: hidden; }
  .mermaid svg { max-width: 100%; height: auto; }
  .side g.node.cur rect, .side g.node.cur polygon { stroke: #fff !important; stroke-width: 3px !important; filter: drop-shadow(0 0 4px #fff8); }

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

  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; }
  .panel-b { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 0 .6rem; }

  .done { background: var(--done-bg); border-color: var(--done-br); color: var(--done-tx); }
  .claimed { background: var(--claimed-bg); border-color: var(--claimed-br); color: var(--claimed-tx); }
  .review { background: var(--review-bg); border-color: var(--review-br); color: var(--review-tx); }
  .open { background: var(--open-bg); border-color: var(--open-br); color: var(--open-tx); }
  .blocked { background: var(--blocked-bg); border-color: var(--blocked-br); color: var(--blocked-tx); }
  .proposed { background: var(--proposed-bg); border-color: var(--proposed-br); color: var(--proposed-tx); }
  .needs { background: var(--human-bg); border-color: var(--human); color: var(--human); }
  .badge.kind { border-color: var(--border); color: var(--ink3); border-style: dashed; }
  .badge.source { border-style: dashed; border-color: var(--claimed-br); color: var(--claimed-tx); }

  /* ---- ticket rows ---- */
  .ticket { border-bottom: 1px solid var(--border); }
  .ticket:last-child { border-bottom: 0; }
  .ticket.off, .ticket.miss { display: none; }
  .ticket summary { display: grid; grid-template-columns: 9.5rem 1.6rem 1fr 8rem 5rem; gap: .8rem; align-items: baseline;
    padding: .45rem .3rem; cursor: pointer; list-style: none; }
  .ticket summary::-webkit-details-marker { display: none; }
  .ticket summary:hover { background: var(--raised); }
  .ftag { font-size: 10.5px; color: var(--ink3); border: 1px dashed var(--border); border-radius: 4px; padding: 0 .35rem; white-space: nowrap;
    justify-self: start; max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
  /* the number copies the row's path: its click target is the whole cell, row padding included */
  .ticket .num { color: var(--ink3); font-size: 12px; text-align: right; cursor: copy; white-space: nowrap;
    padding: .45rem .3rem; margin: -.45rem -.3rem; border: 1px solid transparent; border-radius: 5px; }
  .ticket .num:hover { color: var(--accent); background: var(--raised); border-color: var(--border-strong); }
  .ticket .title { font-size: 13.5px; }
  .row-needs .title { color: var(--ink); }
  .row-open .title { color: var(--open-tx); }
  .row-claimed .title { color: var(--claimed-tx); }
  .row-review .title { color: var(--review-tx); }
  .row-done .title, .row-proposed .title, .row-blocked .title { color: var(--ink2); }
  .row-needs { border-left: 3px solid var(--human); margin-left: -.6rem; padding-left: calc(.6rem - 3px); }
  .dv { font-family: var(--mono); font-size: 10.5px; margin-left: .5rem; padding: 0 .3rem; text-decoration: none;
    color: var(--ink3); border: 1px solid var(--border); border-radius: 4px; }
  .dv:hover { color: var(--ink); border-color: var(--ink3); }
  .dv.gh { border-style: dashed; }
  .dvline { margin: .4rem 0 0; } .dvline .dv { margin-left: 0; padding: .1rem .5rem; }
  .ticket .badges { display: inline-flex; gap: .35rem; white-space: nowrap; justify-self: end; }
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
  @media (max-width: 1100px) { .ticket summary { grid-template-columns: 6rem 1.6rem 1fr auto auto; } }
  .grp { scroll-margin-top: calc(var(--topbar-h) + 10px); }

  .log { padding: .9rem 1.1rem; margin: 0; font-size: 12px; line-height: 1.75; overflow-x: auto; }
  .hash { color: var(--claimed-tx); }
  .footmeta { color: var(--ink3); font-size: 11.5px; font-family: var(--mono); margin-top: .8rem; }

  #toast { position: fixed; bottom: 1.2rem; left: 50%; transform: translateX(-50%); z-index: 50; max-width: 90vw;
    background: var(--raised); border: 1px solid var(--border-strong); border-radius: 6px; padding: .3rem .8rem;
    font: 12px var(--mono); color: var(--ink2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    opacity: 0; transition: opacity .2s; pointer-events: none; }
  #toast.on { opacity: 1; }

  #help { position: fixed; inset: 0; z-index: 100; background: rgba(10,11,13,.7); display: none; align-items: center; justify-content: center; }
  #help.open { display: flex; }
  #help .card { background: var(--panel); border: 1px solid var(--border-strong); border-radius: 10px; padding: 20px 26px; box-shadow: 0 10px 40px rgba(0,0,0,.6); }
  #help table { border-collapse: collapse; font-size: 13px; }
  #help td { padding: 3px 14px 3px 0; }
  #help kbd { font-family: var(--mono); background: var(--raised); border: 1px solid var(--border); border-radius: 4px; padding: 1px 7px; font-size: 12px; }

  /* ---- PROTOTYPE additions ---- */
  .ticket summary { grid-template-columns: 9.5rem 2.4rem 1fr auto 5rem; row-gap: .15rem; }
  .ticket summary .brief { grid-column: 3 / -1; color: var(--ink2); font-size: 12.5px; line-height: 1.45; max-width: 90ch; }
  .ticket summary .calls { grid-column: 3 / -1; margin: .1rem 0; padding: 0; list-style: none; font-size: 12.5px; max-width: 100ch; }
  .calls li { margin: .25rem 0; color: var(--ink); }
  .calls code, .title code { background: var(--raised); border: 1px solid var(--border); border-radius: 4px; padding: 0 .25rem; font-size: .85em; font-family: var(--mono); }
  .cp { font-family: var(--mono); font-size: 10.5px; background: var(--raised); color: var(--ink2); border: 1px solid var(--border-strong);
    border-radius: 4px; padding: 0 .35rem; cursor: copy; white-space: nowrap; }
  .cp:hover { color: var(--accent); border-color: var(--accent-dim); }
  .cp.tag { color: var(--human); border-color: var(--human); background: var(--human-bg); }
  .badge.pri { border-color: var(--border-strong); color: var(--ink2); }
  .badge.pri.p1 { border-color: var(--human); color: var(--human); }
  .badge.pri.p2 { border-color: var(--claimed-br); color: var(--claimed-tx); }
  .badge.pri.none { border-style: dashed; color: var(--ink3); }
  .badge.size { border-color: var(--border); color: var(--ink2); }
  .ticket.mine { border-left: 3px solid var(--human); margin-left: -.6rem; padding-left: calc(.6rem - 3px); }
  .xblock { margin: .6rem 0 .8rem; }
  .xblock h4 { margin: 0 0 .25rem; font-size: 10.5px; text-transform: uppercase; letter-spacing: .12em; color: var(--ink3); font-weight: 600; }
  .xblock ul { list-style: none; padding: 0; margin: 0; } .xblock li { margin: .25rem 0; } .xblock p { margin: .25rem 0; }
  #proto-switch { position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%); z-index: 60; display: flex; gap: 14px;
    align-items: center; background: #f5d76e; color: #1a1a1a; border-radius: 99px; padding: 6px 18px; font: 13px var(--sans);
    box-shadow: 0 4px 18px rgba(0,0,0,.5); }
  #proto-switch a { color: #1a1a1a; font-weight: 700; font-size: 17px; }
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
    <button class="btn" id="sidefold" title="fold the graph panel (b)">▾</button></div>
  <div class="gbody" id="gbody">
    <div class="g" data-feature="" ><div class="gnote">expand a row or move onto one (j / k)</div></div>
    ${graphs}
  </div>
</aside>
</main>

<div id="help"><div class="card"><table>
<tr><td><kbd>j</kbd> <kbd>k</kbd></td><td>next / previous row (the graph follows)</td></tr>
<tr><td><kbd>J</kbd> <kbd>K</kbd></td><td>next / previous group</td></tr>
<tr><td><kbd>gg</kbd> <kbd>G</kbd></td><td>top / bottom</td></tr>
<tr><td><kbd>x</kbd> <kbd>o</kbd> <kbd>Enter</kbd></td><td>expand / collapse the row</td></tr>
<tr><td><kbd>X</kbd> <kbd>O</kbd></td><td>collapse / expand every group</td></tr>
<tr><td><kbd>z</kbd></td><td>fold / unfold the row's group</td></tr>
<tr><td><kbd>d</kbd></td><td>open the row's review page</td></tr>
<tr><td><kbd>y</kbd></td><td>copy the path of the row's file; a click on its number does too</td></tr>
<tr><td><kbd>a</kbd></td><td>graph: the row's feature / the whole tracker</td></tr>
<tr><td><kbd>b</kbd></td><td>fold / unfold the graph panel</td></tr>
<tr><td><kbd>1</kbd>…<kbd>9</kbd> <kbd>0</kbd></td><td>hide / show the nth feature; all on</td></tr>
<tr><td><kbd>/</kbd></td><td>filter rows; <kbd>Esc</kbd> clears</td></tr>
<tr><td><kbd>?</kbd></td><td>this help</td></tr>
</table></div></div>
<div id="toast" role="status"></div>
${switcher}

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
    window.boardState = { saved, off, cache };
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
  const classDefs = ["done", "review", "claimed", "open", "blocked", "proposed"].map((s) =>
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
  const { saved, off, cache } = window.boardState;
  const rowsEl = document.getElementById("rows"), side = document.getElementById("side");
  const search = document.getElementById("search");
  let mode = saved?.mode ?? "feature";
  let cur = saved?.cur ? document.getElementById(saved.cur) : null;
  const inField = (e) => e.target.closest("input, textarea, [contenteditable]");
  const visible = (el) => el.checkVisibility();  // false inside a closed group too, where offsetParent still holds
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
    if (cur && (cur.classList.contains("off") || cur.classList.contains("miss"))) setCur(null);  // a hidden feature takes its row, and its graph, with it
    showGraph();
  }

  // The whole tracker's graph is composed here from its parts, so a hidden feature drops out of it
  // with its edges, and a node left without an edge goes with them. One composition per set of
  // hidden features is rendered and kept.
  function composeAll() {
    const g = side.querySelector('.g[data-feature="*"]'), pre = g.querySelector(".mermaid");
    if (!pre) return;
    const key = "g:*:" + [...off].sort().join(",");
    if (pre.dataset.key === key) return;
    const parts = JSON.parse(g.querySelector(".parts").textContent);
    const on = (f) => !off.has(f);
    const edges = parts.edges.filter((e) => on(e.a) && on(e.b));
    const keep = new Set(edges.flatMap((e) => [e.from, e.to]));
    const lines = ["flowchart LR"];
    for (const f of parts.features) {
      const nodes = f.nodes.filter((n) => keep.has(n.id));
      if (!on(f.name) || !nodes.length) continue;
      lines.push('  subgraph S_b_' + f.name.replace(/[^a-zA-Z0-9]/g, "_") + '["' + f.name + '"]');
      for (const n of nodes) lines.push(...n.lines);
      lines.push("  end");
    }
    lines.push(...edges.map((e) => e.line));
    pre.dataset.key = key;
    pre.textContent = edges.length ? lines.join("\n") : "";
    delete pre.dataset.src;
    pre.hidden = !edges.length;
    g.querySelector(".gnote").hidden = !!edges.length;
    const hit = cache[key];
    if (hit && hit.src === pre.textContent) { pre.dataset.src = hit.src; pre.innerHTML = hit.svg; nodeHover(pre); }
  }

  // The graph panel shows one pre-rendered graph at a time: the cursor row's feature, or the
  // whole tracker. Switching shows another element and marks another node; nothing re-renders,
  // so moving between rows of one feature never flickers.
  function showGraph() {
    const feature = cur?.dataset.feature ?? "";
    const key = mode === "all" ? "*" : (feature === "standalone" ? "*" : feature);
    for (const g of side.querySelectorAll(".g")) g.hidden = g.dataset.feature !== key;
    if (key === "*") composeAll();
    document.getElementById("gname").textContent = mode === "all" ? "whole tracker" : (feature || "");
    for (const b of document.querySelectorAll("[data-gmode]")) b.classList.toggle("on", b.dataset.gmode === mode);
    renderGraphs();
  }
  function markNode() {
    for (const n of side.querySelectorAll("g.node.cur")) n.classList.remove("cur");
    if (!cur?.dataset.num) return;
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
    const all = [...rowsEl.querySelectorAll(".ticket")], list = all.filter(visible);
    if (!list.length) return;
    let i = list.indexOf(cur);
    if (i < 0 && cur) {
      // the cursor row is folded or filtered away: continue from its place in the page
      const at = all.indexOf(cur);
      i = delta > 0 ? list.findIndex((r) => all.indexOf(r) > at) : list.findLastIndex((r) => all.indexOf(r) < at);
      if (i < 0) i = delta > 0 ? list.length - 1 : 0;
      setCur(list[i]);
      return;
    }
    setCur(list[i < 0 ? (delta > 0 ? 0 : list.length - 1) : Math.min(Math.max(i + delta, 0), list.length - 1)]);
  }
  function jumpGroup(delta) {
    const gs = groups();
    if (!gs.length) return;
    // the group holding the viewport top: the last one at or above where a jump to it would land
    const margin = parseFloat(getComputedStyle(gs[0]).scrollMarginTop) || 0;
    const i = gs.findLastIndex((g) => g.offsetTop <= scrollY + margin + 2);
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
  // a click on a row's summary moves the cursor there, so the graph follows the mouse too;
  // one on its number copies the row's path instead of folding the row
  rowsEl.addEventListener("click", (e) => {
    const t = e.target.closest(".ticket");
    if (!t || !e.target.closest("summary")) return;
    if (e.target.closest(".ticket > summary > .num")) { e.preventDefault(); copyPath(t); }
    setCur(t, false);
  });

  const toast = document.getElementById("toast");
  let toastTimer = null;
  function copyPath(t) {
    const path = t?.dataset.path;
    if (!path) return;
    const say = (text) => {
      toast.textContent = text;
      toast.classList.add("on");
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove("on"), 1500);
    };
    // navigator.clipboard is absent outside a secure context
    (navigator.clipboard?.writeText(path) ?? Promise.reject()).then(() => say("copied " + path), () => say("could not copy " + path));
  }

  const help = document.getElementById("help");
  document.getElementById("helpbtn").addEventListener("click", () => help.classList.toggle("open"));
  help.addEventListener("click", () => help.classList.remove("open"));

  // The keys are diffview's where the two pages have the same move (j/k, J/K, gg/G, x/o/Enter,
  // X/O, z, b, /, ?), so one set of habits drives both.
  let gPending = false, gTimer = null;
  document.addEventListener("keydown", (e) => {
    if (inField(e)) {
      if (e.key === "Escape") { search.value = ""; applyFilters(); search.blur(); }
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "g") {
      if (gPending) { clearTimeout(gTimer); gPending = false; scrollTo(0, 0); setCur(rows()[0]); }
      else { gPending = true; gTimer = setTimeout(() => gPending = false, 500); }
      return;
    }
    switch (e.key) {
      case "Escape": help.classList.remove("open"); if (cur?.open) cur.open = false; else setCur(null); break;
      case "?": help.classList.toggle("open"); break;
      case "/": e.preventDefault(); search.focus(); search.select(); break;
      case "j": e.preventDefault(); moveCur(1); break;
      case "k": e.preventDefault(); moveCur(-1); break;
      case "J": jumpGroup(1); break;
      case "K": jumpGroup(-1); break;
      case "G": scrollTo(0, document.body.scrollHeight); setCur(rows().at(-1), false); break;
      case "x": case "o": case "Enter": if (cur) { e.preventDefault(); cur.open = !cur.open; } break;
      case "X": case "O": {
        const open = e.key === "O";
        for (const g of rowsEl.querySelectorAll("details.grp[data-state]")) g.open = open;
        break;
      }
      case "z": { const g = cur?.closest("details.grp") ?? groups()[0]; if (g) g.open = !g.open; break; }
      case "d": { const href = cur?.querySelector("a.dv:not(.gh)")?.href; if (href) window.open(href, "_blank"); break; }
      case "y": copyPath(cur); break;
      case "a": mode = mode === "all" ? "feature" : "all"; showGraph(); break;
      case "b": side.classList.toggle("folded"); break;
      case "0": off.clear(); applyFilters(); break;
      default:
        if (/^[1-9]$$/.test(e.key)) {  // the doubled dollar is the page template's escape
          const chip = document.querySelectorAll(".featchip")[e.key - 1];
          if (chip) { off.has(chip.dataset.feature) ? off.delete(chip.dataset.feature) : off.add(chip.dataset.feature); applyFilters(); }
        }
    }
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

  // the top bar wraps on a narrow window; everything sticky below it follows its measured height
  new ResizeObserver(([e]) => document.documentElement.style.setProperty("--topbar-h", e.target.offsetHeight + "px"))
    .observe(document.querySelector(".top"));
  if (cur) cur.classList.add("kcur");
  applyFilters();
  if (!saved && location.hash) openTarget();

  // PROTOTYPE: copy buttons (a call with its question, a resume command, a demo path) and the variant switcher's arrow keys
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-copy]"); if (!b) return;
    e.preventDefault(); e.stopPropagation();
    const text = b.dataset.copy;
    const say = (m) => { toast.textContent = m; toast.classList.add("on"); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove("on"), 1800); };
    (navigator.clipboard?.writeText(text) ?? Promise.reject()).then(() => say("copied: " + text.split("\n")[0]), () => say("could not copy"));
  }, true);
  document.addEventListener("keydown", (e) => {
    if (inField(e) || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "ArrowLeft") document.getElementById("proto-prev")?.click();
    if (e.key === "ArrowRight") document.getElementById("proto-next")?.click();
  });
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__, prog="board"))
