#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.14"
# dependencies = ["tyro", "pyyaml", "markdown"]
# ///
"""Historical artifact as of 2026-09-23, superseded by mx/skills/tracker/board.py. Not current; kept as the reasoning trail.

What it groups, names and parses is the reading agent/tickets/board-orients/spec.md replaced.

PROTOTYPE, throwaway (board-orients): the board a returning user reads.

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
_FIXTURE = yaml.safe_load(Path(os.environ.get("BOARD_PROTO_FIXTURE") or PROTO / "fixture.yaml").read_text())
FIX, VIRTUAL = _FIXTURE["tickets"], _FIXTURE.get("virtual", {})
SESSIONS = json.loads((SCRATCH / "sessions.json").read_text()) if (SCRATCH / "sessions.json").exists() and not os.environ.get("BOARD_PROTO_FIXTURE") else {}
# a demo tracker's sessions have no transcript on this machine; this file stands in for the transcript lookup
STANDIN = json.loads(Path(os.environ["BOARD_PROTO_SESSIONS"]).read_text()) if os.environ.get("BOARD_PROTO_SESSIONS") else {}
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
    standalone += branch_filed(root, {k.slug for k in standalone}) + virtual_tickets(root)
    for f in features:
        for t in f.tickets:
            enrich(t, f"{f.name}/{t.num}", t.path.parent.parent.parent / "show" / f.name / t.path.stem)
    for k in standalone:
        enrich(k, k.slug, root.parent / "show" / k.slug)
    log = git_log(repo)
    stamp = content_stamp(project, features, standalone, Queue(root / "needs-human.md", []), log)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_page(project, features, standalone, log, stamp, out.name + ".stamp.js"))
    Path(str(out) + ".stamp.js").write_text(f'window.__boardStamp = "{stamp}";\n')
    print(out)


REVIEW_BRANCH = "ticket/figures-and-demos/06-whole-feature-review"


def branch_filed(root: Path, have: set[str]) -> list["Standalone"]:
    """PROTOTYPE: the standalone tickets the final review filed on its own branch, not on master until it merges."""
    repo = root.parent.parent
    names = subprocess.run(["git", "-C", str(repo), "ls-tree", "--name-only", REVIEW_BRANCH, "agent/tickets/"], capture_output=True, text=True).stdout.split()
    out = []
    for name in names:
        slug = Path(name).stem
        if not name.endswith(".md") or slug in have or slug == "needs-human":
            continue
        meta, body = split_frontmatter(subprocess.run(["git", "-C", str(repo), "show", f"{REVIEW_BRANCH}:{name}"], capture_output=True, text=True).stdout)
        head = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        out.append(Standalone(slug, head.group(1).strip() if head else slug, str(meta.get("status", "open")), ticket_kind(meta), [], [],
                              markdown.markdown(body[head.end():] if head else body, extensions=["fenced_code", "tables"]), None, root / f"{slug}.md", "new"))
    return out


def virtual_tickets(root: Path) -> list["Standalone"]:
    """PROTOTYPE: a ticket the fixture stands in for, one that would be filed rather than asked about in a queue."""
    return [Standalone(slug, v["title"], v.get("status", "proposed"), None, [], [], markdown.markdown(v.get("body", "")), None, root / f"{slug}.md", "not filed yet")
            for slug, v in VIRTUAL.items()]


def enrich(t: "Ticket | Standalone", tid: str, show: Path) -> None:
    """PROTOTYPE: what the build reads from the ticket file, git log and the show directory. A real ticket does
    not carry priority, size or a brief yet, so the fixture fills those in where the file is silent."""
    fx = FIX.get(tid) or FIX.get(t.path.stem) or {}
    text = branch_text(t, tid) if t.status == "review" else (t.path.read_text() if t.path.is_file() else "")
    meta, body = split_frontmatter(text)
    if t.status == "review" and body:
        head = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        rest = body[head.end():] if head else body
        t.body_html = render_body(rest, tid.split("/")[0]) if "/" in tid else markdown.markdown(rest, extensions=["fenced_code", "tables"])
    t.priority = meta.get("priority", fx.get("priority"))
    t.size = meta.get("size", fx.get("size"))
    t.brief = section(body, "Brief") or fx.get("brief")
    t.name = meta.get("name", fx.get("name"))
    t.why = fx.get("why")
    t.calls = open_questions(text) if t.status != "done" else []
    t.asks = [(a["tag"], a["text"]) for a in fx.get("asks", [])]
    t.sessions = trailer_sessions(t) or [s for s in SESSIONS.get(tid, SESSIONS.get(t.path.stem, [])) if s.get("cwd")]
    t.show = sorted(p for p in show.rglob("*") if p.is_file() and "/out/" not in str(p)) if show.is_dir() else []
    t.demo = show / "demo" if (show / "demo").is_file() else None
    t.tid = tid


def section(body: str, heading: str) -> str | None:
    """The text under a `## <heading>` of the ticket, up to the next heading."""
    m = re.search(rf"^##\s+{heading}\s*\n(.*?)(?=^##\s|\Z)", body, re.S | re.M)
    return m.group(1).strip() or None if m else None


def open_questions(text: str) -> list[tuple[str, str]]:
    """The tagged calls under the ticket's last "I need from you", less those a `Ruled: D2, D5` line has answered."""
    ruled = {tag for line in re.findall(r"^Ruled:\s*(.+)$", text, re.M) for tag in re.findall(r"D\d+", line)}
    return [(tag, q) for tag, q in need_calls(text) if tag not in ruled]


