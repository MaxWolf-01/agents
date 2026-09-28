# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for `run-log`: the line one model run leaves, the lines a host's log gives up to `pull`,
and the rollups `report` prints. Run: uv run test_run_log.py

The seam is the script itself, run with a stand-in `claude` on PATH that prints what
`--output-format stream-json` prints, cut short where a test wants a run that died, and a stand-in
`ssh` that answers with a remote log. The oracle is the `run-log` ticket: one line per run, written
whether or not claude reported, carrying what the ticket lists; a host's lines come back once.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "run-log"

INIT = {"type": "system", "subtype": "init", "session_id": "sess-1", "model": "claude-opus-5-5"}
# One message streams as several lines that share its id; the tokens are the last line's.
TURN_A = {"type": "assistant", "message": {"id": "m1", "model": "claude-opus-5-5",
          "usage": {"input_tokens": 10, "output_tokens": 2, "cache_read_input_tokens": 500, "cache_creation_input_tokens": 20}}}
TURN_B = {"type": "assistant", "message": {"id": "m1", "model": "claude-opus-5-5",
          "usage": {"input_tokens": 10, "output_tokens": 40, "cache_read_input_tokens": 500, "cache_creation_input_tokens": 20}}}
TURN_C = {"type": "assistant", "message": {"id": "m2", "model": "claude-sonnet-5",
          "usage": {"input_tokens": 12, "output_tokens": 30, "cache_read_input_tokens": 600, "cache_creation_input_tokens": 0}}}
RESULT = {"type": "result", "subtype": "success", "is_error": False, "session_id": "sess-1", "num_turns": 2,
          "duration_ms": 4200, "duration_api_ms": 3900, "total_cost_usd": 0.1234,
          "usage": {"input_tokens": 22, "output_tokens": 70, "cache_read_input_tokens": 1100, "cache_creation_input_tokens": 20},
          "modelUsage": {"claude-opus-5-5-20260101": {"canonicalModel": "claude-opus-5-5"},
                         "claude-sonnet-5-20260101": {"canonicalModel": "claude-sonnet-5"}},
          "result": "The answer.\n"}


def stream(*events: dict) -> str:
    return "".join(json.dumps(e) + "\n" for e in events)


def fake_claude(where: Path, prints: str, then: str = "exit 0") -> Path:
    """A `claude` that records its argv and stdin, prints `prints`, and does `then`."""
    bin_dir = where / "bin"
    bin_dir.mkdir(exist_ok=True)
    (where / "prints").write_text(prints)
    (bin_dir / "claude").write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$@" > "{where}/argv"\n'
        f'cat > "{where}/stdin"\n'
        f'cat "{where}/prints"\n'
        f"{then}\n")
    (bin_dir / "claude").chmod(0o755)
    return bin_dir


