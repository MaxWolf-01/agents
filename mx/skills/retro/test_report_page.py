"""Checks for the retro's page (retro-report-max-can-scan), at the seam `report_page.render`: given a
report in a scratch agent repo, with its earlier versions committed, the page it writes. The oracle is
the two versions below, written by hand: which entry is new, moved, reworked or dropped between them,
each entry's State in each, and the comments saved beside the page.
Run: make test, or pytest on this file with tyro and markdown-it-py.
"""

import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

import report_page
from retro_checks import commit, git

FIRST = """# Workflow retro: agents

Run 2026-10-12, over 2026-10-05 to 2026-10-12. ids: F2, A1

## Findings

### F1 The suite is slow

- **Lens**: agents
- **State**: live
- **Cause**: `mx/skills/dispatch/SKILL.md:42`

### F2 Pages lose comments

- **Lens**: max
- **State**: live

## Candidates

### A1 Fold the hub's two servers

- **Code lens**: architecture
- **Files**: `container-hub`
- **State**: live

### A2 Name the area beside every id

- **Code lens**: footguns
- **Files**: `mx/skills/tracker/board.py`, `mx/skills/dispatch/SKILL.md:3`, `mx/skills/dispatch/SKILL.md:9`
- **State**: live

## Dismissed

- **Pages that explain themselves**: dismissed by max 2026-10-10, "no".
"""

SECOND = """# Workflow retro: agents

Run 2026-10-19, over 2026-10-12 to 2026-10-19. ids: F3, A1

## Findings

### F1 The suite is slow

- **Lens**: agents
- **State**: taken up as faster-suite
- **Cause**: `mx/skills/dispatch/SKILL.md:42`

### F3 Jarvis loses messages

- **Lens**: max
- **Area**: jarvis
- **State**: live
- **Cause**: `mx/skills/tracker/tracker.py:9`

## Candidates

### A1 Fold the hub's two servers into one

- **Code lens**: architecture
- **Files**: `container-hub`
- **State**: live

### A2 Name the area beside every id

- **Code lens**: footguns
- **Files**: `mx/skills/tracker/board.py`, `mx/skills/dispatch/SKILL.md:3`, `mx/skills/dispatch/SKILL.md:9`
- **State**: live

## Dismissed

- **Retro comments in the board**: dismissed by max 2026-10-15, "later".
- **Pages that explain themselves**: dismissed by max 2026-10-10, "no".
"""


@pytest.fixture
def agent(tmp_path: Path) -> Path:
    """An agent repo whose report was committed once, at FIRST, and is rewritten as SECOND, as a run's
    commit has it just before it commits."""
    agent = tmp_path / "agent"
    agent.mkdir()
    git(agent, "init", "-q")
    commit(agent, {"retro/report.md": FIRST}, "retro: the first run", datetime(2026, 10, 12, 3, tzinfo=UTC))
    (agent / "retro/report.md").write_text(SECOND)
    return agent


def rendered(agent: Path) -> tuple[str, dict]:
    page = agent / "retro/report.html"
    report_page.render(agent / "retro/report.md", page)
    text = page.read_text()
    data = re.search(r'<script type="application/json" id="data">(.*?)</script>', text, re.S).group(1)
    return text, json.loads(data.replace("<\\/", "</"))


def changes(page: str) -> dict[str, list[str]]:
    """The ids each of What changed's lists names."""
    lists = dict(re.findall(r'<div class="clist" data-k="(\w+)"[^>]*>(.*?)</div>', page, re.S))
    return {k: re.findall(r'<span class="id">(\w+)</span>', v) for k, v in lists.items()}


def test_the_overview_has_one_row_per_entry_whose_element_carries_its_id(agent: Path) -> None:
    page, _ = rendered(agent)
    homes = re.findall(r'<a class="row" id="([^"]+)"', page)
    assert sorted(homes) == ["a1", "a2", "d-pages-that-explain-themselves", "d-retro-comments-in-the-board", "f1", "f3"]


def test_what_changed_is_derived_entry_by_entry_against_the_previous_committed_version(agent: Path) -> None:
    page, data = rendered(agent)
    assert changes(page) == {"new": ["F3"], "moved": ["F1"], "reworked": ["A1"], "dropped": ["F2"], "unchanged": ["A2"]}
    assert "live → taken up as faster-suite" in page
    assert data["entries"]["f2"]["kind"] == "dropped" and "Pages lose comments" in data["entries"]["f2"]["prev"]


