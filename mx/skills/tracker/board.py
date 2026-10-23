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
from the diffview server over the whole agent repo (`diffview --serve
agent/`), and while it watches it brings that server back on the same port
whenever it exits, so an open tab keeps answering. Where no diffview is
installed or its server does not answer, it opens the file. Served, a review
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
from string import Template
from typing import Annotated, Literal, NoReturn

import markdown
import tyro

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
    """The address the page `out` answers on from the diffview server over the agent repo, or None
    where it can be opened only as a file: the page is outside the agent repo, no diffview is
    installed, or the server does not answer.

    `diffview --serve` is idempotent and prints the server's address, so the port stays diffview's
    to decide, and one that exited comes back on the port it had, which is the one an open page
    knows."""
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
    None where it did not come back: the watcher's part in keeping a served tab answering."""
    return address if answers(address) else served(agent, out)


def answers(address: str) -> bool:
    """Whether a server is listening where `address` points. A connection, not a request: a request
    is what keeps a diffview server from idling out, and this is asked every pass of the watcher."""
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


@dataclass(frozen=True)
class Absence:
    """An optional source the render did without, said once on the page: GitHub, the model, the
    transcripts. A server is one only the open page can tell it lacks, so the notes for the review
    pages' and the board's own are `hidden` and the page shows them."""

    source: str
    words: str
    hidden: bool = False


# ---- an opened ticket -----------------------------------------------------


@dataclass(frozen=True)
class Copy:
    """A button that copies `text`: `word` is what the button itself says, `does` what its click
    does, and `note` what the page says once it has."""

    kind: Literal["qcopy", "qall", "qgroup", "resume", "runcopy"]
    word: str
    does: str
    text: str
    note: str

    @property
    def shows(self) -> str:
        """What it copies, as its hover words carry it: cut off with an ellipsis where it runs past
        COPY_CAP."""
        return self.text if len(self.text) <= COPY_CAP else self.text[:COPY_CAP].rstrip() + "…"


COPY_CAP = 220  # how much of what it copies a button shows before the rest is an ellipsis


@dataclass(frozen=True)
class Asked:
    """One question, as a row lists it or an opened ticket carries it. The headline, the detail and
    the ruling are inline HTML; `says` is the question in full, which the row's headline carries on
    hover since its column may cut it short. `copy` is None where no button copies it: a ruled
    question, or one left on a done ticket. `of` is the slug of the folded child ticket a parent's
    row asks it for, "" for the row's own."""

    tag: str
    headline: str
    detail: str
    ruling: str  # "Ruled <date>: <answer>", "" while it is open
    says: str
    copy: Copy | None
    of: str = ""


@dataclass(frozen=True)
class Worked:
    """A session that worked on the ticket, as an opened ticket lists it."""

    title: str
    when: str  # the days it committed on the ticket
    page: str  # the link to its session page, "" where the board links none
    resume: Copy


@dataclass(frozen=True)
class Artefact:
    """A file of the ticket's show directory, as an opened ticket links it."""

    name: str  # its path inside the show directory
    href: str
    run: Copy | None  # the button copying the command that runs it, for a file that runs


@dataclass(frozen=True)
class Block:
    """One block of an opened ticket: its label, the ticket's own words in it, rendered, and the
    questions, sessions or artefacts it lists. The comments are the block labelled `comments`,
    which the page folds away as history; the words a ticket writes above its first heading are a
    block with no label."""

    label: str | None
    prose: str = ""
    asked: tuple[Asked, ...] = ()
    worked: tuple[Worked, ...] = ()
    artefacts: tuple[Artefact, ...] = ()


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
PAGE_TIP = "This session's page: its turns, the questions it waits on you for, and what it produced. Opens in a new tab."
WHEN_TIP = "When this session first committed on the ticket, and when it last did."


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
# What the page shows of the tickets, as values: every row with the marks it wears, the questions
# it lists and the buttons that copy them, the groups the rows sit in, and the trees' pills. The
# page ("page", below) and the briefing session's state (state_line) are both written from these,
# so a fact a row shows is worked out once.


