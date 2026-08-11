# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Scan Claude Code sessions for Bash commands the permission allowlist does not cover.

Claude Code permission-checks a command *per segment*: it splits on ``|``, ``;``, ``&&``
and ``||``, unwraps ``timeout N ...``, and separately auto-approves a built-in set of
read-only programs without consulting settings.json at all. Matching a whole command
string against the allowlist therefore produces mostly noise -- ``cd /tmp && tre`` looks
unapproved even though neither half ever prompts. This script mirrors the real behaviour,
so what it reports is what actually interrupts you.

Reads the allowlist from settings.json file(s), so results stay in sync with
configuration. Output: JSON array of {signature, count, example} objects sorted by
frequency, one entry per distinct *segment* shape that would prompt.

Examples::

    uv run scan_unapproved.py ~/.claude/projects/ ~/.claude/settings.json
    uv run scan_unapproved.py ~/.claude/projects/-home-max-myproject/ global.json project.json --days 60
    uv run scan_unapproved.py ~/.claude/projects/ ~/.claude/settings.json --show-auto-approved
"""

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from fnmatch import fnmatch
from pathlib import Path
from typing import Annotated

import tyro

# Programs Claude Code auto-approves regardless of settings.json. Version-dependent:
# confirmed by probing a live session (run the command, see whether it prompts). Re-probe
# after a Claude Code upgrade -- a stale entry here hides real friction. `--show-auto-approved`
# lists what this set swallowed, which is where a stale entry shows up.
READ_ONLY_PROGRAMS = frozenset("""
    awk base64 basename cat cd cut date df diff dirname du echo false file find free grep head
    hostname id jq ls lsof man md5sum nproc pgrep printf ps pwd readlink realpath rg sed seq
    sha256sum sleep sort ss stat strings tail tr tree true type uname uniq uptime wc which whoami
    xargs
""".split())

# Only subcommands that cannot mutate. Ambiguous ones (`branch`, `config`, `remote`, `stash`,
# `tag`, `worktree`) are deliberately absent: they mutate under some flags, so they fall
# through to settings.json, where the read-only spellings are listed explicitly.
GIT_READ_SUBCOMMANDS = frozenset("""
    blame cat-file check-attr check-ignore describe diff for-each-ref grep help log ls-files
    ls-remote ls-tree merge-base reflog rev-list rev-parse shortlog show status version
    whatchanged
""".split())

DOCKER_READ_SUBCOMMANDS = frozenset("""
    images info inspect logs ps stats top version
""".split())

# `find` actions that write or run code, which take it out of the read-only set.
FIND_ACTIONS = frozenset("""
    -delete -exec -execdir -ok -okdir -fprint -fprintf -fls
""".split())

# Tools whose first argument selects the operation, so the signature needs two words to be useful.
# Tools taking a file path there (duckdb, sqlite3) stay out, or every database gets its own bucket.
MULTI_WORD_TOOLS = frozenset("""
    apt bun cargo claude codex docker flatpak gh git go gsettings home-manager kubectl make nix
    npm npx pip poetry pnpm ssh systemctl tmux uv yarn
""".split())

# Shell syntax that sits in front of a command without being one.
DISCARDABLE_PREFIXES = frozenset({"do", "then", "else", "!", "time", "command", "exec", "nohup"})
CONTROL_KEYWORDS = frozenset("""
    case done elif esac fi for if in until while { } ( ) [[ ]] EOF PYEOF
