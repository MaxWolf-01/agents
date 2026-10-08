#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright"]
# ///
"""Lay down the demo project, render its board and one review page, and shoot both into mx/assets.

The screenshots in the mx README are of a real render, not a mockup: this builds a throwaway
project under /var/tmp from `fixture.py` (its code, branch by branch) and `tracker/` (its ticket
files as they end up), with the agent repo at `agent/` holding the tickets, the show directories,
a prototype and the sessions' commits, and a CLAUDE_CONFIG_DIR beside it holding those sessions'
transcripts. It then runs `board` and `diffview` against it, screenshots what they produce, and
puts every PNG through `compress.py`. Re-run it whenever either tool's output changes.

`diffview` comes from PATH; without it the board shots still build, with no review links on the
rows, and review-page.png is removed rather than left stale.
"""

import functools
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "mx" / "skills" / "tracker"))
import fixture as F  # noqa: E402
from briefing import cache_path  # noqa: E402

HERE = Path(__file__).parent
ASSETS = HERE.parents[2] / "mx" / "assets"
COMPRESS = HERE.parent / "compress.py"
BIN = HERE.parents[2] / "mx" / "bin"  # this checkout's board and tracker, not whichever is on PATH
DEMO = Path("/var/tmp/mx-demo")
REPO = DEMO / "ledger"
AGENT = REPO / "agent"
CLAUDE = DEMO / "claude"  # the CLAUDE_CONFIG_DIR the sessions' transcripts are in
CHROMIUM = shutil.which("chromium")
WIDE = 1440  # past the board's 1400px breakpoint, where the graph panel sits beside the rows
TALL = 1400  # the side column scrolls inside the window, so a short one would cut its graph off
PAD = 24  # breathing room under the lowest element a shot is clipped to
SCHEMES = {"light": "-light", "dark": ""}  # the suffixes render.py gives the other figures

# The sessions whose commits wrote the ticket files: (title, the directory it ran in). Two ran in
# a worktree dispatch has since removed, as every orchestrator's does; the worker ran on another
# host and has no transcript here, so the board leaves it out.
SESSIONS = {
    "3f9c1e7a-52b4-4d0e-9a61-8c2f7b3d5e10": ("Grilling the CSV import", REPO),
    "8a4d2b6c-1e7f-4c39-b5a0-6d9e2f4a1c83": ("Dispatching csv-import", f"{REPO}-csv-import"),
    "c51e7f03-9b2a-4e68-8d14-3a7c6b9e0f25": ("Grilling saved views", REPO),
    "e7b2940d-6c1f-4a85-9e3b-2d8f5c7a1b96": ("Three takes on the view list", REPO),
    "4b8e1c6f-3d2a-4f97-a0c5-7e9b1d3f6a48": ("Dispatching saved-views", f"{REPO}-saved-views"),
    "9d3a6f2e-8b1c-4e50-b7d9-1f4c8a2e6b07": ("Triage after the long weekend", REPO),
}
GRILL_CSV, ORCH_CSV, GRILL_VIEWS, PROTO, ORCH_VIEWS, TRIAGE = SESSIONS
WORKER = "a06f5d29-7c3e-4b1a-8f62-5e0d9c4b7a31"  # a worker on another host

# The review pages: (title, summary) per ticket with a range. The first is the one shot.
REVIEWS = {
    "upload-and-parse-report": (
        "upload-and-parse-report",
        "The upload gets a report instead of a row list: every line the mapping could not read comes back "
        "with its number and the reason, so the account holder sees the whole statement before anything is "
        "committed. The hinge of csv-import: the mapping and the commit both read this shape."),
    "csv-import": (
        "csv-import, closed out",
        "The whole tree: the parse report, the per-bank mapping and the commit behind its dry run, with the "
        "close-out's one fix. Ruled whole."),
    "map-columns-to-fields": ("map-columns-to-fields", "A bank's corrected mapping is remembered for its next statement."),
    "commit-the-import": ("commit-the-import", "Entries are written after a dry run that says what a commit adds and skips."),
    "filters-as-data": ("filters-as-data", "The filter bar's state as one value with a round trip to text."),
    "flaky-export-test": ("flaky-export-test", "The export test writes into memory, so a slow disk cannot fail it."),
}


# ---- the code repo ---------------------------------------------------------


