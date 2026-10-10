"""What the checks of `dispatch` and of `dispatch-ps` both stage: the runner a host is given, and
the mx install it is pointed at."""

import shutil
from pathlib import Path

SKILL = Path(__file__).parent


def stage_runner(state: Path) -> None:
    """The shipped runner and what it reads beside itself, as `dispatch` stages them on a host."""
    for name in ("run-worker.sh", "worker-prompt.md"):
        shutil.copy(SKILL / name, state / name)
    shutil.copy(SKILL.parent / "run-log" / "run-log", state / "run-log")


def mx(tmp_path: Path) -> Path:
    """The mx install `dispatch-ctl` names to a runner in DISPATCH_PLUGIN_DIR: a directory made here,
    shaped like a real one, whose leaf the lines that name the install print."""
    rules = tmp_path / "mx" / "installed" / "skills" / "session-page"
    rules.mkdir(parents=True, exist_ok=True)
    shutil.copy(SKILL.parent / "session-page" / "RULES.md", rules)
    return tmp_path / "mx" / "installed"
