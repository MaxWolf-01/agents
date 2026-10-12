"""plugin_updates.py, run as Claude Code runs it: from a copy of mx in a scratch directory, with
its own version and CHANGELOG.md, the hook JSON on stdin and $CLAUDE_PLUGIN_DATA set."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

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
    shutil.copy(HOOK, root / "hooks" / HOOK.name)
    return root


def run(plugin: Path, event: str, data: Path | None) -> dict | None:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_DATA"} | ({"CLAUDE_PLUGIN_DATA": str(data)} if data else {})
    done = subprocess.run([plugin / "hooks" / HOOK.name], input=json.dumps({"session_id": SESSION, "hook_event_name": event}),
                          capture_output=True, text=True, env=env, check=True)
    return json.loads(done.stdout) if done.stdout.strip() else None


def record(data: Path) -> str:
    return (data / "sessions" / SESSION).read_text().strip()


def test_a_session_start_records_its_version_and_says_nothing(plugin: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    assert run(plugin, "SessionStart", data) is None
    assert record(data) == "1.0.56"
    assert run(plugin, "UserPromptSubmit", data) is None


def test_a_session_moved_to_a_newer_mx_hears_each_skipped_versions_changes_once(plugin: Path, tmp_path: Path) -> None:
    """Moved from 1.0.54 to 1.0.56: the entries of 1.0.55 and 1.0.56, not 1.0.54's own, then
    nothing on the next prompt."""
    data = tmp_path / "data"
    (data / "sessions").mkdir(parents=True)
    (data / "sessions" / SESSION).write_text("1.0.54\n")
    said = run(plugin, "UserPromptSubmit", data)
    assert said["systemMessage"] == "mx updated 1.0.54 → 1.0.56"
    context = said["hookSpecificOutput"]["additionalContext"]
    assert said["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "- hub: background commands on the session page" in context
    assert "- session page: a turn another session starts is a turn" in context
    assert "fast suite" not in context
    assert record(data) == "1.0.56"
    assert run(plugin, "UserPromptSubmit", data) is None


def test_a_resumed_session_hears_it_at_its_start(plugin: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "sessions").mkdir(parents=True)
    (data / "sessions" / SESSION).write_text("1.0.55\n")
    said = run(plugin, "SessionStart", data)
    assert said["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "background commands" in said["hookSpecificOutput"]["additionalContext"]


def test_a_prompt_with_no_record_is_a_session_moved_from_before_the_hook_existed(plugin: Path, tmp_path: Path) -> None:
    said = run(plugin, "UserPromptSubmit", tmp_path / "data")
    assert said["systemMessage"] == "mx updated to 1.0.56"
    assert "may be out of date" in said["hookSpecificOutput"]["additionalContext"]
    assert record(tmp_path / "data") == "1.0.56"


def test_a_long_changelog_is_cut_and_says_where_the_rest_is(plugin: Path, tmp_path: Path) -> None:
    (plugin / "CHANGELOG.md").write_text("## 1.0.56\n\n" + "".join(f"- change {n}\n" for n in range(30)))
    data = tmp_path / "data"
    (data / "sessions").mkdir(parents=True)
    (data / "sessions" / SESSION).write_text("1.0.55\n")
    context = run(plugin, "UserPromptSubmit", data)["hookSpecificOutput"]["additionalContext"]
    assert "- change 19" in context and "- change 20" not in context
    assert f"and 10 more lines in {plugin / 'CHANGELOG.md'}" in context


def test_without_a_plugin_data_directory_it_does_nothing(plugin: Path) -> None:
    assert run(plugin, "UserPromptSubmit", None) is None