MarkKind = Literal["tree", "slug", "asks", "kin", "rp", "gh", "time", "pri", "chip"]  # in the order a row shows them


@dataclass(frozen=True)
class Mark:
    """A row mark: the words it shows, and what it says it means on hover. `look` is what dresses
    it beyond its kind: what a row asks, a priority, the state GitHub gave a link, a blocker's
    status. `href` is where a mark that is a link goes."""

    kind: MarkKind
    shows: str
    says: str
    look: str = ""
    href: str = ""


@dataclass(frozen=True)
class Row:
    """One ticket as the board shows it. `group` is the group it sits in, FOLDED for a row folded
    under its parent ticket's, and `kids` are the rows folded under it. `questions` are the open
    questions it lists while folded, `copied` those questions as a copy button puts them on the
    clipboard ("" where it asks none), with `copy_all` copying them once there are two; `search` is
    the words a filter finds it by, its folded rows' included. What it reads as opened is its
    ticket's `blocks`."""

    ticket: Ticket
    group: str
    marks: tuple[Mark, ...]
    questions: tuple[Asked, ...]
    copied: str
    copy_all: Copy | None
    search: str
    kids: tuple["Row", ...]


@dataclass(frozen=True)
class Group:
    """One of the board's groups: its rows in the order it lists them, and the button copying every
    question they ask, which only a group whose rows ask one has. The done group is `folded`."""

    state: str
    label: str
    rows: tuple[Row, ...]
    copy: Copy | None
    folded: bool


@dataclass(frozen=True)
class Pill:
    """A tree's pill in the top bar, which hides and shows its rows: its counts, said in full on
    hover, whether any ticket in it waits on the user, and the dependency graph the side column
    draws for it, None where nothing in it waits on anything."""

    tree: str
    says: str
    done: int
    total: int
    waits: bool
    graph: str | None


@dataclass(frozen=True)
class View:
    """The board as values: every ticket's row by slug, the ones folded under another's included,
    the groups that hold a row in the order the page shows them, and a pill per tree."""

    rows: dict[str, Row]
    groups: tuple[Group, ...]
    pills: tuple[Pill, ...]


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

TAG_TIP = (
    "The ticket's own numbering for this question.\n"
    "A session that takes your answer records it under this tag as a `Ruled <date>:` line, which is "
    "what clears the question from the board."
)


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


@dataclass(frozen=True)
class Briefed:
    """The head of the side column: the briefing as markdown, when it was written as the column
    shows it, and the words that says on hover."""

    text: str
    when: str
    says: str


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
# The values as markup. What a ticket writes in prose reaches them already rendered (render_body),
# a criterion's checkbox included (ticked).


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


def group_html(g: Group) -> str:
    return (
        f'<details class="grp" id="grp-{g.state}" data-state="{g.state}"{"" if g.folded else " open"}>'
        f'<summary><h2>{g.label} <span class="n">{len(g.rows)}</span>{copy_html(g.copy) if g.copy else ""}</h2></summary>'
        f'<div class="tickets">{"".join(map(row_html, g.rows))}</div></details>'
    )


def row_html(r: Row) -> str:
    """One ticket row, every mark in a fixed column: the tree, the slug and what the row asks, then
    the name with the marks of its line, the brief under it and, while the row is folded, the open
    questions under that; then the user's time, the priority and the blockers, which move under the
    name below a width. The rows folded under it, then the ticket's remaining text, fold under the
    row."""
    t = r.ticket

    def some(*kinds: MarkKind) -> str:
        return "".join(mark_html(m) for m in r.marks if m.kind in kinds)

    brief = f'<span class="brief">{t.brief}</span>' if t.brief else ""
    inner = f'<div class="kids">{"".join(map(row_html, r.kids))}</div>' if r.kids else ""
    return (
        row_open(r) + some("tree", "slug", "asks")
        + f'<span class="main"><span class="titleline"><span class="title" data-tip="{html.escape(t.title)}">{clipped(t.title)}</span>'
        f'{some("kin", "rp", "gh")}</span>{brief}{asks_html(r)}</span>'
        f'<span class="meta">{some("time", "pri")}<span class="chips">{some("chip")}</span></span>'
        f'</summary>{inner}<div class="body">{"".join(map(block_html, t.blocks))}</div></details>'
    )


