#!/usr/bin/env python3
"""Scan Claude Code session files and extract summary info for triage.

Usage:
    uv run python scan_sessions.py <sessions_dir> [--days N] [--sessions N]

Output: One JSON object per session (non-subagent only), sorted newest-first.
Sessions smaller than 3KB are excluded (empty/trivial).
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


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


def main():
    if len(sys.argv) < 2:
        print("Usage: scan_sessions.py <sessions_dir> [--days N] [--sessions N]", file=sys.stderr)
        sys.exit(1)

    sessions_dir = Path(sys.argv[1])
    max_days = None
    max_sessions = None

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--days" and i + 1 < len(args):
            max_days = int(args[i + 1])
            i += 2
        elif args[i] == "--sessions" and i + 1 < len(args):
            max_sessions = int(args[i + 1])
            i += 2
        else:
            i += 1

    # Collect all main session files (not subagents)
    candidates = []
    for f in sessions_dir.glob("*.jsonl"):
        if f.name.endswith(".wakatime"):
            continue
        candidates.append(f)

    # Sort by modification time, newest first
    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    # Apply filters
    if max_days:
        cutoff = datetime.now() - timedelta(days=max_days)
        candidates = [f for f in candidates if datetime.fromtimestamp(f.stat().st_mtime) >= cutoff]

    if max_sessions:
        candidates = candidates[:max_sessions]

    # Scan and output
    results = []
    for f in candidates:
        result = scan_session(f)
        if result:
            results.append(result)

    json.dump(results, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
