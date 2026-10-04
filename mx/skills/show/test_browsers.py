"""Checks for `browsers`: the handle a run kills its own browsers by on a host other runs share.

The seam is the command line of the launch and of `browsers`, the way a worker meets both. The
launch is render-lint's on a page that never comes to rest, so each browser stays up until
something kills it. The oracle is the ticket's criterion: after one run kills its browsers, a
concurrent run's browser is the same process it was, and a shell whose command line names the
killed run is still running.
"""

import os
import re
import signal
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from test_render_lint import LINT, PAGE, RESTLESS

# Every check here starts a browser.
pytestmark = pytest.mark.full_path

BROWSERS = Path(__file__).parent / "browsers"
REPO = Path(__file__).resolve().parents[3]


def browsers(*args: str, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([str(BROWSERS), *args], capture_output=True, text=True, cwd=cwd, env=env)


def pids(run: str) -> set[str]:
    listed = browsers("list", run)
    return {line.split()[0] for line in listed.stdout.splitlines()}


@pytest.fixture
def restless(tmp_path: Path) -> Iterator[Callable[..., str]]:
    """Start render-lint on a page that never settles, under a run given by MX_RUN or by its
    working directory; every launch is torn down with its browsers when the check ends."""
    page = tmp_path / "restless.html"
    page.write_text(PAGE.format(RESTLESS))
    launched: list[tuple[subprocess.Popen, str]] = []

    def launch(run: str | None = None, cwd: Path = tmp_path) -> str:
        env = {k: v for k, v in os.environ.items() if k != "MX_RUN"} | ({"MX_RUN": run} if run else {})
        lint = subprocess.Popen([str(LINT), str(page), "--patience", "600"], cwd=cwd, env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        tag = run or str(cwd)
        launched.append((lint, tag))
        deadline = time.monotonic() + 90
        while not pids(tag):
            assert lint.poll() is None, f"render-lint for {tag} exited {lint.returncode} before its browser was up"
            assert time.monotonic() < deadline, f"no browser carried --mx-run={tag} within 90s"
            time.sleep(0.25)
        return tag

    yield launch
    for lint, tag in launched:
        browsers("kill", tag)
        os.killpg(lint.pid, signal.SIGKILL)
        lint.wait()


def test_a_run_that_kills_its_browsers_leaves_a_concurrent_runs_alive(tmp_path: Path, restless) -> None:
    """Two runs on one host at once, one named by MX_RUN and one by the directory it ran in: the
    first kills its browsers, and the second's browser is untouched, as is a shell whose command
    line mentions the first run by its tag."""
    mine = restless(f"mine-{tmp_path.name}")
    other_dir = tmp_path / "other-checkout"
    other_dir.mkdir()
    theirs = restless(cwd=other_dir)
    before = pids(theirs)
    bystander = subprocess.Popen(["sh", "-c", f"sleep 600; : --mx-run={mine}"], start_new_session=True)

    try:
        killed = browsers("kill", mine)
        assert killed.returncode == 0, killed.stderr
        assert killed.stdout.startswith("killed "), killed.stdout
        assert pids(mine) == set()
        assert browsers("list", mine).returncode == 1
        assert pids(theirs) == before
        assert bystander.poll() is None, "a shell naming the killed run went with its browsers"
    finally:
        os.killpg(bystander.pid, signal.SIGKILL)
        bystander.wait()


def test_a_run_is_mx_run_where_set_and_the_working_directory_where_not(tmp_path: Path, restless) -> None:
    """`browsers` with no run names the one its caller is in, the same way a launch does."""
    named = restless(f"named-{tmp_path.name}")
    by_directory = restless()
    assert browsers("list", env={**os.environ, "MX_RUN": named}).stdout.split()[0] in pids(named)
    unset = {k: v for k, v in os.environ.items() if k != "MX_RUN"}
    assert browsers(cwd=tmp_path, env=unset).stdout.split()[0] in pids(by_directory)


def launches(text: str, shell: bool) -> Iterator[tuple[int, str]]:
    """Each browser launch in `text` with its line: a Playwright launch call to its closing
    parenthesis, and in a shell script or a doc, a `chromium --headless` command to the end of its
    continued line and a mermaid-cli command line."""
    for m in re.finditer(r"chromium\.launch\(", text):
        depth, end = 1, m.end()
        while depth:
            depth += {"(": 1, ")": -1}.get(text[end], 0)
            end += 1
        yield text.count("\n", 0, m.start()) + 1, text[m.start():end]
    if shell:
        for m in re.finditer(r"^.*(chromium --headless(?:.*\\\n)*.*|npx .*@mermaid-js/mermaid-cli.*)$", text, re.M):
            yield text.count("\n", 0, m.start()) + 1, m.group(1)


def test_every_browser_mx_launches_carries_its_run() -> None:
    """A launch site that leaves the tag off makes a browser no run can kill but by name. The
    mermaid check's tag is in the Puppeteer config it hands mermaid-cli."""
    tracked = subprocess.run(["git", "ls-files", "mx", "docs"], cwd=REPO, capture_output=True, text=True,
                             check=True).stdout.split()
    sites = {}
    for name in tracked:
        if Path(name).suffix not in (".py", ".sh", ".md") or Path(name).name == Path(__file__).name:
            continue
        for line, call in launches((REPO / name).read_text(), shell=Path(name).suffix != ".py"):
            sites[f"{name}:{line}"] = "--mx-run=" in call or '-p "$PUPPETEER_CONFIG"' in call
    assert len(sites) >= 7, f"fewer launch sites than the seven this repo has: {sorted(sites)}"
    assert all(sites.values()), [site for site, tagged in sites.items() if not tagged]