def row_open(r: Row) -> str:
    """The element every row is: what the page's script matches a row on, the file a click on its
    slug copies, and the questions it asks, which the needs-me group's button copies while the row
    is on show."""
    t = r.ticket
    asked = f' data-asks="{len(r.questions)}" data-asked="{html.escape(r.copied)}"' if r.copied else ""
    return (
        f'<details class="ticket row-{t.status}" id="t-{t.slug}" data-tree="{html.escape(t.tree or ALONE)}" '
        f'data-slug="{html.escape(t.slug)}" data-search="{html.escape(r.search)}" data-path="{html.escape(str(t.path))}"{asked}><summary>'
    )


# Each mark's element by its kind. A tree or a slug clips its words to its column inside an element
# of its own, since a box that hides its overflow would hide its own hover words too.
MARK_HTML = {
    "tree": '<span class="tree" data-tip="{says}">{clipped}</span>',
    "slug": '<span class="slug" data-tip="{says}">{clipped}</span>',
    "asks": '<span class="asks a-{look}" data-tip="{says}">{shows}</span>',
    "kin": '<span class="kin" data-tip="{says}">{shows}</span>',
    "rp": '<a class="rp" href="{href}" target="_blank" onclick="event.stopPropagation()" data-tip="{says}">{shows}</a>',
    "gh": '<a class="gh {look}" href="{href}" target="_blank" onclick="event.stopPropagation()" data-tip="{says}">{shows}</a>',
    "time": '<span class="time" data-tip="{says}">{shows}</span>',
    "pri": '<span class="pri {look}" data-tip="{says}">{shows}</span>',
    "chip": '<a class="chip {look}" href="{href}" onclick="event.stopPropagation()" data-tip="{says}">{shows}</a>',
}


def mark_html(m: Mark) -> str:
    return MARK_HTML[m.kind].format(
        shows=html.escape(m.shows), says=html.escape(m.says), look=html.escape(m.look), href=html.escape(m.href),
        clipped=clipped(m.shows),
    )


def clipped(text: str) -> str:
    """A mark's words, cut off with an ellipsis where its column is too narrow."""
    return clipped_html(html.escape(text))


def clipped_html(markup: str) -> str:
    """The same, for words already rendered: a question's headline carries code and emphasis."""
    return f'<span class="clip">{markup}</span>'


def asks_html(r: Row) -> str:
    """The open questions under a folded row: each one's tag and headline with the button that
    copies it, a folded child's under its slug, and the row's copy-all.

    The page's style hides the list while the row is open, where the block below and the rows
    folded under it carry the same questions, so an opened row shows each of them once."""
    if not r.questions:
        return ""
    lines = "".join(
        f'<span class="q"><span class="qtag" data-tip="{html.escape(TAG_TIP)}">'
        + (f"{html.escape(q.of)} " if q.of else "") + f"{q.tag}</span>"
        f'<span class="qhead" data-tip="{html.escape(q.says)}">{clipped_html(q.headline)}</span>'
        + copy_html(q.copy) + "</span>"
        for q in r.questions
    )
    return f'<span class="qs">{lines}' + (copy_html(r.copy_all) if r.copy_all else "") + "</span>"


def copy_html(c: Copy) -> str:
    """A button that copies and says so: what it copies is its hover words, and its note is what
    the page's own note says once it has. It is a span, as the row's number is, since the page
    handles the click itself."""
    return (f'<span class="copier {c.kind}" data-copy="{html.escape(c.text)}" data-copied="{html.escape(c.note)}" '
            f'data-tip="{html.escape(c.does)}\n\n{html.escape(c.shows)}">{html.escape(c.word)}</span>')


