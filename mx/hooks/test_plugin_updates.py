"""plugin_updates.py against a scratch mx tree, with that tree's own version and CHANGELOG.md, the
hook JSON on stdin and $CLAUDE_PLUGIN_DATA set. One run is the hook as Claude Code runs it: by its
path, a process of its own, in this checkout's mx tree."""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import plugin_updates

HOOK = Path(__file__).resolve().parent / "plugin_updates.py"
SESSION = "5158394a-b5c2-4dd5-ba9a-80cabf5ab8c3"
CHANGELOG = """## 1.0.56

- hub: background commands on the session page

## 1.0.55

- session page: a turn another session starts is a turn

## 1.0.54

- testing: the fast suite is defined by what it touches
"""


@pytest.fixture
def plugin(tmp_path: Path) -> Path:
    root = tmp_path / "mx" / "1.0.56"
    (root / "hooks").mkdir(parents=True)
    (root / ".claude-plugin").mkdir()
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "mx", "version": "1.0.56"}))
    (root / "CHANGELOG.md").write_text(CHANGELOG)
    return root


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    def run(plugin: Path, event: str, data: Path | None) -> dict | None:
        if data:
            monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))
        else:
            monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": SESSION, "hook_event_name": event})))
        plugin_updates.main(plugin)
        out = capsys.readouterr().out
        return json.loads(out) if out.strip() else None
    return run


def record(data: Path) -> str:
    return (data / "sessions" / SESSION).read_text().strip()


def test_a_session_start_records_its_version_and_says_nothing(run, plugin: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    assert run(plugin, "SessionStart", data) is None
    assert record(data) == "1.0.56"
    assert run(plugin, "UserPromptSubmit", data) is None


def test_a_session_moved_to_a_newer_mx_hears_each_skipped_versions_changes_once(run, plugin: Path, tmp_path: Path) -> None:
    """Moved from 1.0.54 to 1.0.56: the entries of 1.0.55 and 1.0.56, not 1.0.54's own, then
    nothing on the next prompt."""
    data = tmp_path / "data"
    (data / "sessions").mkdir(parents=True)
    (data / "sessions" / SESSION).write_text("1.0.54\n")
    said = run(plugin, "UserPromptSubmit", data)
    assert said["systemMessage"] == "mx updated from 1.0.54 to 1.0.56"
    context = said["hookSpecificOutput"]["additionalContext"]
    assert said["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "- hub: background commands on the session page" in context
    assert "- session page: a turn another session starts is a turn" in context
    assert "## 1.0.56" in context and "## 1.0.55" in context
    assert "fast suite" not in context and "## 1.0.54" not in context
    assert record(data) == "1.0.56"
    assert run(plugin, "UserPromptSubmit", data) is None


def test_a_resumed_session_hears_it_at_its_start(run, plugin: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "sessions").mkdir(parents=True)
    (data / "sessions" / SESSION).write_text("1.0.55\n")
    said = run(plugin, "SessionStart", data)
    assert said["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "background commands" in said["hookSpecificOutput"]["additionalContext"]


def test_a_prompt_with_no_record_is_a_session_moved_from_before_the_hook_existed(run, plugin: Path, tmp_path: Path) -> None:
    said = run(plugin, "UserPromptSubmit", tmp_path / "data")
    assert said["systemMessage"] == "mx updated to 1.0.56"
    assert "may be out of date" in said["hookSpecificOutput"]["additionalContext"]
    assert record(tmp_path / "data") == "1.0.56"


def test_a_long_changelog_is_cut_and_says_where_the_rest_is(run, plugin: Path, tmp_path: Path) -> None:
    (plugin / "CHANGELOG.md").write_text("## 1.0.56\n\n" + "".join(f"- change {n}\n" for n in range(30)))
    data = tmp_path / "data"
    (data / "sessions").mkdir(parents=True)
    (data / "sessions" / SESSION).write_text("1.0.55\n")
    context = run(plugin, "UserPromptSubmit", data)["hookSpecificOutput"]["additionalContext"]
    assert "- change 18" in context and "- change 19" not in context
    assert f"and 11 more lines in {plugin / 'CHANGELOG.md'}" in context


def test_without_a_plugin_data_directory_it_does_nothing(run, plugin: Path) -> None:
    assert run(plugin, "UserPromptSubmit", None) is None


def test_a_session_that_runs_keeps_its_record_however_old_the_others(run, plugin: Path, tmp_path: Path) -> None:
    """A record is pruned by how long its session has not run: the session's own never, a stale
    one when another session starts, and a run on the same version makes its record young again."""
    data = tmp_path / "data"
    run(plugin, "SessionStart", data)
    own, stale = data / "sessions" / SESSION, data / "sessions" / "a-session-gone-quiet"
    stale.write_text("1.0.40\n")
    long_ago = 1_000_000
    os.utime(own, (long_ago, long_ago))
    os.utime(stale, (long_ago, long_ago))
    assert run(plugin, "SessionStart", data) is None
    assert (own.exists(), stale.exists()) == (True, False)
    assert own.stat().st_mtime > long_ago
    assert run(plugin, "UserPromptSubmit", data) is None


def test_the_hook_run_by_its_path_reads_the_version_and_changelog_of_the_tree_it_sits_in(tmp_path: Path) -> None:
    """This checkout's mx tree: the version its plugin.json carries, the changelog beside it."""
    mx = HOOK.parents[1]
    version = json.loads((mx / ".claude-plugin" / "plugin.json").read_text())["version"]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_DATA"} | {"CLAUDE_PLUGIN_DATA": str(tmp_path)}
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / SESSION).write_text("0.0.0\n")
    done = subprocess.run([HOOK], input=json.dumps({"session_id": SESSION, "hook_event_name": "UserPromptSubmit"}),
                          capture_output=True, text=True, env=env, check=True, timeout=120)
    said = json.loads(done.stdout)
    assert said["systemMessage"] == f"mx updated from 0.0.0 to {version}"
    assert f"## {version}" in said["hookSpecificOutput"]["additionalContext"]
    assert f"more lines in {mx / 'CHANGELOG.md'}" in said["hookSpecificOutput"]["additionalContext"]
    assert record(tmp_path) == version
