#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Check that an em-dash sweep changed punctuation only.

Compares each changed line against its original (git diff of the working tree
or a range) and flags any line where the words moved, disappeared or appeared,
beyond a short allow-list of connectives an em-dash rewrite may legitimately
add. Also flags changed lines that held no em-dash to begin with, and any
em-dash left in a swept file.
"""

import difflib
import re
import subprocess
from dataclasses import dataclass

import tyro

CONNECTIVES = {
    "and", "so", "which", "that", "or", "but", "then", "because", "since",
    "is", "are", "it", "its", "this", "a", "an", "the", "of", "to", "as",
    "with", "when", "where", "in", "for", "on", "by", "if", "not", "no",
    "one", "one's", "they", "them", "there", "was", "be", "be", "at",
    "means", "i", "e", "eg", "ie",
}


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", s.lower())


@dataclass
class Args:
    rev: str = "HEAD"
    """Git revision to diff the working tree against."""

    repo: str = "."


def main(a: Args) -> None:
    files = subprocess.run(
        ["git", "-C", a.repo, "diff", "--name-only", a.rev], capture_output=True, text=True, check=True
    ).stdout.split()
    total_flags = 0
    for f in files:
        if not f.endswith(".md"):
            continue
        old = subprocess.run(
            ["git", "-C", a.repo, "show", f"{a.rev}:{f}"], capture_output=True, text=True, check=True
        ).stdout.splitlines()
        new = open(f"{a.repo}/{f}", encoding="utf-8").read().splitlines()
        left = sum("—" in l for l in new)
        if left:
            print(f"{f}: {left} em-dash(es) remain")
        sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            o, n = old[i1:i2], new[j1:j2]
            if tag == "replace" and len(o) == len(n):
                pairs = list(zip(o, n))
            else:
                pairs = [(" ".join(o), " ".join(n))]
            for ol, nl in pairs:
                if "—" not in ol:
                    print(f"{f}:{j1 + 1}: changed line had no em-dash\n  - {ol}\n  + {nl}")
                    total_flags += 1
                    continue
                ow, nw = words(ol), words(nl)
                # old words must appear in order in new; extras in new must be connectives
                it = iter(nw)
                extras = []
                missing = []
                for w in ow:
                    for x in it:
                        if x == w:
                            break
                        extras.append(x)
                    else:
                        missing.append(w)
                        it = iter([])
                extras += list(it)
                bad = [x for x in extras if x not in CONNECTIVES]
                if missing or bad:
                    print(f"{f}:{j1 + 1}: words changed (missing={missing}, added={bad})\n  - {ol}\n  + {nl}")
                    total_flags += 1
    print(f"flags: {total_flags}")


if __name__ == "__main__":
    main(tyro.cli(Args))