def git(repo: Path, *args: str, when: str | None = None) -> str:
    """git off the machine's identity, hooks and signing key, so nothing of this host's lands in
    the demo's history."""
    env = os.environ | {"GIT_AUTHOR_NAME": "demo", "GIT_AUTHOR_EMAIL": "demo@example.invalid",
                        "GIT_COMMITTER_NAME": "demo", "GIT_COMMITTER_EMAIL": "demo@example.invalid"}
    if when:
        env |= {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    return run("git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args, cwd=repo, env=env)


def run(*args: str, cwd: Path = REPO, env: dict | None = None) -> str:
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)
    if done.returncode:
        sys.exit(f"{' '.join(map(str, args))} failed ({done.returncode}) in {cwd}:\n{done.stdout}\n{done.stderr}")
    return done.stdout.strip()


def write(root: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)


def commit(repo: Path, message: str, when: str, session: str | None = None) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message, *(["-m", f"Session: {session}"] if session else []), when=when)
    return git(repo, "rev-parse", "--short", "HEAD")


def built(slug: str, onto: str, files: dict[str, str], message: str, when: str, merged: str) -> str:
    """A worker's ticket branch cut from `onto`, its one commit, and the orchestrator's `--no-ff`
    merge back into `onto`: the range the ticket's `diff:` names."""
    base = git(REPO, "rev-parse", "--short", onto)
    git(REPO, "checkout", "-q", "-b", f"ticket/{slug}", onto)
    write(REPO, files)
    tip = commit(REPO, message, when)
    git(REPO, "checkout", "-q", onto)
    git(REPO, "merge", "-q", "--no-ff", "-m", f"{slug}: merged into {onto}", f"ticket/{slug}", when=merged)
    return f"code@{base}..{tip}"


def build_code() -> dict[str, list[str]]:
    """The code repo as dispatch would have left it: csv-import closed out on its own branch,
    saved-views' first slice merged into its, the export fix on a ticket branch waiting on a
    ruling, and main still the app before any of it. Answers with each ticket's ranges."""
    git(REPO, "init", "-q", "-b", "main")
    write(REPO, {"GLOSSARY.md": F.GLOSSARY, "Makefile": F.MAKEFILE,
                 ".gitignore": "agent/\n__pycache__/\n.pytest_cache/\n"})
    write(REPO, F.SKELETON)
    commit(REPO, "ledger: accounts, entries, and the CSV export the old screen offered", "2026-09-01T10:04:00+02:00")
    write(REPO, F.PIN)
    main = commit(REPO, "Pin the interpreter to 3.13", "2026-09-11T09:40:00+02:00")

    ranges: dict[str, list[str]] = {}
    git(REPO, "checkout", "-q", "-b", "csv-import")
    write(REPO, F.SEAM)
    commit(REPO, "csv-import: the parse report's seam, stubbed", "2026-09-16T11:02:00+02:00")
    ranges["upload-and-parse-report"] = [built(
        "upload-and-parse-report", "csv-import", F.PARSE_REPORT,
        "upload-and-parse-report: every line the mapping could not read, with its number",
        "2026-09-17T10:20:00+02:00", "2026-09-17T16:45:00+02:00")]
    git(REPO, "branch", "-q", "-D", "ticket/upload-and-parse-report")  # a hinge, accepted: its branch went with the merge
    ranges["map-columns-to-fields"] = [built(
        "map-columns-to-fields", "csv-import", F.MAPPING,
        "map-columns-to-fields: a bank's mapping is remembered for its next statement",
        "2026-09-20T14:12:00+02:00", "2026-09-20T15:30:00+02:00")]
    ranges["commit-the-import"] = [built(
        "commit-the-import", "csv-import", F.COMMIT,
        "commit-the-import: entries, after a dry run that says what will be skipped",
        "2026-09-23T11:05:00+02:00", "2026-09-23T12:10:00+02:00")]
    write(REPO, F.SETTLED)
    tip = commit(REPO, "csv-import: the dry run's already-settled branch had no test", "2026-09-24T10:30:00+02:00")
    ranges["csv-import"] = [f"code@{main}..{tip}"]

    git(REPO, "checkout", "-q", "-b", "saved-views", "main")
    ranges["filters-as-data"] = [built(
        "filters-as-data", "saved-views", F.FILTERS,
        "filters-as-data: the filter bar's state as one value",
        "2026-09-25T09:50:00+02:00", "2026-09-25T11:15:00+02:00")]

    git(REPO, "checkout", "-q", "-b", "ticket/flaky-export-test", "main")
    write(REPO, F.STEADY)
    tip = commit(REPO, "flaky-export-test: the export test writes into memory", "2026-09-26T09:15:00+02:00")
    ranges["flaky-export-test"] = [f"code@{main}..{tip}"]

    for branch in ("csv-import", "saved-views", "ticket/flaky-export-test", "main"):
        git(REPO, "checkout", "-q", branch)
        verify(branch)
    return ranges


