#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Summarise Claude Code sessions for triage: what each one was about and whether it ended.

Reads the *.jsonl session files directly in one project's sessions directory
(~/.claude/projects/<project-path-with-dashes>/), skipping subagent transcripts
(they sit in subdirectories) and files under 3KB (empty or trivial sessions).

JSON schema (stdout), one object per session, newest first:

    [{"session_id": "str", "modified": "YYYY-MM-DD HH:MM", "size_kb": int,
      "user_msgs_total": int, "user_msgs_substantive": int,
      "signals": {"commit": bool, "transcribe": bool, "handoff": bool},
      "interrupted": bool,
      "first_user": "str", "last_user": "str", "last_assistant": "str"}]

- user_msgs_substantive counts user messages that are neither meta nor system-injected
  (command tags, interruption markers).
- signals.* are completion indicators: a git commit/push, a transcript save, a handoff, seen
  either as a tool call or claimed in assistant text.
- interrupted: the last user message was a request interruption.
- first_user / last_user / last_assistant: the text, whitespace-collapsed, command tags
  stripped from first_user, truncated to a few hundred characters.

Examples:

    uv run scan_sessions.py ~/.claude/projects/-home-max-repos-foo --days 10
    uv run scan_sessions.py ~/.claude/projects/-home-max-repos-foo --sessions 100 --exclude <id>
    uv run scan_sessions.py <dir> --days 7 | jq '.[] | select(.interrupted)'
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

import tyro


@dataclass
class Args:
    sessions_dir: Annotated[Path, tyro.conf.Positional]
    """One project's sessions directory under ~/.claude/projects/."""

    days: int = 0
    """Only sessions modified within the last N days; 0 for no limit."""

    sessions: int = 0
    """Only the N most recently modified sessions; 0 for all. Combines with --days."""

    exclude: tyro.conf.UseAppendAction[list[str]] = field(default_factory=list)
    """Session id to leave out; repeatable."""


def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "text":
                parts.append(p.get("text", ""))
        return " ".join(parts)
    return ""


def extract_tool_signals(content):
    signals = set()
    if not isinstance(content, list):
        return signals
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "tool_use":
            inp = str(part.get("input", ""))
            if "git commit" in inp or "git push" in inp:
                signals.add("commit_tool")
            if "transcri" in inp.lower():
                signals.add("transcribe_tool")
            if "handoff" in inp.lower():
                signals.add("handoff_tool")
    return signals


def scan_session(filepath: Path) -> dict | None:
    stat = filepath.stat()
    size_kb = stat.st_size / 1024
    if size_kb < 3:
        return None

    mod_time = datetime.fromtimestamp(stat.st_mtime)
    session_id = filepath.stem

    user_messages = []  # (text, is_meta)
    last_assistant_texts = []
    signals = set()

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = entry.get("message", {})
            if not isinstance(msg, dict):
                continue

            etype = entry.get("type", "")
            role = msg.get("role", "")
            content = msg.get("content", "")
            text = extract_text(content)
            is_meta = bool(entry.get("isMeta"))

            # Collect tool-use signals from content
            signals |= extract_tool_signals(content)

            if role == "user" or etype == "user":
                if text and len(text) > 10:
                    user_messages.append((text, is_meta))

            if role == "assistant" or etype == "assistant":
                # Check text for completion keywords
                lower = text.lower()
                if "commit" in lower and any(
                    w in lower
                    for w in ("success", "pushed", "created commit", "committed")
                ):
                    signals.add("commit_text")
                if any(w in lower for w in ("transcript saved", "saved to")):
                    signals.add("transcribe_text")
                if "handoff written" in lower or "handoff" in lower and "continue" in lower:
                    signals.add("handoff_text")
                if text and len(text) > 20:
                    last_assistant_texts.append(text)

    non_meta_user = [(t, m) for t, m in user_messages if not m]
    # Also skip system-injected messages
    substantive_user = [
        (t, m)
        for t, m in non_meta_user
        if not t.startswith("<system")
        and not t.startswith("<local-command")
        and not t.startswith("<command-name>")
        and t != "[Request interrupted by user]"
        and t != "[Request interrupted by user for tool use]"
    ]

    first_user = None
    for text, _ in substantive_user:
        # Clean command tags
        cleaned = text
        for tag in [
            "<command-message>",
            "</command-message>",
            "<command-name>",
            "</command-name>",
            "<command-args>",
            "</command-args>",
        ]:
            cleaned = cleaned.replace(tag, " ")
        cleaned = " ".join(cleaned.split())
        if len(cleaned) > 15:
            first_user = cleaned
            break

    last_user = None
    for text, _ in reversed(substantive_user):
        cleaned = " ".join(text.split())
        if len(cleaned) > 15:
            last_user = cleaned
            break

    last_asst = None
    if last_assistant_texts:
        last_asst = " ".join(last_assistant_texts[-1].split())

    # Classify signals
    has_commit = "commit_tool" in signals or "commit_text" in signals
    has_transcribe = "transcribe_tool" in signals or "transcribe_text" in signals
    has_handoff = "handoff_tool" in signals or "handoff_text" in signals

    # Determine if last user message was an interruption
    last_raw_user = None
    for text, meta in reversed(non_meta_user):
        if not text.startswith("<system") and not text.startswith("<local-command"):
            last_raw_user = text.strip()
            break

    interrupted = last_raw_user in (
        "[Request interrupted by user]",
        "[Request interrupted by user for tool use]",
    )

    return {
        "session_id": session_id,
        "modified": mod_time.strftime("%Y-%m-%d %H:%M"),
        "size_kb": int(size_kb),
        "user_msgs_total": len(user_messages),
        "user_msgs_substantive": len(substantive_user),
        "signals": {
            "commit": has_commit,
            "transcribe": has_transcribe,
            "handoff": has_handoff,
        },
        "interrupted": interrupted,
        "first_user": (first_user or "")[:400],
        "last_user": (last_user or "")[:300],
        "last_assistant": (last_asst or "")[:400],
    }


def main(args: Args) -> None:
    exclude_ids = set(args.exclude)
    # Top-level files only: subagent transcripts sit in <session-id>/subagents/.
    candidates = [
        f for f in args.sessions_dir.glob("*.jsonl")
        if not f.name.endswith(".wakatime") and f.stem not in exclude_ids
    ]
    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    if args.days:
        cutoff = datetime.now() - timedelta(days=args.days)
        candidates = [f for f in candidates if datetime.fromtimestamp(f.stat().st_mtime) >= cutoff]
    if args.sessions:
        candidates = candidates[: args.sessions]

    results = [r for f in candidates if (r := scan_session(f))]
    json.dump(results, sys.stdout, indent=2)


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