""".split())

ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DURATION = re.compile(r"^\d+(\.\d+)?[smhd]?$")
HEREDOC_BODY = re.compile(r"\s*<<-?\s*['\"]?(\w+)['\"]?\n.*?\n[ \t]*\1\b", re.DOTALL)
# Redirects are stripped without quote awareness: a `>` inside a quoted argument mangles the
# stored example. It never changes the leading word, so bucketing stays correct.
REDIRECT = re.compile(r"\s*\d?>>?\s*\S+|\s*\d?>&\d+|\s*\d?<\s*\S+")

SPLIT_OPERATORS = ("&&", "||")


@dataclass
class Args:
    sessions_dir: Annotated[Path, tyro.conf.Positional]
    """Claude sessions directory. Scanned recursively, so ~/.claude/projects/ covers every project."""

    settings: Annotated[list[Path], tyro.conf.Positional]
    """Settings JSON file(s) containing the permission allowlist."""

    days: int = 30
    """Scan sessions modified within the last N days."""

    show_auto_approved: bool = False
    """Report the segments dropped as built-in read-only instead of the ones that would prompt."""


def main(args: Args) -> None:
    patterns = load_allowlist(*args.settings)
    cutoff = (datetime.now() - timedelta(days=args.days)).timestamp()
    commands = scan_sessions(args.sessions_dir, cutoff)

    blocked: Counter[str] = Counter()
    auto_approved: Counter[str] = Counter()
    examples: dict[str, dict[str, str]] = {"blocked": {}, "auto": {}}
    total_segments = 0

    for raw in commands:
        for segment in split_segments(raw):
            command = normalize(segment)
            if not command:
                continue
            total_segments += 1
            if is_allowed(command, patterns):
                continue
            bucket, store = (
                (auto_approved, examples["auto"])
                if internally_approved(command)
                else (blocked, examples["blocked"])
            )
            sig = signature(command)
            bucket[sig] += 1
            if sig not in store or len(command) < len(store[sig]):
                store[sig] = command[:200]

    reported, store = (
        (auto_approved, examples["auto"])
        if args.show_auto_approved
        else (blocked, examples["blocked"])
    )
    results = [
        {"signature": sig, "count": count, "example": store[sig]}
        for sig, count in reported.most_common()
    ]
    json.dump(results, sys.stdout, indent=2)

    print(
        f"\nScanned: {len(commands)} Bash calls -> {total_segments} segments "
        f"from sessions modified in last {args.days} days",
        file=sys.stderr,
    )
    print(
        f"Would prompt: {sum(blocked.values())} segments, {len(blocked)} distinct",
        file=sys.stderr,
    )
    print(
        f"Auto-approved by Claude Code's built-in read-only set: {sum(auto_approved.values())} segments"
        f" ({len(auto_approved)} distinct; --show-auto-approved to inspect)",
        file=sys.stderr,
    )


def load_allowlist(*settings_paths: Path) -> list[str]:
    """Extract Bash command patterns from settings files."""
    patterns = []
    for path in settings_paths:
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"Warning: could not read {path}", file=sys.stderr)
            continue
        for entry in data.get("permissions", {}).get("allow", []):
            if entry.startswith("Bash(") and entry.endswith(")"):
                patterns.append(entry[5:-1])
    return patterns


def scan_sessions(sessions_dir: Path, cutoff_ts: float) -> list[str]:
    """Return every Bash command from sessions under sessions_dir modified after cutoff."""
    commands = []
    for path in sessions_dir.rglob("*.jsonl"):
        if path.name.endswith(".wakatime") or path.stat().st_mtime < cutoff_ts:
            continue
        try:
            with open(path) as f:
                for line in f:
                    if '"Bash"' not in line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    commands.extend(bash_commands(entry))
        except OSError:
            continue
    return commands


def bash_commands(entry: dict) -> list[str]:
    """Pull Bash tool_use commands out of one transcript line."""
    content = None
    if entry.get("role") == "assistant":
        content = entry.get("content")
    elif isinstance(entry.get("message"), dict) and entry["message"].get("role") == "assistant":
        content = entry["message"].get("content")
    if not isinstance(content, list):
        return []

    out = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use" or block.get("name") != "Bash":
            continue
        command = (block.get("input") or {}).get("command", "").strip()
        if command:
            out.append(command)
    return out


def split_segments(command: str) -> list[str]:
    """Split a shell command the way the permission check does.

    Splits on ``|``, ``;``, ``&&``, ``||``, newlines and backgrounding ``&``, respecting
    quotes. Heredoc bodies are removed first so their contents are not read as shell.
    """
    command = strip_heredocs(command)
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(command):
        char = command[i]
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
            i += 1
        elif char in "'\"":
            quote = char
            current.append(char)
            i += 1
        elif command[i : i + 2] in SPLIT_OPERATORS:
            segments.append("".join(current))
            current = []
            i += 2
        elif char == "&" and i > 0 and command[i - 1] == ">":  # a redirect like 2>&1
            current.append(char)
            i += 1
        elif char in "|&;\n":
            segments.append("".join(current))
            current = []
            i += 1
        else:
            current.append(char)
            i += 1
    segments.append("".join(current))
    return [s.strip() for s in segments if s.strip()]


def strip_heredocs(command: str) -> str:
    """Replace heredoc bodies with a placeholder so their contents are not parsed as shell."""
    command = HEREDOC_BODY.sub(" HEREDOC", command)
    if "<<" in command:  # unterminated heredoc from a truncated transcript; drop the tail
        command = command[: command.index("<<")].rstrip() + " HEREDOC"
    return command


def normalize(segment: str) -> str:
    """Reduce a segment to the command that actually gets permission-checked.

    Drops redirects plus everything that sits in front of the real command: shell keywords,
    environment-variable assignments and ``timeout``/``time`` wrappers. Returns "" for
    segments that are pure control flow and never carry a permission decision.
    """
    words = REDIRECT.sub("", segment).strip().split()
    while words:
        head = words[0]
        if head in DISCARDABLE_PREFIXES or ENV_ASSIGNMENT.match(head):
            words = words[1:]
        elif head == "timeout":
            words = words[1:]
            while words and (words[0].startswith("-") or DURATION.match(words[0])):
                words = words[1:]
        else:
            break
    if not words or words[0] in CONTROL_KEYWORDS:
        return ""
    return " ".join(words)


def is_allowed(command: str, patterns: list[str]) -> bool:
    """Whether an allowlist pattern covers this command."""
    return any(fnmatch(command, pattern) for pattern in patterns)


def internally_approved(command: str) -> bool:
    """Whether Claude Code auto-approves this without consulting settings.json."""
    words = command.split()
    if not words:
        return True
    program = Path(words[0]).name
    if program == "sed":  # read-only only until -i turns it into an editor
        return not any(edits_in_place(word) for word in words[1:])
    if program == "find":
        return FIND_ACTIONS.isdisjoint(words[1:])
    if program in READ_ONLY_PROGRAMS:
        return True
    if program == "git":
        subcommand = words[3:4] if words[1:2] == ["-C"] else words[1:2]
        return bool(subcommand) and subcommand[0] in GIT_READ_SUBCOMMANDS
    if program == "docker":
        return words[1:2] != [] and words[1] in DOCKER_READ_SUBCOMMANDS
    return False


def edits_in_place(word: str) -> bool:
    """Whether a sed argument is an in-place flag, including clusters like -ni and -i.bak."""
    if word.startswith("--in-place"):
        return True
    return word.startswith("-") and not word.startswith("--") and "i" in word


def signature(command: str) -> str:
    """Collapse a command to a groupable label for frequency counting."""
    words = command.split()
    program = words[0]
    if program == "ssh" and len(words) > 2:
        return "ssh * " + " ".join(words[2:4]).strip("'\"") + " ..."
    if words[1:2] == ["compose"] and program == "docker" and len(words) > 2:
        return f"docker compose {words[2]} ..."
    if program == "git" and words[1:2] == ["-C"] and len(words) > 3:
        return f"git -C * {words[3]} ..."
    if program in MULTI_WORD_TOOLS and len(words) > 1:
        return f"{program} {words[1]} ..."
    return f"{program} ..."


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