def verify(branch: str) -> None:
    """Run the demo's own suite: a worked example that does not pass teaches the wrong thing."""
    done = subprocess.run(["uv", "run", "--quiet", "--with", "pytest", "pytest", "-q", "-p", "no:cacheprovider"],
                          cwd=REPO, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"the demo's suite fails on {branch}:\n{done.stdout}\n{done.stderr}")
    print(f"{branch}: {done.stdout.strip().splitlines()[-1]}")


# ---- the agent repo --------------------------------------------------------


def ticket(slug: str, ranges: dict[str, list[str]], status: str | None = None, comments: bool = True) -> str:
    """A ticket file as `tracker/` ends it, with its ranges stamped; earlier in its history, at
    another status and before a closing comment reached it."""
    text = (HERE / "tracker" / f"{slug}.md").read_text()
    if slug in ranges:
        end = text.index("\n---", 3)
        text = text[:end] + f"\ndiff: [{', '.join(ranges[slug])}]" + text[end:]
    if status:
        text = re.sub(r"^status: \w+$", f"status: {status}", text, count=1, flags=re.M)
    if not comments:
        text = text.split("\n## Comments\n")[0].rstrip() + "\n"
    return text


def tickets(ranges: dict[str, list[str]], *specs: str | tuple) -> dict[str, str]:
    """`tickets/<slug>.md` for each spec: a slug for its final text, or (slug, status[, comments])."""
    files = {}
    for spec in specs:
        slug, *how = (spec,) if isinstance(spec, str) else spec
        files[f"tickets/{slug}.md"] = ticket(slug, ranges, *how)
    return files


def reported(slug: str, ranges: dict[str, list[str]], when: str, merged: str) -> None:
    """The worker's report, committed on its ticket branch of the agent repo and merged into the
    branch that repo has out, which is where a child ruled with its parent puts its agent side."""
    base = git(AGENT, "rev-parse", "--short", "HEAD")
    git(AGENT, "checkout", "-q", "-b", f"ticket/{slug}")
    text = ticket(slug, {})
    report = "\n".join(part.strip() for part in re.findall(r"(?ms)^## (?:Questions|Comments)\n.*?(?=^## |\Z)", text))
    write(AGENT, {f"show/{slug}/report.md": report + "\n"})
    tip = commit(AGENT, f"{slug}: the report", when, WORKER)
    git(AGENT, "checkout", "-q", "main")
    git(AGENT, "merge", "-q", "--no-ff", "-m", f"{slug}: its report, merged", f"ticket/{slug}", when=merged)
    ranges[slug].append(f"agent@{base}..{tip}")


