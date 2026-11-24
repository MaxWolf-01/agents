#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown-it-py>=3", "tyro"]
# ///
"""Render a retro's living report, `report.md`, as its page: an overview of every entry, the full entry in a side sheet.

The page is a view of the report and adds no claim to it: titles, lens, state and text all come from
report.md, in its order. What it derives: an entry's area, from its **Area** field or else from the paths
it cites through the tables at the top of this script; and, from the git history of the report, what
changed in each entry since the newest committed version that differs from it, and each entry's State
across every committed version. Comments typed on the page are kept beside it, in
`<page>.state.json`, which the container hub writes; a state file found there is baked in, so the page
shows its comments read-only anywhere.

Example:

    report_page.py agent/retro/report.md agent/retro/report.html
    report_page.py agent/retro/report.md
"""

import html
import json
import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import tyro
from markdown_it import MarkdownIt
from typing import Annotated

# ---------------------------------------------------------------------------------------------------
# Area mapping. An entry's area is the commonest area among the paths it cites in Files and Cause
# (the whole entry when those cite none); a bare `:123` line reference counts toward the path before
# it. A tie goes to the area cited first. No mapped path gives "—".

# Matched against a cited path (its `:line` suffix stripped), first match wins. `\1` takes a group.
AREA_RULES: list[tuple[str, str]] = [
    (r"container-hub", "hub"),
    (r"^mx/skills/([^/]+)/", r"\1"),
    (r"^mx/hooks/", "mx hooks"),
    (r"^mx/bin/([^/]+)", r"\1"),
    (r"^mx/", "mx"),
    (r"^claude/", "claude config"),
    (r"^hypervisor/|^hv-[\w-]+\.ts$", "hypervisor"),
    (r"^(~/\.dotfiles/|nix/|bin/|tests/|\.github/|setup$)", "dotfiles"),
    (r"^prompts/", "code-review"),
    (r"^stages/", "retro"),
    (r"^tools/", "agents tools"),
    (r"^docs/", "docs"),
    (r"^tokens\.css$", "house-style"),
]

# A path whose first segment is an mx skill, cited from inside mx/skills (`dispatch/SKILL.md`).
SKILLS = {d.name for d in Path(__file__).resolve().parent.parent.iterdir() if d.is_dir()}

# Files the report cites by bare name, and where they live (agents and dotfiles, as of 2026-11).
BARE_NAMES: dict[str, str] = {
    **dict.fromkeys(
        "RULES.md session_page.py turn_review.py page.js stop_hook.py test_page_in_a_browser.py "
        "test_session_page.py steps.py live_hook.py session.md".split(),
        "session-page",
    ),
    **dict.fromkeys(
        "worker-prompt.md dispatch-ctl dispatch dispatch-ps run-worker.sh test_dispatch.py "
        "test_dispatch_ps.py".split(),
        "dispatch",
    ),
    **dict.fromkeys("tracker.py board.py board_page.py briefing.py test_tracker.py".split(), "tracker"),
    **dict.fromkeys(
        "retro_collect.py retro_run.py test_retro_run.py lens-pass.md synthesize.md go-deep.md".split(),
        "retro",
    ),
    **dict.fromkeys("TEST-SMELLS.md review test_review.py standards.md".split(), "code-review"),
    **dict.fromkeys("blind_test.py lint_pages.py render_lint.py test_render_lint.py".split(), "show"),
    **dict.fromkeys("checkpoint.py pickup.py".split(), "handoff"),
    "CATALOGUE.md": "writing-for-humans",
    "SMELLS.md": "code-review",
    "auto_mode_critique.py": "retro",
    "build.py": "docs",
    "plugin_updates.py": "mx hooks",
    "scan_sessions.py": "restore-sessions",
    "change_summary.py": "github",
    "model-runs": "model-runs",
    "rendered_from.py": "docs",
    "fixture.py": "docs",
    "affected_tests.py": "agents tools",
    "changelog_section.py": "agents tools",
    **dict.fromkeys(
        "container-hub decisions.test server.test view.test work-containers.test".split(), "hub"
    ),
    **dict.fromkeys(
        "github-mirror.test job.test vault-sync.test whatsapp-chat.test worker.nix timers.nix "
        "shell.nix".split(),
        "dotfiles",
    ),
}

# The word just before a backticked path that names the repo it is in: "dotfiles `bin/job:133`".
REPO_WORDS: dict[str, str] = {"dotfiles": "dotfiles", "helferline": "helferline"}

