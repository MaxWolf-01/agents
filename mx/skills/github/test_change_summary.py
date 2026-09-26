# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro"]
# ///
"""Checks for `change-summary`: the flags that keep its model call bare, the prose rules it hands
the model, its retry past the cap and each way it fails. Run: uv run test_change_summary.py

The seams are the `mx/bin` shim, run with a stand-in `claude` on PATH that records each call's
arguments, stdin and working directory and answers with the reply the test queued for that call,
and the rule selection, catalogue text in, rule blocks out.
The oracles are `agent/tickets/change-summary-tool.md`'s acceptance criteria and the parent
`pr-body` ticket's P1 and P2: the summary is written from the diff alone, and never exceeds 150
words. The rule selection is held to the awk command CATALOGUE.md's header publishes as its
format contract, with the `artifact` scope put in for `chat`.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from change_summary import CATALOGUE, Failure, artifact_rules

SHIM = Path(__file__).resolve().parents[2] / "bin" / "change-summary"

FAKE_CLAUDE = r"""#!/usr/bin/env bash
n=$(( $(cat "$FAKE_DIR/calls" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$FAKE_DIR/calls"
printf '%s\0' "$@" > "$FAKE_DIR/argv.$n"
cat > "$FAKE_DIR/stdin.$n"
pwd > "$FAKE_DIR/cwd.$n"
ls -A > "$FAKE_DIR/ls.$n"
[ -f "$FAKE_DIR/reply.$n" ] && cat "$FAKE_DIR/reply.$n"
[ -n "${FAKE_STDERR:-}" ] && echo "$FAKE_STDERR" >&2
exit "${FAKE_EXIT:-0}"
"""

DIFF = """diff --git a/greet.py b/greet.py
--- a/greet.py
+++ b/greet.py
@@ -1 +1 @@
-print("hello")
+print("hello, world")
"""


def words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


class Claude:
    """The stand-in's directory: replies queued per call, and what each call received."""

    def __init__(self, root: Path) -> None:
        self.dir = root / "fake"
        self.dir.mkdir()
        (root / "bin").mkdir()
        (root / "bin" / "claude").write_text(FAKE_CLAUDE)
        (root / "bin" / "claude").chmod(0o755)
        self.path = f"{root / 'bin'}:{os.environ['PATH']}"

    def replies(self, *texts: str) -> None:
        for n, text in enumerate(texts, 1):
            (self.dir / f"reply.{n}").write_text(text)

    @property
    def calls(self) -> int:
        calls = self.dir / "calls"
        return int(calls.read_text()) if calls.exists() else 0

    def argv(self, n: int = 1) -> list[str]:
        return (self.dir / f"argv.{n}").read_text().split("\0")[:-1]

    def flag(self, name: str, n: int = 1) -> str:
        argv = self.argv(n)
        return argv[argv.index(name) + 1]

    def stdin(self, n: int = 1) -> str:
        return (self.dir / f"stdin.{n}").read_text()


@pytest.fixture
def claude(tmp_path: Path) -> Claude:
    return Claude(tmp_path)


def run(claude: Claude, diff: str = DIFF, *args: str, **env: str) -> subprocess.CompletedProcess:
    base = {k: v for k, v in os.environ.items() if k != "CHANGE_SUMMARY_MODEL"}
    return subprocess.run(
        [str(SHIM), *args], input=diff, capture_output=True, text=True, timeout=120,
        cwd=claude.dir.parent, env={**base, "PATH": claude.path, "FAKE_DIR": str(claude.dir), **env},
    )


def awk_selection() -> str:
    """The header's own command, scoped to `artifact`, run on the real catalogue."""
    program = re.search(r"awk '(.+?)' CATALOGUE\.md", CATALOGUE.read_text()).group(1).replace("`chat`", "`artifact`")
    run = subprocess.run(["awk", program, CATALOGUE], capture_output=True, text=True, check=True)
    return run.stdout.rstrip("\n")


def test_a_diff_gives_its_paragraph_on_stdout(claude: Claude) -> None:
    claude.replies("The greeting now names the world.\n")
    done = run(claude)
    assert (done.returncode, done.stdout, claude.calls) == (0, "The greeting now names the world.\n", 1)
    assert claude.stdin() == DIFF


def test_the_model_call_loads_no_settings_plugins_mcp_tools_commands_or_session(claude: Claude) -> None:
    claude.replies("A paragraph.")
    run(claude)
    argv = claude.argv()
    assert argv[0] == "-p"
    assert claude.flag("--setting-sources") == ""
    assert claude.flag("--tools") == ""
    assert {"--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"} <= set(argv)
    assert "--system-prompt" in argv


def test_the_model_runs_where_no_project_file_is_in_reach(claude: Claude) -> None:
    claude.replies("A paragraph.")
    run(claude)
    assert Path((claude.dir / "cwd.1").read_text().strip()) != claude.dir.parent
    assert (claude.dir / "ls.1").read_text() == ""


def test_the_system_prompt_carries_the_catalogues_artifact_and_both_rules(claude: Claude) -> None:
    claude.replies("A paragraph.")
    run(claude)
    assert claude.flag("--system-prompt").endswith("# Rules\n\n" + awk_selection())


FIXTURE = """# Tells

## Content

- `3` `both` **A rule.** Its first line.
  Before: "indented continuation". After: "rides with its rule".

- `13` `chat` **A rule for replies.** Dropped.

## Style

- `51` `artifact` **A rule for files only.** Kept.
"""


def test_chat_rules_stay_out_of_the_selection() -> None:
    assert artifact_rules(FIXTURE) == (
        '- `3` `both` **A rule.** Its first line.\n'
        '  Before: "indented continuation". After: "rides with its rule".\n\n'
        '- `51` `artifact` **A rule for files only.** Kept.'
    )


def test_a_catalogue_with_no_artifact_rules_fails() -> None:
    with pytest.raises(Failure):
        artifact_rules(FIXTURE.replace("`both`", "`chat`").replace("`artifact`", "`chat`"))


def test_opus_by_default_and_the_flag_beats_the_environment(claude: Claude) -> None:
    claude.replies("A paragraph.")
    run(claude)
    assert claude.flag("--model") == "opus"
    for n, (args, env) in enumerate([((), {"CHANGE_SUMMARY_MODEL": "haiku"}),
                                     (("--model", "sonnet"), {"CHANGE_SUMMARY_MODEL": "haiku"})], 2):
        (claude.dir / f"reply.{n}").write_text("A paragraph.")
        run(claude, DIFF, *args, **env)
    assert (claude.flag("--model", 2), claude.flag("--model", 3)) == ("haiku", "sonnet")


def test_a_paragraph_at_the_cap_is_kept(claude: Claude) -> None:
    claude.replies(words(150))
    done = run(claude)
    assert (done.returncode, done.stdout.strip(), claude.calls) == (0, words(150), 1)


def test_a_paragraph_past_the_cap_is_asked_for_again(claude: Claude) -> None:
    claude.replies(words(151), "A shorter paragraph.")
    done = run(claude)
    assert (done.returncode, done.stdout, claude.calls) == (0, "A shorter paragraph.\n", 2)
    assert claude.stdin(2).startswith(DIFF) and "151 words" in claude.stdin(2)
    assert claude.flag("--system-prompt", 2) == claude.flag("--system-prompt", 1)


def test_a_paragraph_still_past_the_cap_after_the_retry_fails_with_it_on_stderr(claude: Claude) -> None:
    claude.replies(words(200), words(151))
    done = run(claude)
    assert (done.returncode, done.stdout, claude.calls) == (1, "", 2)
    assert "151 words" in done.stderr and words(151) in done.stderr


def test_an_empty_diff_fails_before_any_model_call(claude: Claude) -> None:
    done = run(claude, " \n\n")
    assert (done.returncode, done.stdout, claude.calls) == (1, "", 0)
    assert "no diff" in done.stderr


def test_a_failed_model_call_fails_with_its_reason(claude: Claude) -> None:
    done = run(claude, FAKE_EXIT="3", FAKE_STDERR="rate limited")
    assert (done.returncode, done.stdout) == (1, "")
    assert "exited 3" in done.stderr and "rate limited" in done.stderr


def test_no_claude_on_path_fails_with_its_reason(claude: Claude) -> None:
    tools = claude.dir.parent / "tools"
    tools.mkdir()
    for tool in ("bash", "uv", "readlink", "dirname"):
        (tools / tool).symlink_to(shutil.which(tool))
    claude.path = str(tools)
    done = run(claude)
    assert (done.returncode, done.stdout) == (1, "")
    assert "did not run" in done.stderr


def test_a_diff_that_is_not_utf8_still_reaches_the_model(claude: Claude) -> None:
    claude.replies("A paragraph.")
    done = subprocess.run([str(SHIM)], input=DIFF.replace("world", "w\xf6rld").encode("latin-1"),
                          capture_output=True, timeout=120, env={**os.environ, "PATH": claude.path, "FAKE_DIR": str(claude.dir)})
    assert (done.returncode, done.stdout) == (0, b"A paragraph.\n")
    assert "w\ufffdrld" in claude.stdin()


def test_an_empty_answer_fails(claude: Claude) -> None:
    claude.replies("\n")
    done = run(claude)
    assert (done.returncode, done.stdout) == (1, "")
    assert "no paragraph" in done.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
