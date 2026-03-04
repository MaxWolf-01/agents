# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Scan Claude Code sessions for Bash commands not covered by the permission allowlist.

Reads the actual allowlist from settings.json file(s), so results stay in sync
with current configuration. Output: JSON array of {signature, count, example}
objects sorted by frequency.

Examples::

    uv run scan_unapproved.py ~/.claude/projects/-home-max-myproject/ ~/.claude/settings.json
    uv run scan_unapproved.py sessions/ global.json project.json --days 60
"""

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from fnmatch import fnmatch
from pathlib import Path
from typing import Annotated

import tyro


@dataclass
class Args:
    sessions_dir: Annotated[Path, tyro.conf.Positional]
    """Claude sessions directory (~/.claude/projects/<encoded-path>/)."""

    settings: Annotated[list[Path], tyro.conf.Positional]
    """Settings JSON file(s) containing the permission allowlist."""

    days: int = 30
    """Scan sessions modified within the last N days."""


def load_allowlist(*settings_paths: Path) -> list[str]:
    """Extract Bash command patterns from settings files."""
    patterns = []
    for path in settings_paths:
        try:
            data = json.loads(path.read_text())
            for entry in data.get("permissions", {}).get("allow", []):
                if entry.startswith("Bash(") and entry.endswith(")"):
                    patterns.append(entry[5:-1])
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"Warning: could not read {path}", file=sys.stderr)
    return patterns


def is_allowed(cmd: str, patterns: list[str]) -> bool:
    """Check if a command matches any allowlist pattern via fnmatch glob matching."""
    cmd = cmd.strip()
    return any(fnmatch(cmd, p) for p in patterns)


def cmd_signature(cmd: str) -> str:
    """Collapse a command to a groupable signature for frequency counting."""
    cmd = cmd.strip()

    # SSH: ssh <host> <remote_cmd> -> ssh * <first 2 words of remote>
    m = re.match(r"^ssh\s+\S+\s+(.*)", cmd, re.DOTALL)
    if m:
        remote = m.group(1).strip().strip("'\"").strip()
        words = remote.split()[:2]
        return f"ssh * {' '.join(words)} ..."

    # docker compose <subcmd>
    m = re.match(r"^(docker compose \S+)", cmd)
    if m:
        return m.group(1) + " ..."

    # docker <subcmd>
    m = re.match(r"^(docker \S+)", cmd)
    if m:
        return m.group(1) + " ..."

    # Two-word commands for known multi-word tools
    parts = cmd.split()
    if len(parts) >= 2 and parts[0] in (
        "make", "uv", "nix", "pip", "npm", "npx", "tmux", "gh", "git",
        "systemctl", "claude", "stripe", "cargo", "go",
    ):
        return f"{parts[0]} {parts[1]} ..."

    return parts[0] + " ..." if parts else cmd


def scan_sessions(sessions_dir: Path, cutoff_ts: float) -> list[str]:
    """Return all Bash commands from sessions modified after cutoff."""
    commands = []
    for f in sessions_dir.glob("*.jsonl"):
        if f.name.endswith(".wakatime"):
            continue
        if f.stat().st_mtime < cutoff_ts:
            continue
        try:
            for line in open(f):
                if '"Bash"' not in line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                content = None
                if msg.get("role") == "assistant":
                    content = msg.get("content")
                elif isinstance(msg.get("message"), dict) and msg["message"].get("role") == "assistant":
                    content = msg["message"].get("content")
                if not content or isinstance(content, str):
                    continue

                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use" or block.get("name") != "Bash":
                        continue
                    cmd = (block.get("input") or {}).get("command", "").strip()
                    if cmd:
                        commands.append(cmd)
        except Exception:
            continue
    return commands


def main(args: Args) -> None:
    patterns = load_allowlist(*args.settings)
    cutoff = (datetime.now() - timedelta(days=args.days)).timestamp()

    all_cmds = scan_sessions(args.sessions_dir, cutoff)
    unapproved = [cmd for cmd in all_cmds if not is_allowed(cmd, patterns)]

    counter: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for cmd in unapproved:
        sig = cmd_signature(cmd)
        counter[sig] += 1
        if sig not in examples or len(cmd) < len(examples[sig]):
            examples[sig] = cmd[:200]

    results = [
        {"signature": sig, "count": count, "example": examples[sig]}
        for sig, count in counter.most_common()
    ]
    json.dump(results, sys.stdout, indent=2)

    print(f"\nTotal: {len(unapproved)} unapproved calls, {len(counter)} distinct commands", file=sys.stderr)
    print(f"Scanned: {len(all_cmds)} Bash calls from sessions modified in last {args.days} days", file=sys.stderr)


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
