#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.14"
# dependencies = ["tyro", "pyyaml", "markdown"]
# ///
"""Render the tracker board: one HTML page for a tracker's whole agent/tickets tree.

Run `board` from anywhere inside the repo: it finds the tracker (the nearest
agent/tickets up from the current directory, so a worktree or a clone inside a
workspace repo both work), renders, opens the tab, and keeps re-rendering until
Ctrl-C. --no-watch --no-open is the one-shot form: render the page and exit.

Reads every feature directory (spec.md, NN-<slug>.md tickets with
status/blocked-by/type/priority/size frontmatter, cross-feature refs as
<feature>/NN) and every standalone ticket (*.md at the tracker root, the queue
file aside) and writes one self-contained page beside the tracker,
agent/board.html. The page is the tickets as rows grouped by state: needs me
(the merged needs-human queue), needs my review (work waiting for the user's
ruling), frontier, claimed, blocked, proposed, done folded.

A row reads left to right in fixed columns: the feature, the number, what the
row asks of the user (to rule on, your answer, design session, prototype,
research, legwork, build), the ticket's short name with its review page and the
pull requests and issues its `gh` list names, the ticket brief under the name,
the user's time on it, the priority as a word, and what it waits on. The name
is the ticket's H1, the brief its `## Brief` section, the priority and the size
its frontmatter; a ticket silent on one of those shows its row without that
mark. Rows sort by priority, then by the user's time, within each group. Every
mark says on hover what it means. Below a width the time, the priority and the
blockers move under the name. A click on a row's number copies the absolute
path of the file the row was read from: the ticket, or for a needs-me entry its
needs-human.md.

The page wears the house style in both schemes: it follows the system's, the
switch in the top bar pins one, and ?theme=day|night on the address pins one for
a screenshot. Feature pills in the top bar hide and show a feature's rows, each
counting its done tickets out of all of them, proposed included; a filter box
narrows the rows to a word. An optional source the render did without is said
once at the top of the page. A graph panel, beside the rows on a wide window and
above them on a narrow one, shows the dependency graph of the feature of the row
under the cursor with that ticket marked, or the whole tracker's graph with its cross-feature edges, hidden features left out. A
graph draws only tickets that wait on something or are waited on: a ticket with
no edge is a row, not a node. A proposed ticket, one the user has not ruled on,
keeps its status whatever blocks it and is drawn dashed.

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

# What a row's marks stand for: the word the row shows, and what that word means. Each tip is
# built from the map beside it, so the row and its own explanation cannot drift apart.
PRIORITY = {  # how soon a ticket matters to the user
    1: ("now", "today"), 2: ("next", "this week"), 3: ("soon", "once the ones above are out"),
    4: ("later", "when there is room"), 5: ("someday", "parked"),
}
PRIORITY_TIP = "The priority, an agent's reading of what you have said; tell any session to change one.\n" + "\n".join(
    f"p{level} {word}: {means}" for level, (word, means) in PRIORITY.items()
)
SIZES = {  # the user's own time on a ticket
    "XS": ("15 min", "under 15 min"), "S": ("20 min", "about 20 min"), "M": ("1 h", "about an hour"),
    "L": ("half a day", "half a day"), "XL": ("several sessions", "several sessions"),
}
SIZE_RANK = {size: rank for rank, size in enumerate(SIZES)}
SIZE_TIP = (
    "Your time on this ticket, never the agent's: reading the diff or the design, trying the demo, deciding.\n"
) + "\n".join(f"{size} {means}" for size, (_, means) in SIZES.items())
ASKS = {  # what a row asks of the user: the word in its column, and what that word means
    "review": ("to rule on", "A worker has finished this. Read its review page and try its demo, then accept, amend, redo or reject it."),
    "answer": ("your answer", "The work stops until you answer the questions on this ticket."),
    "design": ("design session", "A decision to talk through with you; nothing is built on it until it is settled."),
    "prototype": ("prototype", "A decision you take in front of something built to compare. You judge the render."),
    "research": ("research", "An agent reads up on this alone. You read what it found when it lands."),
    "legwork": ("legwork", "Work that unblocks a decision: an agent does it, or hands you a checklist."),
    "build": ("build", "An agent builds this alone. It comes back to you as a build to rule on."),
}
GROUPS = [
    ("needs", "needs me"), ("review", "needs my review"), ("open", "frontier"), ("claimed", "claimed"),
    ("blocked", "blocked"), ("proposed", "proposed"), ("done", "done"),
]


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
    serve_diffviews.cache_clear()  # once per directory per render; the next render asks again, which is what revives a server
    diffviews = serve_diffviews(root.parent / "diffviews")
    features = load_features(root, roots.overrides, diffviews)
    # a standalone ticket whose slug names an in-flight feature was absorbed into it (grilling)
    standalone = [k for k in load_standalone(roots, diffviews) if k.slug not in roots.overrides]
    queue = load_needs_human(root / "needs-human.md")
    log = git_log(repo)
    stamp = content_stamp(project, features, standalone, queue, log)
    out.parent.mkdir(parents=True, exist_ok=True)
    page = render_page(project, features, standalone, queue, log, stamp, out.name + ".stamp.js")
    out.write_text(page)
    Path(str(out) + ".stamp.js").write_text(f'window.__boardStamp = "{stamp}";\n')
    print(out)


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
    title: str  # the H1: the short name a row shows
    status: str  # proposed | open | claimed | review | done, plus derived: blocked
    kind: str | None  # a decision ticket's type (research | prototype | grilling | legwork); None on a build ticket
    blocked_by: list[str]
    ext_by: list[tuple[str, str]]  # cross-feature blockers: (ref "<feature>/NN", status)
    gh: list[str]  # the pull requests and issues the ticket names, as owner/repo#number
    body_html: str
    diffview: str | None
    path: Path  # the file read, in whichever checkout holds the feature
    priority: int | None = None  # 1 to 5; None on a ticket whose frontmatter is silent
    size: str | None = None  # XS | S | M | L | XL, the user's time on it
    brief: str = ""  # the ## Brief section, as inline HTML


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
    priority: int | None = None
    size: str | None = None
    brief: str = ""


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
    brief, body = take_brief(body)
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
        priority=ticket_priority(meta, path),
        size=ticket_size(meta, path),
        brief=brief,
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
        brief, body = take_brief(body)
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
                priority=ticket_priority(meta, path),
                size=ticket_size(meta, path),
                brief=brief,
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


def ticket_priority(meta: dict, path: Path) -> int | None:
    priority = meta.get("priority")
    if priority is None:
        return None
    assert priority in PRIORITY, f"{path}: priority {priority!r}; a ticket declares one of {sorted(PRIORITY)}"
    return int(priority)


def ticket_size(meta: dict, path: Path) -> str | None:
    size = meta.get("size")
    if size is None:
        return None
    assert str(size) in SIZES, f"{path}: size {size!r}; a ticket declares one of {list(SIZES)}"
    return str(size)


def take_brief(body: str) -> tuple[str, str]:
    """(the ## Brief section as inline HTML, the body without it): what the row shows under the name,
    and the text that is left to fold under the row. One home per fact, on the row as on the page."""
    match = re.search(r"^##\s+Brief\s*$(.*?)(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL)
    if not match:
        return "", body
    return inline_md(" ".join(match.group(1).split())), body[: match.start()] + body[match.end() :]


def inline_md(text: str) -> str:
    """Markdown as one line of HTML: a brief or a headline carries code and emphasis, never a block."""
    return re.sub(r"^<p>|</p>$", "", markdown.markdown(text).strip())


GH_REF = re.compile(r"[\w.-]+/[\w.-]+#\d+")


def gh_refs(meta: dict, path: Path) -> list[str]:
    refs = [str(r) for r in meta.get("gh") or []]
    for ref in refs:
        assert GH_REF.fullmatch(ref), f"{path}: gh reference {ref!r}; a reference is owner/repo#number"
    return refs


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
          [(t.num, t.title, t.status, t.kind, t.blocked_by, t.ext_by, t.gh, t.body_html, t.diffview, t.path,
            t.priority, t.size, t.brief) for t in f.tickets])
         for f in features],
        [(k.slug, k.title, k.status, k.kind, k.blocked_by, k.gh, k.body_html, k.diffview, k.path, k.source,
          k.priority, k.size, k.brief) for k in standalone],
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


# ---- what a ticket asks of the user ---------------------------------------
# The seams agent/tickets/board-orients/spec.md decides and its later slices fill in. That spec is
# their oracle, held as the properties in test_board.py: each stub's check is an expected failure
# naming the slice that lifts it.

# where a session's transcript is on this machine, as the rest of the repo resolves it
TRANSCRIPTS = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "projects"


def needs_me(status: str, kind: str | None, priority: int | None, open_question: bool) -> bool:
    """Whether a ticket waits on the user, from what its file says: a build in review, a ticket with
    an open question, or an unclaimed design or prototype decision at p1 or p2.
    Lifted by 03-questions-and-needs-me."""
    raise NotImplementedError


@dataclass(frozen=True)
class Question:
    """One `[Dn]` item under a ticket's `## Questions`: a call only the user can make."""

    tag: str  # D1, D2, ... the ticket's running sequence
    headline: str  # the bold sentence the board shows under the row
    detail: str  # the rest of the item, as written
    ruled: str | None  # the date on the `Ruled <date>:` line under it; None while the question is open


def read_questions(text: str) -> list[Question]:
    """The questions a ticket file holds, ruled ones included, in file order. The `[Dn]` tags a
    closing comment carries elsewhere in the file are not questions. Lifted by
    03-questions-and-needs-me."""
    raise NotImplementedError


@dataclass(frozen=True)
class Session:
    """A session whose commits changed a ticket, as the user resumes it."""

    id: str
    title: str  # its /rename name, else Claude Code's own
    cwd: str  # the working directory its transcript records
    first: str  # when it first committed on the ticket
    last: str


def ticket_sessions(path: Path, repo: Path, transcripts: Path | None = None) -> list[Session]:
    """The sessions whose commits changed the ticket file, from the `Session:` trailers on every
    branch, oldest first. A session with no transcript under `transcripts` (TRANSCRIPTS, this
    machine's, by default) is a worker on another host and is left out: the user cannot resume it.
    Lifted by 05-sessions."""
    raise NotImplementedError


def absence_note(source: str, words: str) -> str:
    """An optional source the render did without, said once on the page: GitHub, the model, the
    transcripts, the review-page server."""
    return f'<p class="absent" data-absent="{html.escape(source)}">{html.escape(words)}</p>'


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

type Row = Ticket | Standalone


def asks(status: str, kind: str | None, open_question: bool = False) -> str:
    """Which of ASKS a row asks of the user, from what its ticket file says. `open_question` is
    what 03-questions-and-needs-me passes once it reads a ticket's questions; until then no row
    asks for an answer."""
    if status == "review":
        return "review"
    if open_question and status != "done":
        return "answer"
    return {"grilling": "design", "prototype": "prototype", "research": "research", "legwork": "legwork"}.get(kind or "", "build")


def asks_tag(t: Row) -> str:
    kind = asks(t.status, t.kind)
    word, meaning = ASKS[kind]
    return f'<span class="asks a-{kind}" data-tip="{html.escape(meaning)}">{word}</span>'


def time_tag(t: Row) -> str:
    if not t.size:
        return ""  # a ticket whose file says no size shows none; its column stays, empty
    return f'<span class="time" data-tip="{html.escape(SIZE_TIP)}">{SIZES[t.size][0]}</span>'


def priority_tag(t: Row) -> str:
    if not t.priority:
        return ""
    return f'<span class="pri p{t.priority}" data-tip="{html.escape(PRIORITY_TIP)}">p{t.priority} {PRIORITY[t.priority][0]}</span>'


def sort_key(t: Row) -> tuple:
    """A row's place within its group: the priority first, then the user's time, then the name. A
    ticket whose frontmatter says neither sorts after the ones that do."""
    return (t.priority or len(PRIORITY) + 1, SIZE_RANK.get(t.size or "", len(SIZE_RANK)), t.title.lower())


def dep_chips(feature: str, by_num: dict[str, Ticket], t: Ticket) -> str:
    local = "".join(blocker_chip(b, by_num[b].status, f"#t-{feature}-{b}") for b in t.blocked_by)
    return local + ext_chips(t.ext_by)


def ext_chips(refs: list[tuple[str, str]]) -> str:
    return "".join(blocker_chip(ref, status, ref_anchor(ref)) for ref, status in refs)


def blocker_chip(ref: str, status: str, href: str) -> str:
    done = "done" if status == "done" else "not done yet"
    return (f'<a class="chip {status}" href="{html.escape(href)}" onclick="event.stopPropagation()" '
            f'data-tip="Waits on {html.escape(ref)}, {done}.">{html.escape(ref)}</a>')


def review_link(address: str | None) -> str:
    if not address:
        return ""
    return (f'<a class="rp" href="{html.escape(address)}" target="_blank" onclick="event.stopPropagation()" '
            f'data-tip="This build&#39;s review page: the diff, with the demo to try and a place to write on it (d).">review page</a>')


def gh_links(refs: Sequence[str]) -> str:
    # the issues URL serves a pull request too: GitHub redirects it to the pull page
    return "".join(
        f'<a class="gh" href="https://github.com/{repo}/issues/{num}" target="_blank" '
        f'onclick="event.stopPropagation()" data-tip="A pull request or issue this ticket names, on GitHub.">{html.escape(ref)}</a>'
        for ref in refs for repo, num in [ref.split("#")]
    )


def search_text(*parts: str) -> str:
    return html.escape(re.sub(r"\s+", " ", " ".join(re.sub(r"<[^>]+>", " ", p) for p in parts)).strip().lower(), quote=True)


def row_open(row_id: str, status: str, feature: str, num: str, search: str, path: Path) -> str:
    """The element every row is: what the page's script matches a row on, and the file a click on
    its number copies."""
    return (
        f'<details class="ticket row-{status}" id="{row_id}" data-feature="{html.escape(feature)}" '
        f'data-num="{html.escape(num)}" data-search="{search}" data-path="{html.escape(str(path))}"><summary>'
    )


def clipped(text: str) -> str:
    """A mark's words, cut off with an ellipsis where its column is too narrow. The clipping sits on
    this inner element, since a box that hides its overflow would hide its own hover words too."""
    return f'<span class="clip">{html.escape(text)}</span>'


def row(row_id: str, feature: str, num: str, t: Row, chips: str, on_branch: str = "") -> str:
    """One ticket row, every mark in a fixed column: the feature, the number (a click copies the
    file's path), what the row asks of the user, the name with its review page and GitHub
    references, the ticket brief under the name, the user's time, the priority, the blockers.
    Below a width the time, the priority and the blockers move under the name. The ticket's
    remaining text folds under the row."""
    brief = f'<span class="brief">{t.brief}</span>' if t.brief else ""
    return (
        row_open(row_id, t.status, feature, num, search_text(num, t.title, t.brief, t.body_html, *t.gh), t.path)
        + f'<span class="ftag" data-tip="The feature this ticket belongs to. Its pill in the top bar hides and shows these rows.">{clipped(feature)}</span>'
        f'<span class="num" data-tip="Click to copy the path of the file this row was read from (y):\n{html.escape(str(t.path))}">{html.escape(num)}</span>'
        f'{asks_tag(t)}'
        f'<span class="main"><span class="titleline"><span class="title" data-tip="{html.escape(t.title)}">{clipped(t.title)}</span>'
        f'{review_link(t.diffview)}{gh_links(t.gh)}{on_branch}</span>{brief}</span>'
        f'<span class="meta">{time_tag(t)}{priority_tag(t)}<span class="chips">{chips}</span></span>'
        f'</summary><div class="body">{t.body_html}</div></details>'
    )


def ticket_row(f: Feature, t: Ticket) -> str:
    by_num = {x.num: x for x in f.tickets}
    return row(f"t-{f.name}-{t.num}", f.name, t.num, t, dep_chips(f.name, by_num, t))


def standalone_row(k: Standalone) -> str:
    on_branch = (
        f'<span class="src" data-tip="Filed on branch {html.escape(k.source)}, not on the main branch.">on {html.escape(k.source)}</span>'
        if k.source else ""
    )
    return row(f"standalone-{k.slug}", "standalone", "--", k, ext_chips(k.blocked_by), on_branch)


def needs_row(owner: str, i: int, item: str, queue: Path) -> str:
    """A needs-human.md entry, which is not a ticket and has none of a ticket's marks. The queue
    retires into the tickets its entries belong to (agent/tickets/board-orients/spec.md, ticket 10)."""
    summary, sep, detail = item.partition(" :: ")
    body = markdown.markdown(detail, extensions=["fenced_code"]) if sep else ""
    title = summary if sep else item
    return (
        row_open(f"needs-{owner}-{i}", "needs", owner, "!", search_text(summary, body), queue)
        + f'<span class="ftag" data-tip="The feature this entry was filed under.">{clipped(owner)}</span>'
        f'<span class="num" data-tip="Click to copy the path of the queue file this entry is in (y):\n{html.escape(str(queue))}">!</span>'
        f'<span class="asks a-queue" data-tip="A queue entry: work that waits on you and has no ticket of its own yet.">{ASKS["answer"][0]}</span>'
        f'<span class="main"><span class="titleline"><span class="title" data-tip="{html.escape(title)}">{clipped(title)}</span></span></span>'
        f'</summary><div class="body">{body}</div></details>'
    )


def feature_chip(f: Feature) -> str:
    """A feature's pill in the top bar: its counts, and the click that hides and shows its rows.

    The done count is out of every ticket the feature has, proposed ones included, so a breakdown
    just cut off a spec reads 0/4."""
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


def render_page(
    project: str, features: list[Feature], standalone: list[Standalone], queue: Queue,
    log: str, stamp: str, stamp_src: str
) -> str:
    rows: dict[str, list[str]] = {state: [] for state, _ in GROUPS}
    for f in features:
        rows["needs"].extend(needs_row(f.name, i, item, f.needs_human.path) for i, item in enumerate(f.needs_human.entries))
    rows["needs"].extend(needs_row("standalone", i, item, queue.path) for i, item in enumerate(queue.entries))
    ranked: dict[str, list[tuple[tuple, str, Row]]] = {state: [] for state, _ in GROUPS}
    for f in features:
        for t in f.tickets:
            ranked[t.status].append((sort_key(t), ticket_row(f, t), t))
    for k in standalone:
        ranked[k.status].append((sort_key(k), standalone_row(k), k))
    for state, sortable in ranked.items():
        rows[state].extend(row for _, row, _ in sorted(sortable, key=lambda ranks: ranks[0]))
    grouped = {state: [t for _, _, t in sortable] for state, sortable in ranked.items() if sortable}
    groups = "".join(
        f'<details class="grp" id="grp-{state}" data-state="{state}"{"" if state == "done" else " open"}>'
        f'<summary><h2>{label} <span class="n">{len(rows[state])}</span></h2></summary>'
        f'<div class="tickets">{"".join(rows[state])}</div></details>'
        for state, label in GROUPS if rows[state]
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
    return PAGE.substitute(
        project=html.escape(project), chips=chips, groups=groups, graphs=graphs, log=log_html,
        columns=row_columns(features, standalone, grouped), absences="".join(absences(features, standalone)),
        footmeta=footmeta, stamp=stamp, stamp_src=html.escape(stamp_src),
    )


# How many characters of a tracker's own names a column shows before the rest is cut with an
# ellipsis (a feature name) or wraps to a second line (a blocker reference): the width the column
# had when it was fixed, so a long name costs the row no more than it used to.
NAME_CAP = 14
REF_CAP = 14


def row_columns(features: list[Feature], standalone: list[Standalone], grouped: dict[str, list[Row]]) -> str:
    """The width of each of a row's fixed columns, as the CSS tokens the row's grid reads.

    A column is as wide as the widest mark that can land in it and no wider, so the name and the
    brief take every pixel the row has spare. The widths come from the marks themselves: the closed
    vocabularies for what a row asks, the user's time and the priority, and the tracker's own names
    and references for the feature tag and the blockers. Their marks are all set in the one
    monospace, so a column's width is a count of characters (`--mark-char`), capped where a
    tracker's own names could run away.

    The feature, the number and what the row asks are measured over the whole board, so those
    columns run straight down every row of it. The time, the priority and the blockers are measured
    over each group, since a group of quick unblocked tickets has no use for the width an XL one
    needs: a column still runs down the group the eye is reading, and the rest is the brief's."""
    page = {
        "ftag": min(max([len(f.name) for f in features] + [len("standalone")]), NAME_CAP),
        "num": len("--"),  # a standalone ticket has no number
        "asks": max(len(word) for word, _ in ASKS.values()),
        "time": max(len(word) for word, _ in SIZES.values()),
        "pri": max(len(f"p{level} {word}") for level, (word, _) in PRIORITY.items()),
        "chips": min(max([len(ref) for ref in blocker_refs(features, standalone)], default=2), REF_CAP),
    }
    css = column_tokens(":root", page)
    for state, rows in grouped.items():
        own = {
            "time": max([len(SIZES[r.size][0]) for r in rows if r.size], default=0),
            "pri": max([len(f"p{r.priority} {PRIORITY[r.priority][0]}") for r in rows if r.priority], default=0),
            "chips": min(max([len(ref) for r in rows for ref in blockers_of(r)], default=0), REF_CAP),
        }
        css += column_tokens(f"#grp-{state}", {mark: n for mark, n in own.items() if n < page[mark]})
    return css


PADDING = {"asks": 0.85, "pri": 0.95}  # the tag's border and the pill's, which sit outside the words


def column_tokens(selector: str, widths: dict[str, int]) -> str:
    if not widths:
        return ""
    return f"  {selector} {{\n" + "".join(
        f"    --col-{mark}: calc({count} * var(--mark-char) + {PADDING.get(mark, 0)}rem);\n"
        for mark, count in widths.items()
    ) + "  }\n"


def blockers_of(t: Row) -> list[str]:
    """The blockers one row shows, as the reader sees them written."""
    if isinstance(t, Standalone):
        return [ref for ref, _ in t.blocked_by]
    return t.blocked_by + [ref for ref, _ in t.ext_by]


def blocker_refs(features: list[Feature], standalone: list[Standalone]) -> list[str]:
    """Every blocker the board shows."""
    return [ref for rows in ([t for f in features for t in f.tickets], standalone) for t in rows for ref in blockers_of(t)]


def absences(features: list[Feature], standalone: list[Standalone]) -> list[str]:
    """What this render did without, said once each (the board renders with any optional source
    missing). A review page linked as a file is one nothing answered for; a tracker with no page
    rendered yet has no server to miss, so it says nothing."""
    pages = [t.diffview for f in features for t in f.tickets] + [k.diffview for k in standalone]
    if any(page and page.startswith("file://") for page in pages):
        return [absence_note(
            "review-page-server",
            "Nothing is serving the review pages, so they open as files and what you write on one is not saved.",
        )]
    return []


PAGE = Template(r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>board — ${project}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<script>
  // The scheme before first paint: ?theme= pins it, for a screenshot or a layout check; else the
  // switch's last answer, else the system's.
  (() => {
    const asked = new URLSearchParams(location.search).get("theme");
    const kept = localStorage.getItem("board-theme");
    const night = asked ? asked === "night" : kept ? kept === "night" : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = night ? "night" : "day";
  })();
</script>
<style>
  /* The house tokens, copied from mx/skills/house-style/tokens.css: colours as light-dark() pairs,
     the fonts, and the base rules. The type roles there are for a page of prose; a board sets its
     own below. --muted goes darker than the house value, which is a day-scheme readability fix:
     the board's small text is read on parchment at 100% zoom. */
  :root {
    color-scheme: light dark;
    --ground: light-dark(#f4e4cd, #1a1714);
    --ground-2: light-dark(#eddabe, #201c18);
    --edge: light-dark(#cfbca3, #4a433b);
    --muted: light-dark(#4c443c, #b0a89e);
    --body: light-dark(#37261d, #ede3d2);
    --strong: light-dark(#22140b, #faf2dc);
    --accent: light-dark(#426724, #6ea444);
    --accent-2: light-dark(#674806, #cdb78a);
    --wash: light-dark(rgb(66 103 36 / 0.16), rgb(110 164 68 / 0.22));
    --wash-ink: color-mix(in srgb, var(--muted) 6%, transparent);
    --mark: light-dark(rgb(168 139 81 / 0.35), rgb(205 183 138 / 0.35));
    --font-body: "Newsreader", Georgia, serif;
    --font-mono: "IBM Plex Mono", ui-monospace, monospace;
    --radius: 6px;
    --topbar-h: 52px;  /* measured once the bar is laid out, since it wraps on a narrow window */
    /* one character of a mark: the marks are monospace at .78rem, and IBM Plex Mono advances .6em,
       with the rest the slack a fallback mono needs */
    --mark-char: calc(.78rem * .64);
  }
  /* the row's fixed columns, each as wide as the widest mark that lands in it (board.row_columns) */
${columns}
  [data-theme="day"] { color-scheme: light; }
  [data-theme="night"] { color-scheme: dark; }

  /* The callout hues of mwolf.dev: what a row asks wears one each, the priority ramps on the
     first, and the user's time has the last to itself. The teal is picked again from the
     prototype's, away from the moss accent, which it read as by day. Each day value clears 4.6:1
     against its own 12% tint, since that is the background the tag's text sits on. */
  :root {
    --c-pink: light-dark(#7d4172, #d9a2d0);
    --c-gold: light-dark(#725614, #d9b36f);
    --c-rose: light-dark(#963f37, #fabeb4);
    --c-purple: light-dark(#6546b3, #b8a4ff);
    --c-orange: light-dark(#894c14, #ffc387);
    --c-blue: light-dark(#255d8f, #85baeb);
    --c-slate: light-dark(#4c5b76, #9aaacb);
    --c-time: light-dark(#255a63, #86bcc4);
  }

  * { box-sizing: border-box; }
  html { scrollbar-color: var(--edge) var(--ground); }
  body { margin: 0; background: var(--ground); color: var(--body);
    font: 400 15.5px/1.5 var(--font-body); -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
  p { margin: 0; }
  a { color: inherit; text-decoration: none; transition: color 150ms; }
  a:hover { color: var(--accent); }
  ::selection { background: var(--mark); }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }
  code, kbd, pre { font-family: var(--font-mono); }
  .ftag, .num, .asks, .pri, .time, .src, .chip, .rp, .gh, .label, .n, .featchip, .search,
    .btn, .gname, .log, .footmeta, kbd { font-family: var(--font-mono); }

  /* ---- the top bar: the project, the feature pills, the filter, the graph mode, the scheme ---- */
  .top { position: sticky; top: 0; z-index: 10; display: flex; gap: 1rem; align-items: center; min-height: 52px;
    padding: .4rem 1.25rem; background: var(--ground); border-bottom: 1px solid var(--edge); }
  .top .name { font-weight: 600; color: var(--strong); white-space: nowrap; }
  .top .name span { color: var(--muted); font-weight: 400; }
  .featnav { display: flex; gap: .4rem; overflow-x: auto; flex: 1; min-width: 0; scrollbar-width: none; }
  .featchip { padding: .1rem .7rem; border: 1px solid var(--edge); border-radius: 999px; background: var(--ground-2);
    font-size: .8rem; color: var(--muted); cursor: pointer; white-space: nowrap; display: inline-flex; gap: .4em;
    align-items: center; transition: color 150ms, border-color 150ms; }
  .featchip:hover { color: var(--accent); border-color: var(--accent); }
  .featchip.off { opacity: .5; text-decoration: line-through; }
  .dim { color: var(--muted); }
  .dot { display: inline-block; width: .45em; height: .45em; border-radius: 50%; background: var(--accent-2); }
  .search { background: var(--ground-2); border: 1px solid var(--edge); border-radius: var(--radius); color: var(--body);
    font-size: .82rem; padding: .25rem .6rem; width: 12rem; }
  .search:focus { outline: none; border-color: var(--accent); }
  .btn { background: none; border: 0; color: var(--muted); font-size: .82rem; cursor: pointer; padding: .2rem .45rem;
    transition: color 150ms; white-space: nowrap; }
  .btn:hover, .btn.on { color: var(--accent); }
  .seg { display: inline-flex; border: 1px solid var(--edge); border-radius: var(--radius); }
  .seg .btn.on { background: var(--wash); }
  .seg .btn + .btn { border-left: 1px solid var(--edge); }
  .scheme { display: inline-flex; align-items: center; }
  [data-theme="night"] .sun, [data-theme="day"] .moon { display: none; }

  /* what this render did without, said once each */
  .absences { padding: .6rem 1.25rem 0; display: grid; gap: .2rem; max-width: 110rem; margin: 0 auto; }
  .absences:empty { display: none; }
  .absent { font-size: .92rem; color: var(--muted); border-left: 2px solid var(--accent-2); padding-left: .6rem; }

  /* ---- the rows, the graph panel beside them on a wide window ---- */
  main { display: grid; grid-template-columns: minmax(0, 1fr); gap: 1.5rem; padding: 1rem 1.25rem 5rem;
    align-items: start; max-width: 110rem; margin: 0 auto; }
  /* one column: the graph above the rows, where a glance still reaches it, rather than past every group */
  .side { order: -1; position: sticky; top: var(--topbar-h); max-height: 40vh; overflow: auto; z-index: 5;
    background: var(--ground); border: 1px solid var(--edge); border-radius: var(--radius); padding: .7rem .9rem; }
  .side.folded .gbody { display: none; }
  @media (min-width: 1400px) {
    main { grid-template-columns: minmax(0, 1fr) minmax(16rem, 22rem); gap: 2.5rem; }
    .side { order: 0; top: calc(var(--topbar-h) + 1rem); max-height: calc(100vh - var(--topbar-h) - 2rem);
      border: 0; border-left: 1px solid var(--edge); border-radius: 0; padding: 0 0 0 1.75rem; }
  }
  .ghead { display: flex; gap: .5rem; align-items: baseline; margin-bottom: .3rem; }
  .gname { color: var(--muted); font-size: .8rem; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .gnote { color: var(--muted); font-size: .92rem; padding: .4rem 0; }
  .mermaid { margin: 0; display: flex; justify-content: center; }
  /* out of the layout, not merely invisible: a graph source is one unwrappable line, and a render
     that has not come back yet would widen the column it sits in */
  .mermaid:not(:has(svg)) { display: none; }
  .mermaid svg { max-width: 100%; height: auto; }
  .side g.node.cur rect, .side g.node.cur polygon { stroke-width: 2.5px !important; }

  /* ---- a group of rows ---- */
  .grp { margin-bottom: 1.75rem; }
  .grp > summary { list-style: none; cursor: pointer; padding: .3rem 0 .6rem; }
  .grp > summary::-webkit-details-marker { display: none; }
  .grp.empty { display: none; }
  h2 { font-size: .82rem; font-weight: 400; color: var(--muted); margin: 0; display: flex; align-items: center;
    gap: .6rem; font-family: var(--font-mono); }
  h2::after { content: ""; flex: 1; border-top: 1px solid var(--edge); }
  h2 .n { color: var(--muted); }
  .grp > summary::before { content: "▾"; color: var(--muted); font-size: .7rem; margin-right: .4rem; }
  .grp:not([open]) > summary::before { content: "▸"; }
  .label { font-size: .82rem; color: var(--muted); font-family: var(--font-mono); }

  /* ---- a row: every mark in a fixed column, so the eye scans one ---- */
  .ticket { border-top: 1px solid var(--edge); scroll-margin-top: calc(var(--topbar-h) + 3rem); scroll-margin-bottom: 3rem; }
  .ticket:first-child { border-top: 0; }
  .ticket.off, .ticket.miss { display: none; }
  .ticket > summary { display: grid; column-gap: .9rem; row-gap: .2rem; align-items: baseline; padding: .55rem .5rem;
    cursor: pointer; list-style: none; border-radius: var(--radius); transition: background-color 150ms;
    grid-template-columns: var(--col-ftag) var(--col-num) var(--col-asks) minmax(0, 1fr) var(--col-time) var(--col-pri) var(--col-chips);
    grid-template-areas: "ftag num asks main time pri chips"; }
  .ticket > summary::-webkit-details-marker { display: none; }
  .ticket > summary:hover { background: var(--wash-ink); }
  .ticket.kcur > summary, .ticket.flash > summary { background: var(--wash); }
  .ftag { grid-area: ftag; font-size: .78rem; color: var(--muted); min-width: 0; }
  /* a box that hides its overflow hides its own tooltip with it, so the ellipsis sits one level in */
  .clip { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .num { grid-area: num; font-size: .8rem; color: var(--muted); text-align: right; cursor: copy; white-space: nowrap; }
  .num:hover { color: var(--accent); }
  .main { grid-area: main; display: grid; gap: .1rem; min-width: 0; }
  /* the name is what a row is read by, so it keeps its words: the links wrap under it rather than
     taking the width off it */
  .titleline { display: flex; flex-wrap: wrap; gap: 0 .6rem; align-items: baseline; min-width: 0; }
  .title { color: var(--strong); min-width: 0; }
  .row-done .title, .row-blocked .title, .row-proposed .title { color: var(--muted); }
  .titleline > a, .titleline > .src { flex: none; }
  .brief { color: var(--muted); font-size: .88rem; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ticket[open] .brief { white-space: normal; }
  .meta { display: contents; }
  .asks, .pri, .time, .src, .rp, .gh { font-size: .78rem; white-space: nowrap; }
  .chip { font-size: .78rem; }
  .asks { grid-area: asks; --c: var(--muted); color: var(--c); justify-self: start; max-width: 100%;
    background: color-mix(in srgb, var(--c) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 38%, transparent); border-radius: 4px; padding: 0 .4rem; }
  .a-review { --c: var(--c-gold); }
  .a-answer, .a-queue { --c: var(--c-rose); }
  .a-design { --c: var(--c-purple); }
  .a-prototype { --c: var(--c-orange); }
  .a-research { --c: var(--c-blue); }
  .a-legwork { --c: var(--c-slate); }
  .a-build { background: none; border-color: transparent; padding-left: 0; }
  .time { grid-area: time; color: var(--c-time); justify-self: end; font-variant-numeric: tabular-nums; }
  /* the priority is a ramp, not a set of categories: one hue, strongest at p1 */
  .pri { grid-area: pri; color: var(--c-pink); justify-self: start; padding: 0 .45rem; border-radius: 999px;
    background: color-mix(in srgb, var(--c-pink) 16%, transparent); }
  .pri.p3 { background: color-mix(in srgb, var(--c-pink) 8%, transparent); }
  .pri.p4, .pri.p5 { color: var(--muted); background: none; padding-left: 0; }
  /* the blockers' column is as fixed as the rest, so a long cross-feature reference wraps within
     it rather than widening it and pulling the time and the priority out of line */
  .chips { grid-area: chips; display: flex; gap: .35rem; justify-content: flex-end; flex-wrap: wrap; }
  .chip { color: var(--body); overflow-wrap: anywhere; }
  .chip.done { color: var(--muted); text-decoration: line-through; }
  .rp { color: var(--accent); }
  .rp:hover { text-decoration: underline; text-underline-offset: 3px; }
  .gh { color: var(--muted); }
  .src { color: var(--accent-2); }

  /* below this width the time, the priority and the blockers move under the name, and the top
     bar's pills take a line of their own rather than scrolling out of sight */
  @media (max-width: 1000px) {
    .top { flex-wrap: wrap; padding: .4rem .75rem; }
    .featnav { flex-basis: 100%; order: 1; }
    main { padding: 1rem .75rem 5rem; }
    .absences { padding: .6rem .75rem 0; }
    .ticket > summary { grid-template-columns: var(--col-ftag) var(--col-num) var(--col-asks) minmax(0, 1fr);
      grid-template-areas: "ftag num asks main" ".    .   .    meta"; }
    .meta { grid-area: meta; display: flex; gap: .9rem; align-items: baseline; flex-wrap: wrap; }
    .time, .pri, .chips { grid-area: auto; justify-self: auto; }
  }
  /* narrower still: the name takes the row's width, with its marks over it and under it */
  @media (max-width: 620px) {
    .ticket > summary { grid-template-columns: minmax(0, var(--col-ftag)) var(--col-num) minmax(0, 1fr);
      grid-template-areas: "ftag num asks" "main main main" "meta meta meta"; }
    .search { flex: 1; width: auto; }
  }

  /* ---- a row, opened ---- */
  .body { padding: .4rem .5rem 1.4rem 1rem; margin-left: .5rem; border-left: 1px solid var(--edge);
    max-width: 46rem; color: var(--body); font-size: .96rem; }
  .body > * + * { margin-top: .8em; }
  .body h2 { font-family: var(--font-body); font-size: 1rem; font-weight: 600; color: var(--strong); margin-top: 1.4em; }
  .body h2::after { display: none; }
  .body h3 { font-size: .96rem; font-weight: 600; color: var(--strong); }
  .body a { color: var(--accent); }
  .body code { background: var(--ground-2); border-radius: 3px; padding: 0 .25em; font-size: .85em; }
  .body pre { background: var(--ground-2); border: 1px solid var(--edge); border-radius: var(--radius);
    padding: .6rem .8rem; overflow-x: auto; font-size: .82rem; }
  .body pre code { background: none; padding: 0; }
  .body ul, .body ol { padding-left: 1.2em; }
  .body li + li { margin-top: .3em; }
  .body li::marker { color: var(--muted); }
  .body table { border-collapse: collapse; font-size: .9rem; }
  .body th, .body td { text-align: left; padding: .2rem .8rem .2rem 0; border-bottom: 1px solid var(--edge); }

  /* ---- a mark says in words what it means ---- */
  /* The words appear under the row, at its left edge: the row is the box that is always on screen
     and never hides its overflow, so they cannot be clipped by the mark they belong to or run off
     a narrow window, wherever in the row that mark sits. */
  .ticket > summary { position: relative; }
  [data-tip]:hover::after { content: attr(data-tip); position: absolute; z-index: 60; top: calc(100% - .2rem); left: .5rem;
    width: max-content; max-width: min(28rem, 100%); white-space: pre-line; background: var(--ground); color: var(--body);
    border: 1px solid var(--edge); border-radius: var(--radius); padding: .5rem .7rem;
    font: .8rem/1.5 var(--font-mono); text-decoration: none; pointer-events: none;
    box-shadow: 0 2px 10px color-mix(in srgb, var(--strong) 14%, transparent); }

  .log { margin: 0; font-size: .8rem; line-height: 1.8; overflow-x: auto; white-space: pre-wrap; }
  .hash { color: var(--muted); }
  .footmeta { color: var(--muted); font-size: .78rem; margin-top: .8rem; }

  #toast { position: fixed; bottom: 1.2rem; left: 50%; transform: translateX(-50%); z-index: 50; max-width: 90vw;
    background: var(--ground); border: 1px solid var(--edge); border-radius: var(--radius); padding: .3rem .9rem;
    font: .8rem var(--font-mono); color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    opacity: 0; transition: opacity 200ms; pointer-events: none; }
  #toast.on { opacity: 1; }

  #help { position: fixed; inset: 0; z-index: 100; display: none; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--strong) 40%, transparent); }
  #help.open { display: flex; }
  #help .card { background: var(--ground); border: 1px solid var(--edge); border-radius: var(--radius); padding: 1.2rem 1.5rem; }
  #help table { border-collapse: collapse; font-size: .9rem; }
  #help td { padding: .2rem 1rem .2rem 0; }
  kbd { font-size: .78rem; border: 1px solid var(--edge); border-radius: 4px; padding: 0 .4rem; color: var(--body); }
</style>
</head>
<body data-stamp="${stamp}" data-stamp-src="${stamp_src}">
<div class="top">
  <span class="name">board <span>${project}</span></span>
  <nav class="featnav" id="featnav">${chips}</nav>
  <input class="search" id="search" type="search" placeholder="filter  /" autocomplete="off">
  <span class="seg" id="modes"><button class="btn" data-gmode="feature" title="the graph of the row's feature (a)">feature</button><button class="btn" data-gmode="all" title="the whole tracker's graph (a)">all</button></span>
  <button class="btn" id="helpbtn" title="keys (?)">?</button>
  <button class="btn scheme" id="scheme" title="the other colour scheme">
    <svg class="sun" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
    <svg class="moon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>
  </button>
</div>
<div class="absences">${absences}</div>
<main>
<div class="rows" id="rows">
${groups}
<details class="grp" id="grp-log"><summary><h2>recent commits</h2></summary>
  <pre class="log">${log}</pre>
  <p class="footmeta">${footmeta}</p>
</details>
</div>
<aside class="side" id="side">
  <div class="ghead"><span class="label">dependencies</span><span class="gname" id="gname"></span>
    <button class="btn" id="sidefold" title="fold the graph (b)">fold</button></div>
  <div class="gbody" id="gbody">
    <div class="g" data-feature=""><div class="gnote">open a row or move onto one (j / k)</div></div>
    ${graphs}
  </div>
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
<tr><td><kbd>t</kbd></td><td>the other colour scheme</td></tr>
<tr><td><kbd>1</kbd>…<kbd>9</kbd> <kbd>0</kbd></td><td>hide / show the nth feature; all on</td></tr>
<tr><td><kbd>/</kbd></td><td>filter rows; <kbd>Esc</kbd> clears</td></tr>
<tr><td><kbd>?</kbd></td><td>this help</td></tr>
</table></div></div>
<div id="toast" role="status"></div>

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
    // re-inject cached SVGs: an unchanged graph paints instantly instead of re-running mermaid.
    // Keyed by the scheme too, since mermaid bakes the palette into the SVG.
    for (const el of document.querySelectorAll(".mermaid")) {
      const hit = cache[el.dataset.key + "@" + document.documentElement.dataset.theme];
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

  // Mermaid bakes the colours into the SVG, and a light-dark() token never resolves through
  // getPropertyValue, so every colour is read off a probe element in the scheme on show, and read
  // again when the scheme switches. A status is drawn in the house ink: the work that wants the
  // user wears the accent, the rest steps back to the edge. ghost = a done ticket shown as
  // context, and proposed = not ruled on: both dashed.
  const probe = document.createElement("span");
  probe.style.display = "none";
  document.body.append(probe);
  const rgb = (name) => { probe.style.color = "var(" + name + ")"; return getComputedStyle(probe).color.match(/[\d.]+/g).map(Number); };
  // mermaid's classDef parser takes no rgba(), so a translucent token is laid over the ground and written as hex
  const hex = ([r, g, b, a = 1], [R, G, B] = [0, 0, 0]) =>
    "#" + [r * a + R * (1 - a), g * a + G * (1 - a), b * a + B * (1 - a)].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
  let classDefs = "";
  function setupMermaid() {
    const ground = rgb("--ground");
    const c = Object.fromEntries(["ground", "ground-2", "edge", "muted", "body", "strong", "accent", "wash"]
      .map((n) => [n, hex(rgb("--" + n), ground)]));
    const cls = {
      review: [c.wash, c.accent, c.strong, ""], open: [c["ground-2"], c.body, c.body, ""],
      claimed: [c["ground-2"], c.muted, c.body, ""], blocked: [c.ground, c.edge, c.muted, ""],
      proposed: [c.ground, c.muted, c.body, ",stroke-dasharray:4 3"], done: [c.ground, c.edge, c.muted, ""],
      ghost: [c.ground, c.edge, c.muted, ",stroke-dasharray:2 3"],
    };
    classDefs = Object.entries(cls).map(([s, [fill, stroke, text, extra]]) =>
      "  classDef " + s + " fill:" + fill + ",stroke:" + stroke + ",color:" + text + extra).join("\n");
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
        fontFamily: getComputedStyle(document.body).getPropertyValue("--font-body").trim(), fontSize: "13px",
        primaryColor: c.ground, primaryTextColor: c.body, primaryBorderColor: c.edge, lineColor: c.muted,
        clusterBkg: c.ground, clusterBorder: c.edge, titleColor: c.muted,
      },
    });
  }
  setupMermaid();

  let seq = 0;
  async function renderGraphs() {
    // mermaid.render (string -> svg), never mermaid.run: run's in-DOM processing
    // contaminates across the page's many diagrams, render is hermetic per call.
    // Only the graph on show renders; the others wait for their turn.
    for (const el of document.querySelectorAll(".g:not([hidden]) .mermaid")) {
      if (el.querySelector("svg")) continue;  // already rendered, or restored from the svg cache
      el.dataset.src = el.textContent;
      if (!el.dataset.src.trim()) continue;  // the composed graph with every feature hidden: its note shows instead
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
    const hit = cache[key + "@" + document.documentElement.dataset.theme];
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

  // The scheme the switch lands on is kept, and outlives a re-render; ?theme= overrides it.
  function switchScheme() {
    const root = document.documentElement;
    root.dataset.theme = root.dataset.theme === "night" ? "day" : "night";
    localStorage.setItem("board-theme", root.dataset.theme);
    setupMermaid();
    // a rendered element holds the SVG and its source only in dataset.src; assigning textContent
    // puts the source back and drops the SVG in one step, so the graph returns in the new palette
    for (const el of document.querySelectorAll(".mermaid")) if (el.dataset.src) el.textContent = el.dataset.src;
    renderGraphs();
  }
  document.getElementById("scheme").addEventListener("click", switchScheme);

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
      case "d": { const href = cur?.querySelector("a.rp")?.href; if (href) window.open(href, "_blank"); break; }
      case "y": copyPath(cur); break;
      case "a": mode = mode === "all" ? "feature" : "all"; showGraph(); break;
      case "b": side.classList.toggle("folded"); break;
      case "t": switchScheme(); break;
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
      if (el.querySelector("svg")) svgs[el.dataset.key + "@" + document.documentElement.dataset.theme] = { src: el.dataset.src, svg: el.innerHTML };
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
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__, prog="board"))