def test_once_committed_the_page_still_compares_against_the_version_before(agent: Path) -> None:
    """Rendering by hand after the run's commit: the newest committed version is the report itself."""
    git(agent, "add", "retro/report.md")
    git(agent, "commit", "-qm", "retro: the second run", when=datetime(2026, 10, 19, 3, tzinfo=UTC))
    page, _ = rendered(agent)
    assert changes(page)["new"] == ["F3"]


def test_each_sheet_carries_the_entrys_state_across_every_version(agent: Path) -> None:
    _, data = rendered(agent)
    assert data["entries"]["f1"]["line"] == [["2026-10-12", "live"], ["2026-10-19", "taken up as faster-suite"]]
    assert data["entries"]["f2"]["line"] == [["2026-10-12", "live"], ["2026-10-19", "not in the report"]]
    assert data["entries"]["f3"]["line"] == [["2026-10-19", "live"]]
    assert data["entries"]["a2"]["line"] == [["2026-10-12", "live"]], "a run of one state keeps its first date"


def test_an_entrys_area_is_its_area_field_or_else_read_from_the_paths_it_cites(agent: Path) -> None:
    page, _ = rendered(agent)
    area = dict(re.findall(r'<a class="row" id="(\w+)"[^>]*data-area="([^"]*)"', page))
    assert area == {"f1": "dispatch", "f3": "jarvis", "a1": "hub", "a2": "dispatch"}, \
        "A2 cites tracker once and dispatch twice: the commonest wins"


def test_comments_saved_beside_the_page_are_baked_into_it_and_the_answered_ones_named(agent: Path) -> None:
    (agent / "retro/report.md").write_text(SECOND.replace("- **State**: live\n- **Cause**: `mx/skills/tracker",
                                                          "- **State**: live\n- **History**: answered C1 2026-10-19: kept\n- **Cause**: `mx/skills/tracker"))
    saved = {"writer": "w", "savedAt": 1, "comments": [
        {"id": "C1", "entry": "F3", "at": "2026-10-13T09:00:00Z", "report": "2026-10-12", "text": "is this jarvis?"},
        {"id": "C2", "entry": "A1", "at": "2026-10-13T10:00:00Z", "report": "2026-10-12", "text": "see </script> here"}]}
    (agent / "retro/report.html.state.json").write_text(json.dumps(saved))
    _, data = rendered(agent)
    assert data["saved"] == saved, "C2's text would end the page's data early, unescaped"
    assert data["answered"] == ["C1"]


def test_open_comments_leave_out_the_deleted_and_the_answered_and_name_an_entry_that_left(agent: Path) -> None:
    report = SECOND.replace("- **State**: taken up", "- **History**: answered C2 2026-10-19: taken up\n- **State**: taken up")
    comments = [{"id": "C1", "entry": "F2", "at": "2026-10-13T09:00:00Z", "report": "2026-10-12", "text": "dismiss this"},
                {"id": "C2", "entry": "F1", "at": "2026-10-13T09:00:00Z", "report": "2026-10-12", "text": "take this up"},
                {"id": "C3", "entry": "F3", "at": "2026-10-14T09:00:00Z", "report": "2026-10-19", "text": "x", "deleted": True},
                {"id": "C4", "entry": "F3", "at": "2026-10-14T10:00:00Z", "report": "2026-10-19", "text": "which repo?\nreally"},
                {"id": "C5", "entry": "D-PAGES-THAT-EXPLAIN-THEMSELVES", "at": "2026-10-14T11:00:00Z", "report": "2026-10-19", "text": "fine"}]
    (agent / "retro/report.md").write_text(report)
    text = report_page.open_comments(agent / "retro/report.md", {"comments": comments})
    assert "## F2 (no longer in the report)" in text and "C1, 2026-10-13T09:00:00Z, on the run of 2026-10-12: dismiss this" in text
    assert "## F3 Jarvis loses messages" in text and "which repo?\n  really" in text
    assert "C2" not in text and "C3" not in text
    assert "## D-PAGES-THAT-EXPLAIN-THEMSELVES Pages that explain themselves" in text, "a Dismissed line with no id keeps its comments"