def trailer_sessions(t: "Ticket | Standalone") -> list[dict]:
    """The sessions whose commits changed the ticket file, read from their `Session:` trailers on every branch,
    with the title and directory their transcript on this machine records. A session with no transcript here
    (a worker on another host) is left out: it is not one the user resumes."""
    if not t.path.parent.is_dir():
        return []
    top = subprocess.run(["git", "-C", str(t.path.parent), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode:
        return []
    repo = Path(top.stdout.strip())
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--all", "--format=%aI%x09%(trailers:key=Session,valueonly,separator=%x20)", "--", str(t.path.relative_to(repo))],
        capture_output=True, text=True,
    ).stdout
    seen: dict[str, dict] = {}
    for line in log.splitlines():
        when, _, ids = line.partition("\t")
        for sid in ids.split():
            s = seen.setdefault(sid, {"id": sid, "first": when, "last": when})
            s["first"], s["last"] = min(s["first"], when), max(s["last"], when)
    out = [s | info for sid, s in seen.items() if (info := transcript_info(sid))]
    return sorted(out, key=lambda s: s["first"])


@functools.cache
def transcript_info(sid: str) -> dict | None:
    """A session's title (the /rename name, else Claude Code's own) and working directory, from its transcript."""
    if sid in STANDIN:
        return STANDIN[sid]
    for path in (Path.home() / ".claude" / "projects").glob(f"*/{sid}.jsonl"):
        title = custom = cwd = None
        for line in path.open():
            if '"ai-title"' in line or '"customTitle"' in line or (cwd is None and '"cwd"' in line):
                e = json.loads(line)
                title = e.get("aiTitle") or title
                custom = e.get("customTitle") or custom
                cwd = cwd or e.get("cwd")
        return {"title": custom or title or "untitled", "cwd": cwd}
    return None


def branch_text(t: "Ticket | Standalone", tid: str) -> str:
    """The ticket as its own branch has it: a worker's closing comment lands there, and the branch
    the board reads carries only the status flip until the build merges."""
    repo = Path(git(t.path.parent, "rev-parse", "--show-toplevel"))
    base = tid.split("/")[0] if "/" in tid else git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    branch = f"ticket/{base}/{t.path.stem}"
    done = subprocess.run(["git", "-C", str(repo), "show", f"{branch}:{t.path.relative_to(repo)}"], capture_output=True, text=True)
    return done.stdout if done.returncode == 0 else t.path.read_text()


def need_calls(text: str) -> list[tuple[str, str]]:
    """The tagged calls under the last "I need from you" heading of the ticket's comments."""
    block = text.rsplit("**I need from you**", 1)
    if len(block) < 2:
        return []
    body = re.split(r"\n\*\*[A-Z][^*]*\*\*", block[1], maxsplit=1)[0]
    return [(m.group(1), m.group(2).strip()) for m in re.finditer(r"^\s*(?:[-*]|\d+\.)\s*`?\[(D\d+)\]`?\s*(.+)$", body, re.MULTILINE)]


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
    name: str | None = None
    why: str | None = None
    asks: list = None


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
    name: str | None = None
    why: str | None = None
    asks: list = None


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

SIZE_LABEL = {"XS": "10 min", "S": "20 min", "M": "1 h", "L": "half a day", "XL": "several sessions"}
MINUTES = {"XS": 10, "S": 20, "M": 60, "L": 240, "XL": 480}
GROUPS_V3 = [("needs", "needs me"), ("open", "frontier"), ("claimed", "claimed"), ("blocked", "blocked"), ("proposed", "proposed"), ("done", "done")]
WORDS = "no one two three four five six seven eight nine ten eleven twelve".split()

KIND = {  # what a row asks of the user, in the words the row shows and what its tooltip explains
    "review": ("to rule on", "A worker finished this. Open the review page and the demo, then accept, amend, redo or reject it."),
    "answer": ("your answer", "The ticket cannot go on until you answer the questions under it."),
    "design": ("design session", "A decision to talk through with you. Nothing gets built on it until it is settled."),
    "prototype": ("prototype", "A decision taken by looking at something built to compare. You judge the render."),
    "research": ("research", "An agent investigates on its own. You read the finding when it lands."),
    "legwork": ("legwork", "Work that unblocks a decision: an agent does it, or hands you a checklist."),
    "build": ("build", "An agent builds this on its own. It comes back to you as a build to rule on."),
}
PRI_WORD = {1: "now", 2: "next", 3: "soon", 4: "later", 5: "someday"}
PRI_TIP = ("Priority, the agent's reading of what you have said. Tell it to change one.\n"
           "p1 now: this session or today\np2 next: this week\np3 soon: once the next ones are done\n"
           "p4 later: when there is room\np5 someday: parked")
SIZE_TIP = ("Your time on this ticket, not the agent's: reading the diff or the design, trying the demo, deciding.\n"
            "XS under 15 min\nS about 20 min\nM about an hour\nL half a day\nXL several sessions")


def words(n: int) -> str:
    return WORDS[n] if n < len(WORDS) else str(n)


def dep_chips(feature: str, by_num: dict[str, Ticket], t: Ticket) -> str:
    local = "".join(f'<a class="chip {by_num[b].status}" href="#t-{feature}-{b}">{b}</a>' for b in t.blocked_by)
    return local + ext_chips(t.ext_by)


def ext_chips(refs: list[tuple[str, str]]) -> str:
    return "".join(f'<a class="chip {s}" href="{ref_anchor(ref)}" title="waits on {html.escape(ref)}">{html.escape(ref)}</a>' for ref, s in refs)


def gh_links(refs: Sequence[str]) -> str:
    # the issues URL serves a pull request too: GitHub redirects it to the pull page
    return "".join(
        f'<a class="gh" href="https://github.com/{repo}/issues/{num}" target="_blank">{html.escape(ref)}</a>'
        for ref in refs for repo, num in [ref.split("#")]
    )


def search_text(*parts: str) -> str:
    return html.escape(re.sub(r"\s+", " ", " ".join(re.sub(r"<[^>]+>", " ", p) for p in parts)).strip().lower(), quote=True)


def inline_md(text: str) -> str:
    return re.sub(r"^<p>|</p>$", "", markdown.markdown(text).strip())


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inline_md(text))).strip()


def copy_btn(label: str, payload: str, title: str) -> str:
    return f'<button class="copy" data-copy="{html.escape(payload, quote=True)}" data-tip="{html.escape(title)}">{label}</button>'


def split_call(md: str) -> tuple[str, str]:
    """A call's headline and the rest: its bold lead-in where it has one, else its first sentence."""
    m = re.match(r"\*\*(.+?)\*\*[\s.,:;]*(.*)", md, re.S)
    if m:
        return m.group(1).rstrip(".:"), m.group(2)
    m = re.match(r"(.+?[.?])\s+(.*)", md, re.S)
    return (m.group(1), m.group(2)) if m else (md, "")


def call_payload(t, tag: str, head: str) -> str:
    return f"{t.tid} {tag}, in {t.path}: {plain(head)}\nMy answer: "


def open_calls(t) -> list[tuple[str, str]]:
    return (t.calls or []) + (t.asks or [])


def kind_of(t) -> str:
    if t.status == "review":
        return "review"
    if open_calls(t) and t.status != "done":
        return "answer"
    return {"grilling": "design", "prototype": "prototype", "research": "research", "legwork": "legwork"}.get(t.kind or "", "build")


def needs_me(t) -> bool:
    """Waiting on the user: a build to rule on, a ticket stopped on a question, a near design session."""
    kind = kind_of(t)
    near = (t.priority or 9) <= 2 and t.status in ("open", "proposed")
    return t.status != "done" and (kind in ("review", "answer") or (kind in ("design", "prototype") and near))