def build_agent(ranges: dict[str, list[str]]) -> None:
    """The agent repo's history: every commit that wrote a ticket file, by the session that wrote
    it, which is what an opened ticket lists its sessions from."""
    git(AGENT, "init", "-q", "-b", "main")
    write(AGENT, {".gitignore": "board.html*\ndiffviews/\nsessions/\n.serve.*\n"})
    t = functools.partial(tickets, ranges)
    step = lambda files, msg, when, sid: (write(AGENT, files), commit(AGENT, msg, when, sid))  # noqa: E731

    step(t(("flaky-export-test", "open", False), "retire-the-legacy-exporter", "name-the-categories",
           ("pin-the-python-version", "open")),
         "tickets: filed at triage", "2026-09-10T09:12:00+02:00", TRIAGE)
    step(t("pin-the-python-version"), "pin-the-python-version: done", "2026-09-11T09:45:00+02:00", TRIAGE)
    step(t(("csv-import", "open", False), ("duplicate-rule", "open")),
         "csv-import: grilled; the parent ticket and its duplicate rule", "2026-09-12T15:30:00+02:00", GRILL_CSV)
    step(t(("upload-and-parse-report", "proposed", False), ("map-columns-to-fields", "proposed", False),
           ("commit-the-import", "proposed", False)),
         "csv-import: cut into its slices", "2026-09-14T10:05:00+02:00", GRILL_CSV)
    step(t("duplicate-rule", ("upload-and-parse-report", "open", False), ("map-columns-to-fields", "open", False),
           ("commit-the-import", "open", False)),
         "csv-import: D1 ruled, the slices ruled open", "2026-09-16T09:20:00+02:00", GRILL_CSV)
    step(t(("csv-import", "claimed", False), ("upload-and-parse-report", "claimed", False)),
         "csv-import: claimed for its tree; upload-and-parse-report claimed", "2026-09-16T11:00:00+02:00", ORCH_CSV)
    step(t("upload-and-parse-report", ("map-columns-to-fields", "claimed", False)),
         "upload-and-parse-report: accepted, merged into csv-import", "2026-09-17T16:50:00+02:00", ORCH_CSV)
    step(t(("saved-views", "open"), ("filters-as-data", "proposed", False), ("filters-in-the-address", "proposed"),
           ("view-storage-research", "open"), ("view-list-shape", "open", False),
           ("save-and-reopen-a-view", "proposed"), ("share-a-view-by-link", "proposed")),
         "saved-views: grilled; the parent ticket and six slices", "2026-09-18T16:40:00+02:00", GRILL_VIEWS)
    step(t(("filters-as-data", "open", False), "filters-in-the-address", "save-and-reopen-a-view", "share-a-view-by-link"),
         "saved-views: the slices ruled open", "2026-09-19T10:15:00+02:00", GRILL_VIEWS)
    reported("map-columns-to-fields", ranges, "2026-09-20T14:20:00+02:00", "2026-09-20T15:31:00+02:00")
    step(t("map-columns-to-fields", ("commit-the-import", "claimed", False)),
         "map-columns-to-fields: merged into csv-import, for its close-out", "2026-09-20T15:35:00+02:00", ORCH_CSV)
    reported("commit-the-import", ranges, "2026-09-23T11:20:00+02:00", "2026-09-23T12:11:00+02:00")
    step(t("commit-the-import"),
         "commit-the-import: merged into csv-import, for its close-out", "2026-09-23T12:15:00+02:00", ORCH_CSV)
    write(AGENT, {"prototypes/view-list-shape/index.html": PROTOTYPE,
                  "show/view-list-shape/serve-the-takes": SERVE_TAKES, "show/view-list-shape/three-takes.html": PROTOTYPE})
    (AGENT / "show/view-list-shape/serve-the-takes").chmod(0o755)
    step(t("view-list-shape", "paginate-the-view-list"),
         "view-list-shape: three takes on the list; paging proposed from them", "2026-09-23T17:05:00+02:00", PROTO)
    step(t("csv-import", "blank-column-reason"),
         "csv-import: closed out, for the ruling on the whole; the debrief's one ticket", "2026-09-24T11:00:00+02:00", ORCH_CSV)
    step(t("saved-views", ("filters-as-data", "claimed", False), "view-storage-research"),
         "saved-views: claimed for its tree; filters-as-data and view-storage-research claimed",
         "2026-09-25T09:30:00+02:00", ORCH_VIEWS)
    reported("filters-as-data", ranges, "2026-09-25T10:05:00+02:00", "2026-09-25T11:16:00+02:00")
    step(t("filters-as-data"),
         "filters-as-data: merged into saved-views, for its close-out", "2026-09-25T11:20:00+02:00", ORCH_VIEWS)
    step(t(("flaky-export-test", "claimed", False)), "flaky-export-test: claimed", "2026-09-26T09:00:00+02:00", TRIAGE)
    write(AGENT, {"show/flaky-export-test/rerun-under-load": RERUN})
    (AGENT / "show/flaky-export-test/rerun-under-load").chmod(0o755)
    step(t("flaky-export-test"), "flaky-export-test: for review", "2026-09-26T09:40:00+02:00", TRIAGE)

    for slug in (p.stem for p in (HERE / "tracker").glob("*.md")):  # every ticket ends as tracker/ has it
        written = AGENT / "tickets" / f"{slug}.md"
        assert written.is_file() and written.read_text() == ticket(slug, ranges), f"{slug} does not end as tracker/ has it"
    run(str(BIN / "tracker"), "check", *map(str, sorted((AGENT / "tickets").glob("*.md"))), cwd=AGENT)


