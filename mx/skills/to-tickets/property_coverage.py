#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Check that a breakdown disposes of every property its spec states.

A spec numbers its properties, P1 onward (`/mx:grilling`, SPEC-FORMAT), and a
ticket disposes of one under its `## Acceptance criteria`, naming that id:

    - [ ] Property P3, reviewed: what this slice has to hold
    - [ ] Property P4, executable: the seam its check enters at
    - Property P7, unsliced: why no single slice can hold it

It reads one feature directory: the spec beside the `NN-<slug>.md` tickets sliced
from it. One line per finding, and exit 1 when there is any:

- a property no ticket names, so the slices were cut and it reached none of them
- a criterion naming an id the spec does not have
- a criterion naming no id, so it claims some property without saying which
- a criterion naming a disposition that is none of the three
- a spec property with no id, or one id on two properties

What it answers is whether a ticket claimed the property, never whether the
claim covers the whole of it: holding one against the other stays the Spec
reviewer's read (`/mx:code-review`).

A spec with no `## Properties` section says so and exits 0.

Examples:

    property-coverage agent/tickets/one-flow
    property-coverage agent/tickets/one-flow || echo "the breakdown is not done"
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import tyro

DISPOSITIONS = ("reviewed", "executable", "unsliced")
HEADING = re.compile(r"^##\s+(?P<title>.*?)\s*$")
BULLET = re.compile(r"^-\s+(?P<body>\S.*)$")  # top level: an indented bullet continues the one above it
ID = re.compile(r"^\*{0,2}(?P<id>P\d+)\*{0,2}[.:)]?\s+(?P<text>\S.*)$")
# A claim is "Property" followed by an id or by the comma before its disposition: prose that
# merely opens with the domain word ("Property cards render in a grid") is not one.
CLAIM = re.compile(r"^(?:\[[ xX]\]\s*)?\*{0,2}Property\b(?=[ ]*(?:P\d+|,))[ ]*(?P<rest>.*)$")
CLAIM_REST = re.compile(r"^(?P<id>P\d+)?\*{0,2}\s*,?\s*(?P<disposition>[a-z]+)?")


@dataclass(frozen=True)
class Line:
    """A line of a tracker file, addressed the way an editor jumps to it."""

    path: Path
    number: int

    def __str__(self) -> str:
        return f"{self.path}:{self.number}"


@dataclass(frozen=True)
class Section:
    """One `## ` section of a tracker file: where its heading sits, and its bullets. No such heading, no `at`."""

    at: Line | None
    bullets: list[tuple[Line, str]]


@dataclass(frozen=True)
class Property:
    id: str
    text: str
    at: Line


@dataclass(frozen=True)
class Claim:
    """A criterion disposing of one property: its id, and how the ticket holds it."""

    id: str | None
    disposition: str | None
    at: Line


@dataclass(frozen=True)
class Finding:
    at: Line
    what: str

    def __str__(self) -> str:
        return f"{self.at}: {self.what}"


@dataclass(frozen=True)
class Report:
    """What one run read, and what it found wrong. `summary` is the line the run ends on."""

    properties: list[Property]
    claims: list[Claim]
    findings: list[Finding]
    summary: str

    @property
    def disposed(self) -> set[str]:
        stated = {p.id for p in self.properties}
        return {c.id for c in self.claims if c.id in stated}


@dataclass
class Args:
    feature: Annotated[Path, tyro.conf.Positional]
    """The feature directory: a spec.md and the NN-<slug>.md tickets sliced from it."""


def main(args: Args) -> None:
    report = check(args.feature)
    for finding in report.findings:
        print(finding)
    sys.stdout.flush()
    print(report.summary, file=sys.stderr)
    sys.exit(1 if report.findings else 0)


