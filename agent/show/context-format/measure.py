#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Measures every glossary max's repos carry and writes measure.json beside this file.

An entry is a `**Term**:` line, its definition lines, and an optional `_Avoid_:` line.
The checks are the ones CONTEXT-FORMAT.md states as rules, made mechanical:
sentences per definition (rule: one or two), code identifiers in a definition (a proxy
for mechanism, rule: definitions survive redesign), an Avoid line (rule: be opinionated),
and single-word names (the qualifier question).
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
HOME = Path.home()

GLOSSARIES = {
    "agents (mx)": HOME / "repos/github/MaxWolf-01/agents/CONTEXT.md",
    "skilltree": HOME / "repos/github/MaxWolf-01/skilltree/CONTEXT.md",
    "soup": HOME / "repos/github/MaxWolf-01/soup/CONTEXT.md",
    "dotfiles": HOME / "repos/github/MaxWolf-01/secrets/CONTEXT.md",
    # The work platform lives under ~/work; its name stays out of this public repo.
    "work platform": next(HOME.glob("work/*/CONTEXT.md")),
    "work architecture map": next(HOME.glob("work/*/agent/show/*/CONTEXT.md")),
    "mattpocock/skills": HOME / "repos/github/mattpocock/skills/CONTEXT.md",
}

TERM = re.compile(r"^\*\*(.+?)\*\*(?:,\s*\*\*(.+?)\*\*)?:\s*$")
# Code identifiers: backticked spans, snake_case, table-ish prefixes, file paths, ADR numbers.
CODE = re.compile(r"`[^`]+`|\b[a-z]+_[a-z_]+\b|\b[A-Z]{2}_\w+|\b\w+/\w+\.\w+\b|\bADR \d+")


def sentences(text: str) -> int:
    text = re.sub(r"`[^`]+`", "x", text)
    text = re.sub(r"\b(e\.g|i\.e|etc|vs)\.", "x", text)
    return max(1, len(re.findall(r"[.!?](\s|$)", text)))


def parse(path: Path) -> list[dict]:
    entries, cur, heading = [], None, ""
    for line in path.read_text().splitlines():
        if line.startswith("### "):
            heading = line[4:].strip()
            continue
        if line.startswith("## "):
            heading = ""
            if cur:
                entries.append(cur)
                cur = None
            continue
        m = TERM.match(line)
        if m:
            if cur:
                entries.append(cur)
            cur = dict(term=m.group(1), heading=heading, definition="", avoid=None)
            continue
        if cur is None:
            continue
        if line.startswith("_Avoid_"):
            cur["avoid"] = line.split(":", 1)[1].strip()
        elif line.startswith("_In code_"):
            continue
        elif line.strip() and not line.startswith("- "):
            cur["definition"] += (" " if cur["definition"] else "") + line.strip()
        elif line.startswith("- ") and cur["definition"]:
            entries.append(cur)
            cur = None
    if cur:
        entries.append(cur)
    for e in entries:
        d = e["definition"]
        e["words"] = len(d.split())
        e["sentences"] = sentences(d)
        e["code"] = CODE.findall(d)
        e["single_word"] = " " not in e["term"].strip()
    return entries


def main() -> None:
    out = {}
    for name, path in GLOSSARIES.items():
        entries = parse(path)
        n = len(entries)
        words = sorted(e["words"] for e in entries)
        out[name] = dict(
            path=str(path).replace(str(HOME), "~"),
            entries=n,
            median_words=words[n // 2] if n else 0,
            max_words=words[-1] if n else 0,
            over_two_sentences=sum(e["sentences"] > 2 for e in entries),
            with_code=sum(bool(e["code"]) for e in entries),
            with_avoid=sum(e["avoid"] is not None for e in entries),
            single_word=sum(e["single_word"] for e in entries),
            detail=entries,
        )
    (HERE / "measure.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for name, r in out.items():
        print(f"{name:30} n={r['entries']:3} med={r['median_words']:3} max={r['max_words']:3} "
              f">2s={r['over_two_sentences']:3} code={r['with_code']:3} avoid={r['with_avoid']:3} "
              f"1word={r['single_word']:3}")


if __name__ == "__main__":
    main()
