#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.14"
# dependencies = ["tyro", "pyyaml", "markdown", "markdown-it-py[linkify]"]
# ///
"""Render the tracker board: one HTML page for a tracker's whole agent/tickets tree.

Run `board` from anywhere inside the repo: it finds the tracker the way the
`tracker` command does (the `tickets` of the agent repo the project holds at
`agent/`, in that repo's main checkout), renders, opens the tab served, and
keeps re-rendering until Ctrl-C. --no-watch --no-open is the
one-shot form: render the page and exit.

It reads every ticket of the tracker (agent/tickets/<slug>.md, flat) through the
one command that parses one, `tracker` beside this script, and writes one
self-contained page beside the tracker, agent/board.html: the tickets as rows
grouped by where they stand, needs me first, with their dependency graph and a
briefing on where things stand. One directory holds every ticket it shows:
every ticket file is written and committed in the agent repo's main checkout,
claims and review flips included, so a build is on the board from its claim
onward. Besides the tracker it reads the commits that changed each ticket file
and the transcripts of the sessions that made them, each ticket's show
directory, GitHub through `gh` for the pull requests and issues the tickets
name, and a `claude -p` session that writes the briefing; it renders without any
of these it cannot reach, and the page says so once.

Every link the page writes is relative to it, so it opens wherever the page is
opened: served from any origin, or as a file. `board` opens the page served,
at the address `diffview --serve agent/` prints for the whole agent repo, and
while it watches it runs that again whenever nothing answers there, so an open
tab keeps answering. Where no diffview is installed or nothing answers at the
address, it opens the file. Served, a review
page opened from the board saves the comments written on it; opened as a file,
the board opens its review pages as files, read-only. --no-open starts no
server.

Watching means: every few seconds it looks for a change under the tracker and
re-renders on one, and an open tab reloads itself when what it shows has
changed. It also re-renders on the three things that move with no file under
the tracker moving: a briefing the session has rewritten, GitHub's answer
running past the five minutes it is cached for, and a run of the model that
answered nothing. Each change of a ticket's status is sent to the briefing
session, which spends a run of the model on it, at the cadence briefing.py
beside this script sets. One watcher per board: several of them write the same
page from the same tracker, but each keeps its own briefing schedule, so a
second one pays for every briefing again and resumes the session while the
first is in it.

Once this script or a module it imports from beside it changes on disk and
the new code starts, the watcher restarts on it in place within one pass,
keeping the tab and the briefing schedule. A pass that fails prints its error
once, and an open tab says the board is stale until a pass succeeds again.

Examples:

    board
    board --no-watch --no-open
    board ~/repos/workspace/agent/tickets --out /tmp/board.html
"""

import ast
import datetime
import functools
import hashlib
import html
import json
import os
import re
import shlex
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.parse
from collections import Counter
from itertools import takewhile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Annotated, NoReturn

import markdown
import tyro

from board_page import (  # the page: what it shows as values, their markup and its template, beside this script
    ALONE, COPY_CAP, GRAPH_WINDOW, OVERLAY, PAGE, VIEW_JS, Absence, Artefact, Asked, Block, Briefed, Copy, Group, Mark,
    MarkKind, Pill, Row, View, Worked, absence_html, briefing_html, column_tokens, group_html, pill_html,
)
from board_page import MARK_HTML, PAGE_TIP, STYLE, block_html, copy_html, mark_html, row_html  # noqa: F401  the checks read these off board
import briefing  # the board briefing: the session that writes it, and the cache it lives in, beside this script
import github  # the state of the pull requests and issues the tickets name, beside this script
import qualified  # what a qualified tag the page shows names, which the page links
import tracker  # the one parser of a ticket file, and the rules it refuses one by, beside this script

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "session-page"))
from session_page import PAGE as SESSION_PAGE, sessions_directory  # noqa: E402  where a session's page lives

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
    "review": ("to rule on", "A worker has finished this and it carries calls of yours: rule on the ones its landing shows you, with the review page as the drill-down, then accept, amend, redo or reject it."),
    "answer": ("your answer", "The work stops until you answer the questions on this ticket."),
    "session": ("with you", "A ticket you are in the loop for: it is worked with you, and dispatch keeps it from a worker."),
    "build": ("build", "An agent builds this alone. It comes back to you as a build to rule on."),
    "triage": ("to triage", "Proposed by an agent, it waits off the frontier for a triage you start, which drops it, merges it into another ticket or promotes it to open."),
    "whole": ("with parent", "Built and merged into its parent ticket's branch. You rule on it with the parent, whole, at the parent's close-out."),
}
# what a parent ticket's row says of the child tickets folded under it (board.folded)
KIN_TIP = {
    "closed-out": "Its child tickets, folded under it: you rule on the parent whole with them. Open the row to read each, and amend, redo or reject any one from there.",
    "merged": "Its child tickets in review, merged into its branch: they wait for its close-out, where you rule on them with it. Open the row to read each.",
}
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
    """Open the result in the browser diffview pages open in ($DIFFVIEW_BROWSER, else xdg-open), so the board and the diffs it links share a window: at the address the diffview server over the agent repo answers on, else as the file."""
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
    watching = taken(repo, out) or started(args, tickets_root, repo, out)
    if args.watch:
        try:
            restart(watch(watching, tickets_root, repo, out), out)
        except KeyboardInterrupt:
            pass