# Cited paths that are sources of evidence rather than the code an entry is about.
NOT_AN_AREA = re.compile(
    r"^(todo/|deep/|in-flight/|previous/|sessions/|research/|reviews/|sample/|turns/|ticket/|proto/|~/logs|~/\.cache|~/HOST)"
)

# ---------------------------------------------------------------------------------------------------
# State chip: the first of these the State text names, in the order it names them.
STATE_WORDS: list[tuple[str, str]] = [
    ("back", r"\bback since\b|^back\b"),
    ("to take up", r"\bto take up\b"),
    ("taken up", r"\btaken up\b"),
    ("fix landed", r"\bfix landed\b"),
    ("held", r"\bheld\b"),
    ("live", r"\blive\b"),
]

ID_RE = re.compile(r"\b([FAM]\d+)\b")
md = MarkdownIt("commonmark", {"html": False}).enable("table")


@dataclass
class Entry:
    id: str  # "F1", "A58", "M13", or "" for a dismissed line with no id
    kind: str  # finding | candidate | dismissed
    rank: int  # position within its section, 1-based
    title: str
    body: str  # markdown under the heading
    lens: str = ""
    state: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    anchor: str = ""
    area: str = "—"
    area_counts: list[tuple[str, int]] = field(default_factory=list)
    state_class: str = ""
    state_others: list[str] = field(default_factory=list)
    in_top: bool = False
    group: str = ""  # the `###` heading of a grouped-bullets block, for an entry that is one of its bullets


# ---------------------------------------------------------------------------------------------------
# Grouped bullets: a `###` heading with no single id ("### A27, A10, ...: unchanged, low", "### Taken up
# as tickets") holding one bullet per entry, "- **A27** <title> (<code lenses>). <rest>". One bullet may
# name two entries: "- **A39** <title>, and **A40** <title> (<lenses>). <rest>".

GROUP_BULLET = re.compile(r"^- \*\*([FA]\d+)\*\*")


def group_state(heading: str) -> str:
    if heading.lower().startswith("taken up"):
        return "taken up"
    m = re.search(r":\s*([\w-]+)", heading)
    return m.group(1).lower() if m else ""


def group_bullets(body: str) -> tuple[str, list[str]]:
    """The lead text before the first bullet, and each bullet with its continuation lines joined."""
    lead, bullets = [], []
    for line in body.splitlines():
        if line.startswith("- "):
            bullets.append(line)
        elif bullets and line.startswith(" "):
            bullets[-1] += " " + line.strip()
        elif not bullets:
            lead.append(line)
    return "\n".join(lead), bullets


def bullet_entries(bullet: str) -> list[tuple[str, str, str]]:
    """(id, title, lenses) for each entry a grouped bullet names."""
    head = re.sub(r"^- ", "", bullet)
    m = re.match(r"(.*?) \(([a-z][a-z ,]*)\)\.(\s|$)", head)
    titles, lens = (m.group(1), m.group(2)) if m else (re.split(r"\.\s", head, maxsplit=1)[0], "")
    parts = re.split(r",? and \*\*([FA]\d+)\*\* ", titles)
    first = re.match(r"\*\*([FA]\d+)\*\* (.*)", parts[0])
    out = [(first.group(1), first.group(2), lens)]
    out += [(parts[i], parts[i + 1], lens) for i in range(1, len(parts) - 1, 2)]
    return out


# ---------------------------------------------------------------------------------------------------
# Parsing


def split_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """The preamble before the first `## `, and each `## ` section as (heading, body)."""
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    return parts[0], [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]


def split_entries(body: str) -> tuple[str, list[tuple[str, str]]]:
    parts = re.split(r"^### (.+)$", body, flags=re.M)
    return parts[0], [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]


def parse_fields(body: str) -> dict[str, str]:
    """Top-level `- **Name**...` bullets, each with its continuation lines."""
    fields: dict[str, str] = {}
    current = None
    for line in body.splitlines():
        m = re.match(r"^- \*\*([^*]+?)\*\*(.*)$", line)
        if m:
            name = re.split(r"[ (,]", m.group(1).strip(), maxsplit=1)[0]
            if m.group(1).strip().lower().startswith("cause and proposal"):
                name = "Cause"
            if m.group(1).strip().lower().startswith("code lens"):
                name = "Code lens"
            current = name
            fields[current] = fields.get(current, "") + m.group(2).lstrip(":").strip()
        elif current and (line.startswith(" ") or not line.strip()):
            fields[current] += "\n" + line
        else:
            current = None
    return fields