def check(feature: Path) -> Report:
    """Read the breakdown and hold it against its spec."""
    spec = feature / "spec.md"
    if not spec.is_file():
        sys.exit(f"property-coverage: no spec.md in {feature}")
    tickets = sorted(feature.glob("[0-9][0-9]-*.md"))
    if not tickets:
        sys.exit(f"property-coverage: no NN-<slug>.md tickets in {feature}")

    stated = section(spec, "Properties")
    if stated.at is None:
        return counted([], [], [], f"no ## Properties section in {spec}")
    properties, spec_findings = read_properties(stated.at, stated.bullets)
    if not properties:  # nothing to hold the tickets against, and the finding says what to fix first
        return counted([], [], spec_findings)
    claims, ticket_findings = read_claims(tickets)
    return counted(properties, claims, spec_findings + ticket_findings + coverage(properties, claims, spec))


def counted(properties: list[Property], claims: list[Claim], findings: list[Finding], summary: str = "") -> Report:
    """The report, with the counts line written for it unless the run ends on something else."""
    read = Report(properties, claims, findings, summary)
    plural = "" if len(findings) == 1 else "s"
    return read if summary else Report(properties, claims, findings, f"{len(properties)} properties, {len(read.disposed)} disposed of, {len(findings)} finding{plural}")


def read_properties(at: Line, bullets: list[tuple[Line, str]]) -> tuple[list[Property], list[Finding]]:
    """The spec's `## Properties` bullets, each with the id the tickets cite it by; `at` is the heading's own line."""
    properties: list[Property] = []
    unnumbered: list[Line] = []
    for line, body in bullets:
        if match := ID.match(body):
            properties.append(Property(match["id"], match["text"], line))
        else:
            unnumbered.append(line)
    if not bullets:
        return [], [Finding(at, "the Properties section states none")]
    if not properties:
        return [], [Finding(unnumbered[0], f"the Properties list carries no ids; number it P1 onward, {len(unnumbered)} properties")]

    findings = [Finding(line, "property with no id") for line in unnumbered]
    seen: dict[str, Property] = {}
    for prop in properties:
        if first := seen.get(prop.id):
            findings.append(Finding(prop.at, f"{prop.id} is already the id of the property at line {first.at.number}"))
        seen.setdefault(prop.id, prop)
    return properties, findings


def section(file: Path, heading: str) -> Section:
    """The top-level bullets under one `## ` heading, each with the line it sits on."""
    at: Line | None = None
    bullets: list[tuple[Line, str]] = []
    inside = False
    for number, text in enumerate(file.read_text().splitlines(), start=1):
        if match := HEADING.match(text):
            inside = match["title"] == heading
            at = at or (Line(file, number) if inside else None)
        elif inside and (bullet := BULLET.match(text)):
            bullets.append((Line(file, number), bullet["body"]))
    return Section(at, bullets)


def read_claims(tickets: list[Path]) -> tuple[list[Claim], list[Finding]]:
    """Every `Property <id>, <disposition>:` criterion across the tickets, with what is wrong with one."""
    claims: list[Claim] = []
    findings: list[Finding] = []
    for ticket in tickets:
        for at, body in section(ticket, "Acceptance criteria").bullets:
            if not (claim := CLAIM.match(body)):
                continue
            parts = CLAIM_REST.match(claim["rest"])  # every group optional, so a claim that names neither still parses
            id, disposition = parts["id"], parts["disposition"]
            claims.append(Claim(id, disposition, at))
            if not id:
                findings.append(Finding(at, "criterion names no property id"))
            if disposition not in DISPOSITIONS:
                findings.append(Finding(at, f"disposition {disposition or '(none)'} is none of {', '.join(DISPOSITIONS)}"))
    return claims, findings


def coverage(properties: list[Property], claims: list[Claim], spec: Path) -> list[Finding]:
    """A property no ticket disposed of, and a claim on an id the spec does not have."""
    stated = {p.id for p in properties}
    named = {c.id for c in claims if c.id}
    findings = [Finding(p.at, f"{p.id} reached no ticket: {summarise(p.text)}") for p in properties if p.id not in named]
    findings += [Finding(c.at, f"{c.id} is not a property of {spec}") for c in claims if c.id and c.id not in stated]
    return findings


def summarise(text: str, width: int = 60) -> str:
    if len(text) <= width:
        return text
    cut = text.rfind(" ", 0, width)
    return text[: cut if cut > 0 else width] + "..."


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__, prog="property-coverage"))