@pytest.mark.parametrize("where", ["a History a later version drops", "the run's commit body"])
def test_a_comment_answered_once_stays_answered(agent: Path, where: str) -> None:
    """C1 on F3 is answered in one run; the next version of the report no longer says so."""
    answered = SECOND.replace("- **Area**: jarvis\n", "- **Area**: jarvis\n- **History**: answered C1 2026-10-19: kept\n")
    (agent / "retro/report.md").write_text(answered if where.startswith("a History") else SECOND)
    git(agent, "commit", "-qam", "retro: a run\n\n- F3 new; answered C1: kept" if where.endswith("body") else "retro: a run",
        when=datetime(2026, 10, 19, 3, tzinfo=UTC))
    (agent / "retro/report.md").write_text(SECOND.replace("Run 2026-10-19", "Run 2026-10-26"))
    comment = {"id": "C1", "entry": "F3", "at": "2026-10-13T09:00:00Z", "report": "2026-10-12", "text": "is this jarvis?"}
    assert "C1" not in report_page.open_comments(agent / "retro/report.md", {"comments": [comment]})
    assert rendered(agent)[1]["answered"] == ["C1"]


def test_a_row_names_every_state_its_state_field_names(agent: Path) -> None:
    """max asked what a "+" after a state meant: the further states it hid show on the row."""
    (agent / "retro/report.md").write_text(SECOND.replace("- **State**: live\n- **Cause**: `mx/skills/tracker",
                                                          "- **State**: back since 2026-10-17, after a fix landed 1234abc\n- **Cause**: `mx/skills/tracker"))
    page, _ = rendered(agent)
    (state,) = re.findall(r'<a class="row" id="f3".*?(<span class="st [^"]*"[^>]*>.*?</span>(?:<span class="more">[^<]*</span>)?)', page, re.S)
    assert re.sub(r"<[^>]+>", " ", state).split() == ["back", "fix", "landed"]


def test_what_changed_prints_as_text_entry_by_entry(agent: Path) -> None:
    text = report_page.changes_text(agent / "retro/report.md")
    assert text.splitlines() == ["Since 2026-10-12:", "- New: F3 Jarvis loses messages",
                                 "- State moved: F1 The suite is slow (live → taken up as faster-suite)",
                                 "- Reworked: A1 Fold the hub's two servers into one",
                                 "- Dropped: F2 Pages lose comments (was live)", "- Unchanged: A2 Name the area beside every id"]


def test_an_artefact_an_entry_names_is_embedded_where_it_is_an_image_or_a_page_and_linked_otherwise(agent: Path) -> None:
    (agent / "retro/report.md").write_text(SECOND.replace(
        "- **Code lens**: architecture\n",
        "- **Code lens**: architecture\n- **Artefacts**: `show/hub/before-after.svg`, `show/hub/index.html`, `research/01-hub.md`, `https://example.org/a.png`\n", 1))
    _, data = rendered(agent)
    assert data["entries"]["a1"]["art"] == [
        {"href": "../show/hub/before-after.svg", "name": "show/hub/before-after.svg", "how": "img"},
        {"href": "../show/hub/index.html", "name": "show/hub/index.html", "how": "frame"},
        {"href": "../research/01-hub.md", "name": "research/01-hub.md", "how": "link"},
        {"href": "https://example.org/a.png", "name": "https://example.org/a.png", "how": "img"}]


# The page in headless Chromium, served as the container hub serves it: `/.health` says it saves, and a
# POST to `<page>.state.json` writes that file. It prints what each step saw.
PROBE = r"""
import json, os, shutil, sys, threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

root, page_path = Path(sys.argv[1]), sys.argv[2]

class Hub(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == "/.health":
            body = b'{"saves": true}'
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        else:
            super().do_GET()
    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"]))
        (root / self.path.lstrip("/")).write_bytes(data)
        self.send_response(200); self.end_headers()

server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Hub, directory=str(root)))
threading.Thread(target=server.serve_forever, daemon=True).start()
seen = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{server.server_port}/{page_path}")
    page.wait_for_selector(".row")
    page.keyboard.press("j")
    seen["pos"] = page.inner_text("#pos")
    seen["timeline"] = page.inner_text("#sh-body .tl")
    page.keyboard.press("j")
    page.keyboard.press("j")
    seen["third"] = page.inner_text("#pos")
    seen["images"] = page.eval_on_selector_all("#sh-body .art img", "els => els.map(e => e.getAttribute('src'))")
    page.wait_for_selector("#cm .new textarea")
    page.keyboard.press("n")
    seen["n focuses"] = page.evaluate("document.activeElement.matches('#cm .new textarea')")
    page.keyboard.type("which repo is this?")
    page.keyboard.press("Control+Enter")
    page.wait_for_function("document.querySelector('#cm .cmt') !== null")
    page.keyboard.press("Escape")
    page.keyboard.down("Control"); page.keyboard.down("Alt")
    seen["held"] = page.eval_on_selector_all(".key-over", "els => els.map(e => e.textContent)")
    page.keyboard.up("Alt"); page.keyboard.up("Control")
    seen["let go"] = page.eval_on_selector_all(".key-over", "els => els.length")
    page.keyboard.press("?")
    page.wait_for_function("document.getElementById('help').open")
    seen["list"] = page.evaluate("document.getElementById('help-keys').rows.length")
    seen["errors"] = errors
    browser.close()
server.shutdown()
print(json.dumps(seen))
"""


