#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Print the CHANGELOG.md section of a release: its version, then one entry per commit on HEAD's first-parent line since SINCE that changes something under mx/.

An entry is the commit's subject. A merge's entry adds the first paragraph of its body, joined onto one indented line, unless that paragraph holds only trailers. Commits whose subject is a release's own (`mx v1.2.3`) are left out.

Examples:

    uv run tools/changelog_section.py 5c3cd4bb 1.0.87
"""

import re
import subprocess
from dataclasses import dataclass
from typing import Annotated

import tyro

TRAILER = re.compile(r"[A-Za-z][\w-]*: \S")


@dataclass
class Args:
    since: Annotated[str, tyro.conf.Positional]
    """The commit the section starts after: the previous release's."""

    version: Annotated[str, tyro.conf.Positional]
    """The version the section is headed with."""


def lead(body: str) -> str:
    """The body's first paragraph on one line; empty where the body has none or it is all trailers."""
    lines = body.strip().split("\n\n", 1)[0].splitlines()
    if all(TRAILER.match(line) for line in lines):
        return ""
    return " ".join(line.strip() for line in lines)


def section(since: str, version: str) -> str:
    log = subprocess.run(
        ["git", "log", "--first-parent", "--format=%P%x00%s%x00%b%x1e", f"{since}..HEAD", "--", "mx/"],
        capture_output=True, text=True, check=True,
    ).stdout
    entries = []
    for record in filter(str.strip, log.split("\x1e")):
        parents, subject, body = record.lstrip("\n").split("\x00", 2)
        if re.match(r"mx v[0-9]", subject):
            continue
        entries.append(f"- {subject}")
        if len(parents.split()) > 1 and (paragraph := lead(body)):
            entries.append(f"  {paragraph}")
    return f"## {version}\n\n" + "".join(f"{entry}\n" for entry in entries)


if __name__ == "__main__":
    args = tyro.cli(Args, description=__doc__)
    print(section(args.since, args.version))
