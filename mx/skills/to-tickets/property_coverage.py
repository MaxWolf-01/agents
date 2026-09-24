#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Check that every property a ticket states reaches an acceptance criterion.

A ticket numbers its properties, P1 onward, and a criterion anywhere in the
tracker takes one on by citing it, `<slug>#P<n>`:

    - [ ] `one-flow#P3`: the seam its check enters at

The tracker is read through `tracker data`, so a property, a criterion and a
citation mean here exactly what they mean at a commit. A citation that names no
ticket or no property is refused there, and this command exits with that
refusal; what it adds is the other direction: a property no criterion cites was
stated and never taken on by any slice.

One line per finding, and exit 1 when there is any. What it answers is whether
a criterion claimed the property, never whether the claim covers the whole of
it, nor which of them is executable and which is reviewed: both stay the Spec
reviewer's read (`/mx:code-review`).

A tracker whose tickets state no property says so and exits 0.

Examples:

    property-coverage
    property-coverage ~/repos/workspace || echo "a property reached no criterion"
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import tyro

TRACKER = Path(__file__).resolve().parents[1] / "tracker" / "tracker.py"


@dataclass(frozen=True)
class Property:
    """One property a ticket states, addressed the way an editor jumps to it."""

    ref: str  # <slug>#P<n>, as a criterion cites it
    text: str
    path: Path
    line: int


@dataclass(frozen=True)
class Finding:
    at: Property
    what: str

    def __str__(self) -> str:
        return f"{self.at.path}:{self.at.line}: {self.what}"


@dataclass(frozen=True)
class Report:
    """What one run read, and what it found wrong. `summary` is the line the run ends on."""

    properties: list[Property]
    cited: set[str]
    findings: list[Finding]

    @property
    def summary(self) -> str:
        plural = "" if len(self.findings) == 1 else "s"
        return f"{len(self.properties)} properties, {len(self.cited)} cited, {len(self.findings)} finding{plural}"


@dataclass
class Args:
    at: Annotated[Path, tyro.conf.Positional] = Path(".")
    """A directory inside the tracker to read; the working directory's tracker by default."""


def main(args: Args) -> None:
    report = check(args.at)
    for finding in report.findings:
        print(finding)
    sys.stdout.flush()
    print(report.summary, file=sys.stderr)
    sys.exit(1 if report.findings else 0)


def check(at: Path) -> Report:
    """Hold every property the tracker states against the criteria that cite it."""
    tickets = read_tracker(at)
    properties = [
        Property(ref=f"{ticket['slug']}#{stated['id']}", text=stated["text"],
                 path=Path(ticket["path"]), line=stated["line"])
        for ticket in tickets for stated in ticket["properties"]
    ]
    cited = {ref for ticket in tickets for criterion in ticket["criteria"] for ref in criterion["cites"]}
    findings = [
        Finding(one, f"{one.ref} reached no acceptance criterion: {summarise(one.text)}")
        for one in properties if one.ref not in cited
    ]
    return Report(properties, cited & {one.ref for one in properties}, findings)


def read_tracker(at: Path) -> list[dict]:
    """The tracker as `tracker data` hands it over, run in `at`. A refusal there is a refusal here:
    a tracker no reader can read is not one to report coverage over."""
    if not at.is_dir():
        sys.exit(f"property-coverage: no directory at {at}")
    done = subprocess.run([str(TRACKER), "data"], cwd=at, capture_output=True, text=True)
    if done.returncode != 0:
        sys.exit(done.stderr.strip() or f"property-coverage: tracker data failed in {at}")
    return json.loads(done.stdout)["tickets"]


def summarise(text: str, width: int = 60) -> str:
    if len(text) <= width:
        return text
    cut = text.rfind(" ", 0, width)
    return text[: cut if cut > 0 else width] + "..."


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__, prog="property-coverage"))