def started(args: Args, tickets_root: Path, repo: Path, out: Path) -> "Watch":
    """A start of the board's own. A restart on new code skips it (`taken`): its tab is open, and a
    tracker that refuses must not end it."""
    try:
        render(tickets_root, repo, out)
    except tracker.Refused as refused:
        sys.exit(f"board: the tracker holds a ticket no reader can read:\n{refused}")
    address = None
    if args.open:
        address = served(tickets_root.parent, out)
        browser = os.environ.get("DIFFVIEW_BROWSER") or "xdg-open"
        subprocess.Popen([browser, address or str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return Watch(Seen(), Briefer(repo, out), address)


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
    reading = read(root, repo, out)
    stamp = content_stamp(reading)
    out.write_text(linked_tags(render_page(reading, stamp, stamp_path(out).name), root.parent, out))
    write_stamp(out, stamp)
    print(out)
    return statuses(reading.tickets)


def linked_tags(page: str, agent: Path, out: Path) -> str:
    """The page written to `out` with each qualified tag it shows a link: a ticket's to its row,
    anything else's to the file it lives in, from the agent repo at `agent`."""
    away = qualified.hrefs(agent, out)
    return qualified.link_html(page, qualified.cites(agent), lambda c: ref_anchor(c.ticket) if c.ticket else away(c))


def stamp_path(out: Path) -> Path:
    return Path(str(out) + ".stamp.js")


def write_stamp(out: Path, stamp: str, failing: "Failing | None" = None) -> None:
    """The file an open tab polls: the page's stamp, which reloads a tab showing another, and the
    stale mark, null while passes succeed. The mark lives here because a failing pass draws no page."""
    stale = failing and STALE.format(since=f"{failing.since:%d %b %H:%M}", error=failing.error.splitlines()[0])
    stamp_path(out).write_text(f"window.__boardStamp = {json.dumps(stamp)};\nwindow.__boardStale = {json.dumps(stale)};\n")


def restamp(out: Path, failing: "Failing | None") -> None:
    """Set or clear the stale mark, keeping the stamp so the tab does not reload."""
    try:
        stamp = re.search(r'__boardStamp = "([^"]*)"', stamp_path(out).read_text()).group(1)
    except (FileNotFoundError, AttributeError):  # no page drawn yet, so no tab to tell
        return
    write_stamp(out, stamp, failing)


@dataclass(frozen=True)
class Reading:
    """What one render reads: the page is written from this and nothing else, so everything it
    shows is a format of it. `briefing` is the one the cache beside the page holds, None where no
    session has written one."""

    project: str  # the code repo's name, which the page is named after
    tickets: list["Ticket"]
    log: str  # the project's last commits
    gh: github.Answer = github.NOTHING
    briefing: "briefing.Briefing | None" = None


def read(root: Path, repo: Path, out: Path) -> Reading:
    """Everything a render of the page `out` reads, GitHub asked about the references the tickets
    name where its cached answer will not do."""
    code = project(root)
    session_log.cache_clear()  # once per render: the sessions that committed on a ticket while the board watches
    tickets = load_tickets(root, repo, out.parent)
    log = git_log(code)
    out.parent.mkdir(parents=True, exist_ok=True)
    gh = github.resolve(gh_shown(tickets), github.cache_path(out))
    return Reading(code.name, tickets, log, gh, briefing.Briefing.read(briefing.cache_path(out)))


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
    load of the tracker per watcher start. The links are no part of a status, so this writes them
    from the tracker's own directory (briefing_state does the same)."""
    return statuses(load_tickets(root, repo, root.parent))


def watch(watching: "Watch", tickets_root: Path, repo: Path, out: Path) -> "Watch":
    """Re-render on any change under the tracker, in every checkout that contributes to it, and on
    the three things that move on their own: the briefing a session has rewritten since the page
    was written, GitHub's answer running out of the lifetime it is cached for, and a run of the
    model that came back with nothing. A page opened at `watching.address` keeps a server answering
    there.

    Those three are what the watcher is for as much as the tracker is. A pull request merged while
    the tracker sits still would otherwise show as open until someone touched a ticket, a briefing
    written minutes after the change that asked for it would not show at all, and a run that
    answered nothing writes no file for anything else to notice.

    Returns once the code this process runs has changed on disk and the new code starts. New code
    that does not start is said once and tried again on its next change or CODE_RETRY on, so a
    module saved half-written neither stops the watcher nor strands it on the old code."""
    while True:
        watching = turn(watching, tickets_root, repo, out)
        code = on_disk(path for path, _, _ in watching.code)
        if code != watching.code and (code != watching.unstarted or time.monotonic() >= watching.unstarted_retry):
            said = starts()
            if said is None and on_disk(path for path, _, _ in watching.code) == code:
                return watching
            # code that started but moved again while it was tried is tried again on the next pass
            if said is not None:
                if code != watching.unstarted:
                    print(f"board: the code changed on disk and does not start, so the watcher keeps the code it runs: {said}", file=sys.stderr)
                watching = replace(watching, unstarted=code, unstarted_retry=time.monotonic() + CODE_RETRY)
        time.sleep(PASS)


PASS = 2  # seconds between two passes of the watcher
CODE_RETRY = 600  # seconds before new code that did not start is tried again, unchanged

Code = tuple[tuple[Path, int | None, int | None], ...]  # files, each with its time and size on disk


def on_disk(files: Iterable[Path]) -> Code:
    """A file that cannot be read has no time and no size."""
    def read(path: Path) -> tuple[Path, int | None, int | None]:
        try:
            st = path.stat()
        except OSError:
            return (path, None, None)
        return (path, st.st_mtime_ns, st.st_size)
    return tuple(map(read, files))


SCRIPT = Path(__file__).resolve()
# the code this process runs: every module it loaded from the skills beside this one, as loaded
CODE = on_disk(sorted({
    Path(m.__file__).resolve() for m in list(sys.modules.values())
    if getattr(m, "__file__", None) and Path(m.__file__).resolve().is_relative_to(SCRIPT.parents[1])
}))


@dataclass(frozen=True)
class Failing:
    """A run of failed passes: when the first of them failed, and the error the latest failed on."""

    since: datetime.datetime
    error: str


@dataclass(frozen=True)
class Watch:
    """The watcher between two passes. `retry` is when a server that did not come back is tried
    again, `unstarted_retry` when `unstarted`, the code on disk that last did not start, is; both
    on the monotonic clock."""

    seen: "Seen"
    session: "Briefer"
    address: str | None = None
    retry: float = 0.0
    failing: Failing | None = None
    code: Code = CODE
    unstarted: Code = ()
    unstarted_retry: float = 0.0


def turn(watching: Watch, tickets_root: Path, repo: Path, out: Path) -> Watch:
    """One pass of the watcher. The first pass to succeed after failing ones says so and clears the
    stale mark."""
    try:
        if watching.address and time.monotonic() >= watching.retry:
            back = kept(tickets_root.parent, out, watching.address)
            if back and back != watching.address:
                print(f"board: the server came back at {back}; a tab open at {watching.address} no longer follows the tracker", file=sys.stderr)
            watching = replace(watching, address=back or watching.address, retry=0.0 if back else time.monotonic() + SERVER_RETRY)
        watching = replace(watching, seen=look(watching.seen, watching.session, tickets_root, repo, out))
    except Exception as e:  # a file deleted mid-scan, a half-written ticket, a ticket the tracker refuses
        return replace(watching, failing=failed(watching.failing, e, out))
    if watching.failing:
        print("board: passes succeed again, and the board follows the tracker", file=sys.stderr)
        restamp(out, None)
    return replace(watching, failing=None)


def failed(was: Failing | None, e: Exception, out: Path) -> Failing:
    """The run of failed passes `was`, one pass longer. Only an error not said yet is printed, so a
    standing one does not fill the log every two seconds."""
    error = str(e).strip() or type(e).__name__
    if was and was.error == error:
        return was
    failing = Failing(was.since if was else now(), error)
    print(f"board: {error}\nboard: the board is stale until a pass succeeds; retrying every {PASS} s", file=sys.stderr)
    restamp(out, failing)
    return failing


def starts() -> str | None:
    """None where the script on disk starts, else the last line it said. It runs the way a restart
    does, through its shebang, so a dependency it gained is installed now."""
    try:
        done = subprocess.run([str(SCRIPT), "--help"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return str(e)
    if done.returncode == 0:
        return None
    return ((done.stderr.strip() or done.stdout.strip()).splitlines() or [f"exit {done.returncode}"])[-1]


HANDOVER = "BOARD_HANDOVER"  # the variable naming the file a watcher restarting on new code leaves itself in


def restart(watching: Watch, out: Path) -> NoReturn:
    """Exec the script on disk in this process's place, handing the watcher on through a file
    (`taken`). A briefing run in flight is lost with its thread; the schedule counts it as a run
    that answered nothing. The file is a Python literal, not JSON, because JSON hands the tuples
    back as lists that never compare equal."""
    s = watching.session
    held = Path(str(out) + ".handover")
    held.write_text(repr({
        "address": watching.address, "statuses": watching.seen.statuses,
        "told": s.told, "told_statuses": s.told_statuses,
        "changed_at": s.changed_at and s.changed_at.isoformat(), "tried": s.tried and s.tried.isoformat(),
        "failing": watching.failing and (watching.failing.since.isoformat(), watching.failing.error),
    }))
    os.environ[HANDOVER] = str(held)
    print("board: the code changed on disk; restarting on it", file=sys.stderr)
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(SCRIPT, [str(SCRIPT), *sys.argv[1:]])


def taken(repo: Path, out: Path) -> Watch | None:
    """The watcher a restart handed on, or None on a start of its own. A hand-over this code cannot
    read, from a board older than it, keeps only the tab's address."""
    held = os.environ.pop(HANDOVER, None)
    if not held:
        return None

    def when(at: str | None) -> datetime.datetime | None:
        return at and datetime.datetime.fromisoformat(at)

    state = {}
    try:
        state = ast.literal_eval(Path(held).read_text())
        session = Briefer(repo, out, state["told"], state["told_statuses"], when(state["changed_at"]), when(state["tried"]))
        failing = state["failing"] and Failing(when(state["failing"][0]), state["failing"][1])
        return Watch(Seen(snapshot=(), statuses=state["statuses"]), session, state["address"], failing=failing)
    except Exception as e:
        print(f"board: what the watcher before the restart handed on does not read ({e}); its briefing schedule starts again", file=sys.stderr)
        return Watch(Seen(), Briefer(repo, out), state.get("address") if isinstance(state, dict) else None)
    finally:
        Path(held).unlink(missing_ok=True)


@dataclass(frozen=True)
class Seen:
    """What the last pass of the watcher read, as a value to compare the next one against.

    `snapshot` is the tracker as `tracker_snapshot` reads it, None before the first pass and () in a
    watcher restarted on new code, which no tracker reads as, so that its first pass renders;
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
    code = project(root)
    return state_of(code.name, view(load_tickets(root, repo, root.parent)), git_log(code))


# ---- the board briefing ---------------------------------------------------
# What the session that writes it is given, what it is told when the tracker moves, and what the
# board says where no session has written one. mx/skills/tracker/corpus/board-orients.md is the oracle;
# the session itself and the schedule are briefing.py.

STATE = """The tracker of {project} as the board reads it.

One ticket per line, under the parent ticket its tree runs to: slug, status, what it asks of you,
priority, your time on it, its name, its file, then the parent ticket whose row it folds under,
ruled whole with it. Under it, where the ticket has them:
the brief, what it waits on, its open questions.
"""


def state_of(project: str, board: "View", log: str) -> str:
    """The tracker written out for the briefing session: every row the board shows, as the board
    shows it, under the tree it is part of, and the commits behind it.

    Nothing here is more than the board itself says. The file each line ends with is what the
    session reads for the rest, and the repo around it is what it is for."""
    written = [STATE.format(project=project)]
    tickets = [r.ticket for r in board.rows.values()]
    for tree in trees_of(tickets):
        written.append(f"## {tree}\n" + "".join(state_line(board.rows[t.slug]) for t in in_tree(tickets, tree)))
    return "\n".join(written + [f"## the last commits\n{log.strip()}\n"])


def state_line(r: "Row") -> str:
    """One row, in the words of its own marks."""
    t = r.ticket
    marks = [
        t.slug, t.status, mark(r, "asks").shows, mark(r, "pri").shows, mark(r, "time").shows, t.title, str(t.path),
    ] + ([f"folded under {t.under}"] if t.under else [])
    said = " · ".join(marks) + "\n"
    if t.brief:
        said += f"  brief: {plain(t.brief)}\n"
    if waits := [m.shows for m in r.marks if m.kind == "chip"]:
        said += f"  waits on: {', '.join(waits)}\n"
    for q in r.questions:
        if not q.of:  # a folded child's question is on its own line
            said += f"  asks: [{q.tag}] {plain(q.headline)} {plain(q.detail)}\n".rstrip() + "\n"
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


def fallback(board: "View") -> str:
    """What the board says where no model has written a briefing: the counts of what waits on the
    user and what is being worked on, and the next few by priority, then by what accepting them
    unlocks, then by the user's own time.

    What waits is counted off the rows themselves, so the sentence and the group under it say the
    same thing: a ticket the board tags as a design session is one here whatever else it carries,
    and a parent ticket at its close-out asks its folded child tickets' questions (Row.questions)."""
    rows = board.rows.values()
    mine = [r for r in rows if r.group == "needs"]
    waiting = {
        ("build to rule on", "builds to rule on"): [r for r in mine if mark(r, "asks").look == "review"],
        ("question wanting a word", "questions wanting a word"): [q for r in mine for q in r.questions],
        ("ticket wanting a session", "tickets wanting a session"): [r for r in mine if mark(r, "asks").look == "session"],
    }
    counts = [
        f"{counted(len(held))} {one if len(held) == 1 else many}" for (one, many), held in waiting.items() if held
    ]
    several = len(counts) > 1 or any(len(held) > 1 for held in waiting.values())  # what the verb agrees with
    waits = f"{listed(counts).capitalize()} wait{'' if several else 's'} on you." if counts else "Nothing waits on you."
    running = [r for r in rows if r.ticket.status == "claimed"]
    worked = (
        f"{counted(len(running)).capitalize()} ticket{'s are' if len(running) != 1 else ' is'} being worked on."
        if running else "Nothing is being worked on."
    )
    lead = f"{waits} {worked}"
    unlocks = waited_on([r.ticket for r in rows])
    picks = sorted(
        (r.ticket for r in rows if r.group in ("needs", "open")),
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

    A review page rendered gives its row a link, and a show directory is where an opened ticket
    reads its artefacts from; each file's mode is read with its time and size, since an artefact
    made executable gains a button and `chmod` moves neither.
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


def href(target: Path, here: Path) -> str:
    """A link to `target` from a page in `here`, relative, so it opens wherever the page is opened:
    served from any origin, or as a file."""
    return urllib.parse.quote(os.path.relpath(target.resolve(), here.resolve()))


def review_page(root: Path, slug: str, here: Path) -> str | None:
    """The link to a ticket's review page, `agent/diffviews/<slug>.html` beside the tracker, where
    one has been rendered."""
    page = root.parent / "diffviews" / f"{slug}.html"
    return href(page, here) if page.is_file() else None


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
    blocks: tuple["Block", ...]  # what the ticket reads as opened, in the order the page shows them
    diffview: str | None
    priority: int  # 1 to 5, how soon it matters to the user
    size: str  # XS | S | M | L | XL, the user's time on it
    path: Path  # the ticket file this row was read from
    brief: str = ""  # the ## Brief section, as inline HTML
    questions: list["Question"] = field(default_factory=list)  # its ## Questions, ruled ones included
    freed: list[str] = field(default_factory=list)  # blockers not done that hold it back no longer (tracker.frees)
    under: str | None = None  # the parent ticket whose row this one folds under (board.folded)


def load_tickets(root: Path, repo: Path | None, here: Path) -> list[Ticket]:
    """Every ticket the board shows, read through the one parser of a ticket file.

    One directory holds them all: ticket files are written and committed in the tracker's own
    checkout, claims and review flips included, so nothing of a build in flight is anywhere else.
    `here` is the directory the page is written in, which every link on it is relative to.
    """
    read = parsed(root)
    under = folded(read)
    tickets = [shown(one, read, repo, here, under.get(one.slug)) for one in read.tickets.values()]
    ids = [slug_id(one.slug) for one in tickets]
    assert len(ids) == len(set(ids)), f"slugs collide as mermaid ids: {sorted(ids)}"
    return sorted(tickets, key=lambda one: one.slug)


def parsed(root: Path) -> "tracker.Tracker":
    """One tracker root as the tracker command reads it, its tickets by slug; a root that does not
    exist is a tracker with none. A file no reader can read is refused there, with its own file and
    line."""
    read = tracker.tracker_of(root)
    tracker.refuse([refusal for one in read.tickets.values() for refusal in tracker.refusals_of(one, read)])
    return read


def folded(read: "tracker.Tracker") -> dict[str, str]:
    """The rows that fold under their parent ticket's row, each to that parent's slug. Every child
    of a parent at its close-out does, since the user rules on the parent whole with them. Under a
    parent still being built, each child in review that is merged into the parent's branch does,
    since it waits for that close-out, not on the user. Whether it merged is read in the code repo
    the tracker plans, wherever the board runs from."""
    code = project(read.root)
    return {
        one.slug: one.parent for one in read.tickets.values()
        if one.parent in read.tickets
        and (read.tickets[one.parent].status == "review" or tracker.merged_under_parent(one, read, code))
    }


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
    read: "tracker.Ticket", whole: "tracker.Tracker", repo: Path | None, here: Path,
    under: str | None,
) -> Ticket:
    """One ticket as the board shows it: what its file says, plus the status derived from what it
    waits on, and the review page and sessions beside it. An open ticket is blocked while a
    blocker the board can see holds it back, as the frontier reads it (tracker.frees), with what
    merged read in the code repo the tracker plans, wherever the board runs from."""
    assert_safe_name(read.slug)
    tickets = whole.tickets
    blocked_by = [(ref, ref_status(ref, tickets)) for ref in read.blocked_by]
    freed = [
        ref for ref, state in blocked_by if state != "done" and ref in tickets
        and tracker.frees(tickets[ref], read, whole, project(whole.root))
    ]
    status = read.status
    if status == "open" and any(state != "done" and ref not in freed for ref, state in blocked_by):
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
        freed=freed,
        gh=[str(ref) for ref in read.meta.get("gh") or []],
        blocks=ticket_blocks(read, read.questions, path=read.path, status=status, worked=worked, here=here),
        diffview=review_page(whole.root, read.slug, here),
        path=read.path,
        priority=read.meta.get("priority"),
        size=read.meta.get("size"),
        brief=inline_md(read.brief),
        questions=read.questions,
        under=under,
    )


def ref_status(ref: str, tickets: dict[str, "tracker.Ticket"]) -> str:
    """The status of a ticket another one waits on. A reference the board cannot see counts as
    done: the tracker refuses a dangling one where it is written, so what is left here is a ticket
    retired since the edge onto it was written."""
    return tickets[ref].status if ref in tickets else "done"


def assert_safe_name(name: str) -> None:
    # slugs ride into HTML attributes and mermaid click strings unescaped
    assert re.fullmatch(r"[A-Za-z0-9._-]+", name), f"unsafe tracker name: {name!r}"


def served(agent: Path, out: Path) -> str | None:
    """The address the page `out` answers on where `diffview --serve` serves the agent repo, or None
    where it can be opened only as a file: the page is outside the agent repo, no diffview is
    installed, or nothing answers at the address it prints.

    `diffview --serve` is idempotent and prints the agent repo's address on whichever server it
    handed the repo to, so the port stays diffview's to decide, and a server that exited comes back
    on the port it had, which is the one an open page knows."""
    if not out.is_relative_to(agent):
        return None
    try:
        done = subprocess.run(["diffview", "--serve", str(agent)], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:  # no diffview on this machine, so no server either
        return None
    except subprocess.TimeoutExpired:
        print(f"board: diffview --serve {agent} did not come back; opening the page as a file", file=sys.stderr)
        return None
    found = re.search(r"https?://\S+", done.stdout) if done.returncode == 0 else None
    address = f"{found.group().rstrip('/')}/{href(out, agent)}" if found else None
    if not (address and answers(address)):
        said = (done.stderr or done.stdout).strip()
        print(f"board: diffview does not serve {agent}, so the page opens as a file: {said}", file=sys.stderr)
        return None
    return address


SERVER_RETRY = 60  # seconds between the watcher's tries at a server that did not come back


def kept(agent: Path, out: Path, address: str) -> str | None:
    """The address the open page is served at, its server brought back where it has exited, or
    None where it did not come back: the watcher's part in keeping a served tab answering.

    Whatever serves the page can stop between two passes: a hub its service manager has yet to
    restart, or a server diffview started on a machine with no hub, which nothing restarts. Asking
    is one local connection a pass, so the watcher asks whichever it is."""
    return address if answers(address) else served(agent, out)


def answers(address: str) -> bool:
    """Whether a server is listening where `address` points. A connection, not a request, since it
    is asked every pass of the watcher and listening is all it needs to know."""
    at = urllib.parse.urlsplit(address)
    try:
        socket.create_connection((at.hostname, at.port or 80), timeout=1).close()
    except OSError:
        return False
    return True


def inline_md(text: str) -> str:
    """Markdown as one line of HTML: a brief or a headline carries code and emphasis, never a block."""
    return re.sub(r"^<p>|</p>$", "", markdown.markdown(text).strip()) if text else ""


def ref_anchor(ref: str) -> str:
    return f"#t-{ref}"


def render_body(md: str) -> str:
    out = markdown.markdown(md, extensions=["fenced_code", "tables"], tab_length=3)
    # a link to another ticket file becomes that row's anchor, wherever the writer wrote it from
    return re.sub(r'href="(?:[\w./-]*/)?([a-z0-9][\w-]*)\.md"', r'href="#t-\1"', out)


def content_stamp(reading: Reading) -> str:
    # everything the page shows except the render timestamp: an unchanged board
    # keeps its stamp, so the open tab knows not to reload. A state GitHub gave a link, a briefing
    # a session rewrote and an absence the page says are the three of those that move without a
    # file under the tracker moving with them.
    gh, said = reading.gh, reading.briefing
    key = repr((
        reading.project, reading.tickets, reading.log, sorted(gh.states.items()), gh.missing,
        said and (said.text, said.written), absences(reading),
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
    review, has an open question, or is an unclaimed open ticket at p1 or p2 the user is in the loop
    for; a proposed one waits for a triage instead."""
    if status == "done":
        return False
    if status == "review" or open_question:
        return True
    # a ticket worked with the user, that nobody has taken up yet
    return bool(needs_user) and priority in (1, 2) and status == "open"


Question = tracker.Question  # one `[Dn]` item under a ticket's `## Questions`, read by the one parser


@dataclass(frozen=True)
class Session:
    """A session whose commits changed a ticket, as the user resumes it."""

    id: str
    title: str  # its /rename name, else Claude Code's own, else its id
    cwd: str  # the working directory its transcript records
    first: str  # when it first committed on the ticket
    last: str
    page: Path | None  # its session page, where one has been rendered

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
            title, cwds = written
            found.append(Session(sid, title or sid, cwds[0] if cwds else "", first, last, page_of(sid, cwds, path)))
    return found


def page_of(session: str, cwds: Sequence[str], ticket: Path) -> Path | None:
    """The session's page, or None where there is none to find. The session-page Stop hook writes it
    in the agent repo of the project the session was in when its turn ended, so the newest of its
    directories that holds one answers; where each is gone, as a worktree dispatch removed is, the
    project the ticket is in answers. A page in another project whose every directory the session
    ran in is gone is not found."""
    places = [cwd for cwd in reversed(cwds) if Path(cwd).is_dir()] + [str(ticket.parent)]
    pages = (sessions / session / SESSION_PAGE for sessions in map(sessions_in, places) if sessions)
    return next((page for page in pages if page.is_file()), None)


@functools.cache
def sessions_in(directory: str) -> Path | None:
    """`sessions_directory` once per directory a render asks about, since each answer runs git."""
    return sessions_directory(Path(directory))


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


def transcript(session: str, transcripts: Path) -> tuple[str, tuple[str, ...]] | None:
    """(the session's title, the directories it ran in) from its transcript on this machine, or None
    where this machine has no transcript of it. The newest transcript answers, since a session
    resumed in another directory writes a second one."""
    written = sorted(transcripts.glob(f"*/{session}.jsonl"), key=lambda p: p.stat().st_mtime)
    if not written:
        return None
    return read_transcript(written[-1], written[-1].stat().st_size)


@functools.cache
def read_transcript(path: Path, size: int) -> tuple[str, tuple[str, ...]]:
    """The title a transcript's records carry and the working directories they were written in, in
    the order the session first reached each. The last title the session was given wins, and a name
    it was given by hand wins over the model's.

    `size` keys the cache: a transcript the session is still writing is read again as it grows.
    """
    titles: dict[str, str] = {}
    cwds: dict[str, None] = {}
    for line in path.read_text(errors="replace").splitlines():
        if not any(key in line for key in (*TITLES, "cwd")):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:  # a line the session was still writing when the board read it
            continue
        titles.update({key: record[key] for key in TITLES if record.get(key)})
        if record.get("cwd"):
            cwds.setdefault(str(record["cwd"]))
    return next((titles[key] for key in TITLES if key in titles), ""), tuple(cwds)


# what a served page says once its polls have gone unanswered a while
UNSERVED = "The server this page came from is not answering, so it stops following the tracker until it does."
# what an open page says while every pass of the watcher fails (write_stamp)
STALE = "This board is stale since {since}: every pass of its watcher fails, on {error}"


# ---- an opened ticket -----------------------------------------------------


def ticket_blocks(
    read: "tracker.Ticket", asked: Sequence[Question], path: Path, status: str, worked: Sequence[Session],
    here: Path,
) -> tuple[Block, ...]:
    """A ticket opened on the board, as blocks: its questions with the detail the row has no room
    for, the sessions that worked on it, the artefacts it produced, then its own sections in the
    order the file writes them, the comments last.

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
            blocks.append(Block(word or None, prose(heading, text)))
    front = [asked_block(asked, prose(None, "".join(said)), path, status),
             sessions_block(worked, path.parent.parent, here), artefacts_block(show_dir(path), project(path.parent), here)]
    comments = "".join(history)
    return tuple(filter(None, front + blocks)) + ((Block("comments", render_body(comments)),) if comments.strip() else ())


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


def asked_block(asked: Sequence[Question], said: str, path: Path, status: str) -> Block | None:
    """Every question the ticket asks, the answered ones with the ruling that answered them and
    every open one with the button that copies it: the row lists its questions only while it is
    folded, so this block is where an opened ticket's questions are read and copied. `said` is
    whatever else its `## Questions` section says, which is the ticket's own and stands above them."""
    if not asked and not said:
        return None
    copyable = set(shown_questions(status, asked))
    return Block("questions", said, asked=tuple(asked_of(q, path, q in copyable) for q in asked))


def asked_of(q: Question, path: Path, copyable: bool, of: str = "") -> Asked:
    """One question of the ticket file at `path`, and the button copying it where it has one."""
    return Asked(
        tag=q.tag, headline=inline_md(q.headline), detail=inline_md(q.detail),
        ruling=f"Ruled {q.ruled}: {inline_md(q.answer)}" if q.ruled else "", says=question_tip(q),
        copy=Copy("qcopy", "copy", QCOPY_TIP, copy_text(path, [q]), f"{q.tag} of {path.name}") if copyable else None,
        of=of,
    )


RESUME_TIP = "Click to copy the command that resumes this session in the directory it ran in."


def sessions_block(worked: Sequence[Session], agent: Path, here: Path) -> Block | None:
    """The sessions that worked on the ticket, each with its session page where it has one and the
    command that resumes it. The label says on this machine because that is the list: a worker on
    another host is not in it (ticket_sessions), and a ticket no session has committed on has no
    block at all.

    Only a page in `agent`, the agent repo the board is in, is linked: the board is served from that
    repo, so a page in another project's has no link that opens there, and its session keeps only
    its resume button."""
    if not worked:
        return None
    linked = {s.id: href(s.page, here) for s in worked if s.page and s.page.resolve().is_relative_to(agent.resolve())}
    return Block("sessions on this machine", worked=tuple(
        Worked(session.title, worked_on(session), linked.get(session.id, ""),
               Copy("resume", "copy resume", RESUME_TIP, session.resume, f"the command resuming {session.title}"))
        for session in worked
    ))


def worked_on(session: Session) -> str:
    """The days a session committed on the ticket: the one day, or the first and the last."""
    return session.first if session.first == session.last else f"{session.first} → {session.last}"


RUN_TIP = "Click to copy the command that runs this file, to paste at the code repo's root."


def artefacts_block(show: Path, code: Path, here: Path) -> Block | None:
    """What the ticket produced to look at: every file in its show directory as a link, and each
    one that runs on a button that copies the command running it from the code repo's root."""
    files = artefacts(show)
    if not files:
        return None
    return Block("artefacts", artefacts=tuple(
        Artefact(str(file.relative_to(show)), href(file, here),
                 Copy("runcopy", "copy command", RUN_TIP, shlex.quote(str(file.relative_to(code))),
                      f"the command that runs {file.name}") if runs(file) else None)
        for file in files
    ))


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


# A graph node's ink by its class, as house tokens: fill, stroke, text, and the stroke's dash
# pattern where it has one. The work that wants the user wears the accent, the rest steps back to
# the edge; ghost is a done ticket shown as context, and proposed is not ruled on: both dashed.
GRAPH_INK = {
    "review": ("wash", "accent", "strong", ""), "open": ("ground-2", "body", "body", ""),
    "claimed": ("ground-2", "muted", "body", ""), "blocked": ("ground", "edge", "muted", ""),
    "proposed": ("ground", "muted", "body", "4 3"), "done": ("ground", "edge", "muted", ""),
    "ghost": ("ground", "edge", "muted", "2 3"),
}


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


# ---- the rows -------------------------------------------------------------
# What the page shows of the tickets, as the values board_page.py holds: every row with the marks it
# wears, the questions it lists and the buttons that copy them, the groups the rows sit in, and the
# trees' pills. The page and the briefing session's state (state_line) are both written from these,
# so a fact a row shows is worked out once.


def view(tickets: list[Ticket], gh: github.Answer = github.NOTHING) -> View:
    """The rows of the board, from the tickets as load_tickets reads them and the states GitHub gave
    the references they name. A group's rows are in sort_key order, and so are the rows folded
    under one."""
    kids = folded_under(tickets)
    made: dict[str, Row] = {}

    def row_of(t: Ticket) -> Row:
        if t.slug not in made:
            under = tuple(row_of(one) for one in sorted(kids.get(t.slug, []), key=sort_key))
            made[t.slug] = shown_row(t, under, kids, gh.states)
        return made[t.slug]

    rows = {t.slug: row_of(t) for t in tickets}
    groups = []
    for state, label in GROUPS:
        held = sorted((rows[t.slug] for t in tickets if rows[t.slug].group == state), key=lambda r: sort_key(r.ticket))
        if held:
            groups.append(Group(state, label, tuple(held), group_copy(held), state == "done"))
    return View(rows, tuple(groups), tuple(pill(tree, tickets) for tree in trees_of(tickets)))


def shown_row(t: Ticket, under: tuple[Row, ...], kids: dict[str, list[Ticket]], gh: dict[str, str]) -> Row:
    """One ticket's row, the rows folded under it already made. A parent ticket at its close-out
    lists its folded child tickets' questions with its own, each under its ticket's slug, since the
    user rules on them with it; a word that finds a folded row finds this one too, since it is the
    row that holds it."""
    asked = [(one, shown_questions(one.status, one.questions)) for one in ruled_with(t, kids)]
    asked = [(one, questions) for one, questions in asked if questions]
    count = sum(len(questions) for _, questions in asked)
    copied = "\n\n".join(copy_text(one.path, questions) for one, questions in asked)
    copy_all = None if count < 2 else Copy(  # one question's own button already copies the ticket's whole list
        "qall", f"copy all {count}", "Click to copy every open question on this row, each under the path of the file it is on.",
        copied,
        f"{count} questions of {asked[0][0].path.name}" if len(asked) == 1 else f"{count} questions of {t.slug}'s tree",
    )
    return Row(
        ticket=t, group=group_of(t), marks=marks_of(t, len(under), gh),
        questions=tuple(asked_of(q, one.path, True, "" if one is t else one.slug) for one, questions in asked for q in questions),
        copied=copied,
        copy_all=copy_all,
        search=search_words(*(part for one in with_folded(t, kids) for part in ticket_words(one))),
        kids=under,
    )


TREE_TIP = "The top-level ticket this one's work is part of. Its pill in the top bar hides and shows the tree's rows."
REVIEW_TIP = "This build's review page: the diff, with a place to write on it (d)."
FREED_TIP = "Builds on {ref}, in review and merged into the parent ticket's branch: this can start before you rule on it."
UNKNOWN_REF = "A pull request or issue this ticket names, on GitHub."


def marks_of(t: Ticket, kin: int, gh: dict[str, str]) -> tuple[Mark, ...]:
    """Every mark on a row, in the order the row shows them: the tree the ticket is part of, its
    slug (a click copies the file's path), what the row asks of the user, the
    count of the `kin` child tickets folded under it, its review page and GitHub references, the
    user's time, the priority, the blockers.

    A GitHub reference wears the state GitHub gave it and says it in words. One GitHub was not asked
    about is a bare link, and the page says why once (absences); one it was asked about and did
    not answer for is bare too, and says nothing further."""
    kind = asks_word(t)
    word, meaning = ASKS[kind]
    return (
        Mark("tree", t.tree, TREE_TIP),
        Mark("slug", t.slug, f"Click to copy the path of the file this row was read from (y):\n{t.path}"),
        Mark("asks", word, meaning, look=kind),
        *([Mark("kin", f"{kin} child ticket{'s' if kin != 1 else ''}",
                KIN_TIP["closed-out" if t.status == "review" else "merged"])] if kin else []),
        *([Mark("rp", "review page", REVIEW_TIP, href=t.diffview)] if t.diffview else []),
        # the issues URL serves a pull request too: GitHub redirects it to the pull page
        *(Mark("gh", ref, github.SAYS.get(state, UNKNOWN_REF), look=state or "unknown",
               href=f"https://github.com/{repo}/issues/{num}")
          for ref in t.gh for repo, num in [ref.split("#")] for state in [gh.get(ref)]),
        Mark("time", SIZES[t.size][0], SIZE_TIP),
        Mark("pri", f"p{t.priority} {PRIORITY[t.priority][0]}", PRIORITY_TIP, look=f"p{t.priority}"),
        *(Mark("chip", ref, FREED_TIP.format(ref=ref) if ref in t.freed
               else f"Waits on {ref}, {'done' if status == 'done' else 'not done yet'}.", look=status, href=ref_anchor(ref))
          for ref, status in t.blocked_by),
    )


def mark(r: Row, kind: MarkKind) -> Mark:
    """The row's first mark of `kind`: one every row wears (a tree, a slug, what it asks, the time,
    the priority), or one the caller knows this row has."""
    found = [m for m in r.marks if m.kind == kind]
    assert found, f"{r.ticket.slug} wears no {kind} mark"
    return found[0]


def wears(r: Row, kind: MarkKind) -> bool:
    return any(m.kind == kind for m in r.marks)


def ticket_words(t: Ticket) -> list[str]:
    """What a filter finds a ticket by: its slug, its name, its brief, every word it reads as
    opened, and the references it names."""
    words = [t.slug, t.title, text_of(t.brief)]
    for b in t.blocks:
        words += [b.label or "", text_of(b.prose)]
        words += [part for q in b.asked for part in (q.tag, text_of(q.headline), text_of(q.detail), text_of(q.ruling))]
        words += [part for s in b.worked for part in (s.title, s.when)]
        words += [a.name for a in b.artefacts]
    return words + t.gh


def search_words(*parts: str) -> str:
    return re.sub(r"\s+", " ", " ".join(parts)).strip().lower()


def text_of(markup: str) -> str:
    """Rendered markup as the words in it, a tag standing for a space."""
    return html.unescape(re.sub(r"<[^>]+>", " ", markup))


def asks(status: str, needs_user: bool, open_question: bool) -> str:
    """Which of ASKS a row asks of the user, from what its ticket file says: a build in review asks
    for a ruling, a proposed ticket for a triage, a ticket stopped on a question of its own for the
    answer, and a ticket the user is in the loop for, the session that is the work.

    That session is asked for whether or not a question of the ticket's is written down yet, since
    sitting down together is the work. A proposed ticket carrying an open question asks for the
    answer, as the needs-me group it sits in does (needs_me)."""
    if status == "review":
        return "review"
    if status == "proposed" and not open_question:
        return "triage"
    if needs_user:
        return "session"
    if open_question and status != "done":
        return "answer"
    return "build"


def asks_word(t: Ticket) -> str:
    """Which of ASKS a row asks of the user, from the row itself: a build folded under its parent
    ticket's row is ruled with the parent."""
    if t.under and t.status == "review":
        return "whole"
    return asks(t.status, t.needs_user, bool(open_questions(t.questions)))


def sort_key(t: Ticket) -> tuple:
    """A row's place within its group: the priority first, then the user's time, then the name."""
    return (t.priority, SIZE_RANK[t.size], t.title.lower())


def open_questions(asked: Sequence[Question]) -> list[Question]:
    """The questions no `Ruled` line answers."""
    return [q for q in asked if not q.ruled]


def group_of(t: Ticket) -> str:
    """Which group a row sits in: the needs-me group where the ticket waits on the user, its status
    otherwise. A row is in one group, so needs me takes a ticket out of its status group, and a row
    folded under its parent ticket's is in none but the parent's (FOLDED)."""
    if t.under:
        return FOLDED
    return "needs" if needs_me(t.status, t.needs_user, t.priority, bool(open_questions(t.questions))) else t.status


FOLDED = "folded"  # the group of a row folded under its parent ticket's, which no heading shows


def shown_questions(status: str, asked: Sequence[Question]) -> list[Question]:
    """The open questions a ticket shows, which is what any button on it copies, on the row and in
    the block an opened row reads as.

    A done ticket shows none: a question still open when the user rules on the build is filed as a
    proposed ticket then (the spec's Decisions), so one left on a done ticket is a leftover."""
    return [] if status == "done" else open_questions(asked)


def group_copy(rows: Sequence[Row]) -> Copy | None:
    """The needs-me group's own copy button: every open question its rows ask at once, for pasting
    into an editor. None for a group whose rows ask nothing, which is every other group. The page's
    script words it again for the rows a filter leaves on show (`recount`), so the count and the
    copy are those of the questions the user sees."""
    asking = [r for r in rows if r.copied]
    if not asking:
        return None
    count = sum(len(r.questions) for r in asking)
    return Copy(
        "qgroup", f"copy all {count} question{'s' if count != 1 else ''}",
        "Click to copy every open question of the rows on show, each under the path of the ticket it is on.",
        "\n\n".join(r.copied for r in asking), f"{count} question{'s' if count != 1 else ''}",
    )


def copy_text(path: Path, asked: Sequence[Question]) -> str:
    """What a copy button puts on the clipboard: the questions, each rewritten as one line of the
    markdown the ticket holds, under the path of the file they are on, so the session taking the
    answer knows where to record it."""
    written = (f"- [{q.tag}] **{q.headline}**" + (f" {q.detail}" if q.detail else "") for q in asked)
    return "\n".join([str(path), *written])


QCOPY_TIP = "Click to copy this question under the path of its ticket, to answer in any session."


def question_tip(q: Question) -> str:
    """A question's own words, since the row shows a headline its column may have to cut short."""
    return f"{q.headline}\n\n{q.detail}" if q.detail else q.headline


def folded_under(tickets: list[Ticket]) -> dict[str, list[Ticket]]:
    """The rows folded under each parent ticket's row, by the parent's slug (board.folded)."""
    kids: dict[str, list[Ticket]] = {}
    for t in tickets:
        if t.under:
            kids.setdefault(t.under, []).append(t)
    return kids


def with_folded(t: Ticket, kids: dict[str, list[Ticket]]) -> list[Ticket]:
    """A row and every row folded under it, however deep."""
    return [t, *(one for kid in kids.get(t.slug, []) for one in with_folded(kid, kids))]


def ruled_with(t: Ticket, kids: dict[str, list[Ticket]]) -> list[Ticket]:
    """The tickets whose questions a row asks: a parent ticket at its close-out asks its folded
    children's with its own, since the user rules on them together; any other row asks its own."""
    return with_folded(t, kids) if t.status == "review" else [t]


def pill(tree: str, tickets: list[Ticket]) -> Pill:
    """A tree's pill. The done count is out of every ticket in the tree, proposed ones included, so
    a breakdown just cut off a parent ticket reads 0/4."""
    inside = in_tree(tickets, tree)
    counts = Counter(t.status for t in inside)
    bits = [f"{counts['done']}/{len(inside)} done"]
    bits += [f"{counts[s]} {s}" for s in ("open", "claimed", "review", "blocked", "proposed") if counts[s]]
    return Pill(
        tree, " · ".join(bits), counts["done"], len(inside), any(group_of(t) == "needs" for t in inside),
        tree_graph(tickets, "" if tree == ALONE else tree),
    )


def trees_of(tickets: list[Ticket]) -> list[str]:
    """Every tree the board shows, in the one order the pills, the graphs and the briefing state all
    take: the named trees, then the lone tickets' pill."""
    named = sorted({t.tree for t in tickets if t.tree})
    return named + ([ALONE] if any(not t.tree for t in tickets) else [])


def in_tree(tickets: list[Ticket], tree: str) -> list[Ticket]:
    """The tickets one of `trees_of`'s trees holds."""
    return [t for t in tickets if (t.tree or ALONE) == tree]


def briefed(said: "briefing.Briefing | None", board: View) -> Briefed:
    """Where things stand and what to take up next, as the briefing session wrote it and when, or
    the board's own count where no session has written one."""
    if not said:
        return Briefed(fallback(board), "the board's own", FALLBACK_TIP)
    # the column shows the day and the hour; the words behind it carry the year, which is what a
    # briefing nobody has replaced in months is read by
    return Briefed(said.text, f"written {said.written:%d %b %H:%M}", f"Written {said.written:%Y-%m-%d %H:%M}.\n{BRIEFING_TIP}")


# How many characters of a tracker's own slugs a column shows before the rest is cut with an
# ellipsis (a tree, a row's own slug) or wraps to a second line (a blocker reference), so a long
# slug costs the row no more than the width those columns were fixed at.
NAME_CAP = 14
REF_CAP = 14


def columns(board: View) -> dict[str, dict[str, int]]:
    """The width in characters of each of a row's fixed columns, for the whole board (`:root`) and
    for each group (`#grp-<state>`) that narrows any of them.

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
    tickets = [r.ticket for r in board.rows.values()]
    page = {
        "tree": min(max([len(t.tree) for t in tickets], default=0), NAME_CAP),
        "slug": min(max([len(t.slug) for t in tickets], default=0), NAME_CAP),
        "asks": max(len(word) for word, _ in ASKS.values()),
        "time": max(len(word) for word, _ in SIZES.values()),
        "pri": max(len(f"p{level} {word}") for level, (word, _) in PRIORITY.items()),
        "chips": min(max([len(ref) for ref in blocker_refs(tickets)], default=2), REF_CAP),
    }
    widths = {":root": page}
    for g in board.groups:
        rows = [one for r in g.rows for one in with_kids(r)]
        own = {
            "time": max([len(mark(r, "time").shows) for r in rows], default=0),
            "pri": max([len(mark(r, "pri").shows) for r in rows], default=0),
            "chips": min(max([len(m.shows) for r in rows for m in r.marks if m.kind == "chip"], default=0), REF_CAP),
        }
        if narrowed := {kind: n for kind, n in own.items() if n < page[kind]}:
            widths[f"#grp-{g.state}"] = narrowed
    return widths


def with_kids(r: Row) -> list[Row]:
    """A row and every row folded under it, however deep."""
    return [r, *(one for kid in r.kids for one in with_kids(kid))]


def blockers_of(t: Ticket) -> list[str]:
    """The blockers one row shows, as the reader sees them written."""
    return [ref for ref, _ in t.blocked_by]


def blocker_refs(tickets: list[Ticket]) -> list[str]:
    """Every blocker the board shows."""
    return [ref for t in tickets for ref in blockers_of(t)]


def gh_shown(tickets: list[Ticket]) -> list[str]:
    """Every pull request and issue the board links, the whole of one render's question for GitHub."""
    return [ref for t in tickets for ref in t.gh]


# ---- page -----------------------------------------------------------------


def render_page(reading: Reading, stamp: str, stamp_src: str) -> str:
    """The board as one page. The rows sit in their groups (GROUPS, done folded), each sorted by
    sort_key. The top bar carries a pill per tree that hides and shows its rows, a filter box that
    narrows the rows to a word, and the scheme switch, which pins one of the house style's two
    schemes where the page otherwise follows the system's (`?theme=day|night` on the address pins
    one for a screenshot). The side column, beside the rows on a wide window and above them on a
    narrow one, holds the briefing over a preview of the dependency graph: the tree of the row under
    the cursor with that ticket marked, or the whole tracker's graph with the edges between trees,
    hidden trees left out. The preview's `full` button, or `?graph` on the address, opens the same
    graph at its own size over the board (OVERLAY); `window` opens it in a window of its own beside
    the board (GRAPH_WINDOW)."""
    board = view(reading.tickets, reading.gh)
    graphs = ""
    for p in board.pills:
        inner = (f'<pre class="mermaid" data-key="g:{p.tree}">{p.graph}</pre>' if p.graph
                 else f'<div class="gnote">nothing in {html.escape(p.tree)} waits on anything</div>')
        graphs += f'<div class="g" data-tree="{html.escape(p.tree)}" hidden>{inner}</div>'
    whole = board_graph(reading.tickets)
    graphs += '<div class="g" data-tree="*" hidden>' + (
        f'<pre class="mermaid" data-key="g:*"></pre><div class="gnote" hidden>every ticket with an edge is in a hidden tree</div>'
        f'<script type="application/json" class="parts">{json.dumps(whole).replace("</", "<\\/")}</script>'
        if whole else '<div class="gnote">nothing waits on anything</div>'
    ) + "</div>"

    log_html = "\n".join(
        f'<span class="hash">{html.escape(line.split(" ")[0])}</span> {html.escape(line.partition(" ")[2])}'
        for line in reading.log.strip().splitlines()
    )
    named = [p.tree for p in board.pills if p.tree != ALONE]
    footmeta = f"{len(reading.tickets)} tickets · {len(named)} parent ticket{'' if len(named) == 1 else 's'} · rendered {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · refreshes on change"
    notes = absences(reading) + [Absence("board-server", UNSERVED, hidden=True), Absence("board-stale", "", hidden=True)]
    return PAGE.substitute(
        overlay=OVERLAY, graphwin=json.dumps(GRAPH_WINDOW).replace("</", "<\\/"), viewjs=VIEW_JS, graphink=json.dumps(GRAPH_INK), copycap=COPY_CAP,
        project=html.escape(reading.project), chips="".join(map(pill_html, board.pills)),
        groups="".join(map(group_html, board.groups)), graphs=graphs, log=log_html,
        columns="".join(column_tokens(selector, widths) for selector, widths in columns(board).items()),
        absences="".join(map(absence_html, notes)), briefing=briefing_html(briefed(reading.briefing, board)),
        footmeta=footmeta, stamp=stamp, stamp_src=html.escape(stamp_src),
    )


def absences(reading: Reading) -> list[Absence]:
    """What this render did without, said once each (the board renders with any optional source
    missing). A board opened as a file opens its review pages as files, where nothing they are
    given is saved, which the page says of itself; a tracker with no review page rendered yet has
    no server to miss, so it says nothing. A machine with no transcripts directory
    has run no session this board could name, whatever the commits say. GitHub says its own absence
    in its own words, since what stopped the query is what the user has to fix (github.ask). A
    briefing already written is no absence whatever the machine has now: the column is not empty,
    and what it says of itself is when it was written.

    The model says its own absence in its own words too: a machine with no claude and a login that
    has lapsed are the same empty column and two different things to fix (briefing.missing)."""
    said = []
    if any(t.diffview for t in reading.tickets):
        said.append(Absence(
            "review-page-server",
            "This board is open as a file, so the review pages it links open as files too and what you "
            "write on one is not saved. Run board to open it served.",
            hidden=True,
        ))
    if not TRANSCRIPTS.is_dir():
        said.append(Absence(
            "transcripts",
            f"No session transcripts at {TRANSCRIPTS}, so no ticket lists the sessions that worked on it.",
        ))
    if reading.gh.missing:
        said.append(Absence("github", reading.gh.missing))
    if reading.briefing is None and (why := briefing.missing()):
        said.append(Absence("model", why))
    return said


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__, prog="board"))
