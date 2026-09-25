#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.14"
# dependencies = ["tyro", "pyyaml", "markdown"]
# ///
"""Render the tracker board: one HTML page for a tracker's whole agent/tickets tree.

Run `board` from anywhere inside the repo: it finds the tracker the way the
`tracker` command does (the `tickets` of the agent repo the project holds at
`agent/`, in that repo's main checkout), renders, opens the tab, and keeps
re-rendering until Ctrl-C. --no-watch --no-open is the
one-shot form: render the page and exit.

Reads every ticket of the tracker (agent/tickets/<slug>.md, flat) through the
one command that parses one, `tracker` beside this script, and writes one
self-contained page beside the tracker, agent/board.html. The page is the
tickets as rows grouped by state: needs me, frontier, claimed, blocked,
proposed, done folded.

Needs me holds every ticket whose next step is the user's own time: a build to
rule on, a ticket stopped on a question, and a ticket at p1 or p2 the user is in
the loop for that nobody has taken up (board.needs_me).
Its open questions show under its row while the row is folded, each with a
button that copies it, one that copies the ticket's own, and one on the group
that copies every question on the board; each button says on hover what it will
copy. A build in review carries the worker's questions and closing comment in
the tracker's own copy, where `dispatch review` imported them from the worker's
report.

A row reads left to right in fixed columns: the tree the ticket is part of (the
top-level ticket its ancestry runs to), its own slug, what the row asks of the
user (to rule on, your answer, with you, build), the ticket's short name with
its review page and the
pull requests and issues its `gh` list names, each in the look of the state
GitHub gives it and saying that state on hover, the ticket brief under the name
with the open questions under that, the user's time on it, the priority as a
word, and what it waits on. The name is the ticket's H1, the brief its `##
Brief` section, the questions its `## Questions` section, the priority and the
size its frontmatter, which every ticket declares. Rows sort by priority, then by
the user's time, within each group. Every
mark says on hover what it means. Below a width the time, the priority and the
blockers move under the name. A click on a row's slug copies the absolute
path of the ticket file the row was read from.

An opened row reads as blocks rather than the ticket's whole text: its
questions, each with the detail the row has no room for, the ruling that
answered it and, while it is unanswered, a button that copies it, the sessions
that worked on it, its artefacts, then the ticket's own sections in the order
the file writes them, with the comments folded away as history. The artefacts
are read from the ticket's show directory, agent/show/<slug>/: every file in it
as a link, and each one that runs on a button that copies the command that runs
it from the code repo's root. The sessions are read from the `Session:` trailer
on every commit that changed the ticket file, or an earlier path of it, on
every branch, and named by their transcript under $CLAUDE_CONFIG_DIR/projects;
one with no transcript on this machine, a worker on another host, is left out,
and each of the rest carries a button that copies the command resuming it. The
brief is not repeated there: it is on the row.

The page wears the house style in both schemes: it follows the system's, the
switch in the top bar pins one, and ?theme=day|night on the address pins one for
a screenshot. One pill per tree in the top bar hides and shows that tree's rows,
each counting its done tickets out of all of them, proposed included, with one
more for the tickets in no tree; a filter box
narrows the rows to a word. An optional source the render did without is said
once at the top of the page. A graph panel, beside the rows on a wide window and
above them on a narrow one, shows the dependency graph of the tree of the row
under the cursor with that ticket marked, or the whole tracker's graph with the
edges between trees, hidden trees left out. A
graph draws only tickets that wait on something or are waited on: a ticket with
no edge is a row, not a node. A proposed ticket, one the user has not ruled on,
keeps its status whatever blocks it and is drawn dashed.

Over that panel sits the board briefing: where things stand and three next
picks, written by a `claude -p` session that was given the tracker as the board
reads it and explored the repo from there, with the time it was written beside
it. A watching board sends each change of a ticket's status to that same
session, as a note of what changed, five minutes after the last status to move
and at most one briefing every ten minutes, and the session rewrites the
briefing or leaves it standing; a ticket edited without its status moving is
re-rendered and not sent, and so is one whose status goes back to what the
session was last told. It retires after an hour idle or twenty pings, and the
next change starts a fresh one. The session and its briefing live in a
cache file beside the page. Until a briefing has been written the column holds
the board's own count of what waits and the frontier by priority, then by what
accepting it unlocks, then by the user's time; a machine with no claude, or one
whose last run of it answered nothing, stays there and the page says so once.

That panel is a preview. The `full` button, or ?graph on the address, opens the
same graph at its own size over the board; `window` opens it in a window of its
own, to sit beside the board. Both scroll and drag to pan, and both carry the
tree and whole-tracker switch. A click on a node in the overlay closes it on
that ticket's row; a click on a node in the window leaves the window where it is
and moves the board to that row.

One board per tracker, showing what is actionable now. It reads one directory:
every ticket file is written and committed in the agent repo's main checkout,
claims and review flips included, so a build is on the board from its claim
onward.

A ticket row links its diffview review page when one has been rendered:
agent/diffviews/<slug>.html beside the tracker. Those pages are gitignored, so the
link appears only on the machine that rendered them. Every render asks
`diffview --serve` for the address the pages answer on, so a click from the
board opens a page that saves comments. A server exiting is itself a change to
re-render on, so a watching board keeps its links live; where the pages cannot
be served the link is the file, which the page itself says is read-only.

Every pull request and issue the rows name is resolved in one `gh api graphql`
query per render, GitHub giving issues and pull requests one number space per
repository, and the answer is cached beside the page for five minutes, so a
watching board asks once a window however often it re-renders. Without `gh`,
its auth or the network the references stay bare links and the page says why
once.

Watching means: every few seconds it looks for a change under the tracker and
re-renders on one. It also re-renders on the three things that move with no
file under the tracker moving: a briefing the session has rewritten, GitHub's
answer running past the five minutes it is cached for, and a run of the model
that answered nothing, which the page says once. One watcher per board:
several of them write the same page from the same tracker, and share GitHub's
answer through the cache beside it, but each keeps its own briefing schedule, so
a second one pays for every briefing again and resumes the session while the
first is in it.

The page polls a sidecar stamp file (written beside the HTML) every 5s and
reloads, keeping scroll position, open sections, the cursor and the hidden
trees, only when content actually changed: one open tab stays current
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
import shlex
import stat
import subprocess
import sys
import threading
import time
from collections import Counter
from itertools import takewhile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Annotated

import markdown
import tyro

import briefing  # the board briefing: the session that writes it, and the cache it lives in, beside this script
import github  # the state of the pull requests and issues the tickets name, beside this script
import tracker  # the one parser of a ticket file, and the rules it refuses one by, beside this script

STATUS_SYMBOL = {"done": "✓", "review": "◉", "claimed": "⟳", "open": "○", "blocked": "⊘", "proposed": "◌"}

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
    "Your time on this ticket, never the agent's: reading the diff or the design, looking at its show, deciding.\n"
) + "\n".join(f"{size} {means}" for size, (_, means) in SIZES.items())
ASKS = {  # what a row asks of the user: the word in its column, and what that word means
    "review": ("to rule on", "A worker has finished this. Read its review page and its artefacts, then accept, amend, redo or reject it."),
    "answer": ("your answer", "The work stops until you answer the questions on this ticket."),
    "session": ("with you", "A ticket you are in the loop for: it is worked with you, and dispatch keeps it from a worker."),
    "build": ("build", "An agent builds this alone. It comes back to you as a build to rule on."),
}
ALONE = "alone"  # the pill for a ticket with no parent ticket and no child tickets
# what a row is grouped under (board.group_of); a ticket in review has no group of its own,
# since needs me claims every one of them
GROUPS = [
    ("needs", "needs me"), ("open", "frontier"), ("claimed", "claimed"),
    ("blocked", "blocked"), ("proposed", "proposed"), ("done", "done"),
]


@dataclass
class Args:
    tickets_root: Annotated[Path | None, tyro.conf.Positional, tyro.conf.arg(metavar="[PATH]")] = None
    """Tracker root, e.g. agent/tickets. Default: the tracker this directory's project plans, the `agent/tickets` of the agent repo it holds, in the main checkout ticket files are committed in."""
    out: Path | None = None
    """Output HTML path. Default: board.html beside the tracker (agent/board.html)."""
    repo: Path | None = None
    """Repo for the commit log and the sessions that worked on a ticket. Default: the agent repo the tracker is in, which is where a ticket file's commits are."""
    open: bool = True
    """Open the result in the browser diffview pages open in ($DIFFVIEW_BROWSER, else xdg-open), so the board and the diffs it links share a window."""
    watch: bool = True
    """Keep running and re-render whenever anything under the tracker changes, until Ctrl-C."""