def transcripts() -> None:
    """Each session's transcript, where and as Claude Code writes one: under a directory per
    working directory, every non-alphanumeric character dashed, its title an `ai-title` record.
    The grilling of saved views has a session page too, which the opened ticket links."""
    for sid, (title, cwd) in SESSIONS.items():
        path = CLAUDE / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd)) / f"{sid}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [{"type": "user", "sessionId": sid, "cwd": str(cwd)}, {"type": "ai-title", "aiTitle": title, "sessionId": sid}]
        path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    write(AGENT, {f"sessions/{GRILL_VIEWS}/index.html":
                  "<!doctype html>\n<title>Grilling saved views</title>\n<p>The session page, as the renderer writes it.\n"})


def build_repo() -> None:
    shutil.rmtree(DEMO, ignore_errors=True)
    AGENT.mkdir(parents=True)
    ranges = build_code()
    build_agent(ranges)
    transcripts()


# ---- render and shoot ------------------------------------------------------


def render() -> tuple[Path, Path | None]:
    """The board, and the review pages where `diffview` is installed."""
    review = None
    if shutil.which("diffview"):
        for slug, (title, summary) in REVIEWS.items():
            ranges = [r.removeprefix("code@") for r in ticket_meta(slug) if r.startswith("code@")]
            page = AGENT / "diffviews" / f"{slug}.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            notes = []
            if slug == "upload-and-parse-report":
                (DEMO / "notes.json").write_text(json.dumps(F.NOTES))
                notes = ["--notes", str(DEMO / "notes.json")]
                review = page
            run("diffview", *(f"{REPO}@{r}" for r in ranges), "-o", str(page), "--no-open", "--no-auto-summary",
                *notes, "--title", title, "--summary", summary,
                # rendered for the demo's orchestrator, so its resume button names none of this host's sessions
                env=os.environ | {"MX_ORIGIN_SESSION": ORCH_CSV, "CLAUDE_CONFIG_DIR": str(CLAUDE)})
    else:
        (ASSETS / "review-page.png").unlink(missing_ok=True)  # gone reads as not shot; stale reads as fresh
        print("no diffview on PATH: skipping review-page.png, and the board's review links stay bare")
    board = AGENT / "board.html"
    # one render, so no briefing session runs: the answer one really gave on this tracker stands in
    # for it, which is the column a reader's own board has and the README's prose describes
    shutil.copy(HERE / "briefing.json", cache_path(board))
    run(str(BIN / "board"), str(AGENT / "tickets"), "--no-watch", "--no-open",
        env=os.environ | {"CLAUDE_CONFIG_DIR": str(CLAUDE)})
    return board, review


def ticket_meta(slug: str) -> list[str]:
    return run(str(BIN / "tracker"), "get", slug, "diff", cwd=AGENT).split()


def serve(root: Path) -> ThreadingHTTPServer:
    """The agent repo over http, as `board` opens it: served, the page says nothing of review pages
    that cannot save, and its stamp poll is answered."""
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def shoot(board: Path, review: Path | None) -> list[Path]:
    from playwright.sync_api import sync_playwright

    server = serve(AGENT)
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    url = lambda path: f"{origin}/{path.relative_to(AGENT)}"  # noqa: E731
    shot = []
    with sync_playwright() as p:
        # the run it belongs to, as `browsers --help` defines it
        browser = p.chromium.launch(executable_path=CHROMIUM,
                                    args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])

        def fresh(scheme: str):
            # a page of its own per shot: the board keeps its view in the tab's storage and name
            context = browser.new_context(viewport={"width": WIDE, "height": TALL}, device_scale_factor=2,
                                          color_scheme=scheme)
            page = context.new_page()
            page.goto(url(board))
            page.wait_for_selector(".btn[data-gmode].on", timeout=30_000)  # the module script has its listeners
            absent = page.eval_on_selector_all(".absences .absent:not([hidden])", "notes => notes.map(n => n.textContent)")
            # the board says each missing optional source in a line above the rows, inside the clip
            # band: a shot taken on a host short of one would carry that line into the README
            assert not absent, "the board rendered without an optional source:\n  " + "\n  ".join(absent)
            return page

        for scheme, suffix in SCHEMES.items():
            # the whole tracker's graph beside the groups, needs me with its questions at the top
            page = fresh(scheme)
            page.click(".btn[data-gmode=all]")
            graph(page)
            shot.append(band(page, f"board-overview{suffix}", "#grp-claimed", "#side"))
            page.context.close()

            # one tree: the others hidden by their chips, a ticket opened to its blocks, its graph marked
            page = fresh(scheme)
            for tree in ("csv-import", "alone"):
                page.click(f".treechip[data-tree={tree}]")
            page.evaluate("document.querySelector('#t-view-list-shape > summary').click()")
            page.click(".btn[data-gmode=tree]")
            graph(page)
            shot.append(band(page, f"board-feature{suffix}", "#grp-proposed", "#side"))
            page.context.close()

        if review:
            context = browser.new_context(viewport={"width": 1280, "height": 1020}, device_scale_factor=2,
                                          color_scheme="dark")
            page = context.new_page()
            page.goto(url(review))
            page.wait_for_timeout(1500)
            page.evaluate(DISMISS_BANNER)
            page.evaluate(SCROLL_TO_NOTE)
            page.wait_for_timeout(600)
            out = ASSETS / "review-page.png"
            page.screenshot(path=str(out))
            shot.append(out)
            print(out.name)
        browser.close()
    server.shutdown()
    return shot


