#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Check CONTEXT.md glossary entries against the mechanical rules of CONTEXT-FORMAT.md.

An entry is a `**Term**:` line, its definition lines up to the next blank line, and the
optional `_Avoid_:` and `_In code_:` lines. Only the definition is checked; the two
underscored lines are exempt.

Findings, per entry:
- words: the definition runs past --max-words words.
- sentences: the definition has more than --max-sentences sentences.
- code: the definition names a code identifier (a backticked span, a snake_case word, a
  file path), which belongs on the entry's `_In code_:` line.

Whether a name needs its qualifier, and whether a term earns an entry at all, is judgment
and not checked here.

Exit code 1 when any finding was reported.

JSON schema (--json):

    [{"path": "str", "line": 0, "term": "str", "kind": "words|sentences|code", "detail": "str"}]

Examples:

    glossary-lint                      # ./CONTEXT.md
    glossary-lint CONTEXT.md src/billing/CONTEXT.md
    glossary-lint --json | jq '.[] | select(.kind == "code")'
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Annotated

import tyro

TERM = re.compile(r"^\*\*(.+?)\*\*(?:,\s*\*\*.+?\*\*)*:\s*$")
CODE = re.compile(r"`[^`]+`|\b[a-z][a-z0-9]*_[a-z0-9_]+\b|\b[\w.-]+/[\w./-]*\w\.\w+\b")
ABBREV = re.compile(r"\b(e\.g|i\.e|etc|vs|cf)\.")


@dataclass
class Finding:
    path: str
    line: int
    term: str
    kind: str
    detail: str


@dataclass
class Entry:
    term: str
    line: int
    definition: str


def entries(text: str) -> list[Entry]:
    out: list[Entry] = []
    cur: Entry | None = None
    for n, line in enumerate(text.splitlines(), 1):
        m = TERM.match(line)
        if m:
            cur = Entry(m.group(1), n, "")
            out.append(cur)
        elif cur is None or not line.strip() or line.startswith("#"):
            cur = None
        elif not line.startswith(("_Avoid_", "_In code_")):
            cur.definition += (" " if cur.definition else "") + line.strip()
    return out


def sentences(text: str) -> int:
    text = ABBREV.sub("x", re.sub(r"`[^`]+`", "x", text))
    return max(1, len(re.findall(r"[.!?](?:\s|$)", text)))


def check(path: Path, max_words: int, max_sentences: int) -> list[Finding]:
    found = []
    for e in entries(path.read_text()):
        f = lambda kind, detail: found.append(Finding(str(path), e.line, e.term, kind, detail))
        if (w := len(e.definition.split())) > max_words:
            f("words", f"{w} words, the cap is {max_words}")
        if (s := sentences(e.definition)) > max_sentences:
            f("sentences", f"{s} sentences, the cap is {max_sentences}")
        if ids := CODE.findall(e.definition):
            f("code", "move to an _In code_ line: " + ", ".join(dict.fromkeys(ids)))
    return found


@dataclass
class Args:
    paths: Annotated[list[Path], tyro.conf.Positional] = field(default_factory=lambda: [Path("CONTEXT.md")])
    """Glossary files to check."""
    max_words: int = 40
    """Words a definition may run to."""
    max_sentences: int = 2
    """Sentences a definition may run to."""
    json: bool = False
    """Emit the findings as JSON to stdout."""


def main(args: Args) -> int:
    found = [f for p in args.paths for f in check(Path(p), args.max_words, args.max_sentences)]
    if args.json:
        print(json.dumps([asdict(f) for f in found], indent=1, ensure_ascii=False))
    else:
        for f in found:
            print(f"{f.path}:{f.line}: {f.term}: {f.kind}: {f.detail}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(tyro.cli(Args, description=__doc__)))