def main(args: Args) -> None:
    tickets_root = (args.tickets_root or find_tracker(Path.cwd())).resolve()
    assert tickets_root.is_dir(), f"no tracker at {tickets_root}"
    # A ticket file's own history is the agent repo's, and so are the sessions that wrote it, so
    # the repo read for both is the one the tracker is in, whichever that is: a project whose
    # `agent/` is not yet a repo of its own is read in the repo that holds it. What the page is
    # named after, what its commit log shows and what the briefing session explores is the project
    # itself, which is the repo that holds the agent one (`project`, below).
    repo = (args.repo or toplevel(tickets_root) or project(tickets_root)).resolve()
    out = (args.out or tickets_root.parent / "board.html").resolve()
    try:
        render(tickets_root, repo, out)
    except tracker.Refused as refused:
        sys.exit(f"board: the tracker holds a ticket no reader can read:\n{refused}")
    if args.open:
        browser = os.environ.get("DIFFVIEW_BROWSER") or "xdg-open"
        subprocess.Popen([browser, str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if args.watch:
        try:
            watch(tickets_root, repo, out)
        except KeyboardInterrupt:
            pass


def project(tickets_root: Path) -> Path:
    """The code repo's root: the directory the agent repo sits in, which is the project the tracker
    plans and the repo its commit log and its briefing session read."""
    return tracker.project_root(tickets_root)


def find_tracker(start: Path) -> Path:
    """Where this project's ticket files are, as the one command that writes them answers it: the
    `agent/tickets` of the agent repo the project holds, in that repo's main checkout."""
    try:
        return tracker.tracker_root(start)
    except tracker.Refused as refused:
        sys.exit(f"board: {refused}")


def render(root: Path, repo: Path, out: Path) -> tuple[tuple[str, str], ...]:
    """Write the page, and answer with the status every ticket on it is shown under: the watcher
    pings the briefing session on a status that moved, and the render is where the tracker is
    already read."""
    code = project(root)
    serve_diffviews.cache_clear()  # once per directory per render; the next render asks again, which is what revives a server
    session_log.cache_clear()  # likewise: the sessions that committed on a ticket while the board watches
    tickets = load_tickets(root, repo, serve_diffviews(root.parent / "diffviews"))
    log = git_log(code)
    out.parent.mkdir(parents=True, exist_ok=True)
    gh = github.resolve(gh_shown(tickets), github.cache_path(out))
    said = briefing.Briefing.read(briefing.cache_path(out))
    stamp = content_stamp(code.name, tickets, log, gh, said)
    page = render_page(code.name, tickets, log, stamp, out.name + ".stamp.js", gh, said)
    out.write_text(page)
    Path(str(out) + ".stamp.js").write_text(f'window.__boardStamp = "{stamp}";\n')
    print(out)
    return statuses(tickets)


def statuses(tickets: list["Ticket"]) -> tuple[tuple[str, str], ...]:
    """Every ticket the board shows with the status its file declares, plus the derived `blocked`,
    as a value to compare: what the briefing session is pinged about (`look`). A ticket filed and a
    ticket retired are a status appearing and a status going, so both are a change; a ticket whose
    prose was rewritten is not, nor is one that joins the needs-me group by gaining a question.

    The derived status is in, so a ticket unblocked by its blocker landing reads as the change it
    is."""
    return tuple((t.slug, t.status) for t in tickets)


def tracker_statuses(root: Path, repo: Path) -> tuple[tuple[str, str], ...]:
    """The same, without a render: what the watcher's first pass reads, since the tracker it opens
    on is the baseline every later status is compared against.

    Read here rather than taken from the render `main` does before watching, so that the baseline
    and the file snapshot it is the baseline for are read in the same pass: a status that moves
    between the two would otherwise sit inside the snapshot and outside the baseline. It costs one
    load of the tracker per watcher start. The review pages are no part of a status, so this reads
    them unserved (briefing_state does the same)."""
    return statuses(load_tickets(root, repo, Diffviews(root.parent / "diffviews", None)))


def watch(tickets_root: Path, repo: Path, out: Path) -> None:
    """Re-render on any change under the tracker, in every checkout that contributes to it, and on
    the three things that move on their own: the briefing a session has rewritten since the page
    was written, GitHub's answer running out of the lifetime it is cached for, and a run of the
    model that came back with nothing.

    Those three are what the watcher is for as much as the tracker is. A pull request merged while
    the tracker sits still would otherwise show as open until someone touched a ticket, a briefing
    written minutes after the change that asked for it would not show at all, and a run that
    answered nothing writes no file for anything else to notice."""
    seen, session = Seen(), Briefer(repo, out)
    while True:
        try:
            seen = look(seen, session, tickets_root, repo, out)
        except Exception as e:  # a file deleted mid-scan, a half-written ticket: the next pass sees the settled state
            print(f"board: {e}; retrying", file=sys.stderr)
        time.sleep(2)


@dataclass(frozen=True)
class Seen:
    """What the last pass of the watcher read, as a value to compare the next one against.

    `snapshot` is the tracker as `tracker_snapshot` reads it and None before the first pass;
    `statuses` is every ticket's status as the page it drew shows it, which is what the briefing
    session is pinged about; `briefing` is when the cache file the rendered page holds was written;
    `asked` is when GitHub's answer beside the board was got, and `armed` the answer the render that
    asked again has been done for. `quiet` is what the last run of the model that answered nothing
    said: it writes no cache file, so nothing else here moves with it.
    """

    snapshot: tuple | None = None
    statuses: tuple[tuple[str, str], ...] = ()  # (), not None, before the first pass: the pass that reads it first reads `snapshot` to know
    briefing: int = 0
    asked: datetime.datetime | None = None
    armed: datetime.datetime | None = None
    quiet: str = ""


def look(seen: Seen, session: "Briefer", tickets_root: Path, repo: Path, out: Path) -> Seen:
    """One pass of the watcher: re-render what has moved since the last one, tell the briefing
    session what changed, and return what this pass read.

    Any file under the tracker moving re-renders; only a ticket's status moving reaches the session,
    so the prose of a ticket rewritten all afternoon costs a render each and no model run (the
    spec's Decisions under "The board briefing"). The change is timed from before the render, which
    takes a moment, so a status that moved during one is a status the session has not been told
    about."""
    cache = briefing.cache_path(out)
    snapshot = tracker_snapshot(tickets_root, repo)
    written = cache.stat().st_mtime_ns if cache.exists() else 0
    quiet = briefing.SILENT  # read with the rest of what this pass reads: a run lands on its own thread
    armed, lapsed = seen.armed, run_out(seen.asked, seen.armed)
    current = seen.statuses
    if snapshot != seen.snapshot:
        if seen.snapshot is not None:
            at = now()
            current = render(tickets_root, repo, out)
            session.saw(current, seen.statuses, at)
        else:
            # the start is itself a change where no briefing has ever been written, since a tracker
            # quiet since the last one is the board a returning user opens
            current = tracker_statuses(tickets_root, repo)
            session.opened(snapshot, current, None if briefing.Briefing.read(cache) else now())
    elif written != seen.briefing or quiet != seen.quiet or lapsed:
        render(tickets_root, repo, out)  # nothing under the tracker moved, so no status did either
        if lapsed:
            armed = seen.asked  # only the render that asked again is done with this answer
    session.tick(tickets_root, snapshot, current, now())
    return Seen(snapshot, current, written, github.asked_at(github.cache_path(out)), armed, quiet)


def now() -> datetime.datetime:
    return datetime.datetime.now().astimezone()


def run_out(asked: datetime.datetime | None, armed: datetime.datetime | None) -> bool:
    """Whether GitHub's answer has run out of the lifetime it is cached for and the render that
    would ask again has not happened yet.

    The answer's own time is what arms the clock, so an answer that has had its render is done with:
    a render that asked leaves a later one and the clock arms again a window after it, and a tracker
    that has stopped naming any reference leaves the same one, which fires once and never again."""
    return bool(asked) and asked != armed and now() - asked >= github.LIFETIME


@dataclass
class Briefer:
    """The briefing session as the watcher holds it: what the session has been told about, and
    whether a run of the model is in flight.

    The session itself lives in the cache file beside the board, so a board restarted mid-window
    picks up the one it left. What is held here is only what the file cannot say: the tracker
    snapshot and the statuses the session was told about, so that a ping names what changed since
    and nothing is sent that the session already has, and when a ticket's status last moved, which
    is what the quiet window is measured from (briefing.on_change).

    A run takes minutes, so it runs in a thread of its own: a watcher blocked on the model is a
    board that stops re-rendering. One at a time, and never twice inside the cadence, so a model
    that is not answering is asked once a cadence rather than every pass."""

    repo: Path
    out: Path
    told: tuple = ()  # the tracker snapshot the session was last told about
    told_statuses: tuple[tuple[str, str], ...] | None = None  # and the statuses; None where it has been told nothing at all
    changed_at: datetime.datetime | None = None  # when a ticket's status last moved, None where nothing is owed
    tried: datetime.datetime | None = None  # when a run was last started, answered or not
    running: threading.Thread | None = None

    def opened(self, snapshot: tuple, statuses: tuple, at: datetime.datetime | None) -> None:
        """The watcher's first pass: what the session is told about is measured from here, and `at`
        is set only where the start is itself the change (no briefing has ever been written), where
        the session has been told nothing and every status on the tracker is news."""
        self.told, self.told_statuses, self.changed_at = snapshot, None if at else statuses, at

    def saw(self, statuses: tuple, before: tuple, at: datetime.datetime) -> None:
        """What a render read, against what the pass before it read: a status that moved starts the
        quiet window again, and a tracker back at the statuses the session was told about owes it
        nothing, since a ticket claimed and unclaimed inside a window is news the session has.

        A pass where no status moved leaves the window where it was, so the prose of a ticket
        rewritten every minute neither starts one nor holds one open."""
        if statuses == self.told_statuses:
            self.changed_at = None
        elif statuses != before:
            self.changed_at = at

    def tick(self, root: Path, snapshot: tuple, statuses: tuple, at: datetime.datetime) -> None:
        """Whatever this pass of the watcher owes the briefing session, against the tracker as that
        pass read it. `changed_at` is when a ticket's status last moved, which is what the ping waits
        out the quiet window from."""
        if not self.changed_at or not briefing.available():
            return
        if self.running and self.running.is_alive():
            return
        if self.tried and at - self.tried < briefing.CADENCE:
            # a run that answered nothing is tried again a cadence later, not on the next pass: the
            # failure backoff and the briefing's own cadence are one window
            return
        cached = briefing.Briefing.read(briefing.cache_path(self.out))
        verb = briefing.on_change(cached, self.changed_at, at)
        if verb == "wait":
            return
        note = None if verb == "fresh" else changed_note(self.told, snapshot, project(root))
        self.tried = at
        self.running = threading.Thread(target=self.write, args=(root, cached, note, snapshot, statuses), daemon=True)
        self.running.start()

    def write(
        self, root: Path, cached: "briefing.Briefing | None", note: str | None, snapshot: tuple,
        statuses: tuple,
    ) -> None:
        """The run, off the watcher's own thread: a fresh session on the tracker's state, or the one
        that wrote the briefing told what changed. What it writes is picked up by the next pass,
        which re-renders the board on it.

        What the session has been told stays where it was until it answers: a run that comes back
        with nothing is tried again a window later, and the account of what moved is what that
        retry is for."""
        try:
            said = (
                briefing.ping(cached, note, project(root), now()) if note is not None
                else briefing.first(briefing_state(root, self.repo), project(root), now())
            )
            if said:
                said.write(briefing.cache_path(self.out))
                self.told, self.told_statuses = snapshot, statuses
        except Exception as e:  # the board is a page that renders without the model, this run included
            print(f"board: the briefing session: {e}", file=sys.stderr)


def briefing_state(root: Path, repo: Path) -> str:
    """The tracker as the board reads it, in the words the briefing session is handed it in: the
    tickets from the agent repo, the commits and the name from the project it plans, which is the
    repo that session reads for what the tickets cannot say."""
    # the session is given the tickets; a review page is the user's to read and its address the
    # render's to find, so this reads them unserved
    code = project(root)
    return state_of(code.name, load_tickets(root, repo, Diffviews(root.parent / "diffviews", None)), git_log(code))


# ---- the board briefing ---------------------------------------------------
# What the session that writes it is given, what it is told when the tracker moves, and what the
# board says where no session has written one. mx/skills/tracker/corpus/board-orients.md is the oracle;
# the session itself and the schedule are briefing.py.

STATE = """The tracker of {project} as the board reads it.

One ticket per line, under the parent ticket its tree runs to: slug, status, what it asks of you,
priority, your time on it, its name, its file. Under it, where the ticket has them: the brief, what
it waits on, its open questions.
"""


def state_of(project: str, tickets: list["Ticket"], log: str) -> str:
    """The tracker written out for the briefing session: every ticket the board shows, as the board
    shows it, under the tree it is part of, and the commits behind it.

    Nothing here is more than the board itself says. The file each line ends with is what the
    session reads for the rest, and the repo around it is what it is for."""
    written = [STATE.format(project=project)]
    for tree in trees_of(tickets):
        written.append(f"## {tree}\n" + "".join(state_line(t) for t in in_tree(tickets, tree)))
    return "\n".join(written + [f"## the last commits\n{log.strip()}\n"])


def state_line(t: "Ticket") -> str:
    """One ticket, as the board's own marks read it."""
    marks = [
        t.slug, t.status, ASKS[asks_word(t)][0],
        f"p{t.priority} {PRIORITY[t.priority][0]}", SIZES[t.size][0], t.title, str(t.path),
    ]
    said = " · ".join(marks) + "\n"
    if t.brief:
        said += f"  brief: {plain(t.brief)}\n"
    if waits := blockers_of(t):
        said += f"  waits on: {', '.join(waits)}\n"
    for q in shown_questions(t.status, t.questions):
        said += f"  asks: [{q.tag}] {plain(inline_md(q.headline))} {plain(inline_md(q.detail))}\n".rstrip() + "\n"
    return said


def changed_note(before: tuple, after: tuple, code: Path) -> str:
    """What moved between two of the watcher's snapshots, in the words the briefing session is told
    it in: the ticket files, the review pages and the artefacts, and the commits behind them. Both
    are written for the project, which is the repo that session explores."""
    heads = 2  # what a snapshot leads with, before its files: the agent repo's head and the project's
    was = {path: rest for path, *rest in before[heads:]}
    since = {path: rest for path, *rest in after[heads:]}
    said = [
        f"{word}: {', '.join(shorten(p, code) for p in sorted(paths))}"
        for word, paths in (
            ("new", since.keys() - was.keys()), ("gone", was.keys() - since.keys()),
            ("changed", {p for p in since.keys() & was.keys() if since[p] != was[p]}),
        ) if paths
    ]
    if before[1] != after[1]:
        said.append(f"the repo has moved on: {git_log(code).strip().splitlines()[0]} is its last commit")
    return "\n".join(said) or "something under the tracker was touched without changing"


def shorten(path: str, code: Path) -> str:
    """A path as the project writes it, since that is what the session reads it by."""
    return str(Path(path).relative_to(code)) if Path(path).is_relative_to(code) else path


COUNTED = "no one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()

FALLBACK_TIP = "No model has written a briefing: this is the board's own count, and the frontier by what it unblocks."
# The windows are the schedule's own, so the words and the rule cannot drift apart, as a row's
# marks and their tips do not (PRIORITY_TIP).
BRIEFING_TIP = (
    "The board briefing: a session that explored this repo says where things stand and what to take up next.\n"
    f"A ticket's status changing is sent to that same session {briefing.QUIET.seconds // 60} minutes after the last status to move,\n"
    f"and at most one briefing every {briefing.CADENCE.seconds // 60} minutes;\n"
    f"it retires after {briefing.IDLE.seconds // 3600} h idle or {briefing.PING_CAP} pings, and the next change starts a fresh one."
)


def fallback(tickets: list["Ticket"]) -> str:
    """What the board says where no model has written a briefing: the counts of what waits on the
    user and what is being worked on, and the next few by priority, then by what accepting them
    unlocks, then by the user's own time.

    What waits is counted off the rows' own marks, so the sentence and the group under it say the
    same thing: a ticket the board tags as a design session is one here whatever else it carries."""
    live = [t for t in tickets if t.status != "done"]
    mine = [t for t in live if group_of(t) == "needs"]
    waiting = {
        ("build to rule on", "builds to rule on"): [t for t in mine if asks_word(t) == "review"],
        ("question wanting a word", "questions wanting a word"): [q for t in mine for q in open_questions(t.questions)],
        ("ticket wanting a session", "tickets wanting a session"): [t for t in mine if asks_word(t) == "session"],
    }
    counts = [
        f"{counted(len(held))} {one if len(held) == 1 else many}" for (one, many), held in waiting.items() if held
    ]
    several = len(counts) > 1 or any(len(held) > 1 for held in waiting.values())  # what the verb agrees with
    waits = f"{listed(counts).capitalize()} wait{'' if several else 's'} on you." if counts else "Nothing waits on you."
    running = [t for t in live if t.status == "claimed"]
    worked = (
        f"{counted(len(running)).capitalize()} ticket{'s are' if len(running) != 1 else ' is'} being worked on."
        if running else "Nothing is being worked on."
    )
    lead = f"{waits} {worked}"
    unlocks = waited_on(tickets)
    picks = sorted(
        (t for t in live if group_of(t) in ("needs", "open")),
        key=lambda t: (t.priority, -unlocks[t.slug], *sort_key(t)[1:]),
    )
    if not picks:
        return lead + "\n\nNothing is open to take up."
    return lead + "\n\n## next\n" + "".join(f"- **{t.title}**: {why(t, unlocks[t.slug])}\n" for t in picks[:3])


def waited_on(tickets: list["Ticket"]) -> Counter:
    """How many tickets wait on each, by slug: what accepting one of them unlocks."""
    counts: Counter = Counter()
    for t in tickets:
        counts.update(ref for ref, _ in t.blocked_by)
    return counts


def why(t: "Ticket", unlocks: int) -> str:
    """Why the fallback put a ticket where it did, in the terms it ordered by."""
    return " · ".join(
        [PRIORITY[t.priority][0]]
        + ([f"accepting it unblocks {counted(unlocks)}"] if unlocks else [])
        + [f"{SIZES[t.size][0]} of yours"]
    )


def counted(n: int) -> str:
    return COUNTED[n] if n < len(COUNTED) else str(n)


def listed(said: list[str]) -> str:
    """A list as a sentence says it."""
    return said[0] if len(said) < 2 else ", ".join(said[:-1]) + f" and {said[-1]}"


def plain(markup: str) -> str:
    """Rendered inline markup as the words in it, for a reader that is not a page."""
    return html.unescape(re.sub(r"<[^>]+>", "", markup)).strip()


def tracker_snapshot(root: Path, repo: Path) -> tuple:
    """What the board read last, as a value to compare: the head of each of the project's two repos,
    then the tracker's files, the review pages and the artefacts beside them.

    Both heads, since the page is read off both: the sessions that worked a ticket are commits of
    the repo the tracker is in, and the commit list is the project's, which moves on a merge that
    touches no ticket at all.

    A page server's own bookkeeping counts too, hidden as it is: its exit moves those files, and
    the render that follows is what puts the pages back on an address that answers. So do the show
    directories, where an opened ticket reads its artefacts from; each file's mode is read with its
    time and size, since an artefact made executable gains a button and `chmod` moves neither.
    """
    dirs = [root, root.parent / "diffviews", root.parent / "show"]
    return (git(repo, "rev-parse", "HEAD"), git(project(root), "rev-parse", "HEAD")) + tuple(
        (str(f), st.st_mtime_ns, st.st_size, st.st_mode)
        for d in dirs if d.is_dir() for f in sorted(d.rglob("*")) if f.is_file() for st in [f.stat()]
    )


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
    """One ticket of the tracker, as a row shows it.

    `tree` is the slug of the top-level ticket its ancestry runs to, when that ticket has any
    descendant: the pill in the top bar that hides and shows the rows, and the graph the panel
    draws. A ticket with no parent ticket and no child tickets is in no tree, and its `tree` is "".
    """

    slug: str  # the ticket's id, and the row's
    title: str  # the H1: the short name a row shows
    status: str  # proposed | open | claimed | review | done, plus derived: blocked
    needs_user: bool  # whether the user is in the loop for it, so no worker takes it
    parent: str | None
    tree: str
    blocked_by: list[tuple[str, str]]  # (slug, status) per ticket it waits on
    gh: list[str]  # the pull requests and issues the ticket names, as owner/repo#number
    body_html: str
    diffview: str | None
    priority: int  # 1 to 5, how soon it matters to the user
    size: str  # XS | S | M | L | XL, the user's time on it
    path: Path  # the ticket file this row was read from
    brief: str = ""  # the ## Brief section, as inline HTML
    questions: list["Question"] = field(default_factory=list)  # its ## Questions, ruled ones included


def load_tickets(root: Path, repo: Path | None, diffviews: Diffviews) -> list[Ticket]:
    """Every ticket the board shows, read through the one parser of a ticket file.

    One directory holds them all: ticket files are written and committed in the tracker's own
    checkout, claims and review flips included, so nothing of a build in flight is anywhere else.
    """
    read = parsed(root)
    tickets = [shown(one, read, repo, diffviews) for one in read.values()]
    ids = [slug_id(one.slug) for one in tickets]
    assert len(ids) == len(set(ids)), f"slugs collide as mermaid ids: {sorted(ids)}"
    return sorted(tickets, key=lambda one: one.slug)


def parsed(root: Path) -> dict[str, "tracker.Ticket"]:
    """One tracker root as the tracker command reads it: every ticket file in it, by slug. A file
    no reader can read is refused there, with its own file and line."""
    if not root.is_dir():
        return {}
    read = tracker.tracker_of(root)
    tracker.refuse([refusal for one in read.tickets.values() for refusal in tracker.refusals_of(one, read)])
    return read.tickets


def tree_of(slug: str, tickets: dict[str, "tracker.Ticket"]) -> str:
    """The slug of the top-level ticket this one's ancestry runs to, when that ticket has a
    descendant; "" for a ticket with no parent ticket and no child tickets."""
    root, seen = slug, {slug}
    while (parent := tickets[root].parent) and parent in tickets and parent not in seen:
        seen.add(parent)
        root = parent
    if root != slug:
        return root
    return root if any(one.parent == slug for one in tickets.values()) else ""


def shown(
    read: "tracker.Ticket", tickets: dict[str, "tracker.Ticket"], repo: Path | None, diffviews: Diffviews,
) -> Ticket:
    """One ticket as the board shows it: what its file says, plus the status derived from what it
    waits on, and the review page and sessions beside it."""
    assert_safe_name(read.slug)
    blocked_by = [(ref, ref_status(ref, tickets)) for ref in read.blocked_by]
    status = read.status
    if status == "open" and any(state != "done" for _, state in blocked_by):
        status = "blocked"
    worked = ticket_sessions(read.path, repo)
    return Ticket(
        slug=read.slug,
        title=read.title or read.slug.replace("-", " "),
        status=status,
        needs_user=read.needs_user,
        parent=read.parent,
        tree=tree_of(read.slug, tickets),
        blocked_by=blocked_by,
        gh=[str(ref) for ref in read.meta.get("gh") or []],
        body_html=ticket_blocks(read, read.questions, path=read.path, status=status, worked=worked),
        diffview=diffviews.link(diffviews.root, f"{read.slug}.html"),
        path=read.path,
        priority=read.meta.get("priority"),
        size=read.meta.get("size"),
        brief=inline_md(read.brief),
        questions=read.questions,
    )


def ref_status(ref: str, tickets: dict[str, "tracker.Ticket"]) -> str:
    """The status of a ticket another one waits on. A reference the board cannot see counts as
    done: the tracker refuses a dangling one where it is written, so what is left here is a ticket
    retired since the edge onto it was written."""
    return tickets[ref].status if ref in tickets else "done"


def assert_safe_name(name: str) -> None:
    # slugs ride into HTML attributes and mermaid click strings unescaped
    assert re.fullmatch(r"[A-Za-z0-9._-]+", name), f"unsafe tracker name: {name!r}"


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


def inline_md(text: str) -> str:
    """Markdown as one line of HTML: a brief or a headline carries code and emphasis, never a block."""
    return re.sub(r"^<p>|</p>$", "", markdown.markdown(text).strip()) if text else ""


def ref_anchor(ref: str) -> str:
    return f"#t-{ref}"


def render_body(md: str) -> str:
    out = markdown.markdown(md, extensions=["fenced_code", "tables"], tab_length=3)
    # a link to another ticket file becomes that row's anchor, wherever the writer wrote it from
    return re.sub(r'href="(?:[\w./-]*/)?([a-z0-9][\w-]*)\.md"', r'href="#t-\1"', out)


def content_stamp(
    project: str, tickets: list[Ticket], log: str,
    gh: github.Answer = github.NOTHING, said: "briefing.Briefing | None" = None,
) -> str:
    # everything the page shows except the render timestamp: an unchanged board
    # keeps its stamp, so the open tab knows not to reload. A state GitHub gave a link, a briefing
    # a session rewrote and an absence the page says are the three of those that move without a
    # file under the tracker moving with them.
    key = repr((
        project,
        [(t.slug, t.title, t.status, t.needs_user, t.parent, t.tree, t.blocked_by, t.gh, t.body_html,
          t.diffview, t.path, t.priority, t.size, t.brief, t.questions) for t in tickets],
        log,
        sorted(gh.states.items()),
        gh.missing,
        said and (said.text, said.written),
        absences(tickets, gh, said),
    ))
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def git_log(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline", "-n", "15"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"git log failed in {repo}: {result.stderr.strip()}"
    return result.stdout


# ---- what a ticket asks of the user ---------------------------------------
# The seams mx/skills/tracker/corpus/board-orients.md decides. That spec is their oracle, held as the
# properties in test_board.py.

# where a session's transcript is on this machine, as the rest of the repo resolves it
TRANSCRIPTS = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "projects"

SESSION_TRAILER = "Session"  # the trailer a session's commits carry, added by the dotfiles' git hook


def needs_me(status: str, needs_user: bool, priority: int, open_question: bool) -> bool:
    """Whether a ticket waits on the user, from what its file says: one not done that is a build in
    review, has an open question, or is an unclaimed ticket at p1 or p2 the user is in the loop
    for."""
    if status == "done":
        return False
    if status == "review" or open_question:
        return True
    # a ticket worked with the user, that nobody has taken up yet
    return bool(needs_user) and priority in (1, 2) and status in ("open", "proposed")


Question = tracker.Question  # one `[Dn]` item under a ticket's `## Questions`, read by the one parser


@dataclass(frozen=True)
class Session:
    """A session whose commits changed a ticket, as the user resumes it."""

    id: str
    title: str  # its /rename name, else Claude Code's own, else its id
    cwd: str  # the working directory its transcript records
    first: str  # when it first committed on the ticket
    last: str

    @property
    def resume(self) -> str:
        """The command that picks the session up where it left off, in the directory it ran in.

        The directory is gone once dispatch has cleaned up the worktree a session ran in, and the
        session is still there: `claude --resume` finds it from wherever it is run, so what the
        vanished directory costs is the `cd`, not the resume.
        """
        if not self.cwd or not Path(self.cwd).is_dir():
            return f"claude --resume {self.id}"
        return f"cd {shlex.quote(self.cwd)} && claude --resume {self.id}"


def ticket_sessions(path: Path, repo: Path | None, transcripts: Path | None = None) -> list[Session]:
    """The sessions whose commits changed the ticket file, from the `Session:` trailers on every
    branch, oldest first. A session with no transcript under `transcripts` (TRANSCRIPTS, this
    machine's, by default) is a worker on another host and is left out: the user cannot resume it.
    """
    if repo is None or (name := repo_name(path)) is None:  # a tracker outside any checkout
        return []
    found = []
    for sid, (first, last) in session_log(repo).get(name, {}).items():
        if written := transcript(sid, transcripts or TRANSCRIPTS):
            title, cwd = written
            found.append(Session(sid, title or sid, cwd, first, last))
    return found


# one record per commit: the date the session wrote it, and the session that signed it, with the
# files under it as `<status>\t<name>`, a move as `R<score>\t<old>\t<new>`
SESSION_LOG = f"--format=%x1e%as %(trailers:key={SESSION_TRAILER},valueonly,separator=%x20)"


@functools.cache
def session_log(repo: Path) -> dict[str, dict[str, tuple[str, str]]]:
    """Which sessions changed which file, and the dates of each session's first and last commit on
    it, oldest session first: one pass over every branch of the repo.

    A file that moved is one file: git records the move, so the sessions under its old path are
    carried to the new one as the walk reaches the commit that moved it, through a chain of moves
    too. The old path keeps them as well, since a checkout that has not taken the move still holds
    the file there; a file that arrives at the freed path afterwards carries its own sessions alone.

    Where the carry gets a file's sessions wrong, all of it out of one flat walk over every ref:

    - A commit that moves a file and rewrites more than half of it scores as a delete and an add
      rather than a move, and nothing is carried.
    - A commit on the old path that the walk reaches after the move is not carried either. The walk
      is in commit order across every ref at once, so which side of the move a commit falls on is
      not decided by the branch it is on.
    - A move onto a path some earlier file was deleted from inherits that file's sessions.

    The dates are min and max rather than the ends of the walk, which is in commit order while the
    dates are the author's: a cherry-picked commit would otherwise leave a range running backwards.
    """
    changed: dict[str, dict[str, tuple[str, str]]] = {}
    vacated: set[str] = set()  # paths a move emptied
    # a commit's own account of which session made it, written by the prepare-commit-msg hook
    written = git(repo, "log", "--all", "--reverse", "--name-status", "-M", SESSION_LOG)
    for record in filter(None, written.split("\x1e")):  # git()'s strip eats the leading separator
        head, _, names = record.partition("\n")
        date, *sessions = head.split()
        for line in filter(None, names.split("\n")):
            status, *paths = line.split("\t")
            if not paths:  # no file: a trailer whose value ran on to a line of its own
                continue
            name = paths[-1]  # a move names its destination second
            if status[0] in "AR" and name in vacated:
                changed[name] = {}  # a file arriving where one moved away is its own file
            if status.startswith("R"):
                carry(changed.get(paths[0], {}), changed.setdefault(name, {}))
                vacated.add(paths[0])
            carry({sid: (date, date) for sid in sessions}, changed.setdefault(name, {}))
    return changed


def carry(worked: dict[str, tuple[str, str]], into: dict[str, tuple[str, str]]) -> None:
    """Merge sessions and their first and last dates into `into`, widening the span of one already
    there."""
    for sid, (first, last) in worked.items():
        was_first, was_last = into.get(sid, (first, last))
        into[sid] = (min(was_first, first), max(was_last, last))


def repo_name(path: Path) -> str | None:
    """The file as git names it: its path from the top of the checkout that holds it, which is the
    name every worktree of the repo gives it and the name the log prints. None outside a checkout."""
    top = toplevel(path.parent)
    return str(path.resolve().relative_to(top)) if top else None


@functools.cache
def toplevel(directory: Path) -> Path | None:
    """The top of the checkout `directory` is in, or None where it is in none."""
    done = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    return Path(done.stdout.strip()).resolve() if done.returncode == 0 else None


TITLES = ("customTitle", "aiTitle")  # a session's /rename name, else Claude Code's own


def transcript(session: str, transcripts: Path) -> tuple[str, str] | None:
    """(the session's title, the directory it ran in) from its transcript on this machine, or None
    where this machine has no transcript of it. The newest transcript answers, since a session
    resumed in another directory writes a second one."""
    written = sorted(transcripts.glob(f"*/{session}.jsonl"), key=lambda p: p.stat().st_mtime)
    if not written:
        return None
    return read_transcript(written[-1], written[-1].stat().st_size)


@functools.cache
def read_transcript(path: Path, size: int) -> tuple[str, str]:
    """The title a transcript's records carry and the working directory they were written in. The
    last title the session was given wins, and a name it was given by hand wins over the model's.

    `size` keys the cache: a transcript the session is still writing is read again as it grows.
    """
    titles: dict[str, str] = {}
    cwd = ""
    for line in path.read_text(errors="replace").splitlines():
        if not any(key in line for key in (*TITLES, "cwd")):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:  # a line the session was still writing when the board read it
            continue
        titles.update({key: record[key] for key in TITLES if record.get(key)})
        cwd = cwd or str(record.get("cwd") or "")
    return next((titles[key] for key in TITLES if key in titles), ""), cwd


def absence_note(source: str, words: str) -> str:
    """An optional source the render did without, said once on the page: GitHub, the model, the
    transcripts, the review-page server."""
    return f'<p class="absent" data-absent="{html.escape(source)}">{html.escape(words)}</p>'


# ---- an opened ticket -----------------------------------------------------


def ticket_blocks(
    read: "tracker.Ticket", asked: Sequence[Question], path: Path, status: str, worked: Sequence[Session]
) -> str:
    """A ticket opened on the board, as blocks: its questions with the detail the row has no room
    for, the sessions that worked on it, the artefacts it produced, then its own sections in the
    order the file writes them, the comments folded away as history.

    The brief is not one of them. It is on the row, where it is read without opening anything, and
    a ticket says a thing once. The comments sink to the end whatever place the file gives them,
    since what is folded away is read last.
    """
    blocks, history, said = [], [], []
    for heading, text in shown_sections(read, asked):
        word = heading.lower() if heading else ""
        if word == "questions":  # its items are the block above; whatever else it says is the ticket's
            said.append(text)
        elif word == "comments":
            history.append(text)
        else:
            blocks.append(block(heading, prose(heading, text)))
    front = [asked_block(asked, prose(None, "".join(said)), path, status),
             sessions_block(worked), artefacts_block(show_dir(path), project(path.parent))]
    return "".join(filter(None, front + blocks)) + history_block("".join(history))


def shown_sections(read: "tracker.Ticket", asked: Sequence[Question]) -> list[tuple[str | None, str]]:
    """What an opened ticket reads as, out of the sections the one parser found: whatever stands
    above the first heading, under no heading of its own, since a proposed ticket's line of
    provenance is written there; then each section's own words.

    Two of them are left out, because a ticket says a thing once and the row already says these: the
    H1, which is the row's name, and the brief. A `## Questions` section keeps only what it says
    besides its items, which are the block the questions get to themselves."""
    lines = read.body.splitlines()
    opens = next((n for n, line in enumerate(lines) if line.startswith("## ")), len(lines))
    above = [line for line in lines[:opens] if line.strip() != f"# {read.title}"]
    written = [(None, "\n".join(above))]
    for one in read.sections:
        if one.heading.lower() == "brief":
            continue
        text = one.text
        if one.heading.lower() == "questions":
            tags = tuple(f"- [{q.tag}]" for q in asked)
            text = "\n".join(takewhile(lambda line: not line.startswith(tags), text.splitlines()))
        written.append((one.heading, text))
    return [(heading, text) for heading, text in written if text.strip()]


def block(label: str | None, inner: str) -> str:
    """One block of an opened ticket: what it is, and the ticket's own words under it."""
    words = f'<p class="label">{html.escape(label.lower())}</p>' if label else ""
    return f'<section class="block">{words}{inner}</section>'


# a criterion as markdown writes it, in a tight list (`<li>[ ] ...`) or a loose one (`<li><p>[ ] ...`)
TICKED = re.compile(r"<li>\s*(<p>)?\s*\[([ xX])\]\s*")
MET = {False: ("", "Not met yet."), True: (" met", "Met: whoever built it ticked the box.")}


def prose(heading: str | None, text: str) -> str:
    """A section's own words, rendered. The acceptance criteria become the checklist they are
    written as, so a criterion reads as met or not rather than as a line opening with a bracket."""
    written = render_body(text)
    if heading and heading.lower() == "acceptance criteria":
        return TICKED.sub(ticked, written)
    return written


def ticked(criterion: re.Match) -> str:
    which, words = MET[criterion.group(2) in "xX"]
    return f'<li class="tick{which}" data-tip="{html.escape(words)}">{criterion.group(1) or ""}'


def asked_block(asked: Sequence[Question], said: str, path: Path, status: str) -> str:
    """Every question the ticket asks, the answered ones marked with the ruling that answered them
    and every open one with the button that copies it: the row lists its questions only while it is
    folded, so this block is where an opened ticket's questions are read and copied. `said` is
    whatever else its `## Questions` section says, which is the ticket's own and stands above them."""
    if not asked and not said:
        return ""
    copyable = set(shown_questions(status, asked))
    items = "".join(
        f'<li class="question{" ruled" if q.ruled else ""}">'
        f'<span class="tag" data-tip="{html.escape(TAG_TIP)}">{q.tag}</span><div>'
        f'<p class="head">{inline_md(q.headline)}</p>'
        + (f'<p class="detail">{inline_md(q.detail)}</p>' if q.detail else "")
        + (f'<p class="ruling">Ruled {q.ruled}: {inline_md(q.answer)}</p>' if q.ruled else "")
        + "</div>"
        + (copy_button("qcopy", "copy", QCOPY_TIP, copy_text(path, [q]), f"{q.tag} of {path.name}")
           if q in copyable else "")
        + "</li>"
        for q in asked
    )
    return block("questions", said + (f'<ul class="asked">{items}</ul>' if asked else ""))


RESUME_TIP = "Click to copy the command that resumes this session in the directory it ran in."
WHEN_TIP = "When this session first committed on the ticket, and when it last did."


def sessions_block(worked: Sequence[Session]) -> str:
    """The sessions that worked on the ticket, each with the command that resumes it. The label says
    on this machine because that is the list: a worker on another host is not in it (ticket_sessions),
    and a ticket no session has committed on has no block at all."""
    if not worked:
        return ""
    items = "".join(
        f'<li><span class="stitle">{html.escape(session.title)}</span>'
        f'<span class="when" data-tip="{html.escape(WHEN_TIP)}">{html.escape(worked_on(session))}</span>'
        + copy_button("resume", "copy resume", RESUME_TIP, session.resume, f"the command resuming {session.title}")
        + "</li>"
        for session in worked
    )
    return block("sessions on this machine", f'<ul class="sessions">{items}</ul>')


def worked_on(session: Session) -> str:
    """The days a session committed on the ticket: the one day, or the first and the last."""
    return session.first if session.first == session.last else f"{session.first} → {session.last}"


RUN_TIP = "Click to copy the command that runs this file, to paste at the code repo's root."


def artefacts_block(show: Path, code: Path) -> str:
    """What the ticket produced to look at: every file in its show directory as a link, and each
    one that runs on a button that copies the command running it from the code repo's root."""
    files = artefacts(show)
    if not files:
        return ""
    items = "".join(
        f'<li><a href="file://{html.escape(str(file))}" target="_blank">'
        f'{html.escape(str(file.relative_to(show)))}</a>'
        + (copy_button("runcopy", "copy command", RUN_TIP, shlex.quote(str(file.relative_to(code))),
                       f"the command that runs {file.name}") if runs(file) else "")
        + "</li>"
        for file in files
    )
    return block("artefacts", f'<ul class="artefacts">{items}</ul>')


def artefacts(show: Path) -> list[Path]:
    """Every file in a ticket's show directory, out/ aside, which is where a run writes what it
    regenerates rather than what the directory was kept for."""
    if not show.is_dir():
        return []
    return sorted(p for p in show.rglob("*") if p.is_file() and "out" not in p.relative_to(show).parts)


def runs(file: Path) -> bool:
    """Whether an artefact is one that runs, which is what its executable bit says (/mx:show)."""
    return bool(file.stat().st_mode & stat.S_IXUSR)


def show_dir(path: Path) -> Path:
    """Where a ticket's artefacts are (/mx:show): `agent/show/<slug>/`, beside the tracker the
    ticket was read from."""
    return path.parent.parent / "show" / path.stem


def history_block(comments: str) -> str:
    """The ticket's comments, folded: the conversation on it and a build's closing comment are what
    happened, not what the ticket is, so they open only when the reader asks for them."""
    if not comments.strip():
        return ""
    return ('<details class="history"><summary><span class="label">comments</span></summary>'
            f'{render_body(comments)}</details>')


# ---- graphs ---------------------------------------------------------------


def slug_id(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "_", name)


def node_label(text: str) -> str:
    # a double quote ends mermaid's label string, and the #quot; entity renders literally in an SVG text label
    return text.replace('"', "”")


def node_id(ns: str, slug: str) -> str:
    # ns makes node ids unique per diagram instance: mermaid+elk contaminate across
    # diagrams on one page when two share a node id (DOM lookups hit the first SVG).
    return f"T_{ns}_{slug_id(slug)}"


def drawn(shown: list[Ticket], all_of_them: dict[str, Ticket]) -> tuple[set[str], set[str]]:
    """(drawn, ghost): the live tickets of `shown` plus every done ticket one of them waits on, and
    those done ones, which are drawn as the context they are."""
    live = {t.slug for t in shown if t.status != "done"}
    ghost = {
        ref for slug in live for ref, _ in all_of_them[slug].blocked_by
        if ref in all_of_them and all_of_them[ref].status == "done"
    }
    return live | ghost, ghost


def node_defs(ns: str, tickets: list[Ticket], drawing: set[str], ghost: set[str]) -> list[str]:
    lines = []
    for t in tickets:
        if t.slug in drawing:
            cls = "ghost" if t.slug in ghost else t.status
            lines.append(f'  {node_id(ns, t.slug)}["{STATUS_SYMBOL[t.status]} {node_label(t.title)}"]:::{cls}')
    lines.extend(f'  click {node_id(ns, t.slug)} "#t-{t.slug}"' for t in tickets if t.slug in drawing)
    return lines


def tree_graph(tickets: list[Ticket], tree: str) -> str | None:
    """One tree's dependency graph, edges only: the live tickets of the tree and the done blockers
    they wait on, minus every ticket with no edge. None when nothing in the tree waits on
    anything."""
    by_slug = {t.slug: t for t in tickets}
    inside = [t for t in tickets if t.tree == tree]
    include, ghost = drawn(inside, by_slug)
    edges = [(ref, t.slug) for t in inside if t.slug in include
             for ref, _ in t.blocked_by if ref in include]
    slugs = {slug for edge in edges for slug in edge}
    if not slugs:
        return None
    ns = "f"
    lines = ["flowchart LR", *node_defs(ns, tickets, slugs, ghost & slugs)]
    lines.extend(f"  {node_id(ns, a)} --> {node_id(ns, b)}" for a, b in edges)
    return "\n".join(lines)


def board_graph(tickets: list[Ticket]) -> dict | None:
    """The whole tracker's dependency graph, as the parts the page composes for whichever trees are
    shown: per tree, its nodes with their lines; every edge with the two trees it joins. Edges only,
    as in `tree_graph`; an edge is drawn where both ends are on the board, and a done ticket a live
    one waits on is its dashed context there too. None when nothing waits on anything."""
    ns = "b"
    by_slug = {t.slug: t for t in tickets}
    include, ghost = drawn(tickets, by_slug)
    # the tree a node sits under is named as the pill names it, since the page composes this graph
    # by hiding the trees whose pills are off
    edges = [
        (by_slug[ref].tree or ALONE, node_id(ns, ref), t.tree or ALONE, node_id(ns, t.slug))
        for t in tickets if t.slug in include
        for ref, _ in t.blocked_by if ref in include
    ]
    if not edges:
        return None
    connected = {n for _, a, _, b in edges for n in (a, b)}
    parts: dict = {"trees": [], "edges": [{"a": ta, "from": a, "b": tb, "to": b, "line": f"  {a} --> {b}"}
                                          for ta, a, tb, b in edges]}
    for tree in trees_of(tickets):
        nodes = [
            {"id": node_id(ns, t.slug), "lines": node_defs(ns, [t], {t.slug}, ghost & {t.slug})}
            for t in in_tree(tickets, tree) if node_id(ns, t.slug) in connected
        ]
        if nodes:
            parts["trees"].append({"name": tree, "nodes": nodes})
    return parts


# ---- page -----------------------------------------------------------------

def asks(status: str, needs_user: bool, open_question: bool) -> str:
    """Which of ASKS a row asks of the user, from what its ticket file says: a build in review asks
    for a ruling, a ticket stopped on a question of its own asks for the answer, and a ticket the
    user is in the loop for asks for the session that is the work.

    That session is asked for whether or not a question of the ticket's is written down yet, since
    sitting down together is the work."""
    if status == "review":
        return "review"
    if needs_user:
        return "session"
    if open_question and status != "done":
        return "answer"
    return "build"


def asks_word(t: Ticket) -> str:
    """Which of ASKS a row asks of the user, from the row itself."""
    return asks(t.status, t.needs_user, bool(open_questions(t.questions)))


def asks_tag(t: Ticket) -> str:
    kind = asks_word(t)
    word, meaning = ASKS[kind]
    return f'<span class="asks a-{kind}" data-tip="{html.escape(meaning)}">{word}</span>'


def time_tag(t: Ticket) -> str:
    return f'<span class="time" data-tip="{html.escape(SIZE_TIP)}">{SIZES[t.size][0]}</span>'


def priority_tag(t: Ticket) -> str:
    return f'<span class="pri p{t.priority}" data-tip="{html.escape(PRIORITY_TIP)}">p{t.priority} {PRIORITY[t.priority][0]}</span>'


def sort_key(t: Ticket) -> tuple:
    """A row's place within its group: the priority first, then the user's time, then the name."""
    return (t.priority, SIZE_RANK[t.size], t.title.lower())


def dep_chips(refs: list[tuple[str, str]]) -> str:
    return "".join(blocker_chip(ref, status, ref_anchor(ref)) for ref, status in refs)


def blocker_chip(ref: str, status: str, href: str) -> str:
    done = "done" if status == "done" else "not done yet"
    return (f'<a class="chip {status}" href="{html.escape(href)}" onclick="event.stopPropagation()" '
            f'data-tip="Waits on {html.escape(ref)}, {done}.">{html.escape(ref)}</a>')


def review_link(address: str | None) -> str:
    if not address:
        return ""
    return (f'<a class="rp" href="{html.escape(address)}" target="_blank" onclick="event.stopPropagation()" '
            f'data-tip="This build&#39;s review page: the diff, with a place to write on it (d).">review page</a>')


def gh_links(refs: Sequence[str], gh: dict[str, str]) -> str:
    """The pull requests and issues a ticket names, each in the look of the state GitHub gave it and
    saying that state in words on hover.

    A reference GitHub was not asked about is the bare link it was before, and the page says why
    once (absences). One it was asked about and did not answer for is bare too, and says nothing
    further: the board asked and was answered, so there is no absence to report."""
    # the issues URL serves a pull request too: GitHub redirects it to the pull page
    return "".join(
        f'<a class="gh {state or "unknown"}" href="https://github.com/{repo}/issues/{num}" target="_blank" '
        f'onclick="event.stopPropagation()" data-tip="{html.escape(github.SAYS.get(state, UNKNOWN_REF))}">{html.escape(ref)}</a>'
        for ref in refs for repo, num in [ref.split("#")] for state in [gh.get(ref)]
    )


UNKNOWN_REF = "A pull request or issue this ticket names, on GitHub."


def search_text(*parts: str) -> str:
    return html.escape(re.sub(r"\s+", " ", " ".join(re.sub(r"<[^>]+>", " ", p) for p in parts)).strip().lower(), quote=True)


def row_open(t: Ticket, search: str) -> str:
    """The element every row is: what the page's script matches a row on, and the file a click on
    its slug copies."""
    return (
        f'<details class="ticket row-{t.status}" id="t-{t.slug}" data-tree="{html.escape(t.tree or ALONE)}" '
        f'data-slug="{html.escape(t.slug)}" data-search="{search}" data-path="{html.escape(str(t.path))}"><summary>'
    )


def clipped(text: str) -> str:
    """A mark's words, cut off with an ellipsis where its column is too narrow. The clipping sits on
    this inner element, since a box that hides its overflow would hide its own hover words too."""
    return clipped_html(html.escape(text))


def clipped_html(markup: str) -> str:
    """The same, for words already rendered: a question's headline carries code and emphasis."""
    return f'<span class="clip">{markup}</span>'


def open_questions(asked: Sequence[Question]) -> list[Question]:
    """The questions no `Ruled` line answers."""
    return [q for q in asked if not q.ruled]


def group_of(t: Ticket) -> str:
    """Which group a row sits in: the needs-me group where the ticket waits on the user, its status
    otherwise. A row is in one group, so needs me takes a ticket out of its status group."""
    return "needs" if needs_me(t.status, t.needs_user, t.priority, bool(open_questions(t.questions))) else t.status


def shown_questions(status: str, asked: Sequence[Question]) -> list[Question]:
    """The open questions a ticket shows, which is what any button on it copies, on the row and in
    the block an opened row reads as.

    A done ticket shows none: a question still open when the user rules on the build is filed as a
    proposed ticket then (the spec's Decisions), so one left on a done ticket is a leftover."""
    return [] if status == "done" else open_questions(asked)


def questions_block(t: Ticket) -> str:
    """The open questions under a folded needs-me row: each one's tag and headline with a button
    that copies it, and one that copies the ticket's own once there are two to copy.

    The page's style hides the list while the row is open, where the block below carries the same
    questions with their detail, so an opened row shows each of them once."""
    asked = shown_questions(t.status, t.questions)
    if not asked:
        return ""
    lines = "".join(
        f'<span class="q"><span class="qtag" data-tip="{html.escape(TAG_TIP)}">{q.tag}</span>'
        f'<span class="qhead" data-tip="{html.escape(question_tip(q))}">{clipped_html(inline_md(q.headline))}</span>'
        + copy_button("qcopy", "copy", QCOPY_TIP, copy_text(t.path, [q]), f"{q.tag} of {t.path.name}")
        + "</span>"
        for q in asked
    )
    if len(asked) < 2:  # one question's own button already copies the ticket's whole list
        return f'<span class="qs">{lines}</span>'
    return f'<span class="qs">{lines}' + copy_button(
        "qall", f"copy all {len(asked)}",
        "Click to copy every open question on this ticket, under the path of the file they are on.",
        copy_text(t.path, asked), f"{len(asked)} questions of {t.path.name}",
    ) + "</span>"


def group_copy(rows: Sequence[Ticket]) -> str:
    """The needs-me group's own copy button: every open question on the board at once, for pasting
    into an editor. Empty for a group whose rows ask nothing, which is every other group."""
    asked = [(t.path, shown_questions(t.status, t.questions)) for t in rows]
    asked = [(path, questions) for path, questions in asked if questions]
    if not asked:
        return ""
    count = sum(len(questions) for _, questions in asked)
    return copy_button(
        "qgroup", f"copy all {count} question{'s' if count != 1 else ''}",
        "Click to copy every open question on the board, each under the path of the ticket it is on.",
        "\n\n".join(copy_text(path, questions) for path, questions in asked),
        f"{count} question{'s' if count != 1 else ''}",
    )


def copy_text(path: Path, asked: Sequence[Question]) -> str:
    """What a copy button puts on the clipboard: the questions, each rewritten as one line of the
    markdown the ticket holds, under the path of the file they are on, so the session taking the
    answer knows where to record it."""
    written = (f"- [{q.tag}] **{q.headline}**" + (f" {q.detail}" if q.detail else "") for q in asked)
    return "\n".join([str(path), *written])


QCOPY_TIP = "Click to copy this question under the path of its ticket, to answer in any session."

TAG_TIP = (
    "The ticket's own numbering for this question.\n"
    "A session that takes your answer records it under this tag as a `Ruled <date>:` line, which is "
    "what clears the question from the board."
)


def question_tip(q: Question) -> str:
    """A question's own words, since the row shows a headline its column may have to cut short."""
    return f"{q.headline}\n\n{q.detail}" if q.detail else q.headline


COPY_CAP = 220  # how much of what it copies a button shows before the rest is an ellipsis


def copy_button(variant: str, word: str, what: str, text: str, said: str) -> str:
    """A button that copies `text` and says so: what it copies is its hover words, cut off where
    they run long, and `said` is what the page's own note says once it has. It is a span, as the
    row's number is, since the page handles the click itself."""
    shown = text if len(text) <= COPY_CAP else text[:COPY_CAP].rstrip() + "\u2026"
    return (f'<span class="copier {variant}" data-copy="{html.escape(text)}" data-copied="{html.escape(said)}" '
            f'data-tip="{html.escape(what)}\n\n{html.escape(shown)}">{html.escape(word)}</span>')


TREE_TIP = "The top-level ticket this one's work is part of. Its pill in the top bar hides and shows the tree's rows."


def row(t: Ticket, gh: dict[str, str]) -> str:
    """One ticket row, every mark in a fixed column: the tree the ticket is part of, its slug (a
    click copies the file's path), what the row asks of the user, the name with its review page and
    GitHub references, the ticket brief under the name and, while the row is folded, the open
    questions the ticket asks the user under that, the user's time, the priority, the blockers.
    Below a width the time, the priority and the blockers move under the name. The ticket's
    remaining text folds under the row."""
    brief = f'<span class="brief">{t.brief}</span>' if t.brief else ""
    return (
        row_open(t, search_text(t.slug, t.title, t.brief, t.body_html, *t.gh))
        + f'<span class="tree" data-tip="{html.escape(TREE_TIP)}">{clipped(t.tree)}</span>'
        f'<span class="slug" data-tip="Click to copy the path of the file this row was read from (y):\n{html.escape(str(t.path))}">{clipped(t.slug)}</span>'
        f'{asks_tag(t)}'
        f'<span class="main"><span class="titleline"><span class="title" data-tip="{html.escape(t.title)}">{clipped(t.title)}</span>'
        f'{review_link(t.diffview)}{gh_links(t.gh, gh)}</span>{brief}{questions_block(t)}</span>'
        f'<span class="meta">{time_tag(t)}{priority_tag(t)}<span class="chips">{dep_chips(t.blocked_by)}</span></span>'
        f'</summary><div class="body">{t.body_html}</div></details>'
    )


def tree_chip(tree: str, tickets: list[Ticket]) -> str:
    """A tree's pill in the top bar: its counts, and the click that hides and shows its rows.

    The done count is out of every ticket in the tree, proposed ones included, so a breakdown just
    cut off a parent ticket reads 0/4."""
    inside = in_tree(tickets, tree)
    counts = Counter(t.status for t in inside)
    bits = [f"{counts['done']}/{len(inside)} done"]
    bits += [f"{counts[s]} {s}" for s in ("open", "claimed", "review", "blocked", "proposed") if counts[s]]
    # the dot says the tree holds work of the user's own; the counts above already say how much
    dot = '<i class="dot"></i>' if any(group_of(t) == "needs" for t in inside) else ""
    return (
        f'<button class="treechip" data-tree="{html.escape(tree)}" title="{html.escape(" · ".join(bits))}">{dot}{html.escape(tree)} '
        f'<span class="dim">{counts["done"]}/{len(inside)}</span></button>'
    )


def trees_of(tickets: list[Ticket]) -> list[str]:
    """Every tree the board shows, in the one order the pills, the graphs and the briefing state all
    take: the named trees, then the lone tickets' pill."""
    named = sorted({t.tree for t in tickets if t.tree})
    return named + ([ALONE] if any(not t.tree for t in tickets) else [])


def in_tree(tickets: list[Ticket], tree: str) -> list[Ticket]:
    """The tickets one of `trees_of`'s trees holds."""
    return [t for t in tickets if (t.tree or ALONE) == tree]


def render_page(
    project: str, tickets: list[Ticket],
    log: str, stamp: str, stamp_src: str, gh: github.Answer = github.NOTHING,
    said: "briefing.Briefing | None" = None,
) -> str:
    rows: dict[str, list[str]] = {state: [] for state, _ in GROUPS}
    ranked: dict[str, list[tuple[tuple, str, Ticket]]] = {state: [] for state, _ in GROUPS}
    for t in tickets:
        ranked[group_of(t)].append((sort_key(t), row(t, gh.states), t))
    ranked = {state: sorted(sortable, key=lambda ranks: ranks[0]) for state, sortable in ranked.items()}
    for state, sortable in ranked.items():
        rows[state].extend(row for _, row, _ in sortable)
    grouped = {state: [t for _, _, t in sortable] for state, sortable in ranked.items() if sortable}
    groups = "".join(
        f'<details class="grp" id="grp-{state}" data-state="{state}"{"" if state == "done" else " open"}>'
        f'<summary><h2>{label} <span class="n">{len(rows[state])}</span>{group_copy(grouped.get(state, []))}</h2></summary>'
        f'<div class="tickets">{"".join(rows[state])}</div></details>'
        for state, label in GROUPS if rows[state]
    )

    trees = trees_of(tickets)
    chips = "".join(tree_chip(tree, tickets) for tree in trees)

    graphs = ""
    for tree in trees:
        src = tree_graph(tickets, "" if tree == ALONE else tree)
        inner = f'<pre class="mermaid" data-key="g:{tree}">{src}</pre>' if src else f'<div class="gnote">nothing in {html.escape(tree)} waits on anything</div>'
        graphs += f'<div class="g" data-tree="{html.escape(tree)}" hidden>{inner}</div>'
    board = board_graph(tickets)
    graphs += '<div class="g" data-tree="*" hidden>' + (
        f'<pre class="mermaid" data-key="g:*"></pre><div class="gnote" hidden>every ticket with an edge is in a hidden tree</div>'
        f'<script type="application/json" class="parts">{json.dumps(board).replace("</", "<\\/")}</script>'
        if board else '<div class="gnote">nothing waits on anything</div>'
    ) + "</div>"

    log_html = "\n".join(
        f'<span class="hash">{html.escape(line.split(" ")[0])}</span> {html.escape(line.partition(" ")[2])}'
        for line in log.strip().splitlines()
    )
    named = [tree for tree in trees if tree != ALONE]
    footmeta = f"{len(tickets)} tickets · {len(named)} parent ticket{'' if len(named) == 1 else 's'} · rendered {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · refreshes on change"
    return PAGE.substitute(
        overlay=OVERLAY, graphwin=json.dumps(GRAPH_WINDOW).replace("</", "<\\/"), viewjs=VIEW_JS,
        project=html.escape(project), chips=chips, groups=groups, graphs=graphs, log=log_html,
        columns=row_columns(tickets, grouped),
        absences="".join(absences(tickets, gh, said)),
        briefing=briefing_block(said, tickets),
        footmeta=footmeta, stamp=stamp, stamp_src=html.escape(stamp_src),
    )


def briefing_block(said: "briefing.Briefing | None", tickets: list[Ticket]) -> str:
    """The head of the side column: where things stand and what to take up next, as the briefing
    session wrote it and when, or the board's own count where no session has written one."""
    when, text, tip = (
        # the row shows the day and the hour; the words behind it carry the year, which is what a
        # briefing nobody has replaced in months is read by
        (f"written {said.written:%d %b %H:%M}", said.text, f"Written {said.written:%Y-%m-%d %H:%M}.\n{BRIEFING_TIP}")
        if said else ("the board's own", fallback(tickets), FALLBACK_TIP)
    )
    return (
        f'<div class="bhead"><span class="label">briefing</span>'
        f'<span class="bwhen" title="{html.escape(tip)}">{html.escape(when)}</span></div>'
        f'<div class="btext">{markdown.markdown(text)}</div>'
    )


# How many characters of a tracker's own slugs a column shows before the rest is cut with an
# ellipsis (a tree, a row's own slug) or wraps to a second line (a blocker reference), so a long
# slug costs the row no more than the width those columns were fixed at.
NAME_CAP = 14
REF_CAP = 14


def row_columns(tickets: list[Ticket], grouped: dict[str, list[Ticket]]) -> str:
    """The width of each of a row's fixed columns, as the CSS tokens the row's grid reads.

    A column is as wide as the widest mark that can land in it and no wider, so the name and the
    brief take every pixel the row has spare. The widths come from the marks themselves: the closed
    vocabularies for what a row asks, the user's time and the priority, and the tracker's own names
    and references for the tree, the slug and the blockers. Their marks are all set in the one
    monospace, so a column's width is a count of characters (`--mark-char`), capped where a
    tracker's own names could run away.

    The tree, the slug and what the row asks are measured over the whole board, so those columns
    run straight down every row of it. The time, the priority and the blockers are measured
    over each group, since a group of quick unblocked tickets has no use for the width an XL one
    needs: a column still runs down the group the eye is reading, and the rest is the brief's."""
    page = {
        "tree": min(max([len(t.tree) for t in tickets], default=0), NAME_CAP),
        "slug": min(max([len(t.slug) for t in tickets], default=0), NAME_CAP),
        "asks": max(len(word) for word, _ in ASKS.values()),
        "time": max(len(word) for word, _ in SIZES.values()),
        "pri": max(len(f"p{level} {word}") for level, (word, _) in PRIORITY.items()),
        "chips": min(max([len(ref) for ref in blocker_refs(tickets)], default=2), REF_CAP),
    }
    css = column_tokens(":root", page)
    for state, rows in grouped.items():
        own = {
            "time": max([len(SIZES[r.size][0]) for r in rows], default=0),
            "pri": max([len(f"p{r.priority} {PRIORITY[r.priority][0]}") for r in rows], default=0),
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


def blockers_of(t: Ticket) -> list[str]:
    """The blockers one row shows, as the reader sees them written."""
    return [ref for ref, _ in t.blocked_by]


def blocker_refs(tickets: list[Ticket]) -> list[str]:
    """Every blocker the board shows."""
    return [ref for t in tickets for ref in blockers_of(t)]


def gh_shown(tickets: list[Ticket]) -> list[str]:
    """Every pull request and issue the board links, the whole of one render's question for GitHub."""
    return [ref for t in tickets for ref in t.gh]


def absences(
    tickets: list[Ticket], gh: github.Answer, standing: "briefing.Briefing | None" = None,
) -> list[str]:
    """What this render did without, said once each (the board renders with any optional source
    missing). A review page linked as a file is one nothing answered for; a tracker with no page
    rendered yet has no server to miss, so it says nothing. A machine with no transcripts directory
    has run no session this board could name, whatever the commits say. GitHub says its own absence
    in its own words, since what stopped the query is what the user has to fix (github.ask). A
    briefing already written is no absence whatever the machine has now: the column is not empty,
    and what it says of itself is when it was written.

    The model says its own absence in its own words too: a machine with no claude and a login that
    has lapsed are the same empty column and two different things to fix (briefing.missing)."""
    said = []
    pages = [t.diffview for t in tickets]
    if any(page and page.startswith("file://") for page in pages):
        said.append(absence_note(
            "review-page-server",
            "Nothing is serving the review pages, so they open as files and what you write on one is not saved.",
        ))
    if not TRANSCRIPTS.is_dir():
        said.append(absence_note(
            "transcripts",
            f"No session transcripts at {TRANSCRIPTS}, so no ticket lists the sessions that worked on it.",
        ))
    if gh.missing:
        said.append(absence_note("github", gh.missing))
    if standing is None and (why := briefing.missing()):
        said.append(absence_note("model", why))
    return said


# The full size graph, as the overlay over the board and the window of its own both wear it: one
# head with the tree/whole-tracker switch and whatever that view adds, over one box holding
# either a note or the drawing. Two views of one thing, so one markup and one script for both.
GRAPH_VIEW = Template(
    '<div class="gfhead"><span class="label">dependencies</span><span class="gname"></span>'
    '<span class="seg"><button class="btn" data-gmode="tree" title="${tree_says}">tree</button>'
    '<button class="btn" data-gmode="all" title="${all_says}">all</button></span>${extra}</div>'
    '<div class="gfbody"><div class="gnote" hidden></div><div class="gsvg"></div></div>'
)
OVERLAY = GRAPH_VIEW.substitute(
    tree_says="the graph of the row's top-level ticket (a)", all_says="the whole tracker's graph (a)",
    extra='<button class="btn" id="gwinfull" title="the same graph in a window of its own, beside the board (w)">window</button>'
          '<button class="btn" id="gclose" title="back to the board (Esc)">close</button>',
)
# the window has no keys of its own, so its switch says what it does without naming one
GRAPH_WINDOW = GRAPH_VIEW.substitute(
    tree_says="the graph of the row the board is on", all_says="the whole tracker's graph",
    extra='<span class="gorphan">the board this followed is gone</span>',
)

# What the two views do, run in the board's page and again in the window's: the window is another
# document, and once the board has reloaded once it is another origin too, so nothing it calls can
# live in the board's script. One home here, two realms at run time.
VIEW_JS = r"""
  const hrefOf = (a) => a && (a.getAttribute("href") ?? a.getAttribute("xlink:href"));

  function markCur(root, id) {
    for (const n of root.querySelectorAll("g.node.cur")) n.classList.remove("cur");
    if (id) root.querySelector('g.node[id*="-' + id + '-"]')?.classList.add("cur");
  }

  // A graph at full size is wider than the box it sits in, so the box is dragged as well as
  // scrolled. The click a drag ends with is swallowed wherever it lands, or a pan that finished
  // over a node would open that node, and one that finished on the overlay's backdrop would close
  // the overlay.
  function pannable(el) {
    const doc = el.ownerDocument;
    let from = null, swallow = false;
    el.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      from = { x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop, moved: 0 };
      e.preventDefault();  // no text or node selection under the drag
    });
    doc.addEventListener("mousemove", (e) => {
      if (!from) return;
      from.moved = Math.max(from.moved, Math.abs(e.clientX - from.x) + Math.abs(e.clientY - from.y));
      el.classList.toggle("panning", from.moved > 4);
      el.scrollLeft = from.left - (e.clientX - from.x);
      el.scrollTop = from.top - (e.clientY - from.y);
    });
    doc.addEventListener("mouseup", () => {
      if (!from) return;
      swallow = from.moved > 4;
      el.classList.remove("panning");
      from = null;
    });
    doc.addEventListener("click", (e) => {
      if (!swallow) return;
      swallow = false;
      e.preventDefault();
      e.stopPropagation();
    }, true);
  }

  // A node at full size takes the board to its row: the overlay closes on it, the window of its own
  // stays where it is and the board moves behind it.
  function nodeClicks(el, go) {
    el.addEventListener("click", (e) => {
      const href = hrefOf(e.target.closest("a"));
      if (href?.startsWith("#")) { e.preventDefault(); go(href); }
    });
  }
  function attach(el, go) { pannable(el); nodeClicks(el, go); }

  // One paint for both views. A view whose key has not moved keeps its drawing, and with it
  // whatever the reader had panned to; only the mark on the cursor's node moves.
  function paintView(root, view, last) {
    const name = root.querySelector(".gname");
    name.title = name.textContent = view.name;
    for (const b of root.querySelectorAll("[data-gmode]")) b.classList.toggle("on", b.dataset.gmode === view.mode);
    const body = root.querySelector(".gfbody"), svg = body.querySelector(".gsvg");
    if (view.key !== last) {
      const note = body.querySelector(".gnote");
      note.textContent = view.note;
      note.hidden = !!view.svg;
      svg.innerHTML = view.svg;
      body.scrollTo(0, 0);
    }
    markCur(svg, view.cur);
    return view.key;
  }
"""


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
     first, a question's tag takes the same rose as the answer it waits for, and the user's time
     has the last to itself. The teal is picked again from the
     prototype's, away from the moss accent, which it read as by day. Each day value clears 4.6:1
     against its own 12% tint, since that is the background the tag's text sits on. */
  :root {
    --c-pink: light-dark(#7d4172, #d9a2d0);
    --c-gold: light-dark(#725614, #d9b36f);
    --c-rose: light-dark(#963f37, #fabeb4);
    --c-purple: light-dark(#6546b3, #b8a4ff);
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
  .tree, .slug, .asks, .pri, .time, .chip, .rp, .gh, .label, .n, .treechip, .search,
    .btn, .gname, .log, .footmeta, kbd { font-family: var(--font-mono); }

  /* ---- the top bar: the project, the tree pills, the filter, the graph mode, the scheme ---- */
  .top { position: sticky; top: 0; z-index: 10; display: flex; gap: 1rem; align-items: center; min-height: 52px;
    padding: .4rem 1.25rem; background: var(--ground); border-bottom: 1px solid var(--edge); }
  .top .name { font-weight: 600; color: var(--strong); white-space: nowrap; }
  .top .name span { color: var(--muted); font-weight: 400; }
  .treenav { display: flex; gap: .4rem; overflow-x: auto; flex: 1; min-width: 0; scrollbar-width: none; }
  .treechip { padding: .1rem .7rem; border: 1px solid var(--edge); border-radius: 999px; background: var(--ground-2);
    font-size: .8rem; color: var(--muted); cursor: pointer; white-space: nowrap; display: inline-flex; gap: .4em;
    align-items: center; transition: color 150ms, border-color 150ms; }
  .treechip:hover { color: var(--accent); border-color: var(--accent); }
  .treechip.off { opacity: .5; text-decoration: line-through; }
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
  /* the briefing, at the head of the column: prose, so it is set as the page's prose is */
  .briefing { margin-bottom: 1.1rem; }
  .bhead { display: flex; gap: .5rem; align-items: baseline; justify-content: space-between; margin-bottom: .3rem; }
  .bwhen { color: var(--muted); font-size: .8rem; font-family: var(--font-mono); }
  .btext { font-size: .92rem; line-height: 1.55; }
  .btext > :first-child { margin-top: 0; }
  .btext > :last-child { margin-bottom: 0; }
  .btext h1, .btext h2 { font-size: .82rem; color: var(--muted); font-family: var(--font-mono); font-weight: 400;
    margin: .9rem 0 .35rem; text-transform: lowercase; }
  .btext h1::after, .btext h2::after { content: none; }  /* the rule an h2 carries over a group of rows is for a group of rows */
  .btext ul, .btext ol { margin: .2rem 0; padding-left: 1.1rem; }
  .btext li { margin-top: .3rem; }
  .btext strong { color: var(--strong); font-weight: 600; }

  .ghead { display: flex; gap: .5rem; align-items: baseline; margin-bottom: .3rem; }
  .gname { color: var(--muted); font-size: .8rem; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .gnote { color: var(--muted); font-size: .92rem; padding: .4rem 0; }
  .mermaid { margin: 0; display: flex; justify-content: center; }
  /* out of the layout, not merely invisible: a graph source is one unwrappable line, and a render
     that has not come back yet would widen the column it sits in */
  .mermaid:not(:has(svg)) { display: none; }
  .mermaid svg { max-width: 100%; height: auto; }
  .side g.node.cur rect, .side g.node.cur polygon,
    .gfbody g.node.cur rect, .gfbody g.node.cur polygon { stroke-width: 2.5px !important; }

  /* ---- the same graph at full size: over the board, or in a window of its own ---- */
  .side .gbody { cursor: zoom-in; }  /* the preview opens the full size view */
  .side .gbody a { cursor: pointer; }
  #gfull { position: fixed; inset: 0; z-index: 90; display: none; padding: 1.25rem;
    background: color-mix(in srgb, var(--strong) 40%, transparent); }
  #gfull.open { display: block; }
  #gfull .card { height: 100%; display: flex; flex-direction: column; overflow: hidden;
    background: var(--ground); border: 1px solid var(--edge); border-radius: var(--radius); }
  .gfhead { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap;
    padding: .45rem .8rem; border-bottom: 1px solid var(--edge); }
  /* safe centring: a graph that fits sits in the middle of the box, one that does not starts at
     the edge the scroll starts from rather than having its first node cut off */
  .gfbody { flex: 1; min-width: 0; min-height: 0; overflow: auto; padding: 1rem;
    display: flex; justify-content: safe center; align-items: safe center; }
  .gfbody.panning { cursor: grabbing; user-select: none; }
  /* full size is the graph's own size: what shrinks it in the preview is the width it is given */
  .gfbody svg { max-width: none !important; }
  /* the window of its own is the same head and body, with nothing else in the document */
  body.gwin { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
  .gorphan { display: none; color: var(--accent-2); font-size: .8rem; font-family: var(--font-mono); }
  [data-orphan="1"] .gorphan { display: inline; }

  /* ---- a group of rows ---- */
  .grp { margin-bottom: 1.75rem; }
  .grp > summary { list-style: none; cursor: pointer; padding: .3rem 0 .6rem; position: relative; }
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
    grid-template-columns: var(--col-tree) var(--col-slug) var(--col-asks) minmax(0, 1fr) var(--col-time) var(--col-pri) var(--col-chips);
    grid-template-areas: "tree slug asks main time pri chips"; }
  .ticket > summary::-webkit-details-marker { display: none; }
  .ticket > summary:hover { background: var(--wash-ink); }
  .ticket.kcur > summary, .ticket.flash > summary { background: var(--wash); }
  .tree { grid-area: tree; font-size: .78rem; color: var(--muted); min-width: 0; }
  /* a box that hides its overflow hides its own tooltip with it, so the ellipsis sits one level in */
  .clip { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .slug { grid-area: slug; font-size: .78rem; color: var(--muted); cursor: copy; min-width: 0; }
  .slug:hover { color: var(--accent); }
  .main { grid-area: main; display: grid; gap: .1rem; min-width: 0; }
  /* the name is what a row is read by, so it keeps its words: the links wrap under it rather than
     taking the width off it */
  .titleline { display: flex; flex-wrap: wrap; gap: 0 .6rem; align-items: baseline; min-width: 0; }
  .title { color: var(--strong); min-width: 0; }
  .row-done .title, .row-blocked .title, .row-proposed .title { color: var(--muted); }
  .titleline > a { flex: none; }
  .brief { color: var(--muted); font-size: .88rem; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ticket[open] .brief { white-space: normal; }
  /* a needs-me row's open questions, under the name they belong to; an opened row reads them in
     its questions block instead */
  .qs { display: grid; gap: .15rem; justify-items: start; padding: .2rem 0 .1rem; min-width: 0; }
  .ticket[open] .qs { display: none; }
  .q { display: flex; gap: .5rem; align-items: baseline; max-width: 100%; min-width: 0; }
  .qtag, .asked .tag { flex: none; font-family: var(--font-mono); font-size: .74rem; color: var(--c-rose); }
  .qhead { color: var(--body); font-size: .88rem; min-width: 0; }
  .copier { flex: none; font-family: var(--font-mono); font-size: .72rem; color: var(--muted);
    border: 1px solid var(--edge); border-radius: 4px; padding: 0 .35rem; cursor: copy; overflow: visible; }
  .copier:hover { color: var(--accent); border-color: var(--accent); }
  .meta { display: contents; }
  .asks, .pri, .time, .rp, .gh { font-size: .78rem; white-space: nowrap; }
  .chip { font-size: .78rem; }
  .asks { grid-area: asks; --c: var(--muted); color: var(--c); justify-self: start; max-width: 100%;
    background: color-mix(in srgb, var(--c) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 38%, transparent); border-radius: 4px; padding: 0 .4rem; }
  .a-review { --c: var(--c-gold); }
  .a-answer { --c: var(--c-rose); }
  .a-session { --c: var(--c-purple); }
  .a-build { background: none; border-color: transparent; padding-left: 0; }
  .time { grid-area: time; color: var(--c-time); justify-self: end; font-variant-numeric: tabular-nums; }
  /* the priority is a ramp, not a set of categories: one hue, strongest at p1 */
  .pri { grid-area: pri; color: var(--c-pink); justify-self: start; padding: 0 .45rem; border-radius: 999px;
    background: color-mix(in srgb, var(--c-pink) 16%, transparent); }
  .pri.p3 { background: color-mix(in srgb, var(--c-pink) 8%, transparent); }
  .pri.p4, .pri.p5 { color: var(--muted); background: none; padding-left: 0; }
  /* the blockers' column is as fixed as the rest, so a long reference wraps within
     it rather than widening it and pulling the time and the priority out of line */
  .chips { grid-area: chips; display: flex; gap: .35rem; justify-content: flex-end; flex-wrap: wrap; }
  .chip { color: var(--body); overflow-wrap: anywhere; }
  .chip.done { color: var(--muted); text-decoration: line-through; }
  .rp { color: var(--accent); }
  .rp:hover { text-decoration: underline; text-underline-offset: 3px; }
  /* a GitHub reference in the look of its state; github.SAYS says the same in words on hover.
     Open work takes the accent, a review asking for changes the rose a question wears, a merge the
     callout purple, as GitHub marks a merge. Anything closed is struck through and a draft
     underlined. A reference GitHub was not asked about keeps the muted link it has always been. */
  .gh { color: var(--muted); }
  .gh.pr-open, .gh.issue-open { color: var(--accent); }
  .gh.pr-changes { color: var(--c-rose); }
  .gh.pr-merged { color: var(--c-purple); }
  .gh.pr-draft { text-decoration: underline dotted; text-underline-offset: 3px; }
  .gh.pr-closed, .gh.issue-closed { text-decoration: line-through; }

  /* below this width the time, the priority and the blockers move under the name, and the top
     bar's pills take a line of their own rather than scrolling out of sight */
  @media (max-width: 1000px) {
    .top { flex-wrap: wrap; padding: .4rem .75rem; }
    .treenav { flex-basis: 100%; order: 1; }
    main { padding: 1rem .75rem 5rem; }
    .absences { padding: .6rem .75rem 0; }
    .ticket > summary { grid-template-columns: var(--col-tree) var(--col-slug) var(--col-asks) minmax(0, 1fr);
      grid-template-areas: "tree slug asks main" ".    .    .    meta"; }
    .meta { grid-area: meta; display: flex; gap: .9rem; align-items: baseline; flex-wrap: wrap; }
    .time, .pri, .chips { grid-area: auto; justify-self: auto; }
  }
  /* narrower still: the name takes the row's width, with its marks over it and under it */
  @media (max-width: 620px) {
    .ticket > summary { grid-template-columns: minmax(0, var(--col-tree)) var(--col-slug) minmax(0, 1fr);
      grid-template-areas: "tree slug asks" "main main main" "meta meta meta"; }
    .search { flex: 1; width: auto; }
  }

  /* ---- a row, opened ---- */
  .body { padding: .4rem .5rem 1.4rem 1rem; margin-left: .5rem; border-left: 1px solid var(--edge);
    max-width: 46rem; color: var(--body); font-size: .96rem; }
  .body > * + * { margin-top: .8em; }
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
  /* the blocks an opened ticket reads as, each under the word for what it is. The ticket's own
     prose keeps the body's spacing; the word above it sits closer, as a label does */
  .block > * + *, .history > * + * { margin-top: .8em; }
  .block > .label + *, .history > summary + * { margin-top: .35rem; }
  .body .asked, .body .artefacts, .body .sessions { list-style: none; padding: 0; display: grid; gap: .45rem; }
  /* a line of a block is its own containing block, so a mark's words are laid out from that line
     rather than from the whole block */
  .asked > li, .artefacts > li, .sessions > li { display: flex; gap: .6rem; align-items: baseline; position: relative; }
  .asked .head { color: var(--strong); }
  .asked > li > div > * + * { margin-top: .2rem; }
  /* the button that copies the question sits at the end of its line, clear of the words */
  .asked > li > .copier { margin-left: auto; }
  /* a question the user has answered is history: its words stay, the colours that call for one go */
  .asked .ruled > .tag, .asked .ruled .head { color: var(--muted); }
  .artefacts a { overflow-wrap: anywhere; font-size: .82rem; }
  /* the button that copies the command sits at the end of its line, clear of the name */
  .artefacts > li > .copier { margin-left: auto; }
  /* a session is its name and the days it worked, the command that resumes it on the button */
  .sessions .stitle { color: var(--strong); }
  .sessions .when { flex: none; font-family: var(--font-mono); font-size: .74rem; color: var(--muted); }
  /* a criterion's mark is the glyph its list item carries instead of a bullet */
  .body li.tick { list-style: none; position: relative; }
  .body li.tick::before { content: "○"; display: inline-block; width: 1.2em; margin-left: -1.2em;
    color: var(--muted); font-size: .85em; }
  .body li.tick.met::before { content: "✓"; color: var(--accent); }
  .history > summary { list-style: none; cursor: pointer; }
  .history > summary::-webkit-details-marker { display: none; }
  .history > summary > .label::before { content: "▸"; margin-right: .4rem; }
  .history[open] > summary > .label::before { content: "▾"; }

  /* ---- a mark says in words what it means ---- */
  /* The words appear under the row, at its left edge: the row is the box that is always on screen
     and never hides its overflow, so they cannot be clipped by the mark they belong to or run off
     a narrow window, wherever in the row that mark sits. A group's header is the same box for the
     one mark that sits on it, the button that copies every question in the group. */
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
  <nav class="treenav" id="treenav">${chips}</nav>
  <input class="search" id="search" type="search" placeholder="filter  /" autocomplete="off">
  <span class="seg" id="modes"><button class="btn" data-gmode="tree" title="the graph of the row's top-level ticket (a)">tree</button><button class="btn" data-gmode="all" title="the whole tracker's graph (a)">all</button></span>
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
  <div class="briefing" id="briefing">${briefing}</div>
  <div class="ghead"><span class="label">dependencies</span><span class="gname" id="gname"></span>
    <button class="btn" id="gopen" title="the graph at full size, over the board (f)">full</button>
    <button class="btn" id="gwinopen" title="the graph at full size, in a window of its own beside the board (w)">window</button>
    <button class="btn" id="sidefold" title="fold the graph (b)">fold</button></div>
  <div class="gbody" id="gbody" title="a preview: a click anywhere but a node opens the graph at full size, over the board">
    <div class="g" data-tree=""><div class="gnote">open a row or move onto one (j / k)</div></div>
    ${graphs}
  </div>
</aside>
</main>

<div id="gfull"><div class="card">${overlay}</div></div>

<div id="help"><div class="card"><table>
<tr><td><kbd>j</kbd> <kbd>k</kbd></td><td>next / previous row (the graph follows)</td></tr>
<tr><td><kbd>J</kbd> <kbd>K</kbd></td><td>next / previous group</td></tr>
<tr><td><kbd>gg</kbd> <kbd>G</kbd></td><td>top / bottom</td></tr>
<tr><td><kbd>x</kbd> <kbd>o</kbd> <kbd>Enter</kbd></td><td>open / close the row</td></tr>
<tr><td><kbd>X</kbd> <kbd>O</kbd></td><td>close / open every group</td></tr>
<tr><td><kbd>z</kbd></td><td>fold / unfold the row's group</td></tr>
<tr><td><kbd>d</kbd></td><td>open the row's review page</td></tr>
<tr><td><kbd>y</kbd></td><td>copy the path of the row's file; a click on its number does too</td></tr>
<tr><td><kbd>a</kbd></td><td>graph: the row's top-level ticket / the whole tracker</td></tr>
<tr><td><kbd>b</kbd></td><td>fold / unfold the graph</td></tr>
<tr><td><kbd>f</kbd></td><td>the graph at full size over the board; a click on a node goes to its row</td></tr>
<tr><td><kbd>w</kbd></td><td>the graph at full size in a window of its own, beside the board</td></tr>
<tr><td><kbd>t</kbd></td><td>the other colour scheme</td></tr>
<tr><td><kbd>1</kbd>…<kbd>9</kbd> <kbd>0</kbd></td><td>hide / show the nth tree; all on</td></tr>
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
    for (const b of document.querySelectorAll(".treechip")) b.classList.toggle("off", off.has(b.dataset.tree));
    for (const t of document.querySelectorAll(".ticket")) t.classList.toggle("off", off.has(t.dataset.tree));
    // re-inject cached SVGs: an unchanged graph paints instantly instead of re-running mermaid.
    // Keyed by the scheme too, since mermaid bakes the palette into the SVG.
    for (const el of document.querySelectorAll(".mermaid")) {
      const hit = cache[el.dataset.key + "@" + document.documentElement.dataset.theme];
      if (hit && hit.src === el.textContent) { el.dataset.src = hit.src; el.innerHTML = hit.svg; }
    }
    if (saved) {
      for (const d of document.querySelectorAll("details.grp")) d.open = saved.groups?.includes(d.id) ?? d.open;
      for (const id of saved.open ?? []) document.getElementById(id)?.setAttribute("open", "");
      for (const id of saved.comments ?? []) document.getElementById(id)?.querySelector("details.history")?.setAttribute("open", "");
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

  // What the two full size views do, shared with the window of its own, which runs its own copy
  // (board.VIEW_JS).
${viewjs}

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
      if (!el.dataset.src.trim()) continue;  // the composed graph with every tree hidden: its note shows instead
      const { svg } = await mermaid.render("m" + Date.now() + "_" + seq++, el.dataset.src + "\n" + classDefs);
      el.innerHTML = svg;
      nodeHover(el);
    }
    markNode();
    paintFull();
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

  // ---- state: hidden trees, the cursor row, the graph mode ----
  const { saved, off, cache } = window.boardState;
  const rowsEl = document.getElementById("rows"), side = document.getElementById("side");
  const search = document.getElementById("search");
  let mode = saved?.mode ?? "tree";
  let cur = saved?.cur ? document.getElementById(saved.cur) : null;
  const inField = (e) => e.target.closest("input, textarea, [contenteditable]");
  const visible = (el) => el.checkVisibility();  // false inside a closed group too, where offsetParent still holds
  const rows = () => [...rowsEl.querySelectorAll(".ticket")].filter(visible);
  const groups = () => [...rowsEl.querySelectorAll("details.grp")].filter(visible);

  function applyFilters() {
    const q = search.value.trim().toLowerCase();
    for (const t of rowsEl.querySelectorAll(".ticket")) {
      t.classList.toggle("off", off.has(t.dataset.tree));
      t.classList.toggle("miss", !!q && !t.dataset.search.includes(q));
    }
    for (const g of rowsEl.querySelectorAll("details.grp[data-state]")) {
      const n = g.querySelectorAll(".ticket:not(.off):not(.miss)").length;
      g.querySelector(".n").textContent = n;
      g.classList.toggle("empty", n === 0);
    }
    for (const b of document.querySelectorAll(".treechip")) b.classList.toggle("off", off.has(b.dataset.tree));
    localStorage.setItem("board-off:" + document.title, JSON.stringify([...off]));
    if (cur && (cur.classList.contains("off") || cur.classList.contains("miss"))) setCur(null);  // a hidden tree takes its row, and its graph, with it
    showGraph();
  }

  // The whole tracker's graph is composed here from its parts, so a hidden tree drops out of it
  // with its edges, and a node left without an edge goes with them. One composition per set of
  // hidden trees is rendered and kept.
  function composeAll() {
    const g = side.querySelector('.g[data-tree="*"]'), pre = g.querySelector(".mermaid");
    if (!pre) return;
    const key = "g:*:" + [...off].sort().join(",");
    if (pre.dataset.key === key) return;
    const parts = JSON.parse(g.querySelector(".parts").textContent);
    const on = (f) => !off.has(f);
    const edges = parts.edges.filter((e) => on(e.a) && on(e.b));
    const keep = new Set(edges.flatMap((e) => [e.from, e.to]));
    const lines = ["flowchart LR"];
    for (const f of parts.trees) {
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

  // The graph panel shows one pre-rendered graph at a time: the cursor row's tree, or the whole
  // tracker. Switching shows another element and marks another node; nothing re-renders, so moving
  // between rows of one tree never flickers.
  function showGraph() {
    const tree = cur?.dataset.tree ?? "";
    const key = mode === "all" ? "*" : tree;
    for (const g of side.querySelectorAll(".g")) g.hidden = g.dataset.tree !== key;
    if (key === "*") composeAll();
    const gname = document.getElementById("gname");
    // the column is narrow enough to cut a parent ticket's slug short, so the whole one is on hover
    gname.title = gname.textContent = mode === "all" ? "whole tracker" : (tree || "");
    for (const b of document.querySelectorAll("[data-gmode]")) b.classList.toggle("on", b.dataset.gmode === mode);
    renderGraphs();
  }
  function setMode(m) { mode = m; showGraph(); }

  // the cursor row's node in the graph on show, which carries the namespace that graph was built
  // with: f for one tree's own, b for the whole tracker composed from its parts
  function curNode() {
    if (!cur?.dataset.slug) return "";
    const composed = side.querySelector(".g:not([hidden])")?.dataset.tree === "*";
    return "T_" + (composed ? "b" : "f") + "_" + cur.dataset.slug.replace(/[^a-zA-Z0-9]/g, "_");
  }
  function markNode() { markCur(side, curNode()); }

  // ---- the graph at full size: over the board, or in a window of its own ----
  // The preview is one graph given a column's width; both full size views are the same graph given
  // its own, drawn again from the preview's source so that a node keeps the id and the "#t-..."
  // link the board matches a row by. A drawing is kept per source and scheme, so opening and
  // closing costs one render of each graph rather than one per opening.
  const full = document.getElementById("gfull");
  const fullCache = {};
  let gwin = null;  // the window of its own, while one is open
  let fullKey = null, viewSeq = 0;

  // what the preview is showing, as the two full size views need it
  function shownGraph() {
    const g = side.querySelector(".g:not([hidden])"), pre = g?.querySelector(".mermaid");
    return {
      src: (pre?.dataset.src ?? pre?.textContent ?? "").trim(),
      note: g?.querySelector(".gnote:not([hidden])")?.textContent ?? "",
      name: document.getElementById("gname").textContent, mode, cur: curNode(),
      theme: document.documentElement.dataset.theme,
    };
  }

  async function svgFor(src) {
    const key = src + "@" + document.documentElement.dataset.theme;
    if (!fullCache[key]) {
      const { svg } = await mermaid.render("gf" + Date.now() + "_" + seq++, src + "\n" + classDefs);
      const box = document.createElement("div");
      box.innerHTML = svg;
      nodeHover(box);  // the titles are markup, so they travel to the window of its own with it
      // mermaid sizes its drawing to whatever box it is given (width="100%", capped at the size it
      // drew); full size is that size, which is the one its viewBox counts in.
      const el = box.querySelector("svg"), [, , w, h] = el.getAttribute("viewBox").split(/[\s,]+/);
      el.setAttribute("width", w);
      el.setAttribute("height", h);
      fullCache[key] = box.innerHTML;
    }
    return fullCache[key];
  }

  // The whole of what a full size view shows, drawing included, so the window of its own is sent a
  // picture rather than a source it has no mermaid to draw.
  async function viewOf(g) {
    return {
      key: [g.name, g.mode, g.theme, g.src, g.note].join("|"), name: g.name, mode: g.mode,
      theme: g.theme, note: g.note, cur: g.cur, svg: g.src ? await svgFor(g.src) : "",
    };
  }

  // Paint whichever full size views are open. The sequence number is what keeps a slow drawing
  // from landing after a faster one started later: mermaid resolves in whatever order it finishes.
  async function paintFull() {
    if (!full.classList.contains("open") && !gwin) return;
    const me = ++viewSeq;
    const view = await viewOf(shownGraph());
    if (me !== viewSeq) return;
    if (full.classList.contains("open")) fullKey = paintView(full, view, fullKey);
    sendView(view);
  }

  function openFull(on) {
    full.classList.toggle("open", on);
    if (on) paintFull();
  }

  attach(full.querySelector(".gfbody"), (href) => { openFull(false); openTarget(href); });

  // ---- the window of its own ----
  // It talks to the board by message rather than by reaching into it. The board is a file:// page,
  // so its origin is opaque and a reload mints another one: from the reload on, the window's
  // `opener.<anything>` throws and the board's own handle on the window is gone. A message crosses
  // either way regardless, so the window says hello on a timer and the board answers whoever asked,
  // which is how the two find each other again after every re-render.
  function sendView(view) {
    try {
      if (gwin && !gwin.closed) gwin.postMessage({ graph: "view", view }, "*");
    } catch { gwin = null; }
  }

  addEventListener("message", async (e) => {
    // the only things a message moves are the board's own cursor and its graph mode, so an opaque
    // origin nobody can check costs nothing
    const said = e.data;
    if (said?.graph === "hello") {
      gwin = e.source;
      const view = await viewOf(shownGraph());
      e.source.postMessage(view.key === said.key ? { graph: "alive" } : { graph: "view", view }, "*");
    } else if (said?.graph === "goto") {
      openTarget(said.href);
    } else if (said?.graph === "mode") {
      setMode(said.mode);
    }
  });

  function openWindow() {
    if (gwin && !gwin.closed) { gwin.focus(); return; }
    const win = open("", "board-graph", "popup,width=980,height=800");
    if (!win) { say("the browser blocked the graph window"); return; }
    // the fonts are linked rather than in the stylesheet, and the window renders the same labels
    const head = [...document.querySelectorAll('link[rel="stylesheet"], link[rel="preconnect"]')]
      .map((l) => l.outerHTML).join("")
      + "<style>" + [...document.querySelectorAll("style")].map((s) => s.textContent).join("\n") + "</style>";
    try {
      win.document.write(
        '<!doctype html><html data-theme="' + document.documentElement.dataset.theme + '">' +
        '<head><meta charset="utf-8"><title>' + document.querySelector(".top .name span").textContent +
        " dependencies</title>" + head + '</head><body class="gwin">' + ${graphwin} +
        "<script>" + WINDOW_JS + "<\/script></body></html>"
      );
      win.document.close();
    } catch {
      win.focus();  // a window this page did not open: the board reloaded under one already running
    }
    gwin = win;
  }

  const WINDOW_JS = `
    ${viewjs}
    let last = null, heard = Date.now();
    const body = document.querySelector(".gfbody");
    attach(body, (href) => opener.postMessage({ graph: "goto", href }, "*"));
    for (const b of document.querySelectorAll("[data-gmode]"))
      b.addEventListener("click", () => opener.postMessage({ graph: "mode", mode: b.dataset.gmode }, "*"));
    addEventListener("message", (e) => {
      heard = Date.now();
      if (e.data?.graph !== "view") return;
      document.documentElement.dataset.theme = e.data.view.theme;
      last = paintView(document.body, e.data.view, last);
    });
    // the board answers this, so silence past a few rounds of it is a board that has gone away
    setInterval(() => {
      try { opener.postMessage({ graph: "hello", key: last }, "*"); } catch { }
      document.documentElement.dataset.orphan = Date.now() - heard > 3000 ? "1" : "";
    }, 1000);
  `;

  document.getElementById("gopen").addEventListener("click", () => openFull(true));
  document.getElementById("gclose").addEventListener("click", () => openFull(false));
  document.getElementById("gwinopen").addEventListener("click", openWindow);
  // from inside the overlay, the window is where the graph is going, so the board comes back with it
  document.getElementById("gwinfull").addEventListener("click", () => { openFull(false); openWindow(); });
  full.addEventListener("click", (e) => { if (e.target === full) openFull(false); });
  // the preview is the way in to the full size view; a node in it still goes to its row
  document.getElementById("gbody").addEventListener("click", (e) => { if (!hrefOf(e.target.closest("a"))) openFull(true); });

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

  document.getElementById("treenav").addEventListener("click", (e) => {
    const b = e.target.closest(".treechip"); if (!b) return;
    off.has(b.dataset.tree) ? off.delete(b.dataset.tree) : off.add(b.dataset.tree);
    applyFilters();
  });
  for (const b of document.querySelectorAll("[data-gmode]")) b.addEventListener("click", () => setMode(b.dataset.gmode));
  document.getElementById("sidefold").addEventListener("click", () => side.classList.toggle("folded"));
  search.addEventListener("input", applyFilters);
  // a click on a row's summary moves the cursor there, so the graph follows the mouse too;
  // one on a copy button copies what that button carries, and one on the row's number its path,
  // instead of folding the row or the group
  rowsEl.addEventListener("click", (e) => {
    const copier = e.target.closest("[data-copy]");
    if (copier) { e.preventDefault(); copy(copier.dataset.copy, copier.dataset.copied); return; }
    const t = e.target.closest(".ticket");
    if (!t || !e.target.closest("summary")) return;
    if (e.target.closest(".ticket > summary > .slug")) { e.preventDefault(); copyPath(t); }
    setCur(t, false);
  });

  const toast = document.getElementById("toast");
  let toastTimer = null;
  function say(words) {
    toast.textContent = words;
    toast.classList.add("on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("on"), 1500);
  }
  function copy(text, said) {
    if (!text) return;
    // navigator.clipboard is absent outside a secure context
    (navigator.clipboard?.writeText(text) ?? Promise.reject()).then(() => say("copied " + said), () => say("could not copy " + said));
  }
  function copyPath(t) {
    copy(t?.dataset.path, t?.dataset.path);
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
      case "Escape":
        help.classList.remove("open");
        if (full.classList.contains("open")) openFull(false);
        else if (cur?.open) cur.open = false;
        else setCur(null);
        break;
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
      case "a": setMode(mode === "all" ? "tree" : "all"); break;
      case "b": side.classList.toggle("folded"); break;
      case "f": openFull(!full.classList.contains("open")); break;
      case "w": openWindow(); break;
      case "t": switchScheme(); break;
      case "0": off.clear(); applyFilters(); break;
      default:
        if (/^[1-9]$$/.test(e.key)) {  // the doubled dollar is the page template's escape
          const chip = document.querySelectorAll(".treechip")[e.key - 1];
          if (chip) { off.has(chip.dataset.tree) ? off.delete(chip.dataset.tree) : off.add(chip.dataset.tree); applyFilters(); }
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
    const href = hrefOf(e.target.closest("a"));
    if (href && href.startsWith("#") && href === location.hash) setTimeout(() => openTarget(href));
  });

  function saveState() {
    const state = {
      mode, cur: cur?.id ?? null, folded: side.classList.contains("folded"),
      full: full.classList.contains("open"),
      groups: [...document.querySelectorAll("details.grp[open]")].map((d) => d.id),
      open: [...document.querySelectorAll("details.ticket[open]")].map((d) => d.id).filter(Boolean),
      comments: [...document.querySelectorAll(".ticket details.history[open]")].map((d) => d.closest(".ticket").id),
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
  if (!saved) {
    if (location.hash) openTarget();
    // ?graph opens the overlay on the row the address names, which is what a layout check measures
    if (new URLSearchParams(location.search).has("graph")) openFull(true);
  }
  if (saved?.full) openFull(true);  // the re-render a tracker change triggers puts it back
</script>
</body>
</html>
""")


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__, prog="board"))