def graph(page) -> None:
    page.wait_for_selector(".g:not([hidden]) .mermaid svg", timeout=30_000)
    page.wait_for_timeout(600)


def band(page, name: str, *bottoms: str) -> Path:
    """Screenshot from the top of the page down past every element named, full width.

    The side column is one of them wherever the rows above it are the shorter side, so a briefing
    the model wrote long never costs the shot the graph preview under it."""
    height = PAD + max(page.evaluate("b => document.querySelector(b).getBoundingClientRect().bottom + scrollY", b)
                       for b in bottoms)
    out = ASSETS / f"{name}.png"
    page.screenshot(path=str(out), full_page=True, clip={"x": 0, "y": 0, "width": WIDE, "height": height})
    print(out.name)
    return out


DISMISS_BANNER = """() => document.querySelector("div.readonly")?.remove()"""

# The agent's notes are painted into the diff body once it renders; find one by its own words.
SCROLL_TO_NOTE = """() => {
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) {
    if (!/Rejecting per line/.test(walk.currentNode.nodeValue)) continue;
    walk.currentNode.parentElement.scrollIntoView({block: "center"});
    window.scrollBy(0, -160);
    return;
  }
  throw new Error("note not found");
}"""

# What the row in review offers the reader to run.
RERUN = """#!/usr/bin/env bash
# The export test a hundred times over, against a disk kept busy: the flake it used to show is gone
# because nothing in the test opens a file any more.
set -euo pipefail
dd if=/dev/zero of=/tmp/ledger-load bs=1M count=512 oflag=direct status=none &
uv run --with pytest --with pytest-repeat pytest tests/test_export.py -q --count 100
wait
"""

# What the prototype session left to rule on in front of.
SERVE_TAKES = """#!/usr/bin/env bash
# The three takes on the view list, side by side over the same twelve saved views.
set -euo pipefail
cd "$(dirname "$0")/../../prototypes/view-list-shape"
echo "the three takes: http://localhost:8411/"
python3 -m http.server 8411 --bind 127.0.0.1
"""

PROTOTYPE = """<!doctype html>
<meta charset="utf-8">
<title>The view list: three takes</title>
<style>
  body { font: 15px/1.4 Georgia, serif; margin: 2rem; display: grid; grid-template-columns: repeat(3, 1fr); gap: 2rem; }
  h2 { font: 600 13px ui-monospace, monospace; text-transform: uppercase; letter-spacing: .05em; }
  .rows li { border-bottom: 1px solid #ccc; padding: .2rem 0; list-style: none; }
  .cards { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; }
  .cards div { border: 1px solid #ccc; padding: .5rem; }
  .side { border-right: 1px solid #ccc; }
</style>
<section><h2>A: rows</h2><ul class="rows"><li>Coffee, this year</li><li>February, card only</li><li>Rent and utilities</li></ul></section>
<section><h2>B: cards</h2><div class="cards"><div>Coffee, this year<br><small>payee: Coffee · 2026</small></div><div>February, card only<br><small>card · 1-28 Feb</small></div></div></section>
<section class="side"><h2>C: sidebar</h2><ul class="rows"><li>Coffee, this year</li><li>February, card only</li></ul></section>
"""


if __name__ == "__main__":
    build_repo()
    board, review = render()
    written = shoot(board, review)
    subprocess.run([str(COMPRESS), *map(str, written)], check=True)
    print(f"repo: {REPO}")