def block_html(b: Block) -> str:
    """One block of an opened ticket. The comments are folded, so they open only when the reader
    asks for them: the conversation on a ticket and a build's closing comment are what happened,
    not what the ticket is."""
    if b.label == "comments":
        return f'<details class="history"><summary><span class="label">comments</span></summary>{b.prose}</details>'
    label = f'<p class="label">{html.escape(b.label)}</p>' if b.label else ""
    asked = "".join(
        f'<li class="question{" ruled" if q.ruling else ""}">'
        f'<span class="tag" data-tip="{html.escape(TAG_TIP)}">{q.tag}</span><div>'
        f'<p class="head">{q.headline}</p>'
        + (f'<p class="detail">{q.detail}</p>' if q.detail else "")
        + (f'<p class="ruling">{q.ruling}</p>' if q.ruling else "")
        + "</div>" + (copy_html(q.copy) if q.copy else "") + "</li>"
        for q in b.asked
    )
    worked = "".join(
        f'<li><span class="stitle">{html.escape(s.title)}</span>'
        f'<span class="when" data-tip="{html.escape(WHEN_TIP)}">{html.escape(s.when)}</span>'
        + (f'<a class="spage" href="{html.escape(s.page)}" target="_blank" data-tip="{html.escape(PAGE_TIP)}">page</a>' if s.page else "")
        + copy_html(s.resume) + "</li>"
        for s in b.worked
    )
    made = "".join(
        f'<li><a href="{html.escape(a.href)}" target="_blank">{html.escape(a.name)}</a>'
        + (copy_html(a.run) if a.run else "") + "</li>"
        for a in b.artefacts
    )
    lists = "".join(f'<ul class="{kind}">{items}</ul>' for kind, items in
                    (("asked", asked), ("sessions", worked), ("artefacts", made)) if items)
    return f'<section class="block">{label}{b.prose}{lists}</section>'


def pill_html(p: Pill) -> str:
    # the dot says the tree holds work of the user's own; the counts beside it already say how much
    dot = '<i class="dot"></i>' if p.waits else ""
    return (
        f'<button class="treechip" data-tree="{html.escape(p.tree)}" title="{html.escape(p.says)}">{dot}{html.escape(p.tree)} '
        f'<span class="dim">{p.done}/{p.total}</span></button>'
    )


def briefing_html(b: Briefed) -> str:
    return (
        f'<div class="bhead"><span class="label">briefing</span>'
        f'<span class="bwhen" title="{html.escape(b.says)}">{html.escape(b.when)}</span></div>'
        f'<div class="btext">{markdown.markdown(b.text)}</div>'
    )


def absence_html(a: Absence) -> str:
    return f'<p class="absent" data-absent="{html.escape(a.source)}"{" hidden" if a.hidden else ""}>{html.escape(a.words)}</p>'


PADDING = {"asks": 0.85, "pri": 0.95}  # the tag's border and the pill's, which sit outside the words


def column_tokens(selector: str, widths: dict[str, int]) -> str:
    """Column widths as the CSS tokens the row's grid reads."""
    return f"  {selector} {{\n" + "".join(
        f"    --col-{kind}: calc({count} * var(--mark-char) + {PADDING.get(kind, 0)}rem);\n"
        for kind, count in widths.items()
    ) + "  }\n"


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


