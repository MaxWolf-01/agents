#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Check that a breakdown disposes of every property its spec states.

A spec numbers its properties, P1 onward (`/mx:grilling`, SPEC-FORMAT), and a
ticket disposes of one by naming that id on a line of its acceptance criteria:

    - [ ] Property P3, reviewed: what this slice has to hold
    - [ ] Property P4, executable: the seam its check enters at
    - Property P7, unsliced: why no single slice can hold it

Run it on the feature directory `/mx:to-tickets` published into: the breakdown
is finished when this comes back clean.

    property-coverage agent/tickets/one-flow

One line per finding, and exit 1 when there is any:

- a property no ticket names, so the slices were cut and it reached none of them
- a line naming an id the spec does not have
- a line naming no id, so it claims some property without saying which
- a line naming a disposition that is none of the three
- a spec property with no id, or one id on two properties

A feature whose spec states no properties passes, and says so.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import tyro

DISPOSITIONS = ("reviewed", "executable", "unsliced")
HEADING = re.compile(r"^##\s+(.*?)\s*$")
BULLET = re.compile(r"^\s*-\s+(?P<body>\S.*)$")
ID = re.compile(r"^\*{0,2}(?P<id>P\d+)\*{0,2}[.:)]?\s+(?P<text>\S.*)$")
CLAIM = re.compile(r"^\s*-\s*(?:\[[ xX]\]\s*)?Property\b[ ]*(?P<rest>.*)$")
CLAIM_REST = re.compile(r"^(?P<id>P\d+)?\s*,?\s*(?P<disposition>[a-z]+)?\b")


@dataclass(frozen=True)
class Line:
    """A line of a tracker file, addressed the way an editor jumps to it."""

    path: Path
    number: int

    def __str__(self) -> str:
        return f"{self.path}:{self.number}"


@dataclass(frozen=True)
class Property:
    id: str
    text: str
    at: Line


@dataclass(frozen=True)
class Claim:
    """A ticket line disposing of one property: its id, and how the ticket holds it."""

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
    """What one run read, and what it found wrong."""

    properties: list[Property]
    claims: list[Claim]
    findings: list[Finding]

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
    counts = f"{len(report.properties)} properties, {len(report.disposed)} disposed of, {len(report.findings)} findings"
    print(counts, file=sys.stderr)
    sys.exit(1 if report.findings else 0)


def check(feature: Path) -> Report:
    """Read the breakdown and hold it against its spec."""
    spec = feature / "spec.md"
    if not spec.is_file():
        sys.exit(f"property-coverage: no spec.md in {feature}")
    tickets = sorted(feature.glob("[0-9][0-9]-*.md"))
    if not tickets:
        sys.exit(f"property-coverage: no NN-<slug>.md tickets in {feature}")
    properties, spec_findings = read_properties(spec)
    claims, ticket_findings = read_claims(tickets)
    return Report(properties, claims, spec_findings + ticket_findings + coverage(properties, claims, spec))


def read_properties(spec: Path) -> tuple[list[Property], list[Finding]]:
    """The spec's `## Properties` bullets, each with the id the tickets cite it by."""
    properties: list[Property] = []
    findings: list[Finding] = []
    unnumbered: list[Line] = []
    for line, body in section(spec, "Properties"):
        if match := ID.match(body):
            properties.append(Property(match["id"], match["text"], line))
        else:
            unnumbered.append(line)
    if unnumbered and not properties:
        findings.append(Finding(unnumbered[0], f"the Properties list carries no ids; number it P1 onward, {len(unnumbered)} properties"))
    else:
        findings += [Finding(line, "property with no id") for line in unnumbered]
    seen: dict[str, Property] = {}
    for prop in properties:
        if first := seen.get(prop.id):
            findings.append(Finding(prop.at, f"{prop.id} is already the id of the property at line {first.at.number}"))
        seen.setdefault(prop.id, prop)
    return properties, findings


def section(spec: Path, heading: str) -> list[tuple[Line, str]]:
    """The bullets under one `## ` heading, each with the line it sits on."""
    bullets: list[tuple[Line, str]] = []
    inside = False
    for number, text in enumerate(spec.read_text().splitlines(), start=1):
        if match := HEADING.match(text):
            inside = match[1] == heading
        elif inside and (bullet := BULLET.match(text)):
            bullets.append((Line(spec, number), bullet["body"]))
    return bullets


def read_claims(tickets: list[Path]) -> tuple[list[Claim], list[Finding]]:
    """Every `Property <id>, <disposition>:` line across the tickets, with what is wrong with one."""
    claims: list[Claim] = []
    findings: list[Finding] = []
    for ticket in tickets:
        for number, text in enumerate(ticket.read_text().splitlines(), start=1):
            if not (claim := CLAIM.match(text)):
                continue
            at = Line(ticket, number)
            parts = CLAIM_REST.match(claim["rest"])  # every group optional: a bare "Property" line matches too
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