def kind_tag(t) -> str:
    kind = kind_of(t)
    word, tip = KIND[kind]
    return f'<span class="kindtag k-{kind}" data-tip="{html.escape(tip)}">{word}</span>'


def time_tag(t) -> str:
    if not t.size:
        return '<span class="time"></span>'
    return f'<span class="time" data-tip="{html.escape(SIZE_TIP)}">{SIZE_LABEL[t.size]}</span>'


def pri_tag(t) -> str:
    if not t.priority:
        return '<span class="pri"></span>'
    return f'<span class="pri p{t.priority}" data-tip="{html.escape(PRI_TIP)}">p{t.priority} {PRI_WORD.get(t.priority, "")}</span>'


def minutes(t) -> int:
    return MINUTES.get(t.size or "", 20)


def sort_key(t) -> tuple:
    return (t.priority or 9, minutes(t), (t.name or t.title).lower())


def calls_summary(t) -> str:
    rows = []
    for tag, text in open_calls(t):
        head, _ = split_call(text)
        rows.append(f'<li><span class="tag">{tag}</span><span class="head">{inline_md(head)}</span>'
                    f'{copy_btn("copy", call_payload(t, tag, head), "copy the question with its tag, to answer in any session")}</li>')
    return f'<ol class="calls">{"".join(rows)}</ol>' if rows else ""


def body_html(t, ticket_body: str) -> str:
    parts = []
    if t.name and t.name != t.title:
        parts.append(f'<p class="fulltitle">{inline_md(t.title)}</p>')
    ticket_body = re.sub(r"<h2>Brief</h2>.*?(?=<h2|\Z)", "", ticket_body, flags=re.S)
    calls = open_calls(t)
    if calls:
        lis = "".join(
            f'<li><span class="tag">{tag}</span><div><p class="head">{inline_md(head)}</p>'
            + (f'<p class="rest">{inline_md(rest)}</p>' if rest.strip() else "") + "</div></li>"
            for tag, text in calls for head, rest in [split_call(text)]
        )
        parts.append(f'<section><p class="label">calls</p><ol class="calls-full">{lis}</ol></section>')
    if t.sessions:
        lis = "".join(
            f'<li><span class="stitle">{html.escape(s["title"])}</span><span class="when">{s["first"][5:10]} to {s["last"][5:10]}</span>'
            f'{copy_btn("copy resume", f"cd {s["cwd"]} && claude --resume {s["id"]}", "copy the command that resumes this session")}</li>'
            for s in reversed(t.sessions)
        )
        parts.append(f'<section><p class="label">sessions on this machine</p><ul class="sessions">{lis}</ul></section>')
    if t.demo or t.show:
        demo = f'<li><code>{html.escape(str(t.demo))}</code>{copy_btn("copy path", str(t.demo), "copy the demo path")}</li>' if t.demo else ""
        files = "".join(f'<li><a href="file://{html.escape(str(p))}" target="_blank">{html.escape(p.name)}</a></li>' for p in t.show if p.name != "demo")
        parts.append(f'<section><p class="label">artefacts</p><ul class="artefacts">{demo}{files}</ul></section>')
    parts.append(f'<section class="ticket-text"><p class="label">ticket</p><div class="prose-s">{ticket_body}</div></section>')
    return "".join(parts)


def row(row_id: str, feature: str, num: str, t, chips: str, group: str) -> str:
    """One ticket row, every field in a fixed column: feature, number (a click copies the file's path), what the
    row asks of the user, name with its links and brief, your time, priority, blockers. A ticket waiting on the
    user lists its open questions under it; the rest folds."""
    name = t.name or t.title
    links = (f'<a class="rp" href="{html.escape(t.diffview)}" target="_blank">review page</a>' if t.diffview else "") + gh_links(t.gh)
    source = f'<span class="src">{html.escape(t.source)}</span>' if getattr(t, "source", None) else ""
    brief = f'<span class="brief">{inline_md(t.brief)}</span>' if t.brief else ""
    calls = calls_summary(t) if group == "needs" else ""
    return (
        f'<details class="ticket" id="{row_id}" data-feature="{html.escape(feature)}" data-num="{html.escape(num)}" '
        f'data-search="{search_text(num, name, t.title, t.brief or "", t.body_html, *t.gh)}" data-path="{html.escape(str(t.path))}"><summary>'
        f'<span class="ftag">{html.escape(feature)}</span>'
        f'<span class="num" data-tip="Click to copy this ticket\'s path (y)">{html.escape(num)}</span>'
        f'{kind_tag(t)}'
        f'<span class="main"><span class="titleline"><span class="title">{html.escape(name)}</span>{links}{source}</span>{brief}</span>'
        f'{time_tag(t)}{pri_tag(t)}'
        f'<span class="chips">{chips}</span>{calls}</summary>'
        f'<div class="body">{body_html(t, t.body_html)}</div></details>'
    )


def feature_chip(f: Feature) -> str:
    counts = Counter(t.status for t in f.tickets)
    total = len(f.tickets)
    title = f"spec {f.spec_status}" if f.spec_status else ""
    return (f'<button class="pill" data-feature="{html.escape(f.name)}" title="{html.escape(title)}">{html.escape(f.name)}'
            f' <span class="count">{counts["done"]}/{total}</span></button>')


def reason(t, features: list[Feature], all_tickets: list) -> str | None:
    """Why a ticket is picked next, stated from the tracker: what accepting it lets happen."""
    def refs(x) -> list[str]:  # the other-feature and standalone tickets x waits on
        return [r for r, _ in (x.ext_by if isinstance(x, Ticket) else x.blocked_by)]

    waiting = [x for x in all_tickets if isinstance(t, Standalone) and t.slug in refs(x)]
    for f in features:
        if any(x is t for x in f.tickets):
            if all(x.status == "done" for x in f.tickets if x is not t):
                return f"The last open ticket of {f.name}: accepting it lets the feature merge."
            waiting = [x for x in f.tickets if t.num in x.blocked_by] + [x for x in all_tickets if f"{f.name}/{t.num}" in refs(x)]
    if waiting:
        return f"{words(len(waiting)).capitalize()} ticket{'s wait' if len(waiting) != 1 else ' waits'} on it."
    return None