# The page's stylesheet: the house tokens, then the board's own rules. `${columns}` is where PAGE
# puts the widths of a row's fixed columns (board.columns).
STYLE = r"""  /* The house tokens, copied from mx/skills/house-style/tokens.css: colours as light-dark() pairs,
     the fonts, and the base rules. The type roles there are for a page of prose; a board sets its
     own below. --muted goes darker than the house value, which is a day-scheme readability fix:
     the board's small text is read on parchment at 100% zoom. */
  :root {
    color-scheme: light dark;
    --ground: light-dark(#f4e4cd, #14110e);
    --ground-2: light-dark(#eddabe, #1b1713);
    --edge: light-dark(#cfbca3, #463f37);
    --muted: light-dark(#4c443c, #b0a89e);
    --body: light-dark(#37261d, #ede3d2);
    --strong: light-dark(#22140b, #faf2dc);
    --accent: light-dark(#426724, #75a252);
    --accent-2: light-dark(#674806, #cdb78a);
    --wash: light-dark(rgb(66 103 36 / 0.16), rgb(117 162 82 / 0.22));
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
  /* the row's fixed columns, each as wide as the widest mark that lands in it (board.columns) */
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
  .row-done > summary .title, .row-blocked > summary .title, .row-proposed > summary .title { color: var(--muted); }
  .titleline > a { flex: none; }
  .brief { color: var(--muted); font-size: .88rem; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ticket[open] > summary .brief { white-space: normal; }
  /* a needs-me row's open questions, under the name they belong to; an opened row reads them in
     its questions block instead */
  .qs { display: grid; gap: .15rem; justify-items: start; padding: .2rem 0 .1rem; min-width: 0; }
  .ticket[open] > summary .qs { display: none; }
  .q { display: flex; gap: .5rem; align-items: baseline; max-width: 100%; min-width: 0; }
  .qtag, .asked .tag { flex: none; font-family: var(--font-mono); font-size: .74rem; color: var(--c-rose); }
  .qhead { color: var(--body); font-size: .88rem; min-width: 0; }
  .copier { flex: none; font-family: var(--font-mono); font-size: .72rem; color: var(--muted);
    border: 1px solid var(--edge); border-radius: 4px; padding: 0 .35rem; cursor: copy; overflow: visible; }
  .copier:hover { color: var(--accent); border-color: var(--accent); }
  .meta { display: contents; }
  .asks, .pri, .time, .rp, .gh, .kin { font-size: .78rem; white-space: nowrap; }
  .chip { font-size: .78rem; }
  .asks { grid-area: asks; --c: var(--muted); color: var(--c); justify-self: start; max-width: 100%;
    background: color-mix(in srgb, var(--c) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--c) 38%, transparent); border-radius: 4px; padding: 0 .4rem; }
  .a-review { --c: var(--c-gold); }
  .a-answer { --c: var(--c-rose); }
  .a-session { --c: var(--c-purple); }
  .a-build { background: none; border-color: transparent; padding-left: 0; }
  .a-whole { --c: var(--muted); }
  .kin { color: var(--muted); }
  /* the rows folded under a parent ticket's row, set in by the rule the opened body carries: a
     row's fixed columns leave the name no width to give up to a deeper indent on a narrow window */
  .kids { margin-left: .5rem; border-left: 1px solid var(--edge); }
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
  .sessions .spage { flex: none; font-size: .82rem; }
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
<script type="importmap">
{"integrity": {
  "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.2.2/dist/mermaid-layout-elk.esm.min.mjs": "sha256-xBkLW+qMellY+DuZMpYPTCrktZEq5EF2eXDqaqcznEU=",
  "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.2.2/dist/chunks/mermaid-layout-elk.esm.min/chunk-SP2CHFBE.mjs": "sha256-OlxTRTJXQsIIjtqqpnZh8ACC0go+GQLkhkrF/rXpGPk=",
  "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.2.2/dist/chunks/mermaid-layout-elk.esm.min/render-FL5BWEWF.mjs": "sha256-Hnzk53loGUiOW5BNdXfD72ZHqAiFm6ndvA8CAGoQZns="
}}
</script>
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
""" + STYLE + r"""</style>
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
    <div class="gnote" id="gunloaded" hidden>the graph could not load: its engine, from cdn.jsdelivr.net, did not arrive, or arrived other than its pinned copy</div>
    <div class="gnote" id="gundrawn" hidden>the graph could not be drawn: a piece of its engine, from cdn.jsdelivr.net, did not arrive, or arrived other than its pinned copy; a reload tries again</div>
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
  // Synchronous state restore, before first paint. The module below runs once the page has
  // parsed; doing any of this there makes every reload visibly collapse the groups and drop
  // expanded tickets for a beat.
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
  // The graph engine and its layout come from the CDN the first time a graph is drawn, so a board
  // with no way to the CDN loses its graph and nothing else. A failed load is not retried. Every
  // file is pinned by hash, the layout's chunks through the import map in the head: the local server
  // that opens this page also serves every agent directory to it, so a file changed at the CDN is
  // refused, and the board says the engine did not arrive. mermaid comes as its one-file classic build, which needs
  // one pin where its module build would need one per chunk.
  const MERMAID = ["https://cdn.jsdelivr.net/npm/mermaid@11.17.2/dist/mermaid.min.js",
                   "sha256-WB7X10vZBI0OOpE2OSfXLvIpQtdyJUayf3zCnjU5Drg="];
  const ELK = "https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.2.2/dist/mermaid-layout-elk.esm.min.mjs";
  const classic = ([src, integrity]) => new Promise((loaded, failed) => {
    const s = Object.assign(document.createElement("script"), { src, integrity, crossOrigin: "anonymous" });
    // the classic build draws every .mermaid on the page at window load unless told not to
    s.onload = () => { globalThis.mermaid.startOnLoad = false; loaded(globalThis.mermaid); };
    s.onerror = () => failed(new Error("refused or missing: " + src));
    document.head.append(s);
  });
  let mermaid = null, loading = null;
  function engine() {
    if (loading) return loading;
    loading = Promise.all([classic(MERMAID), import(ELK)]).then(([m, elk]) => {
      mermaid = m;
      mermaid.registerLayoutLoaders(elk.default);
      setupMermaid();
      return mermaid;
    });
    loading.catch((e) => console.error("the graph engine did not load:", e));
    return loading;
  }
  const drawable = () => engine().then(() => true, () => false);
  const unloaded = document.getElementById("gunloaded"), undrawable = document.getElementById("gundrawn");
  // the engine fetches the rest of itself while it draws, so a draw can fail after the engine loaded
  const drawOf = (id, src) => mermaid.render(id, src + "\n" + classDefs)
    .catch((e) => console.error("the graph did not draw:", e));

  // What the two full size views do, shared with the window of its own, which runs its own copy
  // (board.VIEW_JS).
${viewjs}

  // Mermaid bakes the colours into the SVG, and a light-dark() token never resolves through
  // getPropertyValue, so every colour is read off a probe element in the scheme on show, and read
  // again when the scheme switches. A node's class names its tokens (board.GRAPH_INK).
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
    const ink = (token) => hex(rgb("--" + token), ground);
    const c = Object.fromEntries(["ground", "edge", "muted", "body"].map((n) => [n, ink(n)]));
    classDefs = Object.entries(${graphink}).map(([s, [fill, stroke, text, dash]]) =>
      "  classDef " + s + " fill:" + ink(fill) + ",stroke:" + ink(stroke) + ",color:" + ink(text) +
      (dash ? ",stroke-dasharray:" + dash : "")).join("\n");
    // SVG text labels, not HTML ones: mermaid switches an HTML label into wrapping
    // mode only when its measured width equals the wrap width exactly, and the
    // measurement misses by a fraction of a pixel at any page zoom other than 100%
    // and at some device scale factors (1.75 and 2.225, though not 1.25 or 2), so
    // every long label stays on one line and clips (mermaid-js/mermaid#7794).
    // SVG labels wrap by mermaid's own measure.
    mermaid?.initialize({
      startOnLoad: false, suppressErrorRendering: true, layout: "elk", securityLevel: "loose", theme: "base", htmlLabels: false,
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
    // What is drawn already, or restored from the svg cache, is left as it is; the composed graph
    // with every tree hidden has no source, and its note shows instead.
    const undrawn = () => [...document.querySelectorAll(".g:not([hidden]) .mermaid")]
      .filter((el) => !el.querySelector("svg") && el.textContent.trim());
    const drawn = !undrawn().length || await drawable();
    // asked again after the wait, which can outlast the cursor's stay on the graph that started it
    unloaded.hidden = drawn || !undrawn().length;
    for (const el of drawn ? undrawn() : []) {
      if (el.querySelector("svg")) continue;  // drawn by a call that started before this one
      el.dataset.src = el.textContent;
      const done = await drawOf("m" + Date.now() + "_" + seq++, el.dataset.src);
      // a failed graph is left undrawn, so the next call tries it again
      if (!done) { el.dataset.failed = ""; continue; }
      delete el.dataset.failed;
      el.innerHTML = done.svg;
      nodeHover(el);
    }
    undrawable.hidden = !document.querySelector(".g:not([hidden]) .mermaid[data-failed]");
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
      const n = g.querySelectorAll(":scope > .tickets > .ticket:not(.off):not(.miss)").length;
      g.querySelector(".n").textContent = n;
      g.classList.toggle("empty", n === 0);
    }
    for (const c of rowsEl.querySelectorAll(".qgroup")) recount(c);
    for (const b of document.querySelectorAll(".treechip")) b.classList.toggle("off", off.has(b.dataset.tree));
    localStorage.setItem("board-off:" + document.title, JSON.stringify([...off]));
    if (cur && (cur.classList.contains("off") || cur.classList.contains("miss"))) setCur(null);  // a hidden tree takes its row, and its graph, with it
    showGraph();
  }

  // The needs-me group's copy button, worded as group_copy words it for the rows a filter leaves on
  // show, and gone while none of them asks a question.
  function recount(c) {
    const asking = [...c.closest("details.grp").querySelectorAll(":scope > .tickets > .ticket[data-asked]:not(.off):not(.miss)")];
    const n = asking.reduce((sum, t) => sum + Number(t.dataset.asks), 0), text = asking.map((t) => t.dataset.asked).join("\n\n");
    const counted = n + " question" + (n === 1 ? "" : "s");
    const shows = text.length <= ${copycap} ? text : text.slice(0, ${copycap}).trimEnd() + "…";
    Object.assign(c.dataset, { copy: text, copied: counted, tip: c.dataset.tip.split("\n\n")[0] + "\n\n" + shows });
    c.textContent = "copy all " + counted;
    c.hidden = !n;
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
    // a failure is kept too: the window of its own asks every second, and only a reload can mend it
    if (!(key in fullCache)) {
      const done = await drawOf("gf" + Date.now() + "_" + seq++, src);
      if (!done) return fullCache[key] = "";
      const box = document.createElement("div");
      box.innerHTML = done.svg;
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
    const draw = g.src && await drawable(), svg = draw ? await svgFor(g.src) : "";
    const note = !g.src ? g.note : !draw ? unloaded.textContent : !svg ? undrawable.textContent : g.note;
    return {
      key: [g.name, g.mode, g.theme, g.src, note].join("|"), name: g.name, mode: g.mode,
      theme: g.theme, note, cur: g.cur, svg,
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
  // It talks to the board by message rather than by reaching into it. A board opened as a file has
  // an opaque origin, and a reload mints another one: from the reload on, the window's
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

  // opened as a file, the review pages it links cannot save either, which the page says of itself
  const served = location.protocol !== "file:";
  if (!served) document.querySelector("[data-absent=review-page-server]")?.removeAttribute("hidden");
  const gone = document.querySelector("[data-absent=board-server]");
  const stale = document.querySelector("[data-absent=board-stale]");
  let unanswered = 0;

  // Reload only when the renderer wrote different content. fetch() is blocked on
  // file://, but a classic script tag isn't — so poll the sidecar stamp file the
  // renderer writes beside this page.
  function poll() {
    const s = document.createElement("script");
    s.src = document.body.dataset.stampSrc + "?" + Date.now();
    s.onload = () => {
      s.remove();
      unanswered = 0;
      gone.hidden = true;
      stale.textContent = window.__boardStale || "";
      stale.hidden = !window.__boardStale;
      if (window.__boardStamp !== document.body.dataset.stamp) { saveState(); location.reload(); }
      else setTimeout(poll, 5_000);
    };
    // opened as a file, no sidecar: stay current the blunt way. Served, the server is between an exit
    // and the watcher bringing it back on this port, and a reload now would land on an error page;
    // three polls unanswered say so on the page, since a tab left behind shows nothing else.
    s.onerror = () => {
      s.remove();
      if (!served) { saveState(); location.reload(); return; }
      gone.hidden = ++unanswered < 3;
      setTimeout(poll, 5_000);
    };
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
