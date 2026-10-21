"""Checks for auto_mode_critique.py, run as go-deep's permissions worker runs it, with a `claude` on
PATH that records the profile it was run under. Run: make test, or pytest on this file."""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "auto_mode_critique.py"
ENTRY = "Force Push [named+specifics — must name: the branch]: a force push to a branch the session did not create."

# Records the settings and the files of the profile it runs under into $STUB_SAW, then prints
# $STUB_SAYS as the real critique prints its findings.
STUB = r"""#!/usr/bin/env bash
[ "$*" = "auto-mode critique" ] || exit 2
cp "$CLAUDE_CONFIG_DIR/settings.json" "$STUB_SAW/settings.json"
readlink "$CLAUDE_CONFIG_DIR/.credentials.json" > "$STUB_SAW/credentials"
echo "Analyzing your auto mode rules…"
printf '%s\n' "$STUB_SAYS"
"""


@pytest.fixture
def saw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "claude").write_text(STUB)
    (tmp_path / "bin" / "claude").chmod(0o755)
    (tmp_path / "profile").mkdir()
    (tmp_path / "profile" / ".credentials.json").write_text("{}")
    (tmp_path / "saw").mkdir()
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{os.environ['PATH']}")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "profile"))
    monkeypatch.setenv("STUB_SAW", str(tmp_path / "saw"))
    return tmp_path / "saw"


def critique(run: Path, proposed: object, says: str) -> tuple[int, str]:
    if proposed is not None:
        (run / "deep").mkdir(parents=True)
        (run / "deep" / "auto-mode.json").write_text(json.dumps(proposed))
    done = subprocess.run([str(SCRIPT), str(run)], capture_output=True, text=True, timeout=120,
                          env={**os.environ, "STUB_SAYS": says})
    return done.returncode, (run / "deep" / "critique.md").read_text()


def test_the_critique_reads_the_proposed_entries_beside_the_shipped_defaults_alone_logged_in_as_the_profile(
        tmp_path: Path, saw: Path) -> None:
    status, written = critique(tmp_path / "run", {"soft_deny": [ENTRY], "allow": []}, "The rule has no consent bar.")

    assert status == 0
    assert json.loads((saw / "settings.json").read_text()) == {"autoMode": {"soft_deny": ["$defaults", ENTRY]}}
    assert (saw / "credentials").read_text().strip() == str(tmp_path / "profile" / ".credentials.json")
    assert "The rule has no consent bar." in written and "Analyzing" not in written


@pytest.mark.parametrize("says", ["No critique was generated.", ""])
def test_a_critique_that_printed_none_is_written_as_none_and_fails(tmp_path: Path, saw: Path, says: str) -> None:
    status, written = critique(tmp_path / "run", {"allow": [ENTRY]}, says)

    assert status == 1
    assert "No critique:" in written


@pytest.mark.parametrize("proposed", [{}, {"allow": [], "soft_deny": []}])
def test_no_entries_proposed_is_said_and_runs_no_critique(tmp_path: Path, saw: Path, proposed: dict) -> None:
    status, written = critique(tmp_path / "run", proposed, "unused")

    assert status == 0
    assert "No auto mode entries were proposed." in written
    assert not (saw / "settings.json").exists()


def test_no_proposed_entries_file_is_no_critique_and_fails(tmp_path: Path, saw: Path) -> None:
    status, written = critique(tmp_path / "run", None, "unused")

    assert status == 1
    assert "No critique: no deep/auto-mode.json was written" in written
    assert not (saw / "settings.json").exists()


@pytest.mark.parametrize("proposed", [{"deny": [ENTRY]}, {"soft_deny": ENTRY}, [ENTRY]])
def test_entries_in_another_shape_than_auto_modes_are_refused_with_the_shape_it_takes(
        tmp_path: Path, saw: Path, proposed: object) -> None:
    status, written = critique(tmp_path / "run", proposed, "unused")

    assert status == 1
    assert "No critique:" in written and "soft_deny" in written and "list of entries" in written
    assert not (saw / "settings.json").exists()