def brief_panel(features: list[Feature], all_tickets: list, anchor: dict) -> str:
    live = [t for t in all_tickets if t.status != "done"]
    mine = sorted([t for t in live if needs_me(t)], key=sort_key)
    builds = [t for t in mine if t.status == "review"]
    sessions = [t for t in mine if t.kind in HITL and t.status != "review"]
    answers = len([t for t in live if kind_of(t) == "answer"])  # a build's own questions are part of its ruling
    running = [t for t in live if t.status == "claimed" and not t.kind]
    said = []
    if builds:
        said.append(f"{words(len(builds)).capitalize()} build{'s' if len(builds) != 1 else ''} wait for your ruling")
    if sessions:
        said.append(f"{words(len(sessions))} design session{'s' if len(sessions) != 1 else ''} for you")
    if answers:
        said.append(f"{words(answers)} ticket{'s wait' if answers != 1 else ' waits'} on an answer from you")
    lead = (", ".join(said[:-1]) + (" and " if len(said) > 1 else "") + said[-1] + ". ") if said else "Nothing waits on you. "
    lead += (f"{words(len(running)).capitalize()} build{'s are' if len(running) != 1 else ' is'} in progress." if running else "No agent is working.")
    total = sum(minutes(t) for t in mine)
    # within a priority, what accepting lets happen goes first, then the cheapest
    picks = sorted(mine, key=lambda t: (t.priority or 9, 0 if (t.why or reason(t, features, all_tickets)) else 1, minutes(t)))[:3]
    lis = "".join(
        f'<li><div class="pickline">{kind_tag(t)}<a href="#{anchor[id(t)]}">{html.escape(t.name or t.title)}</a>{time_tag(t)}</div>'
        + (f'<p class="why">{inline_md(why)}</p>' if (why := t.why or reason(t, features, all_tickets)) else "") + "</li>"
        for t in picks
    )
    h, m = divmod(total, 60)
    return (f'<section class="brief-panel"><p class="label">brief</p><p class="lead">{html.escape(lead)}</p>'
            f'<p class="label next-label">next <span class="total">about {h} h{f" {m} min" if m else ""} waits on you</span></p><ol class="next">{lis}</ol></section>')


def render_page(project: str, features: list[Feature], standalone: list[Standalone], log: str, stamp: str, stamp_src: str) -> str:
    rows: dict[str, list[tuple[tuple, str]]] = {state: [] for state, _ in GROUPS_V3}
    anchor: dict[int, str] = {}
    everything = []
    for f in features:
        by_num = {x.num: x for x in f.tickets}
        for t in f.tickets:
            group = "needs" if t.status != "done" and needs_me(t) else t.status
            anchor[id(t)] = f"t-{f.name}-{t.num}"
            rows[group].append((sort_key(t), row(anchor[id(t)], f.name, t.num, t, dep_chips(f.name, by_num, t), group)))
            everything.append(t)
    for k in standalone:
        group = "needs" if k.status != "done" and needs_me(k) else k.status
        anchor[id(k)] = f"standalone-{k.slug}"
        rows[group].append((sort_key(k), row(anchor[id(k)], "standalone", "--", k, ext_chips(k.blocked_by), group)))
        everything.append(k)
    groups = "".join(
        f'<details class="grp" id="grp-{state}" data-state="{state}"{"" if state == "done" else " open"}>'
        f'<summary><span class="label">{label}</span><span class="n">{len(rows[state])}</span><span class="rule"></span></summary>'
        f'<div class="tickets">{"".join(h for _, h in sorted(rows[state], key=lambda x: x[0]))}</div></details>'
        for state, label in GROUPS_V3 if rows[state]
    )
    chips = "".join(feature_chip(f) for f in features)
    if standalone:
        chips += f'<button class="pill" data-feature="standalone" title="tickets without a spec">standalone <span class="count">{len(standalone)}</span></button>'

    graphs = ""
    for f in features:
        src = feature_graph(f)
        inner = f'<pre class="mermaid" data-key="g:{f.name}">{src}</pre>' if src else f'<p class="gnote">nothing in {html.escape(f.name)} waits on anything</p>'
        graphs += f'<div class="g" data-feature="{html.escape(f.name)}" hidden>{inner}</div>'
    board = board_graph(features, standalone)
    graphs += '<div class="g" data-feature="*" hidden>' + (
        f'<pre class="mermaid" data-key="g:*"></pre><p class="gnote" hidden>every ticket with an edge is in a hidden feature</p>'
        f'<script type="application/json" class="parts">{json.dumps(board).replace("</", "<\\/")}</script>'
        if board else '<p class="gnote">nothing waits on anything</p>'
    ) + "</div>"
    log_html = "\n".join(
        f'<span class="hash">{html.escape(line.split(" ")[0])}</span> {html.escape(line.partition(" ")[2])}'
        for line in log.strip().splitlines()
    )
    footmeta = f"{len(features)} feature{'s' if len(features) != 1 else ''} · {len(standalone)} standalone · rendered {datetime.datetime.now():%Y-%m-%d %H:%M:%S}"
    subs = {
        "PROJECT": html.escape(project), "CHIPS": chips, "GROUPS": groups, "GRAPHS": graphs, "LOG": log_html,
        "FOOTMETA": footmeta, "STAMP": stamp, "STAMP_SRC": html.escape(stamp_src), "BRIEF": brief_panel(features, everything, anchor),
        "TOKENS": TOKENS,
    }
    page = PAGE
    for k, v in subs.items():
        page = page.replace("{{" + k + "}}", v)
    return page