def plain(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_state(state: str) -> tuple[str, list[str]]:
    hits = []
    for name, pattern in STATE_WORDS:
        m = re.search(pattern, state, flags=re.I)
        if m:
            hits.append((m.start(), name))
    if not hits:
        first = re.match(r"[a-z-]+(?: [a-z]+)?\b", state.strip(), flags=re.I)
        return (first.group(0).lower() if first else "—"), []
    hits.sort()
    return hits[0][1], [n for _, n in hits[1:]]


# ---------------------------------------------------------------------------------------------------
# Area


def area_of_path(path: str, repo: str | None) -> str | None:
    path = re.sub(r":[\d,\s-]+$", "", path)
    if NOT_AN_AREA.match(path) or path.startswith("/"):
        return None
    if repo == "helferline":
        return "helferline"
    if repo == "dotfiles":
        return "hub" if "container-hub" in path else "dotfiles"
    for pattern, area in AREA_RULES:
        m = re.search(pattern, path)
        if m:
            return m.expand(area)
    first = path.split("/", 1)[0]
    if "/" in path and first in SKILLS:
        return first
    return BARE_NAMES.get(path)


def areas_cited(text: str) -> list[str]:
    """Every area cited, in order, a bare `:line` counting toward the path before it."""
    out: list[str] = []
    last: str | None = None
    for m in re.finditer(r"([\w']+)?\s?`([^`\s]+)`", text):
        word, token = (m.group(1) or "").lower().removesuffix("'s"), m.group(2)
        if re.fullmatch(r":[\d,-]+", token):
            if last:
                out.append(last)
            continue
        area = area_of_path(token, REPO_WORDS.get(word))
        if area:
            out.append(area)
            last = area
        elif "/" in token or "." in token:
            last = None
    return out


def derive_area(entry: Entry) -> None:
    if named := plain(entry.fields.get("Area", "")):
        entry.area = named
        return
    cited = areas_cited(entry.fields.get("Files", "") + "\n" + entry.fields.get("Cause", ""))
    if not cited:
        cited = areas_cited(entry.body if entry.kind != "dismissed" else entry.title + entry.body)
    if not cited:
        return
    counts = Counter(cited)
    entry.area_counts = sorted(counts.items(), key=lambda kv: (-kv[1], cited.index(kv[0])))
    entry.area = entry.area_counts[0][0]


# ---------------------------------------------------------------------------------------------------
# Rendering


def linkify(fragment: str, ids: set[str]) -> str:
    """Turn every id the page holds into a link that opens its entry, outside links and code."""
    out, skip = [], 0
    for part in re.split(r"(<[^>]+>)", fragment):
        if part.startswith("<"):
            m = re.match(r"<(/?)(\w+)", part)
            if m and m.group(2).lower() in ("a", "code", "pre", "h3"):
                skip += -1 if m.group(1) else 1
            out.append(part)
        elif skip == 0:
            out.append(
                ID_RE.sub(
                    lambda m: f'<a class="ref" href="#{m[1].lower()}">{m[1]}</a>' if m[1] in ids else m[0],
                    part,
                )
            )
        else:
            out.append(part)
    return "".join(out)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def parse(text: str):
    preamble, sections = split_sections(text)
    title = (m.group(1).strip() if (m := re.search(r"^# (.+)$", preamble, flags=re.M)) else "")
    rest = re.sub(r"^# .+$", "", preamble, count=1, flags=re.M).strip()
    run_line, _, intro = rest.partition("\n\n")
    entries: list[Entry] = []
    for heading, body in sections:
        if heading in ("Findings", "Candidates"):
            kind = "finding" if heading == "Findings" else "candidate"
            rank = 0
            for h, b in split_entries(body)[1]:
                m = re.match(r"([FA]\d+)\s+(.*)", h)
                if m:
                    rank += 1
                    e = Entry(id=m.group(1), kind=kind, rank=rank, title=m.group(2), body=b)
                    e.fields = parse_fields(b)
                    e.lens = plain(e.fields.get("Lens" if kind == "finding" else "Code lens", ""))
                    e.state = e.fields.get("State", "")
                    entries.append(e)
                    continue
                for bullet in group_bullets(b)[1]:
                    if not GROUP_BULLET.match(bullet):
                        continue
                    named = bullet_entries(bullet)
                    for i, (eid, t, lens) in enumerate(named):
                        rank += 1
                        e = Entry(id=eid, kind=kind, rank=rank, title=t.rstrip(","), body=bullet, group=h)
                        e.fields = {"Files": bullet}
                        e.lens = lens
                        st = re.search(r"\*\*State\*\*:\s*(.*?)(?:\s\*\*History\*\*|$)", bullet)
                        e.state = st.group(1) if st else h
                        e.state_class = group_state(h)
                        entries.append(e)
        elif heading == "Dismissed":
            lines = [l[2:] for l in body.splitlines() if l.startswith("- ")]
            for rank, line in enumerate(lines, 1):
                m = re.match(r"\*\*([^*]+)\*\*(.*)", line)
                bold, after = (m.group(1), m.group(2)) if m else ("", line)
                if re.fullmatch(r"[FAM]\d+", bold):
                    eid = bold
                    t = re.sub(r"^\s*(\([^)]*\))?\s*,?\s*", "", after)
                    t = re.split(r"\.\s", t, maxsplit=1)[0]
                    t = re.sub(r"\s*\((code lens|a seed proposal)[^)]*\)\s*$", "", t)
                else:
                    eid, t = "", bold
                lens = re.search(r"\(code lens: ([^)]*)\)", line)
                e = Entry(id=eid, kind="dismissed", rank=rank, title=plain(t), body=line)
                e.lens = lens.group(1) if lens else ""
                e.state = "dismissed"
                entries.append(e)
    for e in entries:
        # a Dismissed line with no id is known by its words, which stay put when lines above it come and go
        e.anchor = e.id.lower() if e.id else f"d-{slug(e.title)}"
    for i, e in enumerate(entries):
        if any(o.anchor == e.anchor for o in entries[:i]):
            e.anchor += f"-{e.rank}"
    return title, run_line, intro, sections, entries


STATE_TIPS = {
    "live": "Live: the friction is current and nothing taken up covers it.",
    "back": "Back: a fix landed and the friction returned.",
    "taken up": "Taken up: a ticket was filed for it.",
    "fix landed": "Fix landed: a commit addresses it; the next runs read whether it holds.",
    "held": "Held: a landed fix has held since.",
    "to take up": "To take up: max asked for it to be taken up, in a comment on the page; a session files its ticket.",
    "dismissed": "Dismissed by max; returns only on newer evidence.",
}


def chip_state(e: Entry) -> str:
    cls = e.state_class if e.state_class in STATE_TIPS else "other"
    tip = plain(e.state) if e.kind != "dismissed" else STATE_TIPS["dismissed"]
    more = f'<span class="more">{html.escape(", ".join(e.state_others))}</span>' if e.state_others else ""
    return f'<span class="st st-{slug(cls)}" title="{html.escape(tip[:600])}">{html.escape(e.state_class)}{more}</span>'


def row(e: Entry, group_lens: str | None, home: bool = False) -> str:
    """An entry's row; its `home` row, the grouped view's, carries the entry's id as its element's, which
    a qualified tag elsewhere links to (tracker/qualified.py)."""
    area_tip = (
        "Area, as its Area field names it" if e.fields.get("Area") else
        "Area, read from the paths it cites: " + ", ".join(f"{a} ×{n}" for a, n in e.area_counts)
        if e.area_counts
        else "No path it cites maps to an area."
    )
    lens = e.lens
    if group_lens is not None:  # grouped view: the group head carries the first lens
        names = [n.strip() for n in re.split(r",\s*(?:and\s+)?|\s+and\s+", lens) if n.strip()]
        lens = ", ".join(names[1:]) if names[:1] == [group_lens] else lens
        lens = ("+ " + lens) if lens else ""
    top = '<span class="top" title="Named in the top recommendation">top</span>' if e.in_top else ""
    return (
        f'<a class="row"{f' id="{e.anchor}"' if home else ""} href="#{e.anchor}" data-a="{e.anchor}" data-area="{html.escape(e.area)}" '
        f'data-state="{html.escape(e.state_class)}" data-q="{html.escape((e.id + " " + e.title).lower())}">'
        f'<span class="rk" title="Rank {e.rank} in its section, the report\'s weighing order">{e.rank}</span>'
        f'<span class="id">{e.id or "—"}</span>'
        f'<span class="ar" title="{html.escape(area_tip)}">{html.escape(e.area)}</span>'
        f'<span class="tt">{md.renderInline(e.title)}{top}<span class="ln">{html.escape(lens)}</span></span>'
        f"{chip_state(e)}</a>"
    )


def overview(entries: list[Entry]) -> tuple[str, str]:
    """The grouped view and the report-order view."""
    grouped, flat = [], []
    for kind, label, by in (
        ("finding", "Findings", "lens"),
        ("candidate", "Candidates", "code lens"),
        ("dismissed", "Dismissed", None),
    ):
        es = [e for e in entries if e.kind == kind]
        if not es:
            continue
        flat.append(f'<section class="grp"><h2 class="sec">{label} <span class="n">{len(es)}</span></h2>')
        last_group = ""
        for e in es:
            if e.group and e.group != last_group:
                flat.append(f'<h3 class="gh">{md.renderInline(e.group)}</h3>')
            last_group = e.group
            flat.append(row(e, None))
        flat.append("</section>")
        grouped.append(f'<section class="grp"><h2 class="sec">{label} <span class="n">{len(es)}</span></h2>')
        if by is None:
            grouped += [row(e, None, True) for e in es]
        else:
            groups: dict[str, list[Entry]] = {}
            for e in es:
                first = re.split(r",|\s+and\s+", e.lens)[0].strip() or "—"
                groups.setdefault("\0" + e.group if e.group else first, []).append(e)
            for name, ges in groups.items():
                label = (
                    md.renderInline(name[1:]) if name.startswith("\0") else f"{by} <b>{html.escape(name)}</b>"
                )
                grouped.append(f'<div class="sub"><h3 class="gh">{label} <span class="n">{len(ges)}</span></h3>')
                grouped += [row(e, None if name.startswith("\0") else name, True) for e in ges]
                grouped.append("</div>")
        grouped.append("</section>")
    return "".join(grouped), "".join(flat)


def full_report(title, run_line, intro, sections, entries, ids) -> str:
    """The whole report in its order, each entry wrapped so the sheet can show it."""
    by_heading = {(e.kind, e.id, e.title): e for e in entries}
    out = [f'<h1 class="v-title" id="full">{html.escape(title)}</h1>', md.render(run_line), md.render(intro)]
    for heading, body in sections:
        out.append(f'<h2 id="full-{slug(heading)}">{md.renderInline(heading)}</h2>')
        if heading in ("Findings", "Candidates"):
            kind = "finding" if heading == "Findings" else "candidate"
            lead, items = split_entries(body)
            out.append(md.render(lead))
            for h, b in items:
                m = re.match(r"([FA]\d+)\s+(.*)", h)
                if not m:
                    lead_b, bullets = group_bullets(b)
                    out.append(f'<h3 id="full-{slug(h)}">{md.renderInline(h)}</h3>{md.render(lead_b)}<ul>')
                    for bullet in bullets:
                        named = bullet_entries(bullet) if GROUP_BULLET.match(bullet) else []
                        anchors = [eid.lower() for eid, _, _ in named]
                        li_id = f' id="full-{anchors[0]}" class="entry"' if anchors else ""
                        extra = "".join(f'<span id="full-{a}" data-alias="full-{anchors[0]}"></span>' for a in anchors[1:])
                        out.append(f"<li{li_id}>{extra}<div class=\"eb\">{md.renderInline(bullet[2:])}</div></li>")
                    out.append("</ul>")
                    continue
                e = by_heading[(kind, m.group(1), m.group(2))]
                out.append(
                    f'<section class="entry" id="full-{e.anchor}"><h3><a class="open" href="#{e.anchor}" '
                    f'title="Open in the side sheet">{e.id}</a> {md.renderInline(e.title)}</h3>'
                    f'<div class="eb">{md.render(b)}</div></section>'
                )
        elif heading == "Dismissed":
            lines = [l for l in body.splitlines() if l.startswith("- ")]
            lead = body.split("\n- ", 1)[0] if not body.lstrip().startswith("- ") else ""
            out.append(md.render(lead))
            out.append("<ul>")
            for e, line in zip([e for e in entries if e.kind == "dismissed"], lines):
                out.append(f'<li class="entry" id="full-{e.anchor}"><div class="eb">{md.renderInline(line[2:])}</div></li>')
            out.append("</ul>")
        else:
            out.append(md.render(body))
    return linkify("".join(out), ids)


def load(text: str):
    """The report parsed, each entry with its area and state chip."""
    title, run_line, intro, sections, entries = parse(text)
    by_id = {e.id: e for e in entries if e.id}
    for e in entries:
        derive_area(e)
        if e.kind == "dismissed":
            e.state_class = "dismissed"
        elif not e.state_class:  # a grouped bullet has its heading's
            e.state_class, e.state_others = classify_state(plain(e.state))
    return title, run_line, intro, sections, entries


def run_date(run_line: str) -> str:
    m = re.search(r"Run (\d{4}-\d{2}-\d{2})", run_line)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------------------------------
# Changes since the previous report, entry by entry, by id.

CHANGE_KINDS = [("new", "New"), ("moved", "State moved"), ("reworked", "Reworked"), ("dropped", "Dropped"), ("unchanged", "Unchanged")]


KNOWN_STATES = {name for name, _ in STATE_WORDS} | {"dismissed"}


def state_key(e: Entry) -> str | None:
    """The State field's first clause: what a state move compares. None where the entry states none: a
    grouped bullet with no **State** of its own, under a heading whose word is no state ("unchanged")."""
    if e.kind == "dismissed":
        return "dismissed"
    if e.group and not re.search(r"\*\*State\*\*", e.body):
        if e.state_class in KNOWN_STATES:
            return e.state_class
        cls, _ = classify_state(plain(e.body))
        return cls if cls in KNOWN_STATES else None
    text = plain(e.state)
    return re.split(r"[.;]\s|[.;]$|,\s|\s\(", text, maxsplit=1)[0].strip() or None


def entry_text(e: Entry) -> str:
    return re.sub(r"\s+", " ", e.title + " " + e.body).strip()


def compare(cur: list[Entry], prev: list[Entry]) -> dict[str, list[dict]]:
    pm = {e.id: e for e in prev if e.id}
    cm = {e.id: e for e in cur if e.id}
    out: dict[str, list[dict]] = {k: [] for k, _ in CHANGE_KINDS}
    for e in cur:
        if not e.id:
            continue
        row = {"a": e.anchor, "id": e.id, "title": e.title}
        if e.id not in pm:
            out["new"].append(row)
            continue
        old, new = state_key(pm[e.id]), state_key(e)
        if old and new and old.lower() != new.lower():
            out["moved"].append({**row, "from": old, "to": new})
        elif entry_text(pm[e.id]) != entry_text(e):
            out["reworked"].append(row)
        else:
            out["unchanged"].append(row)
    for e in prev:
        if e.id and e.id not in cm:
            out["dropped"].append({"a": e.anchor, "id": e.id, "title": e.title, "state": state_key(e) or "no state given"})
    return out


def prev_html(e: Entry, ids: set[str]) -> str:
    if e.group or e.kind == "dismissed":
        return linkify(f'<div class="eb">{md.renderInline(re.sub(r"^- ", "", e.body))}</div>', ids)
    return linkify(f"<h3>{e.id} {md.renderInline(e.title)}</h3><div class=\"eb\">{md.render(e.body)}</div>", ids)


def changes_block(changes: dict[str, list[dict]], prev_run: str) -> str:
    """A pill per kind of change, each opening its list of entries."""
    pills, lists = [], []
    for kind, label in CHANGE_KINDS:
        rows = changes[kind]
        items = []
        for r in rows:
            extra = ""
            if kind == "moved":
                extra = f'<span class="mv">{html.escape(r["from"])} → {html.escape(r["to"])}</span>'
            elif kind == "dropped":
                extra = f'<span class="mv">was {html.escape(r["state"])}</span>'
            items.append(
                f'<a class="crow" href="#{r["a"]}"><span class="id">{r["id"]}</span>'
                f'<span class="tt">{md.renderInline(r["title"])}</span>{extra}</a>'
            )
        pills.append(f'<button class="pill cgb" data-k="{kind}" aria-keyshortcuts="{len(pills) + 1}">{label} <span class="n">{len(rows)}</span></button>')
        lists.append(f'<div class="clist" data-k="{kind}" hidden>{"".join(items) or "<p class=v-meta>none</p>"}</div>')
    return (
        f'<section class="changes"><div class="line"><span class="lbl">since {html.escape(prev_run)}</span>{"".join(pills)}</div>'
        f'{"".join(lists)}</section>'
    )


# ---------------------------------------------------------------------------------------------------
# The report's history, from git: what changed since its previous version, and each entry's timeline.


@dataclass(frozen=True)
class Version:
    date: str  # the commit's date
    message: str  # the commit's, whose body a run fills with the why of each change
    text: str


def versions(report: Path) -> list[Version]:
    """Every committed version of `report`, oldest first; none where it is in no git repo."""
    where = report.resolve().parent
    log = subprocess.run(["git", "-C", str(where), "log", "-z", "--format=%H %cs%n%B", "--", report.name],
                         capture_output=True, text=True)
    if log.returncode:
        return []
    out = []
    for commit in reversed([c for c in log.stdout.split("\0") if c]):
        head, _, message = commit.partition("\n")
        sha, date = head.split()
        shown = subprocess.run(["git", "-C", str(where), "show", f"{sha}:./{report.name}"],
                               capture_output=True, text=True, check=True)
        out.append(Version(date, message, shown.stdout))
    return out


def previous_of(committed: list[Version], text: str) -> Version | None:
    """What What changed compares against: the newest committed version that differs from `text`."""
    return next((v for v in reversed(committed) if v.text != text), None)


def timelines(history: list[tuple[str, list[Entry]]]) -> dict[str, list[tuple[str, str]]]:
    """Each id's State across the versions, oldest first, as (date, state): a run of one state keeps its
    first date, and a version without the id reads "not in the report" once the id has appeared."""
    seen: dict[str, list[tuple[str, str]]] = {}
    for date, entries in history:
        present = {e.id: state_key(e) or e.state_class or "—" for e in entries if e.id}
        for i in present.keys() | seen.keys():
            state = present.get(i, "not in the report")
            line = seen.setdefault(i, [])
            if not line or line[-1][1] != state:
                line.append((date, state))
    return seen


# ---------------------------------------------------------------------------------------------------
# Artefacts an entry names in its **Artefacts** field, by path from the agent repo's root or by URL:
# an image or a page is embedded in its sheet, anything else linked.

EMBEDDED = {".png": "img", ".svg": "img", ".jpg": "img", ".jpeg": "img", ".gif": "img", ".webp": "img",
            ".html": "frame"}


def artefacts(e: Entry, root: Path, page_dir: Path) -> list[dict]:
    out = []
    for name in re.findall(r"`([^`\s]+)`", e.fields.get("Artefacts", "")):
        href = name if "://" in name else os.path.relpath(root / name, page_dir)
        out.append({"href": href, "name": name, "how": EMBEDDED.get(Path(name.split("?")[0]).suffix.lower(), "link")})
    return out


def repo_root(report: Path) -> Path:
    """The root of the git repo the report is in, where an artefact's path starts; else its directory's parent."""
    top = subprocess.run(["git", "-C", str(report.resolve().parent), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    return Path(top.stdout.strip()) if top.returncode == 0 else report.resolve().parent.parent


# ---------------------------------------------------------------------------------------------------
# Comments: the page's state file, and the ones a run has yet to answer.

ANSWERED = re.compile(r"\banswered (C\d+)\b")


def state_file(page: Path) -> Path:
    return page.with_name(page.name + ".state.json")


def answered_in(texts: list[str]) -> set[str]:
    """The comments any of these texts answered, the report's versions and the run commits' bodies: an
    answer stays one once a later version drops its line, as a dropped entry's History does."""
    return {i for t in texts for i in ANSWERED.findall(t)}


def open_comments(report: Path, state: dict | None) -> str:
    """max's comments on the page that are neither deleted nor answered in any version of the report,
    as markdown grouped by entry, for a run's stages to read."""
    text = report.read_text()
    entries = load(text)[4]
    titles = {e.id or e.anchor.upper(): plain(e.title) for e in entries}
    answered = answered_in([t for v in versions(report) for t in (v.text, v.message)] + [text])
    pending = [c for c in (state or {}).get("comments", []) if not c.get("deleted") and c["id"] not in answered]
    if not pending:
        return "No comment of max's on the report's page is open.\n"
    by: dict[str, list[dict]] = {}
    for c in pending:
        by.setdefault(c["entry"], []).append(c)
    out = ["# max's open comments on the report's page"]
    for entry, cs in by.items():
        out += ["", f"## {entry} {titles.get(entry, '(no longer in the report)')}", ""]
        for c in cs:
            edited = f", edited {c['edited']}" if c.get("edited") else ""
            text = c["text"].replace("\n", "\n  ")
            out.append(f"- {c['id']}, {c['at']}{edited}, on the run of {c['report']}: {text}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------------------------------
# The page


def render(report: Path, page: Path) -> None:
    """Write the page of `report` to `page`."""
    text = report.read_text()
    title, run_line, intro, sections, entries = load(text)
    by_id = {e.id: e for e in entries if e.id}
    ids = set(by_id)
    for i in set(ID_RE.findall(dict(sections).get("Top recommendation", ""))) & ids:
        by_id[i].in_top = True

    committed = versions(report)
    history = [(v.date, load(v.text)[4]) for v in committed]
    if not committed or committed[-1].text != text:
        history.append((run_date(run_line) or "this version", entries))
    lines = timelines(history)

    changes, dropped, prev_run = None, {}, ""
    if previous := previous_of(committed, text):
        _, prev_line, _, _, prev_entries = load(previous.text)
        prev_run = run_date(prev_line) or previous.date
        changes = compare(entries, prev_entries)
        pm = {e.id: e for e in prev_entries if e.id}
        dropped = {r["a"]: pm[r["id"]] for r in changes["dropped"]}
        ids |= set(pm)

    grouped, flat = overview(entries)
    areas = Counter(e.area for e in entries)
    states = Counter(e.state_class for e in entries)
    area_pills = "".join(
        f'<button class="pill" data-area="{html.escape(a)}"{"" if i else " aria-keyshortcuts=\"a\""}>{html.escape(a)} <span class="n">{n}</span></button>'
        for i, (a, n) in enumerate(sorted(areas.items(), key=lambda kv: (kv[0] == "—", -kv[1], kv[0])))
    )
    state_order = ["live", "back", "to take up", "taken up", "fix landed", "held", "dismissed"]
    state_pills = "".join(
        f'<button class="pill" data-state="{html.escape(s)}"{"" if i else " aria-keyshortcuts=\"s\""}>{html.escape(s)} <span class="n">{n}</span></button>'
        for i, (s, n) in enumerate(sorted(states.items(), key=lambda kv: (state_order.index(kv[0]) if kv[0] in state_order else 99, kv[0])))
    )

    header = (
        f'<header class="head"><div><h1 class="ttl">{html.escape(title)}</h1>'
        f'<p class="v-meta">{md.renderInline(run_line)}</p></div>'
        f'<button id="scheme" title="Switch day and night" aria-keyshortcuts="t">{SUN}{MOON}</button></header>'
        + (changes_block(changes, prev_run) if changes else "")
        + f'<details class="fold prose"><summary aria-keyshortcuts="r">Rulings read before this run</summary>{linkify(md.render(intro), ids)}</details>'
    )
    root = repo_root(report)
    data = {
        e.anchor: {
            "id": e.id or e.anchor.upper(),
            "title": plain(e.title),
            "kind": e.kind,
            "rank": e.rank,
            "group": e.group,
            "line": lines.get(e.id, []),
            "art": artefacts(e, root, page.resolve().parent),
        }
        for e in entries
    }
    for a, e in dropped.items():
        data[a] = {"id": e.id, "title": plain(e.title), "kind": "dropped", "rank": 0, "group": "",
                   "prev": prev_html(e, ids), "prevRun": prev_run, "line": lines.get(e.id, []), "art": []}
    saved_at = state_file(page)
    saved = json.loads(saved_at.read_text()) if saved_at.is_file() else None
    page_data = {"entries": data, "run": run_date(run_line), "title": title, "key": str(page.resolve()),
                 "saved": saved, "answered": sorted(answered_in([t for v in committed for t in (v.text, v.message)] + [text]))}
    page.write_text(
        TEMPLATE.replace("__TITLE__", html.escape(f"{title}, {run_date(run_line)}"))
        .replace("__HEADER__", header)
        .replace("__AREAS__", area_pills)
        .replace("__STATES__", state_pills)
        .replace("__GROUPED__", grouped)
        .replace("__FLAT__", flat)
        .replace("__FULL__", full_report(title, run_line, intro, sections, entries, ids))
        .replace("__DATA__", json.dumps(page_data).replace("</", "<\\/"))
    )


SUN = '<svg class="sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
MOON = '<svg class="moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>'

TEMPLATE = Path(__file__).with_name("report_page.html").read_text()


def changes_text(report: Path) -> str:
    """What changed since the report's previous committed version, entry by entry by id, as the page
    derives it, one line per entry."""
    text = report.read_text()
    previous = previous_of(versions(report), text)
    if previous is None:
        return "No earlier committed version of the report differs from it.\n"
    _, prev_line, _, _, prev_entries = load(previous.text)
    changes = compare(load(text)[4], prev_entries)
    out = [f"Since {run_date(prev_line) or previous.date}:"]
    for kind, label in CHANGE_KINDS:
        for r in changes[kind]:
            how = f" ({r['from']} → {r['to']})" if kind == "moved" else f" (was {r['state']})" if kind == "dropped" else ""
            out.append(f"- {label}: {r['id']} {plain(r['title'])}{how}")
    return "\n".join(out) + "\n"


def cli(
    report: Annotated[Path, tyro.conf.Positional],
    page: Annotated[Path | None, tyro.conf.Positional] = None,
) -> None:
    """Render a retro's living report as its page, or, given no page, print what changed in it.

    Args:
        report: The report.md to render; where it is in a git repo, its committed versions give what changed and each entry's timeline.
        page: The HTML page to write; comments saved beside it, in <page>.state.json, are baked in. Without it, the script prints what changed since the report's previous committed version, entry by entry, as the page shows it.
    """
    if page is None:
        print(changes_text(report), end="")
    else:
        render(report, page)


if __name__ == "__main__":
    tyro.cli(cli, description=__doc__)
