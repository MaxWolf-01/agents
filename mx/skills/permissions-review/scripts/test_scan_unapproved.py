# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Checks for the shell parsing in scan_unapproved.py. Run: uv run test_scan_unapproved.py

Every case below is a real command shape taken from session transcripts. The parsing exists
to mirror Claude Code's permission check, so the cases that matter are the ones where naive
whole-string matching gets the answer wrong.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scan_unapproved import (
    internally_approved,
    is_allowed,
    normalize,
    signature,
    split_segments,
    strip_heredocs,
)


def test_splits_on_every_operator() -> None:
    assert split_segments("cd /tmp && tre --limit 3") == ["cd /tmp", "tre --limit 3"]
    assert split_segments("npm test | tail -6") == ["npm test", "tail -6"]
    assert split_segments("uptime; free -h") == ["uptime", "free -h"]
    assert split_segments("make check || echo failed") == ["make check", "echo failed"]
    assert split_segments("npm run dev &") == ["npm run dev"]


def test_redirect_is_not_an_operator() -> None:
    """`2>&1` must survive splitting: the & is part of the redirect, not a background op."""
    assert split_segments("npm test 2>&1 | tail -6") == ["npm test 2>&1", "tail -6"]
    assert split_segments("echo hi >&2") == ["echo hi >&2"]


def test_operators_inside_quotes_are_literal() -> None:
    assert split_segments("""tmux send-keys -t s -l 'make dev && make test'""") == [
        "tmux send-keys -t s -l 'make dev && make test'"
    ]
    assert split_segments('grep "a|b" file') == ['grep "a|b" file']


def test_heredoc_body_is_not_parsed_as_shell() -> None:
    command = "python3 - <<'EOF'\nimport os; os.system('x')\nEOF"
    assert split_segments(command) == ["python3 - HEREDOC"]
    assert "os.system" not in strip_heredocs(command)
    # An unterminated heredoc (truncated transcript) must not leak its body either.
    assert "rm -rf" not in strip_heredocs("cat > f <<'EOF'\nrm -rf /")


def test_normalize_strips_what_sits_in_front_of_the_command() -> None:
    assert normalize("timeout 90 chromium --headless --screenshot=/x.png") == (
        "chromium --headless --screenshot=/x.png"
    )
    assert normalize("timeout -k 5 300 npm test") == "npm test"
    assert normalize("MEMORY_DIR=/x uv run python y.py") == "uv run python y.py"
    assert normalize("time uv run experiments/sweep.py") == "uv run experiments/sweep.py"
    assert normalize("npm test 2>&1") == "npm test"
    assert normalize("do node --test x.ts") == "node --test x.ts"


def test_normalize_discards_pure_control_flow() -> None:
    for keyword in ("done", "fi", "for i in 1 2 3", "while true", "esac"):
        assert normalize(keyword) == "", keyword


def test_git_reads_are_auto_approved_but_writes_are_not() -> None:
    assert internally_approved("git merge-base HEAD dev")
    assert internally_approved("git -C /home/max/repos/x status --short")
    assert internally_approved("git -C /home/max/repos/x merge-base a b")
    assert not internally_approved("git -C /home/max/repos/x commit -m msg")
    assert not internally_approved("git add -A")
    # Ambiguous subcommands fall through to settings.json rather than being assumed safe.
    assert not internally_approved("git branch -d feature")
    assert not internally_approved("git -C /x worktree add ../y")


def test_read_only_programs_lose_the_exemption_when_they_can_write() -> None:
    assert internally_approved("sed -n 1,60p CONTEXT.md")
    assert not internally_approved("sed -i s/a/b/ file")
    assert not internally_approved("sed -i.bak s/a/b/ file")
    assert not internally_approved("sed -ni p file")
    assert internally_approved("find . -name '*.py'")
    assert not internally_approved("find . -name '*.tmp' -delete")
    assert not internally_approved("find . -exec rm {} ;")


def test_absolute_paths_do_not_bypass_the_read_only_set() -> None:
    assert internally_approved("/usr/bin/cat file")
    assert not internally_approved("/tmp/shot.py --url http://x")


def test_signature_groups_by_the_word_that_carries_the_meaning() -> None:
    assert signature("git -C /home/max/repos/skilltree-23 commit -m x") == "git -C * commit ..."
    assert signature("git -C /home/max/repos/other commit -q") == "git -C * commit ..."
    assert signature("ssh jarvis docker ps -a") == "ssh * docker ps ..."
    assert signature("docker compose logs -f gateway") == "docker compose logs ..."
    assert signature("npm run check:web") == "npm run ..."
    assert signature("chromium --headless --screenshot=/x.png") == "chromium ..."


def test_allowlist_globs_span_arguments() -> None:
    patterns = ["npm --prefix * run check", "chromium --headless *", "chromium --headless=*"]
    assert is_allowed("npm --prefix /home/max/repos/x run check", patterns)
    assert is_allowed("chromium --headless --disable-gpu --screenshot=/x.png", patterns)
    assert is_allowed("chromium --headless=new --dump-dom about:blank", patterns)
    assert not is_allowed("chromium --window-size=800,600 file.html", patterns)


def test_the_case_the_old_scanner_got_wrong() -> None:
    """`cd X && tre` was the scanner's single largest reported offender. It never prompts."""
    patterns = ["tre *"]
    segments = [normalize(s) for s in split_segments("cd /tmp/greyline && tre --limit 60")]
    assert all(is_allowed(s, patterns) or internally_approved(s) for s in segments)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} passed")
