#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright", "tyro", "pyyaml", "markdown-it-py"]
# ///
"""Lay down five made-up orchestrator sessions, run the container hub over them, and shoot its tab.

The README's hub figure is the real hub tab, not a mockup: this builds a throwaway HOME holding a small
ledger app, its tracker, and the session pages of five sessions on it (`fixture.py`), each rendered by this
checkout's session-page renderer, registers the sessions as running (one in a pane of a tmux server of the run's
own, a `sleep` standing in for its process, so its box offers to hand off), starts the container hub on that HOME,
opens each session's pages through it, and screenshots the tab at the selected session in the night scheme, the one
the README shows, to mx/assets/hub.png. Nothing reaches the real ~/.claude, a
running hub, or the user's tmux server, and the HOME and the run's tmux server go when the shot is taken. Re-run it
whenever the hub tab or the session page changes how it looks.

Needs chromium and tmux on PATH and the network (the hub fetches its pane library from jsDelivr, the pages their
fonts). The container hub lives in the dotfiles repo, with diffview beside it.

Examples:

    docs/figures/hub-fixture/build.py
    docs/figures/hub-fixture/build.py --hub ~/.dotfiles/bin/container-hub
"""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import tyro

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[2]
MX = CHECKOUT / "mx"
OUT = MX / "assets"
sys.dont_write_bytecode = True  # no __pycache__ beside the fixture or in the plugin's skills
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(MX / "skills" / "session-page"))
import fixture  # noqa: E402
import session_page  # noqa: E402  this checkout's renderer, not the installed plugin's

