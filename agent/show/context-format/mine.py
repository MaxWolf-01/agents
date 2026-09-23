#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Mines Claude Code session transcripts for glossary friction; writes mine.json beside this file.

Reads only user text (not tool results) and assistant text blocks, plus the file paths of
Edit/Write tool calls, from the sessions of the repos that carry a CONTEXT.md.
"""

import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
PROJECTS = Path.home() / ".claude/projects"
REPOS = ("agents", "skilltree", "soup", "dotfiles")

USER_PATTERNS = {
    "names the glossary": re.compile(r"\b(glossary|CONTEXT\.md|context\.md|ubiquitous language)\b", re.I),
    "corrects a word": re.compile(r"\b(wrong (word|term|name)|bad name|naming is|misnomer|rename (it|this)|don'?t call it|not called|call it .{1,30} instead|what does .{1,30} mean|what is a .{1,20}\?)", re.I),
    "too generic": re.compile(r"\b(too (generic|specific|vague)|overloaded|ambiguous|could mean)\b", re.I),
}
ASSISTANT_PATTERNS = {
    "challenges against the glossary": re.compile(r"(glossary (defines|says|calls)|CONTEXT\.md (defines|says|calls)|the glossary's (word|term))", re.I),
    "flags an avoided word": re.compile(r"\b(_Avoid_|avoid-list|avoided (word|term))\b", re.I),
    "coins a term": re.compile(r"\b(I('ll| will) call (it|this)|let'?s call (it|this)|new term|coin(ed|ing)? (a |the )?(term|word|name))\b", re.I),
}


def texts(content):
    if isinstance(content, str):
        yield content
        return
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            yield block.get("text", "")


def main() -> None:
    sessions = 0
    hits = {k: [] for k in [*USER_PATTERNS, *ASSISTANT_PATTERNS]}
    edits = Counter()
    glossary_sessions = set()
    for d in PROJECTS.iterdir():
        if not any(r in d.name for r in REPOS) or "tmp-skilltree" in d.name or "cache-skilltree" in d.name:
            continue
        for f in d.glob("*.jsonl"):
            sessions += 1
            for line in f.open(errors="ignore"):
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = rec.get("message") or {}
                role = rec.get("type")
                content = msg.get("content")
                if role == "assistant" and isinstance(content, list):
                    for b in content:
                        if b.get("type") == "tool_use" and b.get("name") in ("Edit", "Write"):
                            p = str((b.get("input") or {}).get("file_path", ""))
                            if p.endswith("CONTEXT.md"):
                                edits[d.name] += 1
                                glossary_sessions.add(f.name)
                pats = USER_PATTERNS if role == "user" else ASSISTANT_PATTERNS if role == "assistant" else {}
                for t in texts(content):
                    if role == "user" and (t.startswith("<") or "Base directory for this skill" in t):
                        continue  # system reminders, skill bodies, command wrappers
                    for name, pat in pats.items():
                        m = pat.search(t)
                        if m:
                            s = max(0, m.start() - 220)
                            hits[name].append(dict(project=d.name.replace("-home-max-", ""), session=f.stem[:8],
                                                   ts=rec.get("timestamp", "")[:10],
                                                   quote=t[s:m.end() + 260].replace("\n", " ")))
    out = dict(sessions=sessions, glossary_edit_sessions=len(glossary_sessions),
               glossary_edits_by_project=edits.most_common(),
               counts={k: len(v) for k, v in hits.items()}, hits=hits)
    (HERE / "mine.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps({k: out[k] for k in ("sessions", "glossary_edit_sessions", "glossary_edits_by_project", "counts")}, indent=1))


if __name__ == "__main__":
    main()