def run_log(where: Path, *args: str, stdin: str = "", env: dict | None = None,
            cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([str(SCRIPT), *args], cwd=cwd or where, input=stdin, capture_output=True, text=True, timeout=60,
                          env={**os.environ, "RUN_LOG": str(where / "runs.jsonl"),
                               "PATH": f"{where / 'bin'}:{os.environ['PATH']}", **(env or {})})


def lines(where: Path) -> list[dict]:
    return [json.loads(line) for line in (where / "runs.jsonl").read_text().splitlines()]


def test_a_run_leaves_one_line_with_what_claude_reported_and_prints_the_answer(tmp_path: Path) -> None:
    fake_claude(tmp_path, stream(INIT, TURN_A, TURN_B, TURN_C, RESULT))
    done = run_log(tmp_path, "run", "--site", "review", "--ticket", "warm-preset", "--axis", "tests", "--range", "a1b2c3d..e4f5a6b", "--",
                   "claude", "-p", "--model", "opus", "--effort", "medium", "--tools", "", stdin="the brief")
    assert done.returncode == 0, done.stderr
    assert done.stdout == "The answer.\n", "the caller sees what the model answered"
    assert (tmp_path / "stdin").read_text() == "the brief", "claude reads the caller's stdin"
    assert "--verbose\n--output-format\nstream-json" in (tmp_path / "argv").read_text()
    (line,) = lines(tmp_path)
    assert {k: line[k] for k in ("site", "ticket", "axis", "attempt", "range", "model", "effort", "session", "ran", "exit", "end")} == {
        "site": "review", "ticket": "warm-preset", "axis": "tests", "attempt": None, "range": "a1b2c3d..e4f5a6b", "model": "opus", "effort": "medium",
        "session": "sess-1", "ran": ["claude-opus-5-5", "claude-sonnet-5"], "exit": 0, "end": "success"}
    assert (line["cost_usd"], line["api_s"], line["turns"]) == (0.1234, 3.9, 2)
    assert line["tokens"] == {"input": 22, "output": 70, "cache_read": 1100, "cache_write": 20}, "the result's totals, not the messages'"
    assert line["at"].endswith("Z") and line["id"] and line["host"]


def test_a_run_in_a_repo_names_the_repo_off_its_git_dir(tmp_path: Path) -> None:
    """The name a worker host's bare repo and a checkout share, `<repo>.git` and `<repo>/.git`,
    which is how `dispatch` names its scratch dirs."""
    fake_claude(tmp_path, stream(INIT, RESULT))
    checkout = tmp_path / "lamp"
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    done = run_log(tmp_path, "run", "--site", "briefing", "--", "claude", "-p", cwd=checkout)
    assert done.returncode == 0, done.stderr
    assert lines(tmp_path)[0]["repo"] == "lamp"
    bare = tmp_path / "lamp.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(checkout), str(bare)], check=True)
    subprocess.run(["git", "-C", str(checkout), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "one"], check=True)
    subprocess.run(["git", "-C", str(bare), "fetch", "-q", str(checkout), "HEAD:refs/heads/main"], check=True)
    worktree = tmp_path / "lamp-warm-preset"
    subprocess.run(["git", "-C", str(bare), "worktree", "add", "-q", str(worktree), "main"], check=True)
    done = run_log(tmp_path, "run", "--site", "worker", "--", "claude", "-p", cwd=worktree)
    assert done.returncode == 0, done.stderr
    assert lines(tmp_path)[1]["repo"] == "lamp"


def test_a_run_that_ends_without_a_result_still_gets_its_line(tmp_path: Path) -> None:
    """Killed, crashed or cut off: the line says so, sums the tokens of the messages that arrived,
    one per message however many lines it streamed as, and carries claude's exit and the session
    id a resume needs. What claude printed goes through, since with no result it is the error."""
    synthetic = {"type": "assistant", "message": {"id": "m9", "model": "<synthetic>", "usage": {"input_tokens": 0, "output_tokens": 0}}}
    fake_claude(tmp_path, stream(INIT, TURN_A, TURN_B, synthetic) + "API Error: overloaded\n", then="exit 1")
    done = run_log(tmp_path, "run", "--site", "worker", "--attempt", "2", "--range", "", "--", "claude", "-p", "--model", "opus")
    assert done.returncode == 1
    assert done.stdout == "API Error: overloaded\n"
    (line,) = lines(tmp_path)
    assert (line["exit"], line["end"], line["cost_usd"], line["turns"], line["attempt"]) == (1, "no result", None, None, 2)
    assert line["session"] == "sess-1" and line["ran"] == ["claude-opus-5-5"]
    assert line["tokens"] == {"input": 10, "output": 40, "cache_read": 500, "cache_write": 20}


def test_a_term_ends_the_run_and_the_line_says_stopped(tmp_path: Path) -> None:
    """What `dispatch-ctl stop` sends: claude gets it, the line is written, the exit is TERM's."""
    # a claude that writes one more message on its way out, which the line has to carry
    (tmp_path / "late").write_text(stream({"type": "assistant", "message": {"id": "m7", "model": "claude-opus-5-5",
                                   "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 1, "cache_creation_input_tokens": 1}}}))
    fake_claude(tmp_path, stream(INIT, TURN_A), then=f"trap 'sleep 0.5; cat {tmp_path}/late; exit 143' TERM\nsleep 30 & wait $!")
    proc = subprocess.Popen([str(SCRIPT), "run", "--site", "worker", "--", "claude", "-p"], cwd=tmp_path,
                            env={**os.environ, "RUN_LOG": str(tmp_path / "runs.jsonl"),
                                 "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}"},
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for _ in range(100):
        if (tmp_path / "argv").exists():
            break
        time.sleep(0.1)
    time.sleep(0.3)
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=20)
    assert proc.returncode == 143
    (line,) = lines(tmp_path)
    assert (line["exit"], line["end"], line["session"]) == ("stopped", "no result", "sess-1")
    assert line["duration_s"] < 10, "claude was signalled rather than waited out"
    assert line["tokens"] == {"input": 11, "output": 3, "cache_read": 501, "cache_write": 21}, "what claude wrote after TERM is in the line"


def test_a_timeout_ends_the_run_the_way_a_term_does_and_the_line_says_so(tmp_path: Path) -> None:
    """The callers with a limit of their own (the briefing, change-summary) give it to run-log,
    which is what can still write the line and stop claude; a kill from above would leave claude
    running and the line unwritten."""
    fake_claude(tmp_path, stream(INIT, TURN_A), then="trap 'exit 143' TERM\nsleep 30 & wait $!")
    done = run_log(tmp_path, "run", "--site", "briefing", "--timeout", "1", "--", "claude", "-p")
    assert done.returncode == 124
    (line,) = lines(tmp_path)
    assert (line["exit"], line["end"], line["session"]) == ("timeout", "no result", "sess-1")
    assert line["duration_s"] < 10
    fake_claude(tmp_path, stream(INIT, RESULT))
    done = run_log(tmp_path, "run", "--site", "briefing", "--timeout", "30", "--", "claude", "-p")
    assert done.returncode == 0 and done.stdout == "The answer.\n", "a run within its limit is untouched"
    assert lines(tmp_path)[1]["exit"] == 0
    assert "whole number" in run_log(tmp_path, "run", "--site", "x", "--timeout", "soon", "--", "claude").stderr


def test_json_prints_the_result_object_for_a_caller_that_reads_it(tmp_path: Path) -> None:
    """The last result where a stream carries several, in both forms."""
    first = {**RESULT, "session_id": "sess-0", "result": "An earlier answer.\n"}
    fake_claude(tmp_path, stream(INIT, first, RESULT))
    done = run_log(tmp_path, "run", "--site", "briefing", "--json", "--", "claude", "-p")
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == RESULT
    done = run_log(tmp_path, "run", "--site", "briefing", "--", "claude", "-p")
    assert done.stdout == "The answer.\n"
    assert [line["session"] for line in lines(tmp_path)] == ["sess-1", "sess-1"]


def test_run_refuses_a_call_with_no_site_or_no_command(tmp_path: Path) -> None:
    fake_claude(tmp_path, "")
    assert "--site" in run_log(tmp_path, "run", "--", "claude").stderr
    assert "after --" in run_log(tmp_path, "run", "--site", "worker").stderr
    done = run_log(tmp_path, "run", "--site", "worker", "--", "no-such-claude", "-p")
    assert (done.returncode, done.stdout) == (127, "") and "not on PATH" in done.stderr
    assert not (tmp_path / "runs.jsonl").exists()


def test_needs_names_the_commands_the_script_runs_and_nothing_it_does_not(tmp_path: Path) -> None:
    """What a host or a test's PATH has to hold: every external command the script runs is in the
    list, and everything in the list is on this machine."""
    fake_claude(tmp_path, "")
    needs = run_log(tmp_path, "needs").stdout.split()
    assert {"jq", "git", "ssh", "hostname", "column"} <= set(needs)
    for tool in needs:
        assert subprocess.run(["sh", "-c", f"command -v {tool}"], capture_output=True).returncode == 0, tool
    source = SCRIPT.read_text()
    for tool in ("jq", "git", "hostname", "realpath", "basename", "dirname", "mktemp", "date", "cat", "grep", "sed", "wc",
                 "mkdir", "rm", "tee", "touch", "column", "ssh", "timeout", "kill"):
        assert tool in needs, f"{tool} is run by the script but not in its Needs line"
        assert tool in source


def test_pull_appends_the_lines_a_host_has_that_this_log_lacks_and_no_line_twice(tmp_path: Path) -> None:
    here = [{"id": "a", "at": "2026-09-26T10:00:00Z", "site": "worker"}]
    there = here + [{"id": "b", "at": "2026-09-26T11:00:00Z", "site": "review"}]
    (tmp_path / "runs.jsonl").write_text(stream(*here))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "ssh").write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{tmp_path}/ssh.calls"\ncat "{tmp_path}/remote.jsonl"\n')
    (bin_dir / "ssh").chmod(0o755)
    (tmp_path / "remote.jsonl").write_text(stream(*there))
    done = run_log(tmp_path, "pull", "agent@far")
    assert done.returncode == 0, done.stderr
    assert "pulled 1 new run(s) from agent@far" in done.stdout
    assert [line["id"] for line in lines(tmp_path)] == ["a", "b"]
    call = (tmp_path / "ssh.calls").read_text()
    assert "agent@far" in call and "RUN_LOG" in call and "logs/agent/runs.jsonl" in call, "the same path is read on the host"
    done = run_log(tmp_path, "pull", "agent@far")
    assert "pulled 0 new run(s)" in done.stdout and [line["id"] for line in lines(tmp_path)] == ["a", "b"]


def test_report_rolls_cost_and_time_up_per_site_ticket_and_axis(tmp_path: Path) -> None:
    def line(**fields: object) -> dict:
        return {"id": str(fields), "at": "2026-09-26T10:00:00Z", "repo": "agents", "ticket": "", "axis": "",
                "cost_usd": 0.5, "duration_s": 120, "end": "success", **fields}
    (tmp_path / "runs.jsonl").write_text(stream(
        line(site="worker", ticket="warm-preset", cost_usd=2.0, duration_s=600, model="opus", effort="high"),
        line(site="review", ticket="warm-preset", axis="tests", duration_s=300, model="opus", effort="medium"),
        line(site="review", ticket="warm-preset", axis="spec", model="opus", effort="medium"),
        line(site="review", ticket="warm-preset", axis="tests", cost_usd=None, end="no result", at="2026-09-20T10:00:00Z", model="opus", effort="high"),
        line(site="briefing", repo="lamp", model="opus", effort="medium"),
    ) + "{half a line\n")
    done = run_log(tmp_path, "report", "--json")
    assert done.returncode == 0, done.stderr
    assert "1 line(s)" in done.stderr and "could not be read" in done.stderr
    rows = json.loads(done.stdout)
    assert {r["key"]: (r["runs"], r["cost_usd"], r["minutes"], r["mean_minutes"]) for r in rows["by_site"]} == {
        "worker": (1, 2.0, 10, 10), "review": (3, 1.0, 9, 3.0), "briefing": (1, 0.5, 2, 2)}
    assert {r["key"]: (r["runs"], r["no_result"]) for r in rows["by_axis"]} == {"tests": (2, 1), "spec": (1, 0)}
    assert [r["key"] for r in rows["by_ticket"]] == ["warm-preset"]
    assert {r["key"]: r["runs"] for r in rows["by_effort"]} == {"worker opus high": 1, "review opus medium": 2, "review opus high": 1, "briefing opus medium": 1}
    rows = json.loads(run_log(tmp_path, "report", "--json", "--since", "2026-09-25", "--repo", "agents").stdout)
    assert {r["key"]: r["runs"] for r in rows["by_site"]} == {"worker": 1, "review": 2}
    rows = json.loads(run_log(tmp_path, "report", "--json", "--site", "review").stdout)
    assert [r["key"] for r in rows["by_site"]] == ["review"] and {r["key"] for r in rows["by_axis"]} == {"tests", "spec"}
    table = run_log(tmp_path, "report").stdout
    assert "by_site" in table and "warm-preset" in table and "tests" in table and "review opus medium" in table


def test_report_with_nothing_logged_says_so(tmp_path: Path) -> None:
    done = run_log(tmp_path, "report")
    assert done.returncode == 1 and "no runs logged" in done.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
