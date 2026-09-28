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


def test_every_browser_mx_launches_carries_its_run() -> None:
    """A launch site that leaves the tag off makes a browser no run can kill but by name."""
    tracked = subprocess.run(["git", "ls-files", "*.py", "*.sh"], cwd=REPO, capture_output=True,
                             text=True, check=True).stdout.split()
    launches = {}
    for name in tracked:
        text = (REPO / name).read_text()
        for m in re.finditer(r"chromium\.launch\(|mermaid-cli ", text):
            launches[f"{name}:{text.count(chr(10), 0, m.start()) + 1}"] = "--mx-run=" in text[m.start():m.start() + 200] \
                or "PUPPETEER_CONFIG" in text[m.start():m.start() + 200]
    assert launches, "no launch site found, so this check reads nothing"
    assert all(launches.values()), [site for site, tagged in launches.items() if not tagged]