TOKENS = (Path.home() / ".claude/plugins/cache/MaxWolf-01/mx/0.1.69/skills/house-style/tokens.css").read_text()

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>board · {{PROJECT}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400;1,6..72,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<script>
  // the scheme before first paint: ?theme= pins it for a screenshot, else the system's
  (() => {
    const q = new URLSearchParams(location.search).get("theme");
    const saved = localStorage.getItem("board-theme");
    const night = q ? q === "night" : saved ? saved === "night" : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = night ? "night" : "day";
  })();
</script>
<style>
{{TOKENS}}
  * { box-sizing: border-box; }
  :root { --size-body: 15px; --leading-body: 1.5; --topbar-h: 52px; }
  p { margin: 0; }
  .mono, .ftag, .num, .meta, .chip, .pill, .label, .n, .tag, .copy, .when, .size, .gnote, .log, .footmeta, .search, .btn, kbd { font-family: var(--font-mono); }

  /* ---- top bar: name, feature filters, filter box, graph mode, scheme ---- */
  .top { position: sticky; top: 0; z-index: 10; display: flex; gap: 1.25rem; align-items: center; min-height: var(--topbar-h);
    padding: .5rem 1.5rem; background: var(--ground); border-bottom: 1px solid var(--edge); }
  .top .name { font-weight: 600; color: var(--strong); font-size: 1.05rem; white-space: nowrap; }
  .top .name span { color: var(--muted); font-weight: 400; }
  .featnav { display: flex; gap: .4rem; overflow-x: auto; flex: 1; min-width: 0; scrollbar-width: none; }
  .pill { padding: .1rem .7rem; border: 1px solid var(--edge); border-radius: 999px; background: none; font-size: .78rem;
    color: var(--muted); cursor: pointer; white-space: nowrap; transition: color 150ms, border-color 150ms; }
  .pill:hover { color: var(--accent); border-color: var(--accent); }
  .pill .count { opacity: .75; }
  .pill.off { opacity: .45; text-decoration: line-through; }
  .search { background: var(--ground-2); border: 1px solid var(--edge); border-radius: var(--radius); color: var(--body);
    font-size: .8rem; padding: .3rem .6rem; width: 13rem; }
  .search:focus { outline: none; border-color: var(--accent); }
  .btn { background: none; border: 0; color: var(--muted); font-size: .8rem; cursor: pointer; padding: .2rem .35rem; transition: color 150ms; }
  .btn:hover, .btn.on { color: var(--accent); }
  .scheme { display: inline-flex; }
  [data-theme="night"] .sun, [data-theme="day"] .moon { display: none; }

  /* ---- rows beside the side column ---- */
  main { display: grid; grid-template-columns: minmax(0, 1fr) minmax(20rem, 30rem); gap: 3rem; padding: 1.5rem 1.5rem 6rem; align-items: start; max-width: 110rem; margin: 0 auto; }
  @media (max-width: 1100px) { main { grid-template-columns: 1fr; } .side { position: static; max-height: none; } }

  .grp { margin-bottom: 2.25rem; }
  .grp > summary { list-style: none; cursor: pointer; display: flex; align-items: center; gap: .6rem; padding: .25rem 0 .75rem; }
  .grp > summary::-webkit-details-marker { display: none; }
  .grp .label { color: var(--body); }
  .grp .n { color: var(--muted); font-size: .78rem; }
  .grp .rule { flex: 1; height: 1px; background: var(--edge); }
  .grp.empty { display: none; }
  .label { font-size: .8rem; color: var(--muted); }

  .ticket { border-top: 1px solid var(--edge); scroll-margin-top: calc(var(--topbar-h) + 60px); }
  .ticket:first-child { border-top: 0; }
  .ticket.off, .ticket.miss { display: none; }
  .ticket > summary { display: grid; grid-template-columns: 8.5rem 2rem minmax(0, 1fr) auto 4.5rem; column-gap: 1rem; align-items: baseline;
    padding: .7rem .5rem; cursor: pointer; list-style: none; border-radius: var(--radius); transition: background-color 150ms; }
  .ticket > summary::-webkit-details-marker { display: none; }
  .ticket > summary:hover { background: var(--wash-ink); }
  .ticket.kcur > summary { background: var(--wash); }
  .ticket.flash > summary { background: var(--wash); }
  .ftag { font-size: .72rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .num { font-size: .78rem; color: var(--muted); text-align: right; cursor: copy; }
  .num:hover { color: var(--accent); }
  .main { display: grid; gap: .1rem; min-width: 0; }
  .title { color: var(--strong); font-size: 1.02rem; }
  .brief { color: var(--muted); font-size: .9rem; line-height: 1.45; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ticket[open] .brief { white-space: normal; }
  .gh { font-family: var(--font-mono); font-size: .72rem; color: var(--muted); margin-left: .6rem; }
  .gh:hover { color: var(--accent); }
  .meta { display: flex; gap: .9rem; align-items: baseline; justify-content: flex-end; font-size: .74rem; color: var(--muted); white-space: nowrap; }
  .meta .rp { color: var(--accent); }
  .meta .rp:hover { text-decoration: underline; text-underline-offset: 3px; }
  .meta .pri { min-width: 1.4rem; text-align: right; }
  .chips { display: flex; gap: .35rem; justify-content: flex-end; flex-wrap: wrap; }
  .chip { font-size: .72rem; color: var(--body); }
  .chip.done { color: var(--muted); text-decoration: line-through; }

  /* the open calls of a ticket waiting on the user, under its name */
  ol.calls { grid-column: 3 / -1; list-style: none; margin: .55rem 0 .1rem; padding: 0; display: grid; gap: .35rem; }
  ol.calls li { display: grid; grid-template-columns: 2.2rem minmax(0, 1fr) auto; gap: .6rem; align-items: baseline; font-size: .9rem; }
  .tag { font-size: .72rem; color: var(--muted); }
  .head { color: var(--body); }
  .head code, .brief code, .rest code, .prose-s code { font-size: .82em; background: var(--ground-2); padding: 0 .25em; border-radius: 3px; }
  .copy { border: 0; background: none; padding: 0; font-size: .72rem; color: var(--muted); cursor: pointer; transition: color 150ms; white-space: nowrap; }
  .copy:hover { color: var(--accent); }

  /* ---- a row, opened ---- */
  .body { padding: .5rem .5rem 1.5rem 13rem; display: grid; gap: 1.4rem; max-width: calc(13.5rem + 46rem); }
  .body > section { min-width: 0; }
  .body .label { margin-bottom: .45rem; }
  .fulltitle { color: var(--muted); font-style: italic; }
  ol.calls-full { list-style: none; margin: 0; padding: 0; display: grid; gap: .9rem; }
  ol.calls-full li { display: grid; grid-template-columns: 2.2rem 1fr; gap: .6rem; align-items: baseline; }
  ol.calls-full .rest { color: var(--muted); font-size: .9rem; margin-top: .2rem; }
  ul.sessions, ul.artefacts { list-style: none; margin: 0; padding: 0; display: grid; gap: .35rem; }
  ul.sessions li, ul.artefacts li { display: flex; gap: 1rem; align-items: baseline; }
  .stitle { flex: 1; }
  .when { font-size: .74rem; color: var(--muted); }
  ul.artefacts code { flex: 1; font-size: .78rem; color: var(--muted); overflow-wrap: anywhere; }
  ul.artefacts a { color: var(--accent); }
  .prose-s { max-width: 46rem; color: var(--body); }
  .prose-s > * + * { margin-top: .8em; }
  .prose-s h2 { font-size: 1rem; font-weight: 600; color: var(--strong); margin-top: 1.4em; }
  .prose-s a { color: var(--accent); }
  .prose-s pre { background: var(--ground-2); border: 1px solid var(--edge); border-radius: var(--radius); padding: .6rem .8rem; overflow-x: auto; font-size: .8rem; }
  .prose-s pre code { background: none; padding: 0; }
  .prose-s ul, .prose-s ol { padding-left: 1.2em; }

  /* ---- the side column: the brief, then the dependencies ---- */
  .side { position: sticky; top: calc(var(--topbar-h) + 1.5rem); max-height: calc(100vh - var(--topbar-h) - 3rem); overflow: auto;
    border-left: 1px solid var(--edge); padding-left: 2rem; display: grid; gap: 2.25rem; }
  .brief-panel .lead { margin-top: .5rem; color: var(--body); font-size: 1.02rem; }
  .brief-panel .next-label { margin-top: 1.4rem; display: flex; justify-content: space-between; }
  .brief-panel .total { color: var(--muted); }
  ol.next { margin: .6rem 0 0; padding-left: 1.2em; display: grid; gap: .7rem; }
  ol.next li::marker { color: var(--muted); font-family: var(--font-mono); font-size: .8rem; }
  ol.next a { color: var(--accent); }
  ol.next .size { float: right; font-size: .74rem; color: var(--muted); }
  ol.next .why { color: var(--muted); font-size: .9rem; margin-top: .1rem; }
  .ghead { display: flex; gap: .5rem; align-items: baseline; }
  .ghead .gname { color: var(--muted); font-size: .8rem; flex: 1; font-family: var(--font-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .side.folded .gbody { display: none; }
  .gnote { color: var(--muted); font-size: .78rem; padding: .4rem 0; }
  .mermaid { margin: .5rem 0 0; display: flex; justify-content: center; }
  .mermaid:not(:has(svg)) { visibility: hidden; }
  .mermaid svg { max-width: 100%; height: auto; }
  .side g.node.cur rect, .side g.node.cur polygon { stroke-width: 2.5px !important; }

  #grp-log .log { margin: 0; font-size: .78rem; line-height: 1.8; color: var(--body); white-space: pre-wrap; }
  .hash { color: var(--muted); }
  .footmeta { color: var(--muted); font-size: .74rem; margin-top: 1rem; }

  /* ---- v4: kinds, priority and time get colours from the mwolf.dev callouts, in fixed columns ---- */
  :root {
    --c-pink: light-dark(#8e4a82, #d9a2d0); --c-lav: light-dark(#5a53c2, #afaaff); --c-blue: light-dark(#2a6aa3, #85baeb);
    --c-slate: light-dark(#52627f, #9aaacb); --c-teal: light-dark(#1d6f69, #74d0c8); --c-gold: light-dark(#7d5f16, #d9b36f);
    --c-purple: light-dark(#6546b3, #b8a4ff); --c-orange: light-dark(#9a5516, #ffc387); --c-rose: light-dark(#a3453c, #fabeb4);
  }
  .ticket > summary { grid-template-columns: 7rem 2rem 7.6rem minmax(0, 1fr) 5.2rem 6.2rem minmax(3rem, max-content); column-gap: .9rem; }
  .chips { flex-wrap: nowrap; white-space: nowrap; }
  ol.calls { grid-column: 4 / -1; }
  .body { padding-left: calc(7rem + 2rem + 7.6rem + 2.7rem + .5rem); max-width: calc(19.8rem + 46rem); }
  .kindtag, .pri, .time, .src { font-family: var(--font-mono); font-size: .72rem; white-space: nowrap; justify-self: start; }
  .kindtag { --c: var(--muted); color: var(--c); background: color-mix(in srgb, var(--c) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 35%, transparent); border-radius: 4px; padding: 0 .4rem; }
  .k-review { --c: var(--c-gold); } .k-answer { --c: var(--c-rose); } .k-design { --c: var(--c-purple); }
  .k-prototype { --c: var(--c-orange); } .k-research { --c: var(--c-blue); } .k-legwork { --c: var(--c-slate); }
  .k-build { background: none; border-color: transparent; padding-left: 0; }
  .time { color: var(--c-teal); justify-self: end; }
  .pri { --c: var(--muted); color: var(--c); justify-self: start; padding: 0 .45rem; border-radius: 999px;
    background: color-mix(in srgb, var(--c) 12%, transparent); }
  .pri.p1 { --c: var(--c-pink); } .pri.p2 { --c: var(--c-lav); } .pri.p3 { --c: var(--c-blue); } .pri.p4 { --c: var(--c-slate); }
  .pri.p5 { background: none; }
  .titleline { display: flex; gap: .7rem; align-items: baseline; min-width: 0; }
  .titleline .title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .titleline > a, .titleline > .src { flex: none; }
  .rp { font-family: var(--font-mono); font-size: .72rem; color: var(--accent); }
  .rp:hover { text-decoration: underline; text-underline-offset: 3px; }
  .src { color: var(--c-teal); }
  .meta { display: none; }
  /* buttons read as buttons, filters as pills, copy as a small outlined button */
  .copy { border: 1px solid var(--edge); border-radius: 4px; padding: 0 .4rem; background: var(--ground); }
  .copy:hover { border-color: var(--accent); }
  .pill { background: var(--ground-2); }
  .seg { display: inline-flex; border: 1px solid var(--edge); border-radius: var(--radius); overflow: visible; }
  .seg .btn { padding: .2rem .7rem; border-radius: 0; }
  .seg .btn.on { background: var(--wash); color: var(--accent); }
  .seg .btn + .btn { border-left: 1px solid var(--edge); }
  .pickline { display: grid; grid-template-columns: 7.6rem minmax(0, 1fr) auto; gap: .6rem; align-items: baseline; }
  ol.next { padding-left: 0; list-style: none; }
  ol.next a { color: var(--strong); }
  ol.next a:hover { color: var(--accent); }
  ol.next .why { padding-left: 8.2rem; }
  /* a tooltip that says what a mark means, styled like the page */
  [data-tip] { position: relative; }
  [data-tip]:hover::after { content: attr(data-tip); position: absolute; z-index: 60; top: calc(100% + .4rem); left: 0;
    width: max-content; max-width: 24rem; white-space: pre-line; background: var(--ground); color: var(--body);
    border: 1px solid var(--edge); border-radius: var(--radius); padding: .5rem .7rem; font: .76rem/1.55 var(--font-mono);
    text-decoration: none; pointer-events: none; }
  .time[data-tip]:hover::after, .pri[data-tip]:hover::after, .copy[data-tip]:hover::after { left: auto; right: 0; }

  #toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); z-index: 50; background: var(--ground);
    border: 1px solid var(--edge); border-radius: var(--radius); padding: .35rem .9rem; font: .78rem var(--font-mono); color: var(--muted);
    opacity: 0; transition: opacity 200ms; pointer-events: none; max-width: 90vw; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #toast.on { opacity: 1; }
  #help { position: fixed; inset: 0; z-index: 100; background: color-mix(in srgb, var(--strong) 40%, transparent); display: none; align-items: center; justify-content: center; }
  #help.open { display: flex; }
  #help .card { background: var(--ground); border: 1px solid var(--edge); border-radius: var(--radius); padding: 1.25rem 1.5rem; }
  #help table { border-collapse: collapse; font-size: .9rem; }
  #help td { padding: .2rem 1rem .2rem 0; }
  kbd { font-size: .78rem; border: 1px solid var(--edge); border-radius: 4px; padding: 0 .4rem; color: var(--body); }
</style>
</head>
<body data-stamp="{{STAMP}}" data-stamp-src="{{STAMP_SRC}}">
<div class="top">
  <span class="name">board <span>{{PROJECT}}</span></span>
  <nav class="featnav" id="featnav">{{CHIPS}}</nav>
  <input class="search" id="search" type="search" placeholder="filter  /" autocomplete="off">
  <span class="seg" data-tip="The dependency graph: the feature of the row you are on, or the whole tracker (a)"><button class="btn" data-gmode="feature">feature</button><button class="btn" data-gmode="all">all</button></span>
  <button class="btn" id="helpbtn" title="keys (?)">?</button>
  <button class="btn scheme" id="scheme" title="switch colour scheme">
    <svg class="sun" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
    <svg class="moon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>
  </button>
</div>
<main>
<div class="rows" id="rows">
{{GROUPS}}
<details class="grp" id="grp-log"><summary><span class="label">recent commits</span><span class="rule"></span></summary>
  <pre class="log">{{LOG}}</pre>
  <p class="footmeta">{{FOOTMETA}}</p>
</details>
</div>
<aside class="side" id="side">
  {{BRIEF}}
  <section>
    <div class="ghead"><p class="label">dependencies</p><span class="gname" id="gname"></span>
      <button class="btn" id="sidefold" title="fold the graph (b)">fold</button></div>
    <div class="gbody" id="gbody">
      {{GRAPHS}}
    </div>
  </section>
</aside>
</main>

<div id="help"><div class="card"><table>
<tr><td><kbd>j</kbd> <kbd>k</kbd></td><td>next / previous row (the graph follows)</td></tr>
<tr><td><kbd>J</kbd> <kbd>K</kbd></td><td>next / previous group</td></tr>
<tr><td><kbd>gg</kbd> <kbd>G</kbd></td><td>top / bottom</td></tr>
<tr><td><kbd>x</kbd> <kbd>o</kbd> <kbd>Enter</kbd></td><td>open / close the row</td></tr>
<tr><td><kbd>X</kbd> <kbd>O</kbd></td><td>close / open every group</td></tr>
<tr><td><kbd>z</kbd></td><td>fold / unfold the row's group</td></tr>
<tr><td><kbd>d</kbd></td><td>open the row's review page</td></tr>
<tr><td><kbd>y</kbd></td><td>copy the path of the row's file; a click on its number does too</td></tr>
<tr><td><kbd>a</kbd></td><td>graph: the row's feature / the whole tracker</td></tr>
<tr><td><kbd>b</kbd></td><td>fold / unfold the graph</td></tr>
<tr><td><kbd>1</kbd>…<kbd>9</kbd> <kbd>0</kbd></td><td>hide / show the nth feature; all on</td></tr>
<tr><td><kbd>/</kbd></td><td>filter rows; <kbd>Esc</kbd> clears</td></tr>
<tr><td><kbd>?</kbd></td><td>this help</td></tr>
</table></div></div>
<div id="toast" role="status"></div>

<script>
  // Synchronous state restore, before first paint.
  (() => {
    let saved = null;
    try { saved = JSON.parse(sessionStorage.getItem("board-view") ?? "null"); } catch {}
    if (!saved && window.name.startsWith("board:")) { try { ({ saved = null } = JSON.parse(window.name.slice(6))); } catch {} }
    const off = new Set(JSON.parse(localStorage.getItem("board-off:" + document.title) ?? "[]"));
    for (const b of document.querySelectorAll(".pill")) b.classList.toggle("off", off.has(b.dataset.feature));
    for (const t of document.querySelectorAll(".ticket")) t.classList.toggle("off", off.has(t.dataset.feature));
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

  // Mermaid bakes colours into the SVG, and the tokens are light-dark() pairs a custom property never resolves,
  // so each token is read off a probe element in the scheme on show.
  const probe = document.createElement("span");
  probe.style.display = "none";
  document.body.append(probe);
  const rgb = (name) => { probe.style.color = `var(${name})`; return getComputedStyle(probe).color.match(/[\d.]+/g).map(Number); };
  // mermaid's classDef parser takes no rgba(), so a translucent token is laid over the ground and written as hex
  const hex = ([r, g, b, a = 1], [R, G, B] = [0, 0, 0]) =>
    "#" + [r * a + R * (1 - a), g * a + G * (1 - a), b * a + B * (1 - a)].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
  function setupMermaid() {
    const ground = rgb("--ground");
    const c = Object.fromEntries(["ground", "ground-2", "edge", "muted", "body", "strong", "accent", "wash"].map((n) => [n, hex(rgb("--" + n), ground)]));
    const cls = {
      review: [c.wash, c.accent, c.strong, ""], open: [c["ground-2"], c.body, c.body, ""], claimed: [c["ground-2"], c.muted, c.body, ""],
      blocked: [c.ground, c.edge, c.muted, ""], proposed: [c.ground, c.muted, c.body, ",stroke-dasharray:4 3"],
      done: [c.ground, c.edge, c.muted, ""], ghost: [c.ground, c.edge, c.muted, ",stroke-dasharray:2 3"],
    };
    window.classDefs = Object.entries(cls).map(([s, [f, st, tx, ex]]) => `  classDef ${s} fill:${f},stroke:${st},color:${tx}${ex}`).join("\n");
    mermaid.initialize({
      startOnLoad: false, layout: "elk", securityLevel: "loose", theme: "base", htmlLabels: false,
      elk: { mergeEdges: false }, flowchart: { htmlLabels: false },
      themeVariables: { fontFamily: "Newsreader, Georgia, serif", fontSize: "14px", primaryColor: c.ground, primaryTextColor: c.body,
        primaryBorderColor: c.edge, lineColor: c.muted, clusterBkg: c.ground, clusterBorder: c.edge, titleColor: c.muted },
    });
  }
  setupMermaid();

  let seq = 0;
  async function renderGraphs() {
    for (const el of document.querySelectorAll(".g:not([hidden]) .mermaid")) {
      if (el.querySelector("svg")) continue;
      el.dataset.src = el.dataset.src ?? el.textContent;
      if (!el.dataset.src.trim()) continue;
      const { svg } = await mermaid.render("m" + Date.now() + "_" + seq++, el.dataset.src + "\n" + window.classDefs);
      el.innerHTML = svg;
    }
    markNode();
  }

  const { saved, off } = window.boardState;
  const rowsEl = document.getElementById("rows"), side = document.getElementById("side");
  const search = document.getElementById("search");
  let mode = saved?.mode ?? "feature";
  let cur = saved?.cur ? document.getElementById(saved.cur) : null;
  const inField = (e) => e.target.closest("input, textarea, [contenteditable]");
  const visible = (el) => el.checkVisibility();
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
    for (const b of document.querySelectorAll(".pill")) b.classList.toggle("off", off.has(b.dataset.feature));
    localStorage.setItem("board-off:" + document.title, JSON.stringify([...off]));
    if (cur && (cur.classList.contains("off") || cur.classList.contains("miss"))) setCur(null);
    showGraph();
  }

  function composeAll() {
    const g = side.querySelector('.g[data-feature="*"]'), pre = g.querySelector(".mermaid");
    if (!pre) return;
    const key = "g:*:" + [...off].sort().join(",");
    if (pre.dataset.key === key && pre.dataset.src !== undefined) return;
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
    pre.dataset.src = edges.length ? lines.join("\n") : "";
    pre.innerHTML = "";
    pre.hidden = !edges.length;
    g.querySelector(".gnote").hidden = !!edges.length;
  }

  function showGraph() {
    const feature = cur?.dataset.feature ?? "";
    const key = mode === "all" || !feature || feature === "standalone" ? "*" : feature;
    for (const g of side.querySelectorAll(".g")) g.hidden = g.dataset.feature !== key;
    if (key === "*") composeAll();
    document.getElementById("gname").textContent = key === "*" ? "whole tracker" : feature;
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
    const i = gs.findLastIndex((g) => g.offsetTop <= scrollY + 80);
    gs[Math.min(Math.max(i + delta, 0), gs.length - 1)].scrollIntoView({ block: "start" });
  }

  document.getElementById("featnav").addEventListener("click", (e) => {
    const b = e.target.closest(".pill"); if (!b) return;
    off.has(b.dataset.feature) ? off.delete(b.dataset.feature) : off.add(b.dataset.feature);
    applyFilters();
  });
  for (const b of document.querySelectorAll("[data-gmode]")) b.addEventListener("click", () => { mode = b.dataset.gmode; showGraph(); });
  document.getElementById("sidefold").addEventListener("click", () => side.classList.toggle("folded"));
  search.addEventListener("input", applyFilters);

  const toast = document.getElementById("toast");
  let toastTimer = null;
  const say = (text) => { toast.textContent = text; toast.classList.add("on"); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove("on"), 1600); };
  const copyText = (text, what) => (navigator.clipboard?.writeText(text) ?? Promise.reject()).then(() => say("copied " + what), () => say("could not copy"));

  // a click on a row's number copies its path; a copy button copies its payload; links inside a row open, the row stays as it was
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-copy]");
    if (b) { e.preventDefault(); e.stopPropagation(); copyText(b.dataset.copy, b.textContent.trim() === "copy" ? "the question" : b.textContent.trim().replace("copy ", "the ")); return; }
    const t = e.target.closest(".ticket");
    if (!t || !e.target.closest(".ticket > summary")) return;
    if (e.target.closest("a")) { setCur(t, false); return; }
    if (e.target.closest(".num")) { e.preventDefault(); copyText(t.dataset.path, "the path"); }
    setCur(t, false);
  }, true);

  const help = document.getElementById("help");
  document.getElementById("helpbtn").addEventListener("click", () => help.classList.toggle("open"));
  help.addEventListener("click", () => help.classList.remove("open"));

  document.getElementById("scheme").addEventListener("click", () => {
    const root = document.documentElement;
    root.dataset.theme = root.dataset.theme === "night" ? "day" : "night";
    localStorage.setItem("board-theme", root.dataset.theme);
    setupMermaid();
    for (const el of document.querySelectorAll(".mermaid")) el.innerHTML = "";
    renderGraphs();
  });

  let gPending = false, gTimer = null;
  document.addEventListener("keydown", (e) => {
    if (inField(e)) { if (e.key === "Escape") { search.value = ""; applyFilters(); search.blur(); } return; }
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
      case "X": case "O": { const open = e.key === "O"; for (const g of rowsEl.querySelectorAll("details.grp[data-state]")) g.open = open; break; }
      case "z": { const g = cur?.closest("details.grp") ?? groups()[0]; if (g) g.open = !g.open; break; }
      case "d": { const href = cur?.querySelector("a.rp")?.href; if (href) window.open(href, "_blank"); break; }
      case "y": if (cur) copyText(cur.dataset.path, "the path"); break;
      case "a": mode = mode === "all" ? "feature" : "all"; showGraph(); break;
      case "b": side.classList.toggle("folded"); break;
      case "0": off.clear(); applyFilters(); break;
      default:
        if (/^[1-9]$/.test(e.key)) {
          const chip = document.querySelectorAll(".pill")[e.key - 1];
          if (chip) { off.has(chip.dataset.feature) ? off.delete(chip.dataset.feature) : off.add(chip.dataset.feature); applyFilters(); }
        }
    }
  });

  function openTarget(hash = location.hash) {
    const el = document.getElementById(hash.slice(1));
    if (!el) return;
    for (let d = el; d; d = d.parentElement) if (d.tagName === "DETAILS") d.open = true;
    if (el.classList.contains("ticket")) setCur(el, false);
    el.scrollIntoView({ block: "start" });
    el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 1500);
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
    try { sessionStorage.setItem("board-view", JSON.stringify(state)); } catch {}
    try { window.name = "board:" + JSON.stringify({ saved: state }); } catch {}
  }
  function poll() {
    const s = document.createElement("script");
    s.src = document.body.dataset.stampSrc + "?" + Date.now();
    s.onload = () => { s.remove(); if (window.__boardStamp !== document.body.dataset.stamp) { saveState(); location.reload(); } else setTimeout(poll, 5000); };
    s.onerror = () => { s.remove(); setTimeout(poll, 5000); };
    document.head.append(s);
  }
  setTimeout(poll, 5000);

  new ResizeObserver(([e]) => document.documentElement.style.setProperty("--topbar-h", e.target.offsetHeight + "px")).observe(document.querySelector(".top"));
  if (cur) cur.classList.add("kcur");
  applyFilters();
  if (!saved && location.hash) openTarget();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__, prog="board"))