@pytest.mark.full_path
def test_the_page_in_a_browser_opens_entries_shows_their_timeline_and_artefacts_and_reaches_everything_by_key(
        agent: Path) -> None:
    """Acceptance criteria 2 and 4: j opens the first entry, its area beside its id, its timeline in its
    sheet; the candidate's image shows in its; n opens a comment that the hub saves; Ctrl+Alt held shows
    the keys and letting go hides them; ? lists them."""
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to drive the page with")
    (agent / "show/hub").mkdir(parents=True)
    (agent / "show/hub/before-after.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
    (agent / "retro/report.md").write_text(SECOND.replace(
        "- **Code lens**: architecture\n", "- **Code lens**: architecture\n- **Artefacts**: `show/hub/before-after.svg`\n", 1))
    rendered(agent)
    done = subprocess.run(["uv", "run", "--quiet", "--with", "playwright", "python", "-", str(agent), "retro/report.html"],
                          input=PROBE, capture_output=True, text=True, timeout=180, env=os.environ)
    assert done.returncode == 0, done.stderr[-2000:]
    seen = json.loads(done.stdout)
    assert seen["pos"].startswith("F1 · dispatch")
    assert seen["timeline"] == "2026-10-12 live → 2026-10-19 taken up as faster-suite"
    assert seen["third"].startswith("A1 · hub") and seen["images"] == ["../show/hub/before-after.svg"]
    assert seen["n focuses"]
    saved = json.loads((agent / "retro/report.html.state.json").read_text())
    assert [(c["id"], c["entry"], c["text"]) for c in saved["comments"]] == [("C1", "A1", "which repo is this?")]
    assert {"j", "k", "/", "g", "c", "y", "w", "?", "1", "a", "s", "n", "t"} <= set(seen["held"]), seen["held"]
    assert seen["let go"] == 0
    assert seen["list"] == len(report_page.PAGE_KEYS), "the ? list renders from page-keys"
    assert seen["errors"] == []


# How the page's script names a key it handles, and how page-keys names it.
SHOWN_AS = {"Escape": "Esc", "ArrowDown": "↓", "ArrowUp": "↑", "ArrowLeft": "←", "ArrowRight": "→",
            "Enter": "Ctrl+Enter", "Control": "Ctrl+Alt", "Alt": "Ctrl+Alt"}


def test_every_key_the_page_handles_is_in_its_page_keys_which_its_list_and_the_hub_read(agent: Path) -> None:
    """hub-lists-the-framed-pages-keys reads the page-keys block to list a framed page's keys; the page's
    own `?` list renders from it, so a key missing there is missing from both."""
    script = (Path(report_page.__file__).with_name("report_page.html")).read_text()
    actions = script[script.index("const ACTIONS = {"):].split("};", 1)[0]
    handled = set(re.findall(r"e\.key === '([^']+)'", script))
    handled |= {a or b for a, b in re.findall(r"(?<![\w$.(])(?:'([^']+)'|\b([a-z])\b)\s*:", actions)}
    handled |= set(re.findall(r"\b(Arrow\w+):", script))
    if "/^[1-5]$/.test(e.key)" in script:
        handled |= set("12345")
    page, _ = rendered(agent)
    block = json.loads(re.search(r'<script type="application/json" id="page-keys">(.*?)</script>', page, re.S).group(1))
    assert block["title"] == "Workflow retro: agents"
    listed = {k for entry in block["keys"] for k in entry["keys"].split()}
    assert all(entry["does"] for entry in block["keys"])
    assert len(handled) > 20, handled
    assert {SHOWN_AS.get(k, k) for k in handled} <= listed, {SHOWN_AS.get(k, k) for k in handled} - listed


def test_the_rendered_page_holds_no_em_dash(agent: Path) -> None:
    """max: "no em dashes in the copy". The fixture's report holds none, so any the page shows are its own."""
    (agent / "retro/report.html.state.json").write_text(json.dumps({"comments": []}))
    page, _ = rendered(agent)
    assert "—" not in page and "&mdash;" not in page and "\\u2014" not in page
