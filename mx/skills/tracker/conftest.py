"""What the board's checks share: the path entry that makes the scripts beside them importable, the
demo tracker built once per run, and a PATH the board's optional tools are absent from."""

import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import board  # noqa: E402
from demo_tracker import Demo, build  # noqa: E402

KEPT = ("git", "uv", "chromium")  # what a check may still need: the repo, a script's own run, a browser


@pytest.fixture(scope="session")
def demo(tmp_path_factory: pytest.TempPathFactory) -> Demo:
    """A tracker exercising every element the board shows, with its git history, sessions and
    review pages: the fixture the layout, row and session checks read.

    The row checks name its tickets: which ask what of the user, which blocker is done, and which
    session committed on which ticket. Changing a ticket's status, type, priority or blocking edge
    moves those checks with it."""
    return build(tmp_path_factory.mktemp("demo-tracker"))


@pytest.fixture
def transcribed(demo: Demo, monkeypatch: pytest.MonkeyPatch) -> Demo:
    """The demo tracker with its transcripts where this machine keeps its own, so the sessions its
    commits name are ones the board can read a title and a working directory for."""
    monkeypatch.setattr(board, "TRANSCRIPTS", demo.transcripts)
    return demo


@pytest.fixture
def path_with(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., Path]:
    """A PATH cut down to KEPT, so the board's optional tools — diffview, gh, the model — are
    genuinely absent rather than the machine's own. Calling it puts a stub of `name` there that
    records one line per run and answers with `answer`, and returns the file it records into."""
    bin_dir = tmp_path / "path"
    bin_dir.mkdir()
    for tool in KEPT:
        if found := shutil.which(tool):
            (bin_dir / tool).symlink_to(found)
    monkeypatch.setenv("PATH", str(bin_dir))

    def stub(name: str, answer: str = "") -> Path:
        script = bin_dir / name
        # one line per run whatever the arguments hold: a GraphQL query arrives with newlines in it
        script.write_text(
            f'#!/bin/sh\nprintf "%s\\n" "$(printf "%s" "$*" | tr "\\n" " ")" >> "{bin_dir / f"{name}.runs"}"\n{answer}\n'
        )
        script.chmod(0o755)
        return bin_dir / f"{name}.runs"

    return stub