SCHEMES = {"dark": "hub"}  # the README shows the hub at night only
WIDTH, HEIGHT = 1600, 1000
GIT = {"GIT_AUTHOR_NAME": "demo", "GIT_AUTHOR_EMAIL": "demo@example.com", "GIT_COMMITTER_NAME": "demo",
       "GIT_COMMITTER_EMAIL": "demo@example.com", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


@dataclass
class Args:
    hub: Path = Path(shutil.which("container-hub") or "container-hub")
    """The container hub to run: its script in the dotfiles' bin/, with diffview beside it."""
    keep: bool = False
    """Leave the temp directory and its hub log in place, and print where, to look at what the hub was given."""


def fail(why: str) -> None:
    raise SystemExit(f"hub-fixture: {why}")


def clean_env(home: Path) -> dict[str, str]:
    """The environment the hub and every tool here run in: this HOME, and nothing that names the real Claude Code
    config, a session, a tmux server or a running hub. The plugin's bin/ leaves PATH too, so the hub finds `tracker`
    in this checkout, symlinked into the HOME's plugin cache."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CLAUDE", "MX_", "GIT_", "XDG_", "CONTAINER_HUB", "TMUX"))}
    env["PATH"] = os.pathsep.join(p for p in env["PATH"].split(os.pathsep) if "/.claude" not in p)
    for k, args in (("UV_CACHE_DIR", ("cache", "dir")), ("UV_PYTHON_INSTALL_DIR", ("python", "dir"))):
        env[k] = subprocess.run(["uv", *args], capture_output=True, text=True, check=True).stdout.strip()
    return {**env, **GIT, "HOME": str(home)}


def run(env: dict, *args: str, cwd: Path | None = None) -> str:
    done = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if done.returncode:
        fail(f"{' '.join(map(str, args))} failed ({done.returncode}):\n{done.stdout}\n{done.stderr}")
    return done.stdout.strip()


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def at(minutes_ago: int, now: float) -> float:
    return now - 60 * minutes_ago


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# --- the project ----------------------------------------------------------------------------------


def lay_project(code: Path, env: dict, diffview: Path) -> None:
    """The code repo with the saved-views slice landed, and its agent repo with the tickets, each session's
    tickets committed under its `Session:` trailer, which is how the hub gives a unit its tree."""
    code.mkdir(parents=True)
    run(env, "git", "init", "-q", "-b", "main", cwd=code)
    write(code / ".gitignore", "agent/\n__pycache__/\n")
    for rel, body in fixture.SKELETON.items():
        write(code / rel, body)
    run(env, "git", "add", "-A", cwd=code)
    run(env, "git", "commit", "-q", "-m", "ledger: rows, filters and the rows endpoint", cwd=code)
    base = run(env, "git", "rev-parse", "--short", "HEAD", cwd=code)
    for rel, body in fixture.SAVED_VIEWS.items():
        write(code / rel, body)
    run(env, "git", "add", "-A", cwd=code)
    run(env, "git", "commit", "-q", "-m", "save-and-reopen-a-view: a view saved by name and reopened as it was", cwd=code)
    head = run(env, "git", "rev-parse", "--short", "HEAD", cwd=code)

    agent = code / "agent"
    agent.mkdir()
    run(env, "git", "init", "-q", "-b", "main", cwd=agent)
    tickets = {t.slug: t for t in fixture.TICKETS}
    for s in fixture.SESSIONS:
        for slug in s.tickets:
            write(agent / "tickets" / f"{slug}.md", tickets[slug].text(f"{base}..{head}"))
        run(env, "git", "add", "-A", cwd=agent)
        run(env, "git", "commit", "-q", "-m", f"{s.tickets[0]}: filed", "-m", f"Session: {s.id}", cwd=agent)
    for s in fixture.SESSIONS:  # committed after every prompt the transcripts hold, so each is fresh
        if s.handoff:
            slug, body = s.handoff
            day = datetime.now().strftime("%Y-%m-%d")
            write(agent / "handoffs" / f"{day}-{slug}.md", f"---\nsession: {s.id}\npurpose: continuation\n---\n\n{body}")
            run(env, "git", "add", "-A", cwd=agent)
            run(env, "git", "commit", "-q", "-m", f"handoff: {slug}", cwd=agent)
    tracker = MX / "skills" / "tracker" / "tracker.py"
    run(env, str(tracker), "check", *(str(p) for p in sorted((agent / "tickets").glob("*.md"))), cwd=code)

    tokens = (MX / "skills" / "house-style" / "tokens.css").read_text()
    for rel, body in fixture.PAGES.items():
        write(agent / rel, body.replace("__TOKENS__", tokens))
    review = agent / "diffviews" / "save-and-reopen-a-view.html"
    notes = write(Path(env["HOME"]) / "notes.json", json.dumps(fixture.REVIEW_NOTES))
    run(env, str(diffview), f"{code}@{base}..{head}", "-o", str(review), "--no-open", "--no-auto-summary",
        "--notes", str(notes), "--title", "save-and-reopen-a-view", "--summary", fixture.REVIEW_SUMMARY, cwd=code)
    # the board the rail links: one render, which starts no briefing session
    run(env, str(MX / "bin" / "board"), str(agent / "tickets"), "--no-watch", "--no-open", cwd=code)


# --- the sessions ---------------------------------------------------------------------------------


@contextmanager
def home_is(home: Path):
    """The renderer reads the session's short name from Claude Code's registry under ~/.claude: this HOME's."""
    was = os.environ.get("HOME"), os.environ.pop("CLAUDE_CONFIG_DIR", None)
    os.environ["HOME"] = str(home)
    try:
        yield
    finally:
        os.environ["HOME"] = was[0]
        if was[1] is not None:
            os.environ["CLAUDE_CONFIG_DIR"] = was[1]


def lay_session(s: fixture.Session, code: Path, home: Path, now: float, pane: tuple[str, int] | None) -> Path:
    """The session's records, a transcript that pairs them with the user's prompts, its page rendered from both,
    and its entry in the registry, naming this process so the hub reads it as running, or, for a session in a tmux
    pane, the pane's own process, which the hub checks the pane still holds before it offers anything there."""
    directory = code / "agent" / "sessions" / s.id
    transcript = home / ".claude" / "projects" / ("-" + str(code).strip("/").replace("/", "-")) / f"{s.id}.jsonl"
    lines, number, first = [], 0, at(s.turns[0].ago, now)
    write(directory / "session.md", f"---\nsession: {s.id}\nrepo: {code}\n---\n\n# {s.title}\n\n## Brief\n\n{s.brief}\n")
    for turn in s.turns:
        end = at(turn.ago, now)
        for i, prompt in enumerate(turn.prompts):
            asked = end - 60 * (12 - i)
            lines.append({"type": "user", "message": {"role": "user", "content": prompt}, "timestamp": iso(asked),
                          "sessionId": s.id, "cwd": str(code), "origin": {"kind": "human"}, "promptSource": "typed"})
        day = datetime.fromtimestamp(end).strftime("%Y-%m-%d")
        if turn.chat:
            path = session_page.chat_path(directory / "turns", datetime.fromtimestamp(end, UTC))
            write(path, session_page.chat_record(turn.record, datetime.fromtimestamp(end).astimezone()))
        else:
            number += 1
            path = write(directory / "turns" / f"{number:02d}.md", turn.record.replace("{date}", day))
            writes = [path] + ([directory / "session.md"] if number == 1 else [])
            lines.append({"type": "assistant", "timestamp": iso(end - 30), "sessionId": s.id, "cwd": str(code),
                          "message": {"role": "assistant", "content": [
                              {"type": "tool_use", "id": f"toolu_{s.id[:8]}_{number:02d}_{i}", "name": "Write",
                               "input": {"file_path": str(p)}} for i, p in enumerate(writes)]}})
        os.utime(path, (end, end))
    if s.runs:
        lines.append({"type": "assistant", "timestamp": iso(at(s.turns[-1].ago, now) - 45), "sessionId": s.id,
                      "cwd": str(code), "message": {"role": "assistant", "content": [
                          {"type": "tool_use", "id": f"toolu_{s.id[:8]}_run_{i}", "name": "Bash",
                           "input": {"command": command, "description": what, "run_in_background": True}}
                          for i, (what, command) in enumerate(s.runs)]}})
    write(transcript, "".join(json.dumps(line) + "\n" for line in lines))
    os.utime(directory / "session.md", (first, first))

    last = at(s.turns[-1].ago, now)
    n = s.name.rsplit("-", 1)[1]
    target, pid = pane or (f"ledger:@{n}.%{n}", os.getpid())
    entry = {"pid": pid, "procStart": started_at(pid), "sessionId": s.id, "name": s.name, "status": s.status,
             "statusUpdatedAt": int(last * 1000), "tmux": target, "cwd": str(code),
             **({"waitingFor": s.waiting_for} if s.waiting_for else {})}
    write(home / ".claude" / "sessions" / f"{s.id[:8]}.json", json.dumps(entry))
    pct, tokens = s.context
    write(home / ".cache" / "claude-statusline" / f"{s.id}.json", json.dumps({
        "session_id": s.id, "config_dir": str(home / ".claude"), "written_at": now,
        "context_window": {"used_percentage": pct, "total_input_tokens": tokens},
        "rate_limits": {k: {"used_percentage": used, "resets_at": now + 3600 * hours}
                        for k, (used, hours) in fixture.USAGE.items()}}))

    with home_is(home):
        try:
            page = session_page.render_session(directory, transcript, datetime.fromtimestamp(last))
        except session_page.RecordError as e:
            fail(f"the session page of {s.name} did not render: {e}")
    index = write(directory / session_page.PAGE, page)
    os.utime(index, (last, last))
    return index


def install_plugin(home: Path) -> None:
    """This checkout's mx as the newest plugin in the HOME's cache, where the hub looks for the session page's
    reader and `tracker`."""
    version = json.loads((MX / ".claude-plugin" / "plugin.json").read_text())["version"]
    cache = home / ".claude" / "plugins" / "cache" / "demo" / "mx"
    cache.mkdir(parents=True)
    (cache / version).symlink_to(MX)


# --- the hub --------------------------------------------------------------------------------------


def started_at(pid: int) -> str:
    """A process's start time as Claude Code's registry records it, which the hub checks a pid against."""
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def start_tmux(socket_path: Path, env: dict) -> dict[str, tuple[str, int]]:
    """A tmux server of this run's own, with a pane for each session that runs in one: its registry entry's tmux
    target and the pid the pane holds, by session id. No config, so nothing of the user's tmux setup loads."""
    panes = {}
    for s in (s for s in fixture.SESSIONS if s.pane):
        how = (["-f", os.devnull, "new-session", "-s", "ledger", "-x", "160", "-y", "40"] if not panes
               else ["new-window", "-t", "ledger"])
        shown = run(env, "tmux", "-S", str(socket_path), *how, "-d", "-P", "-F",
                    "#{session_name}:#{window_id}.#{pane_id} #{pane_pid}", "exec sleep 86400")
        target, pid = shown.split()
        panes[s.id] = target, int(pid)
    return panes


def stop_tmux(socket_path: Path, env: dict) -> None:
    subprocess.run(["tmux", "-S", str(socket_path), "kill-server"], env=env, capture_output=True, check=False)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_hub(hub: Path, port: int, scratch: Path, tmux_socket: Path, env: dict) -> subprocess.Popen:
    log = (scratch / "hub.log").open("a")
    started = subprocess.Popen([str(hub), "--port", str(port), "--state", str(scratch / "state"),
                                "--tmux-socket", str(tmux_socket)],
                               env=env, stdout=log, stderr=log, start_new_session=True)
    deadline = time.monotonic() + 120  # its first start resolves its dependencies through uv
    while time.monotonic() < deadline:
        if started.poll() is not None:
            fail(f"the hub exited ({started.returncode}) before it answered:\n{(scratch / 'hub.log').read_text()}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/.health", timeout=2):
                return started
        except (OSError, urllib.error.URLError):
            time.sleep(0.2)
    fail(f"the hub never answered on port {port}:\n{(scratch / 'hub.log').read_text()}")


def stop_hub(hub: subprocess.Popen) -> None:
    """The whole process group: `uv run` leads it, and the server under it holds the port until it goes too."""
    try:
        os.killpg(hub.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    hub.wait()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            os.killpg(hub.pid, 0)
            time.sleep(0.05)
        except ProcessLookupError:
            return


def api(port: int, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode() if body else None,
                                 method="POST" if body else "GET", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        fail(f"{path} {json.dumps(body)} answered {e.code}: {e.read().decode(errors='replace')}")


def open_pages(port: int, code: Path, pages: dict[str, Path]) -> str:
    """Each session opens its session page, then its other pages, as its own agent would; the user has looked at
    every unit but the one left new since its last turn, and the selected one, which the tab visits. Answers the
    hub tab's id of the page the shot brings to the front."""
    front = None
    for s in fixture.SESSIONS:
        for target in [pages[s.id], *(code / "agent" / rel for rel in s.opens)]:
            opened = api(port, "/api/open", {"target": str(target), "session": s.id, "cwd": str(code)})
            if "unit" not in opened:
                fail(f"the hub did not take {target} into {s.name}'s unit: {opened}")
            if s is fixture.SELECTED and target == code / "agent" / fixture.FRONT:
                front = f"{s.id}~{opened['id']}"
    time.sleep(1.1)  # a visit counts what was written before it, to the second
    for s in fixture.SESSIONS:
        if s.visited and s is not fixture.SELECTED:
            api(port, "/api/visit", {"unit": s.id})
    units = {u["session"]: u for u in api(port, "/api/hub")["units"]}
    for s in fixture.SESSIONS:
        u = units.get(s.id)
        state = "idle" if s.status == "shell" else s.status  # the hub's: a shell left running is an idle session
        if not u or u["state"] != state:
            fail(f"{s.name} is not a running unit in state {state}: {u and u['state']}")
        if not u["status_line"]:
            fail(f"{s.name} has no status line: the hub did not read its session page through the plugin's reader")
        details = api(port, f"/api/u/{s.id}")
        if details["session_page"]["url"].startswith("/pages/"):
            fail(f"{s.name} shows the hub's stand-in, not its session page")
        if s.runs and len(details["background"]) != len(s.runs):
            fail(f"{s.name} shows {details['background']} running in the background, not its {len(s.runs)} runs")
        if s.handoff and (details["handoff"] or {}).get("offer") != "hand-off":
            fail(f"{s.name}'s box does not offer to hand off from its handoff: {details['handoff']}")
    return front


# --- the shot -------------------------------------------------------------------------------------

LOADED = """n => {
  if (!window.ws || ws.views().length < n) return false;
  const frames = [...document.querySelectorAll("iframe")].filter((f) => f.offsetParent);
  return frames.length >= 3 && frames.every((f) => f.contentDocument?.readyState === "complete");
}"""


def shoot(port: int, selected: str, panes: int, front: str) -> list[Path]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright

    chromium = shutil.which("chromium")
    if not chromium:
        fail("no chromium on PATH")
    shots = []
    with sync_playwright() as p:
        # the run it belongs to, as `browsers --help` defines it
        browser = p.chromium.launch(executable_path=chromium,
                                    args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
        try:
            for scheme, name in SCHEMES.items():
                # the hub tab follows the system's scheme, and every page in it follows the tab
                context = browser.new_context(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=2,
                                              color_scheme=scheme)
                tab = context.new_page()
                errors = []
                tab.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                tab.goto(f"http://127.0.0.1:{port}/u/{selected}")
                try:
                    tab.wait_for_function(LOADED, arg=panes, timeout=60_000)
                except PlaywrightTimeout:
                    fail(f"the hub tab never showed {panes} panes and the session page, all loaded: "
                         f"{tab.evaluate('window.ws ? ws.views().map(v => v.id) : null')}")
                tab.evaluate("id => ws.focus(id)", front)
                tab.wait_for_function(LOADED, arg=panes, timeout=30_000)
                session = tab.frame_locator("#session-frames .current iframe")
                if not session.locator("#open-questions").count():
                    fail("the selected session's page shows no open question at its top")
                tab.evaluate("document.fonts.ready")
                tab.wait_for_timeout(2500)  # the panes' own fonts, and the rail's rings at a still frame
                if errors:
                    fail("the hub tab threw:\n  " + "\n  ".join(errors))
                shot = OUT / f"{name}.png"
                tab.screenshot(path=str(shot), animations="disabled")
                shots.append(shot)
                print(shot.relative_to(CHECKOUT))
                context.close()
        finally:
            browser.close()
    return shots


def main(args: Args) -> None:
    hub_path = args.hub.expanduser().resolve()
    if not hub_path.is_file():
        fail(f"no container hub at {args.hub}; pass --hub with the dotfiles' bin/container-hub")
    diffview = hub_path.parent / "diffview"
    if not diffview.is_file():
        fail(f"no diffview beside the hub, at {diffview}")
    scratch = Path(tempfile.mkdtemp(prefix="hub-fixture."))
    home, now, hub = scratch / "home", time.time(), None
    tmux_socket = scratch / "tmux.sock"
    code = home / "code" / "ledger"
    try:
        env = clean_env(home)
        install_plugin(home)
        lay_project(code, env, diffview)
        in_tmux = start_tmux(tmux_socket, env)
        pages = {s.id: lay_session(s, code, home, now, in_tmux.get(s.id)) for s in fixture.SESSIONS}
        port = free_port()
        hub = start_hub(hub_path, port, scratch, tmux_socket, env)
        front = open_pages(port, code, pages)
        panes = len(fixture.SELECTED.opens)
        shots = shoot(port, fixture.SELECTED.id, panes, front)
        run(os.environ.copy(), str(HERE.parent / "compress.py"), *map(str, shots))
    finally:
        if hub:
            stop_hub(hub)
        if tmux_socket.exists():  # the server started, so env is set
            stop_tmux(tmux_socket, env)
        if args.keep:
            print(f"kept: {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
