#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# dependencies = ["tyro>=0.9", "markdown-it-py>=3", "pyyaml>=6"]
# ///
"""Render a session directory into its session page, or a spec into its spec page.

Each page is one self-contained HTML file in the house style, both colour schemes,
driven by diffview's keys (press ? on the page).

A session directory holds session.md (frontmatter session, repo, spec; an H1 title;
a ## Brief) and turns/NN.md, each a turn record: frontmatter date, answered,
superseded; an H1 headline; the sections ## Questions, ## Links, ## Details, any
absent. turns/NN.you.md holds the user's messages for turn NN, queued messages
separated by three or more blank lines.

A record that does not parse is reported as file:line: reason on stderr, the exit
code is 1, and no page is written.

Examples:

    render.py session agent/prototypes/session-page/sample -o agent/show/session-page/round-3/session.html
    render.py spec agent/tickets/session-page/spec.md --base 185d279 -o agent/show/session-page/round-3/spec.html
"""

from __future__ import annotations

import datetime as dt
import html
import math
import os
import re
import shlex
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Annotated

import tyro
import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token


# ----------------------------------------------------------------------------- CLI


@dataclass
class Session:
    """Render a session directory into its session page."""

    dir: Annotated[Path, tyro.conf.Positional]
    """Session directory: session.md and turns/."""
    output: Annotated[Path, tyro.conf.arg(aliases=["-o"])]
    """HTML file to write."""
    spec_page: Annotated[Path | None, tyro.conf.arg(metavar="PATH")] = None
    """Spec page the spec button and the S key open. Default: spec.html beside the output."""


@dataclass
class Spec:
    """Render a spec into its spec page, with the changes since a base commit marked per block."""

    spec: Annotated[Path, tyro.conf.Positional]
    """The spec's markdown file, inside a git repository."""
    base: str
    """Commit holding the previous round's version of the spec, at the same path."""
    output: Annotated[Path, tyro.conf.arg(aliases=["-o"])]
    """HTML file to write."""
    show_dir: Annotated[Path | None, tyro.conf.arg(metavar="PATH")] = None
    """Directory whose files are figures: a link into it is shown in place. Default: agent/show/<spec's directory name>/ in the spec's repository."""
    session_page: Annotated[Path | None, tyro.conf.arg(metavar="PATH")] = None
    """Session page an open mark such as (open → Q7) links to. Default: session.html beside the output, when it exists."""


Cmd = Annotated[Session, tyro.conf.subcommand(name="session", prefix_name=False)] | Annotated[
    Spec, tyro.conf.subcommand(name="spec", prefix_name=False)
]


class RecordError(Exception):
    """A record that does not parse: where, and why."""

    def __init__(self, path: Path, line: int | None, reason: str) -> None:
        super().__init__(f"{path}{f':{line}' if line else ''}: {reason}")


def main() -> None:
    cmd = tyro.cli(Cmd, description=__doc__)
    try:
        page = render_session(cmd) if isinstance(cmd, Session) else render_spec(cmd)
    except RecordError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    cmd.output.parent.mkdir(parents=True, exist_ok=True)
    cmd.output.write_text(page)
    print(cmd.output)


# ----------------------------------------------------------------------------- the session page


@dataclass
class Option:
    letter: str
    html: str
    pick: bool


@dataclass
class Question:
    qid: str
    turn: str
    headline: str
    detail: str
    options: list[Option] = field(default_factory=list)
    why: str = ""
    answer: str | None = None
    answered_in: str | None = None
    superseded_by: str | None = None
    superseded_in: str | None = None

    @property
    def open(self) -> bool:
        return self.answer is None and self.superseded_by is None


@dataclass
class Link:
    title: str
    href: str
    desc: str
    exists: bool


@dataclass
class Turn:
    num: str
    path: Path
    date: str
    headline: str
    questions: list[Question]
    links: list[Link]
    details: str
    answered: dict[str, str]
    superseded: dict[str, str]
    you: list[list[str]] | None


def render_session(args: Session) -> str:
    out_dir = args.output.parent.resolve()
    meta, title, brief = read_session_record(args.dir / "session.md", out_dir)
    turns = read_turns(args.dir / "turns", out_dir)
    link_answers(turns)

    spec_page = args.spec_page or args.output.parent / "spec.html"
    spec_href = os.path.relpath(spec_page.resolve(), out_dir)
    resume = f"cd {shlex.quote(str(meta['repo']))} && claude --resume {meta['session']}"
    questions = [q for t in turns for q in t.questions]
    waiting = [q for q in questions if q.open]
    dates = sorted({t.date for t in turns})
    span = dates[0] if len(dates) == 1 else f"{dates[0]} to {dates[-1]}"
    rendered = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    counted = f"{len(turns)} turn{'s' * (len(turns) != 1)}"
    sid = str(meta["session"])

    top = "".join(open_question_html(q) for q in waiting) or '<p class="v-small muted none">Nothing waits on you.</p>'
    waiting_label = f"waiting on you · {len(waiting)} question{'s' * (len(waiting) != 1)}" if waiting else "waiting on you"
    newest_first = sorted(turns, key=lambda t: int(t.num), reverse=True)
    body = "".join(turn_html(t, open_=(i == 0)) for i, t in enumerate(newest_first))
    spec_missing = "" if spec_page.exists() else '<span class="v-meta missing">not built yet</span>'

    page = f"""
<header class="page bar">
  <span class="v-meta where">session page · {esc(Path(str(meta['repo'])).name)}</span>
  {KEYS_BUTTON}{SCHEME_BUTTON}
</header>
<main class="page">
  <section class="intro">
    <h1 class="v-title">{title}</h1>
    <p class="v-meta">session {esc(sid[:8])} · {counted} · {esc(span)} · rendered {rendered}</p>
    <div class="prose brief">{brief}</div>
    <div class="actions">
      <button class="button" id="resume" data-cmd="{esc(resume)}" title="{esc(resume)}"><span>copy resume command</span><kbd>y</kbd></button>
      <a class="button" id="spec" href="{esc(spec_href)}" target="_blank" rel="noopener" title="the spec page of {esc(meta['spec'])}"><span>spec page</span><kbd>S</kbd></a>{spec_missing}
    </div>
  </section>
  <section class="waiting" aria-labelledby="waiting">
    <div class="divider"><h2 class="v-meta" id="waiting">{waiting_label}</h2></div>
    {top}
  </section>
  <section class="turns" aria-labelledby="turns">
    <div class="divider"><h2 class="v-meta" id="turns">turns · newest first</h2></div>
    {body}
  </section>
</main>
{help_html(SESSION_KEYS)}
<div class="toast" id="toast" role="status" aria-live="polite"></div>"""
    return document(f"{strip_tags(title)} · session page", SESSION_CSS, page, SESSION_JS)


def read_session_record(path: Path, out_dir: Path) -> tuple[dict, str, str]:
    front, body, offset = split_frontmatter(path, required={"session", "repo", "spec"}, allowed={"session", "repo", "spec"})
    h1, sections = split_sections(path, body, offset, allowed={"Brief"})
    md = markdown(path.parent, out_dir)
    brief = md.render(sections["Brief"][1], {}) if "Brief" in sections else ""
    return front, md.renderInline(h1, {}), brief


def read_turns(turns_dir: Path, out_dir: Path) -> list[Turn]:
    if not turns_dir.is_dir():
        raise RecordError(turns_dir, None, "no turns/ directory")
    files = sorted((p for p in turns_dir.glob("*.md") if re.fullmatch(r"\d+\.md", p.name)), key=lambda p: int(p.stem))
    if not files:
        raise RecordError(turns_dir, None, "no turn records (turns/NN.md)")
    return [read_turn(p, out_dir) for p in files]


def read_turn(path: Path, out_dir: Path) -> Turn:
    front, body, offset = split_frontmatter(path, required={"date"}, allowed={"date", "answered", "superseded"})
    for key in ("answered", "superseded"):
        value = front.get(key) or {}
        if not isinstance(value, dict):
            raise RecordError(path, 2, f"{key}: a mapping of question ids, like `Q1: a`")
        front[key] = {str(k): str(v) for k, v in value.items()}
        for k in front[key]:
            if not re.fullmatch(r"Q\d+", k):
                raise RecordError(path, 2, f"{key}: {k!r} is not a question id like Q7")
    for old, new in front["superseded"].items():
        if not re.fullmatch(r"Q\d+", new):
            raise RecordError(path, 2, f"superseded: {old} names {new!r}, not a question id like Q7")
    h1, sections = split_sections(path, body, offset, allowed={"Questions", "Links", "Details"})
    md = markdown(path.parent, out_dir)
    num = path.stem.zfill(2)
    questions = parse_questions(path, *sections["Questions"], md, num) if "Questions" in sections else []
    links = parse_links(path, *sections["Links"], md, out_dir) if "Links" in sections else []
    details = md.render(sections["Details"][1], {}) if "Details" in sections else ""
    you_file = path.with_name(f"{path.stem}.you.md")
    return Turn(
        num=num,
        path=path,
        date=str(front["date"]),
        headline=md.renderInline(h1, {}),
        questions=questions,
        links=links,
        details=details,
        answered=front["answered"],
        superseded=front["superseded"],
        you=split_messages(you_file.read_text()) if you_file.exists() else None,
    )


def split_frontmatter(path: Path, required: set[str], allowed: set[str]) -> tuple[dict, str, int]:
    """The frontmatter as data, the body after it, and the body's first line number."""
    text = path.read_text()
    m = re.match(r"---\n(.*?\n)---\n", text, re.S)
    if not m:
        raise RecordError(path, 1, "no frontmatter: the file opens with --- and a YAML block closed by ---")
    try:
        front = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        line = getattr(getattr(e, "problem_mark", None), "line", 0) + 2
        raise RecordError(path, line, f"frontmatter is not YAML: {getattr(e, 'problem', e)}") from None
    if not isinstance(front, dict):
        raise RecordError(path, 2, "frontmatter is not a mapping")
    if unknown := set(front) - allowed:
        raise RecordError(path, 2, f"unknown frontmatter field {sorted(unknown)[0]!r}; the fields are {', '.join(sorted(allowed))}")
    if missing := required - set(front):
        raise RecordError(path, 2, f"frontmatter lacks {sorted(missing)[0]!r}")
    return front, text[m.end() :], m.group(0).count("\n") + 1


def split_sections(path: Path, body: str, offset: int, allowed: set[str]) -> tuple[str, dict[str, tuple[int, str]]]:
    """The H1 and each ## section as (first line number, text); fenced code is not split."""
    lines = body.split("\n")
    h1: str | None = None
    sections: dict[str, tuple[int, list[str]]] = {}
    current: str | None = None
    fence = False
    for i, line in enumerate(lines):
        n = offset + i
        if line.startswith("```"):
            fence = not fence
        if not fence and (m := re.match(r"#(?!#)\s+(.+?)\s*$", line)):
            if h1 is not None:
                raise RecordError(path, n, "a second H1; a record has one H1, its headline")
            if current is not None:
                raise RecordError(path, n, "the H1 comes before the first section")
            h1 = m.group(1)
            continue
        if not fence and (m := re.match(r"##(?!#)\s+(.+?)\s*$", line)):
            name = m.group(1)
            if name not in allowed:
                raise RecordError(path, n, f"unknown section {name!r}; the sections are {', '.join('## ' + a for a in sorted(allowed))}")
            if name in sections:
                raise RecordError(path, n, f"a second ## {name}")
            if h1 is None:
                raise RecordError(path, n, "a section before the H1")
            current = name
            sections[name] = (n + 1, [])
            continue
        if current is None:
            if line.strip():
                where = "before the H1" if h1 is None else "between the H1 and the first section"
                raise RecordError(path, n, f"text {where}; it belongs in a section")
            continue
        sections[current][1].append(line)
    if h1 is None:
        raise RecordError(path, offset, "no H1")
    out = {}
    for name, (start, ls) in sections.items():
        while ls and not ls[0].strip():
            ls, start = ls[1:], start + 1
        out[name] = (start, "\n".join(ls).rstrip())
    return h1, out


Q_ITEM = re.compile(r"- \[(Q\d+)\] \*\*(.+?)\*\*(?:\s+(.*))?")
SUB_ITEM = re.compile(r"\s{2,}- (.*)")
OPTION = re.compile(r"\(([a-z])\)\s+(.*)")
PICK = re.compile(r"\s*\*my pick\*\s*")
WHY = re.compile(r"Why:\s*(.*)")


def parse_questions(path: Path, start: int, text: str, md: MarkdownIt, num: str) -> list[Question]:
    raw: list[dict] = []
    part: dict | None = None
    for i, line in enumerate(text.split("\n")):
        n = start + i
        if not line.strip():
            continue
        if m := Q_ITEM.fullmatch(line):
            part = {"qid": m.group(1), "headline": m.group(2), "detail": m.group(3) or "", "options": [], "why": None, "line": n}
            raw.append(part)
            continue
        if line.startswith("- "):
            raise RecordError(path, n, "a question is `- [Q7] **headline** detail`")
        if not raw:
            raise RecordError(path, n, "text before the first question")
        q = raw[-1]
        if m := SUB_ITEM.fullmatch(line):
            sub = m.group(1)
            if o := OPTION.fullmatch(sub):
                part = {"letter": o.group(1), "text": o.group(2), "line": n}
                q["options"].append(part)
            elif w := WHY.fullmatch(sub):
                if q["why"] is not None:
                    raise RecordError(path, n, f"a second Why: under {q['qid']}")
                part = {"text": w.group(1)}
                q["why"] = part
            else:
                raise RecordError(path, n, "a question's sub-item is an option `(a) text` or `Why: text`")
            continue
        if line.startswith(" ") and part is not None:
            key = "detail" if part is q else "text"
            part[key] = (part[key] + " " + line.strip()).strip()
            continue
        raise RecordError(path, n, "unexpected text in ## Questions")
    out = []
    for q in raw:
        letters = [o["letter"] for o in q["options"]]
        if len(set(letters)) != len(letters):
            raise RecordError(path, q["line"], f"{q['qid']} repeats an option letter")
        options = []
        for o in q["options"]:
            pick = bool(PICK.search(o["text"]))
            options.append(Option(o["letter"], md.renderInline(PICK.sub(" ", o["text"]).strip(), {}), pick))
        if sum(o.pick for o in options) > 1:
            raise RecordError(path, q["line"], f"{q['qid']} marks more than one option *my pick*")
        out.append(
            Question(
                qid=q["qid"],
                turn=num,
                headline=md.renderInline(q["headline"], {}),
                detail=md.renderInline(q["detail"], {}),
                options=options,
                why=md.renderInline(q["why"]["text"], {}) if q["why"] else "",
            )
        )
    return out


LINK_ITEM = re.compile(r"- \[(.+?)\]\(([^()\s]+)\)(?::\s*(.*))?\s*")


def parse_links(path: Path, start: int, text: str, md: MarkdownIt, out_dir: Path) -> list[Link]:
    links: list[Link] = []
    for i, line in enumerate(text.split("\n")):
        n = start + i
        if not line.strip():
            continue
        if m := LINK_ITEM.fullmatch(line):
            href, target = resolve_href(m.group(2), path.parent, out_dir)
            exists = target.exists() if target else True
            links.append(Link(md.renderInline(m.group(1), {}), href, m.group(3) or "", exists))
            continue
        if line.startswith(" ") and links:
            links[-1].desc = (links[-1].desc + " " + line.strip()).strip()
            continue
        raise RecordError(path, n, "a link is `- [title](path): description`")
    for link in links:
        link.desc = md.renderInline(link.desc, {})
    return links


def split_messages(text: str) -> list[list[str]]:
    """Messages as lists of paragraphs: three or more blank lines part two messages, one parts paragraphs."""
    text = re.sub(r"[ \t]+\n", "\n", text).strip("\n")
    messages = re.split(r"\n(?:[ \t]*\n){3,}", text)
    return [[p.strip() for p in re.split(r"\n[ \t]*\n+", m) if p.strip()] for m in messages if m.strip()]


def link_answers(turns: list[Turn]) -> None:
    """Mark each question answered or superseded from later turns' frontmatter; unknown ids do not parse."""
    seen: dict[str, Question] = {}
    for t in turns:
        for kind, table in (("answered", t.answered), ("superseded", t.superseded)):
            for qid, value in table.items():
                q = seen.get(qid)
                if q is None:
                    raise RecordError(t.path, 2, f"{kind}: {qid} is not a question of an earlier turn")
                if not q.open:
                    raise RecordError(t.path, 2, f"{kind}: {qid} was already settled in turn {q.answered_in or q.superseded_in}")
                if kind == "answered":
                    q.answer, q.answered_in = value, t.num
                else:
                    q.superseded_by, q.superseded_in = value, t.num
        for q in t.questions:
            if q.qid in seen:
                raise RecordError(t.path, None, f"{q.qid} was already asked in turn {seen[q.qid].turn}")
            seen[q.qid] = q
    for t in turns:
        for qid, new in t.superseded.items():
            if new not in seen:
                raise RecordError(t.path, 2, f"superseded: {qid} names {new}, which no turn asks")


def open_question_html(q: Question) -> str:
    return f"""
<article class="q blk" id="{q.qid.lower()}" tabindex="-1" data-block data-turn="t{q.turn}">
  <span class="rail v-num">{q.qid}</span>
  <div class="q-main">
    <h3 class="v-h3">{q.headline}</h3>
    {f'<p class="q-detail">{q.detail}</p>' if q.detail else ''}
    {options_html(q)}
    {f'<p class="why v-small"><span class="v-meta">why</span> {q.why}</p>' if q.why else ''}
    <p class="v-meta asked-in">asked in <a href="#t{q.turn}">turn {q.turn}</a></p>
  </div>
</article>"""


def options_html(q: Question, answer: str | None = None) -> str:
    if not q.options:
        return ""
    items = []
    for o in q.options:
        cls = " ".join(c for c in ("pick" if o.pick else "", "chosen" if answer == o.letter else "", "passed" if answer and answer != o.letter else "") if c)
        tags = ""
        if answer == o.letter:
            tags += '<span class="tag you">your answer</span>'
        if o.pick:
            tags += '<span class="tag">my pick</span>'
        items.append(f'<li class="{cls}"><span class="k v-num">{o.letter}</span><span>{o.html}{tags}</span></li>')
    return f'<ol class="opts">{"".join(items)}</ol>'


def turn_html(t: Turn, open_: bool) -> str:
    you = you_html(t.you)
    answers = answers_line(t)
    details = f'<div class="prose details">{t.details}</div>' if t.details else ""
    links = links_html(t.links)
    asked = "".join(asked_html(q) for q in t.questions)
    asked = f'<div class="asked">{asked}</div>' if asked else ""
    return f"""
<details class="turn blk" id="t{t.num}" data-block{' open' if open_ else ''}>
  <summary class="head">
    <span class="rail v-num">{t.num}</span>
    <span class="hl v-h3">{t.headline}</span>
    <span class="v-meta date">{esc(t.date)}</span>
  </summary>
  <div class="turn-body">
    {you}{answers}{details}{links}{asked}
  </div>
</details>"""


def you_html(messages: list[list[str]] | None) -> str:
    if messages is None:
        return '<p class="v-meta you-none">your message is not in the transcript</p>'
    words = sum(len(p.split()) for m in messages for p in m)
    first = " ".join(messages[0][0].split()) if messages and messages[0] else ""
    count = f"{len(messages)} messages · " if len(messages) > 1 else ""
    parts = "".join(
        '<div class="msg">' + "".join(f"<p>{esc(p).replace(chr(10), '<br>')}</p>" for p in m) + "</div>" for m in messages
    )
    return f"""
<details class="you">
  <summary><span class="v-meta who">you</span><span class="preview">{esc(first)}</span><span class="v-meta count">{count}{words:,} words</span></summary>
  <div class="you-text">{parts}</div>
</details>"""


def answers_line(t: Turn) -> str:
    """What this turn settled: the user's answers, then the questions it replaced."""
    answered = ", ".join(f'<a href="#{qid.lower()}">{qid}</a> {esc(v)}' for qid, v in t.answered.items())
    replaced = [f'<a href="#{old.lower()}">{old}</a> replaced by <a href="#{new.lower()}">{new}</a>' for old, new in t.superseded.items()]
    bits = ([f"your answers {answered}"] if answered else []) + replaced
    return f'<p class="v-meta answers">{" · ".join(bits)}</p>' if bits else ""


def links_html(links: list[Link]) -> str:
    if not links:
        return ""
    items = []
    for i, link in enumerate(links, start=1):
        key = f'<kbd class="n">{i}</kbd>' if i <= 9 else '<span class="n"></span>'
        missing = '<span class="v-meta missing">not built yet</span>' if not link.exists else ""
        desc = f'<span class="desc v-small">{link.desc}</span>' if link.desc else ""
        items.append(
            f'<li>{key}<span class="link-main"><a class="link" href="{esc(link.href)}" target="_blank" rel="noopener">{link.title}</a>{missing}{desc}</span></li>'
        )
    return f'<ol class="links">{"".join(items)}</ol>'


def asked_html(q: Question) -> str:
    anchor = f'id="{q.qid.lower()}"'
    if q.open:  # its one home is the top of the page, which names this turn
        return ""
    if q.superseded_by:
        state = f'replaced by <a href="#{q.superseded_by.lower()}">{q.superseded_by}</a> in turn {q.superseded_in}'
        return f'<div class="aq superseded" {anchor}><span class="k v-num">{q.qid}</span><div><p class="aq-h">{q.headline}</p><p class="v-meta">{state}</p></div></div>'
    letter = q.answer if any(o.letter == q.answer for o in q.options) else None
    free = "" if letter else f'<p class="v-small free"><span class="v-meta">your answer</span> {esc(q.answer or "")}</p>'
    return f"""
<div class="aq answered" {anchor}>
  <span class="k v-num">{q.qid}</span>
  <div>
    <p class="aq-h">{q.headline}</p>
    {options_html(q, letter)}{free}
    <p class="v-meta">answered in <a href="#t{q.answered_in}">turn {q.answered_in}</a></p>
  </div>
</div>"""


# ----------------------------------------------------------------------------- the spec page


@dataclass
class Block:
    kind: str  # h1..h6, p, li, code, quote, table, hr, html
    key: str  # normalised source: what the diff compares
    html: str  # rendered inner html
    text: str  # plain text, for the word diff
    section: str  # the heading it sits under
    list_id: int | None = None  # the list it belongs to, for li
    ordered: bool = False
    start: int = 1
    figures: list[str] = field(default_factory=list)


@dataclass
class Change:
    state: str  # same, new, edited, moved
    old: Block | None = None


def render_spec(args: Spec) -> str:
    spec = args.spec.resolve()
    out_dir = args.output.parent.resolve()
    repo = Path(git(spec.parent, "rev-parse", "--show-toplevel"))
    rel = spec.relative_to(repo).as_posix()
    show_dir = (args.show_dir or repo / "agent" / "show" / spec.parent.name).resolve()
    session_page = args.session_page or args.output.parent / "session.html"
    session_href = os.path.relpath(session_page.resolve(), out_dir) if session_page.exists() else None
    try:
        old_src = git(repo, "show", f"{args.base}:{rel}")
    except subprocess.CalledProcessError:
        raise RecordError(spec, None, f"{args.base} holds no {rel}") from None
    base_line = git(repo, "log", "-1", "--format=%h · %cs", args.base)
    base_subject = git(repo, "log", "-1", "--format=%s", args.base)

    env = {"session_href": session_href}
    new_front, new_body = strip_frontmatter(spec.read_text())
    _, old_body = strip_frontmatter(old_src)
    md = markdown(spec.parent, out_dir)
    new = blocks_of(md, new_body, env, spec.parent, out_dir, show_dir)
    old = blocks_of(md, old_body, {}, spec.parent, out_dir, None)  # the old round's open marks link nowhere
    changes, removed = diff_blocks(old, new)

    counts = defaultdict(int)
    for c in changes:
        counts[c.state] += 1
    counts["removed"] = sum(len(g) for g in removed.values())
    status = str(new_front.get("status", ""))

    headings = [(i, b) for i, b in enumerate(new) if b.kind in ("h2", "h3")]
    section_changes = changes_per_section(new, changes, removed)
    toc = "".join(
        f'<a class="v-small {b.kind}" href="#{slug(b.text)}" data-for="{slug(b.text)}">{b.html}'
        + (f'<span class="v-num n" title="{section_changes[i]} changed blocks">{section_changes[i]}</span>' if section_changes[i] else "")
        + "</a>"
        for i, b in headings
    )
    body = spec_body_html(new, changes, removed)
    title_block = body.pop(0) if body and body[0].startswith('<div class="blk h1') else ""
    legend = " ".join(
        f'<span class="lg {k}"><i></i>{counts[k]} {label}</span>'
        for k, label in (("new", "new"), ("edited", "edited"), ("moved", "moved"), ("removed", "removed"))
        if counts[k]
    )
    opens = [(j, re.findall(r"Q\d+", m)) for j, b in enumerate(new) for m in re.findall(r'class="pm open[^"]*"[^>]*>([^<]*)<', b.html)]
    if opens:
        j = opens[0][0]
        ids = ", ".join(dict.fromkeys(q for _, qs in opens for q in qs)) or f"{len(opens)}"
        legend += f' <a class="pm open" href="#{slug(new[j].text) if new[j].kind in ("h2", "h3") else f"b{j}"}" title="the first open mark">open: {esc(ids)}</a>'
    title_text = new[0].text if new and new[0].kind == "h1" else spec.stem

    page = f"""
<header class="page bar">
  <span class="v-meta where">spec page · {esc(spec.parent.name)}</span>
  <button class="button ghost" id="next" aria-keyshortcuts="d"><span>next change</span><kbd>d</kbd></button>
  {KEYS_BUTTON}{SCHEME_BUTTON}
</header>
<div class="page layout">
  <nav class="toc" aria-label="contents"><span class="v-meta">contents</span>{toc}</nav>
  <main class="doc">
    {title_block}
    <p class="v-meta docmeta">{esc(status + ' · ' if status else '')}{esc(rel)}</p>
    <p class="v-meta since">changes since <span title="{esc(base_subject)}">{esc(base_line)}</span></p>
    <p class="legend v-meta">{legend or 'no changes'}</p>
    {''.join(body)}
  </main>
</div>
{help_html(SPEC_KEYS)}"""
    return document(f"{title_text} · spec page", SPEC_CSS, page, SPEC_JS)


def git(cwd: Path, *argv: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *argv], check=True, capture_output=True, text=True).stdout.strip()


def strip_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"---\n(.*?\n)---\n", text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, text[m.end() :]


def blocks_of(md: MarkdownIt, src: str, env: dict, base: Path, out_dir: Path, show_dir: Path | None) -> list[Block]:
    """Headings, paragraphs and top-level list items, each a block the diff can mark."""
    tokens = md.parse(src, env)
    lines = src.split("\n")
    out: list[Block] = []
    section = ""
    list_count = 0

    def make(kind: str, toks: list[Token], lo: int, hi: int, **kw) -> Block:
        inner = md.renderer.render(toks, md.options, env)
        figures = figures_in(toks, base, out_dir, show_dir) if show_dir else []
        key = " ".join(" ".join(lines[lo:hi]).split())
        key = re.sub(r"^(#+|[-*+]|\d+[.)])\s+", "", key)
        return Block(kind, key, inner, " ".join(strip_tags(inner).split()), section, figures=figures, **kw)

    i = 0
    while i < len(tokens):
        t = tokens[i]
        close = matching_close(tokens, i)
        if t.type == "heading_open":
            b = make(t.tag, tokens[i + 1 : close], *t.map)
            out.append(b)
            section = b.text
        elif t.type in ("bullet_list_open", "ordered_list_open"):
            list_count += 1
            ordered = t.type == "ordered_list_open"
            start = int(t.attrGet("start") or 1)
            j = i + 1
            while j < close:
                item_close = matching_close(tokens, j)
                item = tokens[j]
                out.append(make("li", tokens[j + 1 : item_close], *item.map, list_id=list_count, ordered=ordered, start=start))
                j = item_close + 1
        elif t.type == "paragraph_open":
            out.append(make("p", tokens[i : close + 1], *t.map))
        elif t.map:
            kind = {"fence": "code", "code_block": "code", "blockquote_open": "quote", "table_open": "table", "hr": "hr"}.get(t.type, "html")
            out.append(make(kind, tokens[i : close + 1], *t.map))
        i = close + 1
    return out


def matching_close(tokens: list[Token], i: int) -> int:
    if tokens[i].nesting != 1:
        return i
    depth = 0
    for j in range(i, len(tokens)):
        depth += tokens[j].nesting
        if depth == 0:
            return j
    return len(tokens) - 1


def figures_in(tokens: list[Token], base: Path, out_dir: Path, show_dir: Path) -> list[str]:
    figs = []
    for t in tokens:
        for child in t.children or []:
            if child.type != "link_open":
                continue
            href = child.attrGet("href") or ""
            rel_href, target = resolve_href(href, base, out_dir)
            if target and (target == show_dir or show_dir in target.parents):
                figs.append(figure_html(rel_href, target, show_dir))
    return figs


def figure_html(href: str, target: Path, show_dir: Path) -> str:
    name = target.relative_to(show_dir).as_posix()
    head = f'<div class="fig-head"><span class="v-meta">{esc(name)}</span><a class="button ghost" href="{esc(href)}" target="_blank" rel="noopener">open in its own tab</a></div>'
    if not target.exists():
        where = os.path.relpath(target, Path.cwd())
        return f'<figure class="fig missing">{head}<div class="ph"><p class="v-small">Not built yet: <code>{esc(where)}</code>. It shows here once it exists and the spec page is rendered again.</p></div></figure>'
    if target.suffix.lower() in (".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"):
        return f'<figure class="fig">{head}<div class="frame"><img src="{esc(href)}" alt="{esc(name)}"></div></figure>'
    return f'<figure class="fig">{head}<div class="frame sized"><iframe data-src="{esc(href)}" title="{esc(name)}" loading="lazy"></iframe></div></figure>'


def diff_blocks(old: list[Block], new: list[Block]) -> tuple[list[Change], dict[int, list[Block]]]:
    """Each new block's change against the old version, and the removed old blocks keyed by the new block they precede."""
    changes = [Change("same") for _ in new]
    matched_old: dict[int, int] = {}
    free_new = set(range(len(new)))
    region_old: dict[int, int] = {}
    region_new: dict[int, int] = {}
    sm = SequenceMatcher(None, [b.key for b in old], [b.key for b in new], autojunk=False)
    for n, (tag, i1, i2, j1, j2) in enumerate(sm.get_opcodes()):
        if tag == "equal":
            for k in range(i2 - i1):
                matched_old[i1 + k] = j1 + k
                free_new.discard(j1 + k)
        elif tag == "replace":
            region_old.update(dict.fromkeys(range(i1, i2), n))
            region_new.update(dict.fromkeys(range(j1, j2), n))
    free_old = [i for i in range(len(old)) if i not in matched_old]

    by_key: dict[str, list[int]] = defaultdict(list)
    for i in free_old:
        by_key[old[i].key].append(i)
    for j in sorted(free_new):
        if by_key.get(new[j].key):
            i = by_key[new[j].key].pop(0)
            changes[j] = Change("moved", old[i])
            matched_old[i] = j
            free_new.discard(j)
    free_old = [i for i in free_old if i not in matched_old]

    def family(b: Block) -> str:
        return "heading" if b.kind.startswith("h") and b.kind != "hr" else "text" if b.kind in ("p", "li") else b.kind

    # An edit keeps its bold lead (a named decision), or enough of its rarer words: shared boilerplate
    # such as "As the user, I want" weighs little. A block that stayed in place needs less than one that moved.
    similar = Similarity([b.key for b in old + new])
    pairs = []
    for i in free_old:
        for j in free_new:
            if family(old[i]) != family(new[j]):
                continue
            score = similar(old[i].key, new[j].key)
            same_lead = lead(old[i].key) is not None and lead(old[i].key) == lead(new[j].key)
            in_place = i in region_old and region_old[i] == region_new.get(j)
            bar = LEAD_BAR if same_lead else IN_PLACE_BAR if in_place else MOVED_BAR
            if score >= bar:
                pairs.append((same_lead, score, i, j))
    for _, _, i, j in sorted(pairs, reverse=True):
        if i in matched_old or j not in free_new:
            continue
        changes[j] = Change("edited", old[i])
        matched_old[i] = j
        free_new.discard(j)
    for j in free_new:
        changes[j] = Change("new")

    # A removed block shows before its next surviving neighbour, else after its previous one.
    removed: dict[int, list[Block]] = defaultdict(list)
    stays = {k: j for k, j in matched_old.items() if changes[j].state != "moved"}
    for i in (i for i in range(len(old)) if i not in matched_old):
        after = next((stays[k] for k in range(i + 1, len(old)) if k in stays), None)
        before = next((stays[k] + 1 for k in range(i - 1, -1, -1) if k in stays), len(new))
        removed[after if after is not None else before].append(old[i])
    return changes, removed


LEAD_BAR, IN_PLACE_BAR, MOVED_BAR = 0.15, 0.33, 0.5


class Similarity:
    """Word overlap between two blocks, each word weighted by how rare it is across the document (idf)."""

    def __init__(self, keys: list[str]) -> None:
        df: dict[str, int] = defaultdict(int)
        for k in keys:
            for w in set(words(k)):
                df[w] += 1
        n = len(keys)
        self.weight = lambda w: math.log((n + 1) / (df.get(w, 0) + 0.5))

    def __call__(self, a: str, b: str) -> float:
        wa, wb = words(a), words(b)
        total = sum(map(self.weight, wa)) + sum(map(self.weight, wb))
        if not total:
            return 0.0
        shared = sum(self.weight(w) for m in SequenceMatcher(None, wa, wb, autojunk=False).get_matching_blocks() for w in wa[m.a : m.a + m.size])
        return 2 * shared / total


def words(s: str) -> list[str]:
    return re.findall(r"\w+", s.lower())


def lead(key: str) -> str | None:
    m = re.match(r"\*\*(.+?)\*\*", key)
    return " ".join(words(m.group(1))) if m else None


def changes_per_section(new: list[Block], changes: list[Change], removed: dict[int, list[Block]]) -> dict[int, int]:
    """Changed blocks under each h2 and h3, an h2 counting its h3s."""
    counts: dict[int, int] = defaultdict(int)
    h2 = h3 = None
    for j, b in enumerate(new + [None]):  # type: ignore[operator]
        if j in removed:
            for h in (h2, h3):
                if h is not None:
                    counts[h] += len(removed[j])
        if b is None:
            break
        if b.kind in ("h1", "h2"):
            h2, h3 = (j if b.kind == "h2" else None), None
        elif b.kind == "h3":
            h3 = j
        if changes[j].state != "same":
            for h in (h2, h3):
                if h is not None:
                    counts[h] += 1
    return counts


def spec_body_html(new: list[Block], changes: list[Change], removed: dict[int, list[Block]]) -> list[str]:
    """The spec as html chunks, the first being the title; lists are opened and closed around their items."""
    out: list[str] = []
    open_list: int | None = None
    number = 0
    for j, b in enumerate(new + [None]):  # type: ignore[operator]
        in_list = b is not None and b.kind == "li"
        if open_list is not None and (not in_list or b.list_id != open_list):
            if j in removed and all(r.kind == "li" for r in removed[j]):  # items removed from a list's end stay in it
                out.append(gone_html(removed.pop(j), as_item=True))
            out.append("</ol>" if new[j - 1].ordered else "</ul>")
            open_list = None
        if b is None:
            break
        if in_list and open_list is None:
            open_list, number = b.list_id, b.start - 1
            out.append(f'<ol start="{b.start}">' if b.ordered else "<ul>")
        if j in removed:
            out.append(gone_html(removed[j], as_item=in_list))
        if in_list:
            number += 1
        out.append(block_html(b, changes[j], j, number if b.ordered else None))
    if len(new) in removed:
        out.append(gone_html(removed[len(new)], as_item=False))
    return out


def block_html(b: Block, c: Change, j: int, value: int | None) -> str:
    tag = "li" if b.kind == "li" else "div"
    attrs = f' id="b{j}"'
    if b.kind in ("h2", "h3"):
        attrs = f' id="{slug(b.text)}"'
    if value is not None:
        attrs += f' value="{value}"'
    state = "" if c.state == "same" else f" {c.state}"
    mark = was = ""
    if c.state == "new":
        mark = '<span class="mk v-meta">new</span>'
    elif c.state in ("edited", "moved") and c.old is not None:
        mark = f'<button class="mk v-meta" aria-expanded="false" aria-controls="was{j}">{c.state}</button>'
        under = f"under {esc(c.old.section) or 'the title'}"
        if c.state == "moved":
            body = f'<p class="v-meta">unchanged, moved this round from {under if c.old.section != b.section else "elsewhere in this section"}</p>'
        else:
            where = f"before this round, {under}" if c.old.section != b.section else "before this round"
            body = f'<p class="v-meta">{where}</p><p class="wd">{word_diff(c.old.text, b.text)}</p>'
        was = f'<div class="was" id="was{j}" hidden>{body}</div>'
    inner = b.html
    if b.kind == "h1":
        inner = f'<h1 class="v-title">{strip_p(inner)}</h1>'
    elif b.kind.startswith("h") and b.kind != "hr":
        inner = f"<{b.kind}>{strip_p(inner)}</{b.kind}>"
    figs = "".join(b.figures)
    focusable = ' tabindex="-1"' if c.state != "same" else ""
    return f'<{tag} class="blk {b.kind}{state}"{attrs}{focusable} data-state="{c.state}">{mark}{inner}{figs}{was}</{tag}>'


def gone_html(blocks: list[Block], as_item: bool) -> str:
    tag = "li" if as_item else "div"
    n = len(blocks)
    parts = []
    for b in blocks:
        if b.kind.startswith("h") and b.kind != "hr":
            parts.append(f'<p class="gone-h">{strip_p(b.html)}</p>')
        elif b.kind == "li":
            parts.append(f'<div class="gone-li">{b.html}</div>')
        else:
            parts.append(b.html)
    where = esc(blocks[0].section) or "the title"
    return (
        f'<{tag} class="blk gone" tabindex="-1" data-state="removed">'
        f'<button class="gone-btn v-meta" aria-expanded="false"><i></i>{n} removed</button>'
        f'<div class="gone-body" hidden><p class="v-meta">removed this round, from {where}</p>{"".join(parts)}</div></{tag}>'
    )


def word_diff(a: str, b: str) -> str:
    tokens = re.compile(r"[\w'’/-]+|[^\w\s]|\s+")
    wa, wb = tokens.findall(a), tokens.findall(b)
    out = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append(esc("".join(wa[i1:i2])))
            continue
        if tag in ("delete", "replace"):
            out.append(f"<del>{esc(''.join(wa[i1:i2]))}</del>")
        if tag in ("insert", "replace"):
            out.append(f"<ins>{esc(''.join(wb[j1:j2]))}</ins>")
    return "".join(out)


# ----------------------------------------------------------------------------- shared


MARK = re.compile(r"\((you|my call|open|figure)\b(.*)\)", re.S)


def markdown(base: Path, out_dir: Path) -> MarkdownIt:
    """CommonMark with tables; links resolved from base to out_dir and opened in a new tab; provenance marks as tags."""
    md = MarkdownIt("commonmark").enable("table")

    def link_open(self, tokens, idx, options, env):
        t = tokens[idx]
        source = dict(t.attrs)  # the token keeps the link as written; only the output is rewritten
        href, _ = resolve_href(t.attrGet("href") or "", base, out_dir)
        t.attrSet("href", href)
        if not href.startswith("#"):
            t.attrSet("target", "_blank")
            t.attrSet("rel", "noopener")
        rendered = self.renderToken(tokens, idx, options, env)
        t.attrs = source
        return rendered

    def code_inline(self, tokens, idx, options, env):
        content = tokens[idx].content
        if m := MARK.fullmatch(content):
            return mark_html(m.group(1), content[1:-1], env)
        return f"<code>{esc(content)}</code>"

    md.add_render_rule("link_open", link_open)
    md.add_render_rule("code_inline", code_inline)
    return md


def mark_html(kind: str, text: str, env: dict) -> str:
    cls = {"you": "you", "my call": "mine", "open": "open", "figure": "figure"}[kind] + (" long" if len(text) > 24 else "")
    if kind == "open":
        qid = re.search(r"Q\d+", text)
        href = env.get("session_href")
        if qid and href:
            return f'<a class="pm open" href="{esc(href)}#{qid.group(0).lower()}" target="_blank" rel="noopener" title="a question waiting on you">{esc(text)}</a>'
        return f'<span class="pm open" title="a question waiting on you">{esc(text)}</span>'
    return f'<span class="pm {cls}">{esc(text)}</span>'


def resolve_href(href: str, base: Path, out_dir: Path) -> tuple[str, Path | None]:
    """A relative link rewritten to work from out_dir, and the file it points at; other links unchanged."""
    if not href or href.startswith("#") or re.match(r"[a-z][a-z0-9+.-]*:", href, re.I):
        return href, None
    path, hash_, frag = href.partition("#")
    path, q, query = path.partition("?")
    target = (Path(path) if path.startswith("/") else base / path).resolve()
    rel = os.path.relpath(target, out_dir)
    return rel + (q + query) + (hash_ + frag), target


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def strip_p(s: str) -> str:
    return re.sub(r"^\s*<p>|</p>\s*$", "", s.strip())


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "section"


def help_html(keys: list[tuple[str, str]]) -> str:
    key = lambda k: '<span class="v-meta">to</span>' if k == "to" else f"<kbd>{esc(k)}</kbd>"
    rows = "".join(f"<tr><td>{' '.join(map(key, combo.split()))}</td><td>{esc(what)}</td></tr>" for combo, what in keys)
    return f"""
<div class="help" id="help" role="dialog" aria-modal="true" aria-labelledby="help-title" hidden>
  <div class="card">
    <p class="v-h3" id="help-title">Keys</p>
    <table>{rows}</table>
    <p class="v-meta">diffview's keys, where diffview has the move</p>
  </div>
</div>"""


SESSION_KEYS = [
    ("j k", "next, previous block"),
    ("o Enter", "open or close the turn"),
    ("O", "open or close every turn"),
    ("g g", "top"),
    ("G", "last block"),
    ("1 to 9", "open the turn's nth link"),
    ("y", "copy the resume command"),
    ("S", "open the spec page"),
    ("?", "this list"),
]

SPEC_KEYS = [
    ("j k", "next, previous section"),
    ("d D", "next, previous change"),
    ("o Enter", "show or hide what the change was"),
    ("g g", "top"),
    ("G", "bottom"),
    ("?", "this list"),
]


def document(title: str, css: str, body: str, js: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400;1,6..72,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{TOKENS_CSS}{COMMON_CSS}{css}</style>
<script>{THEME_JS}</script>
</head>
<body>{body}
<script>{COMMON_JS}{js}</script>
</body>
</html>
"""


KEYS_BUTTON = '<button class="icon" id="keys" aria-label="keyboard shortcuts" aria-keyshortcuts="?"><kbd>?</kbd></button>'
SCHEME_BUTTON = """<button class="icon" id="scheme" aria-label="switch to night">
    <svg class="sun" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
    <svg class="moon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>
  </button>"""


# ----------------------------------------------------------------------------- styles and scripts

TOKENS_CSS = """
:root {
  color-scheme: light dark;
  --ground: light-dark(#f4e4cd, #1a1714);
  --ground-2: light-dark(#eddabe, #201c18);
  --edge: light-dark(#cfbca3, #4a433b);
  --muted: light-dark(#5e5650, #b0a89e);
  --body: light-dark(#37261d, #ede3d2);
  --strong: light-dark(#22140b, #faf2dc);
  --accent: light-dark(#426724, #6ea444);
  --accent-2: light-dark(#674806, #cdb78a);
  --wash: light-dark(rgb(66 103 36 / 0.16), rgb(110 164 68 / 0.22));
  --wash-ink: color-mix(in srgb, var(--muted) 6%, transparent);
  --mark: light-dark(rgb(168 139 81 / 0.35), rgb(205 183 138 / 0.35));
  --miss: color-mix(in srgb, var(--accent-2) 18%, transparent);
  --font-body: "Newsreader", Georgia, serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
  --size-body: 19px;
  --leading-body: 1.62;
  --measure: 38rem;
  --page: 62rem;
  --radius: 6px;
}
[data-theme="day"] { color-scheme: light; }
[data-theme="night"] { color-scheme: dark; }
"""

COMMON_CSS = """
body { margin: 0; background: var(--ground); color: var(--body); font: 400 var(--size-body) / var(--leading-body) var(--font-body); -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }
::selection { background: var(--mark); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 2px; }
a { color: inherit; text-decoration: none; transition: color 150ms; }
a:hover { color: var(--accent); }
code, kbd, pre { font-family: var(--font-mono); }
code { font-size: 0.84em; background: var(--ground-2); padding: 0.08em 0.32em; border-radius: 3px; }
kbd { display: inline-block; min-width: 1.35em; box-sizing: border-box; padding: 0 0.3em; border: 1px solid var(--edge); border-radius: 3px; background: var(--ground-2); font: 400 0.72rem/1.5 var(--font-mono); color: var(--muted); text-align: center; }
p { margin: 0; }
h1, h2, h3, h4 { margin: 0; }
.muted { color: var(--muted); }
.v-title { font-weight: 600; font-size: clamp(1.875rem, 3.5vw, 2.5rem); line-height: 1.12; letter-spacing: -0.022em; color: var(--strong); }
.v-h2 { font-weight: 600; font-size: 1.3em; line-height: 1.3; letter-spacing: -0.012em; color: var(--strong); }
.v-h3 { font-weight: 600; font-size: 1.05em; line-height: 1.4; color: var(--strong); }
.v-small { font-size: 0.92em; line-height: 1.6; }
.v-meta { font-family: var(--font-mono); font-size: 0.8125rem; line-height: 1.5; color: var(--muted); font-variant-numeric: tabular-nums; font-weight: 400; }
.v-num { font-family: var(--font-mono); font-size: 0.92em; font-variant-numeric: tabular-nums; }

.prose { max-width: var(--measure); }
.prose > * + * { margin-top: 0.9em; }
.prose a, a.inline { color: var(--accent); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; text-decoration-color: color-mix(in srgb, var(--accent) 40%, transparent); }
.prose a:hover { text-decoration-color: var(--accent); }
.prose strong { font-weight: 600; color: var(--strong); }
.prose > :first-child { margin-top: 0; }
.prose ul, .prose ol { padding-left: 1.2em; margin-bottom: 0; }
.prose > ul, .prose > ol { margin-top: 0; }
.prose > * + ul, .prose > * + ol { margin-top: 0.9em; }
.prose li + li { margin-top: 0.4em; }
.prose li::marker { color: var(--muted); }
.prose blockquote { margin: 0; border-left: 2px solid var(--edge); padding-left: 1.2em; color: var(--muted); }
.prose pre { background: var(--ground-2); border: 1px solid var(--edge); border-radius: var(--radius); padding: 0.75rem 1rem; overflow-x: auto; font-size: 0.8rem; line-height: 1.6; }
.prose pre code { background: none; padding: 0; font-size: inherit; }

.page { max-width: var(--page); margin: 0 auto; padding: 0 2rem; box-sizing: border-box; }
.bar { display: flex; align-items: center; gap: 0.5rem; min-height: 3.25rem; border-bottom: 1px solid var(--edge); }
.bar .where { flex: 1; }
.icon { display: inline-flex; align-items: center; padding: 0.3rem; border: 0; background: none; color: var(--muted); cursor: pointer; transition: color 150ms; }
.icon:hover { color: var(--accent); }
.icon kbd { font-size: 0.78rem; }
.icon:hover kbd { color: var(--accent); border-color: var(--accent); }
[data-theme="night"] .sun, [data-theme="day"] .moon { display: none; }
.button { display: inline-flex; align-items: center; gap: 0.6rem; height: 2.25rem; padding: 0 0.85rem; border: 1px solid var(--edge); border-radius: var(--radius); background: none; color: var(--body); font: 400 0.9rem/1 var(--font-body); cursor: pointer; text-decoration: none; white-space: nowrap; transition: color 150ms, border-color 150ms; }
.button:hover { border-color: var(--accent); color: var(--accent); }
.button:hover kbd { color: var(--accent); }
.button.ghost { border-color: transparent; color: var(--muted); padding: 0 0.5rem; }
.button.ghost:hover { color: var(--accent); }
.divider { display: flex; align-items: center; gap: 0.75rem; margin: 0 0 1.75rem; }
.divider::after { content: ""; flex: 1; height: 1px; background: var(--edge); }
.missing { color: var(--accent-2); }

.help { position: fixed; inset: 0; z-index: 10; display: grid; place-items: center; background: color-mix(in srgb, var(--strong) 40%, transparent); }
.help[hidden] { display: none; }
.help .card { background: var(--ground); border: 1px solid var(--edge); border-radius: var(--radius); padding: 1.25rem 1.5rem 1rem; min-width: 20rem; }
.help table { border-collapse: collapse; margin: 0.75rem 0; }
.help td { padding: 0.3rem 1.5rem 0.3rem 0; font-size: 0.92rem; vertical-align: baseline; }
.help td:first-child { white-space: nowrap; }
.toast { position: fixed; left: 50%; bottom: 1.5rem; transform: translateX(-50%); max-width: min(40rem, calc(100vw - 3rem)); box-sizing: border-box; padding: 0.5rem 0.9rem; border: 1px solid var(--edge); border-radius: var(--radius); background: var(--ground); font: 400 0.8rem/1.5 var(--font-mono); color: var(--body); opacity: 0; pointer-events: none; transition: opacity 200ms; overflow-wrap: anywhere; }
.toast.on { opacity: 1; }

@media (max-width: 50rem) {
  .page { padding: 0 1.25rem; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition: none !important; scroll-behavior: auto !important; }
}
"""

SESSION_CSS = """
:root { --size-body: 18px; --leading-body: 1.6; --page: 58rem; --rail: 3.25rem; --measure: 40rem; }

.intro { padding: 3.25rem 0 3rem; }
.intro .v-title { max-width: 22em; }
.intro > .v-meta { margin-top: 0.75rem; }
.brief { margin-top: 1.5rem; font-size: 1.1em; line-height: 1.58; color: var(--muted); }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; margin-top: 1.75rem; }
#resume.copied { border-color: var(--accent); color: var(--accent); }

.waiting { padding-bottom: 2.75rem; }
.none { padding-left: var(--rail); }
.blk { position: relative; scroll-margin-top: 1.5rem; }
.blk.cur::before { content: ""; position: absolute; left: -1rem; top: 0.35rem; bottom: 0.35rem; width: 2px; border-radius: 1px; background: var(--accent); }
.blk:focus { outline: none; }
.rail { color: var(--muted); padding-top: 0.12rem; }
.blk.cur > .rail, .blk.cur > summary .rail { color: var(--accent); }

/* a question waiting on the user */
.q { display: grid; grid-template-columns: var(--rail) minmax(0, 1fr); padding: 0.25rem 0 0; }
.q + .q { margin-top: 2.25rem; }
.q-main { max-width: 46rem; }
.q-detail { margin-top: 0.35rem; }
.opts { list-style: none; margin: 0.8rem 0 0; padding: 0; display: grid; gap: 0.4rem; }
.opts li { display: grid; grid-template-columns: 1.75rem minmax(0, 1fr); }
.opts .k { color: var(--muted); padding-top: 0.08rem; }
.opts .pick .k { color: var(--strong); font-weight: 500; }
.tag { font: 400 0.75rem/1 var(--font-mono); color: var(--muted); margin-left: 0.6rem; white-space: nowrap; }
.opts .pick .tag:not(.you) { color: var(--body); }
.tag.you { color: var(--accent); }
.why { margin-top: 0.8rem; color: var(--muted); max-width: 44rem; }
.why .v-meta, .free .v-meta { margin-right: 0.35rem; }
.asked-in { margin-top: 0.75rem; }
.asked-in a { text-decoration: underline; text-decoration-color: var(--edge); text-underline-offset: 3px; }

/* turns */
.turn { border-top: 1px solid var(--edge); }
.turn:last-of-type { border-bottom: 1px solid var(--edge); }
.turn > summary { list-style: none; cursor: pointer; display: grid; grid-template-columns: var(--rail) minmax(0, 1fr) auto; column-gap: 0; align-items: baseline; padding: 1rem 0; }
.turn > summary::-webkit-details-marker { display: none; }
.turn > summary:focus-visible { outline: none; }
.turn > summary:focus-visible .hl { outline: 2px solid var(--accent); outline-offset: 4px; border-radius: 2px; }
.turn > summary .hl { font-weight: 400; color: var(--body); transition: color 150ms; padding-right: 1.5rem; }
.turn[open] > summary .hl { font-weight: 600; color: var(--strong); }
.turn > summary:hover .hl { color: var(--accent); }
.turn > summary .date { white-space: nowrap; }
.turn-body { padding: 0 0 2.5rem var(--rail); display: grid; gap: 1.5rem; }

.you > summary { list-style: none; cursor: pointer; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 0.75rem; align-items: baseline; padding: 0.45rem 0.8rem; margin-left: -0.8rem; border-radius: var(--radius); transition: background-color 150ms; }
.you > summary::-webkit-details-marker { display: none; }
.you > summary:hover { background: var(--wash-ink); }
.you > summary .who { color: var(--accent); }
.you > summary .preview { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--muted); font-size: 0.92em; }
.you[open] > summary .preview { visibility: hidden; }
.you > summary .count { white-space: nowrap; }
.you-text { margin: 0.5rem 0 0.25rem; padding-left: 1.1rem; border-left: 2px solid var(--edge); max-width: var(--measure); font-size: 0.95em; }
.you-text p + p { margin-top: 0.7em; }
.you-text .msg + .msg { margin-top: 1.1rem; padding-top: 1.1rem; border-top: 1px dashed var(--edge); }
.you-none { font-style: normal; }

.answers a { color: var(--body); text-decoration: underline; text-decoration-color: var(--edge); text-underline-offset: 3px; }
.answers a:hover { color: var(--accent); }
.details { max-width: var(--measure); }

.links { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.7rem; max-width: 44rem; }
.links li { display: grid; grid-template-columns: 2rem minmax(0, 1fr); align-items: baseline; }
.links .n { justify-self: start; }
.link-main { display: flex; flex-wrap: wrap; column-gap: 0.6rem; align-items: baseline; }
.links a.link { color: var(--accent); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; text-decoration-color: color-mix(in srgb, var(--accent) 40%, transparent); }
.links a.link:hover { text-decoration-color: var(--accent); }
.links .desc { flex-basis: 100%; color: var(--muted); }

.asked { display: grid; gap: 1.1rem; padding-top: 1.25rem; border-top: 1px solid color-mix(in srgb, var(--edge) 60%, transparent); max-width: 46rem; }
.aq { display: grid; grid-template-columns: 2.5rem minmax(0, 1fr); scroll-margin-top: 1.5rem; }
.aq .k { color: var(--muted); padding-top: 0.08rem; }
.aq-h { font-weight: 600; color: var(--strong); }
.aq .opts { margin-top: 0.35rem; gap: 0.2rem; font-size: 0.95em; }
.aq .opts li.passed { color: var(--muted); }
.aq .opts li.chosen { color: var(--strong); }
.aq .opts li.chosen .k { color: var(--accent); font-weight: 500; }
.aq > div > .v-meta { margin-top: 0.3rem; }
.aq.superseded .aq-h, .aq.open .aq-h { font-weight: 400; color: var(--body); }
.aq.open a.v-meta { margin-left: 0.5rem; }
.aq a { text-decoration: underline; text-decoration-color: var(--edge); text-underline-offset: 3px; }
.free { margin-top: 0.3rem; }

@media (max-width: 50rem) {
  :root { --rail: 2.5rem; }
  .blk.cur::before { left: -0.75rem; }
  .turn > summary { grid-template-columns: var(--rail) minmax(0, 1fr); }
  .turn > summary .date { grid-column: 2; }
  .you > summary { grid-template-columns: auto minmax(0, 1fr); }
  .you > summary .count { display: none; }
}
"""

SPEC_CSS = """
:root { --page: 76rem; --gutter: 5.25rem; }
.bar #next { margin-right: 0.25rem; }
.layout { display: grid; grid-template-columns: 12.5rem minmax(0, 1fr); column-gap: 2.5rem; align-items: start; }
.toc { position: sticky; top: 0; max-height: 100vh; overflow-y: auto; box-sizing: border-box; padding: 3.5rem 0 2rem; display: grid; gap: 0.3rem; align-content: start; }
.toc > .v-meta { margin-bottom: 0.4rem; }
.toc a { color: var(--muted); display: flex; justify-content: space-between; gap: 0.75rem; line-height: 1.4; padding: 0.1rem 0; }
.toc a.h3 { padding-left: 0.9rem; }
.toc a.current, .toc a:hover { color: var(--accent); }
.toc a code { font-size: 0.8em; }
.toc .n { font-size: 0.72rem; color: var(--muted); padding-top: 0.15rem; }
.toc a.current .n { color: var(--accent); }

.doc { padding: 3.5rem 0 6rem var(--gutter); min-width: 0; }
.doc > .blk, .doc > ul, .doc > ol, .doc > .docmeta, .doc > .since, .doc > .legend { max-width: var(--measure); }
.doc > .blk + .blk, .doc > .blk + ul, .doc > .blk + ol, .doc > ul + .blk, .doc > ol + .blk, .doc > ul + ul, .doc > ol + ol { margin-top: 1.05em; }
.doc > .blk.h2 { margin-top: 2.6em; }
.doc > .blk.h3 { margin-top: 1.9em; }
.doc > .blk.h2 + .blk, .doc > .blk.h3 + .blk, .doc > .blk.h2 + ul, .doc > .blk.h3 + ul, .doc > .blk.h2 + ol, .doc > .blk.h3 + ol { margin-top: 0.7em; }
.doc h2 { font-weight: 600; font-size: 1.3em; line-height: 1.3; letter-spacing: -0.012em; color: var(--strong); }
.doc h3 { font-weight: 600; font-size: 1.05em; line-height: 1.4; color: var(--strong); }
.doc a:not(.button, .pm) { color: var(--accent); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; text-decoration-color: color-mix(in srgb, var(--accent) 40%, transparent); }
.doc strong { font-weight: 600; color: var(--strong); }
.doc ul, .doc ol { margin: 0; padding-left: 1.3em; }
.doc li + li { margin-top: 0.55em; }
.doc li::marker { color: var(--muted); font-variant-numeric: tabular-nums; }
.doc li > p + p { margin-top: 0.5em; }
.docmeta { margin-top: 0.9rem; }
.since { margin-top: 0.1rem; }
.legend { display: flex; flex-wrap: wrap; gap: 0.35rem 1.25rem; margin-top: 0.9rem; padding-bottom: 0.5rem; }
.lg { display: inline-flex; align-items: center; gap: 0.45rem; }
.lg i { display: inline-block; width: 2px; height: 0.95rem; border-radius: 1px; }
.lg.new i { background: var(--accent); }
.lg.edited i { background: repeating-linear-gradient(var(--accent) 0 3px, transparent 3px 5px); }
.lg.moved i { background: var(--edge); }
.lg.removed i { background: var(--accent-2); height: 2px; width: 0.8rem; }

/* change marks: a bar at the text's left edge, a word in the gutter */
.blk { position: relative; scroll-margin-top: 2rem; }
.blk:focus { outline: none; }
.blk.new::before, .blk.edited::before, .blk.moved::before { content: ""; position: absolute; left: var(--bar, -1rem); top: 0.3em; bottom: 0.3em; width: 2px; border-radius: 1px; }
.blk.new::before { background: var(--accent); }
.blk.edited::before { background: repeating-linear-gradient(var(--accent) 0 4px, transparent 4px 7px); }
.blk.moved::before { background: var(--edge); }
li.blk { --bar: calc(-1rem - 1.3em); }
.mk { position: absolute; left: var(--mk, calc(-1 * var(--gutter))); width: calc(var(--gutter) - 1.75rem); top: 0.28em; text-align: right; font-size: 0.72rem; line-height: 1.4; }
li.blk > .mk { --mk: calc(-1 * var(--gutter) - 1.3em); }
.blk.h1 > .mk, .blk.h2 > .mk { top: 0.55em; }
span.mk { color: var(--accent); }
button.mk { padding: 0; border: 0; background: none; cursor: pointer; color: var(--muted); text-decoration: underline; text-decoration-color: var(--edge); text-underline-offset: 3px; }
button.mk:hover, button.mk[aria-expanded="true"] { color: var(--accent); text-decoration-color: var(--accent); }
.blk.cur > .mk { color: var(--accent); }
.blk.cur::after { content: ""; position: absolute; inset: -0.35rem -0.6rem; border-radius: var(--radius); background: var(--wash-ink); z-index: -1; }
.doc { position: relative; z-index: 0; }

.was, .gone-body { margin: 0.75rem 0 0.25rem; padding: 0.1rem 0 0.15rem 1rem; border-left: 2px solid var(--edge); font-size: 0.9em; line-height: 1.65; }
.was > .v-meta, .gone-body > .v-meta { margin-bottom: 0.3rem; font-size: 0.72rem; }
.wd { color: var(--muted); }
.wd del { color: var(--accent-2); background: var(--miss); text-decoration: line-through; text-decoration-thickness: 1px; border-radius: 2px; }
.wd ins { color: var(--strong); background: var(--wash); text-decoration: underline; text-decoration-color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 3px; border-radius: 2px; }

.gone { list-style: none; }
.doc > .gone { margin-top: 0.7em; }
.gone-btn { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0; border: 0; background: none; cursor: pointer; color: var(--accent-2); font-size: 0.72rem; }
.gone-btn i { display: inline-block; width: 0.8rem; height: 2px; background: var(--accent-2); border-radius: 1px; }
.gone-btn:hover, .gone-btn[aria-expanded="true"] { text-decoration: underline; text-underline-offset: 3px; }
.gone-body { border-left-color: var(--accent-2); color: var(--muted); }
.gone-body > * + * { margin-top: 0.6em; }
.gone-body .gone-h { font-weight: 600; }
.gone-body a { color: inherit; }
.gone-body .pm, .gone-body .pm.open { color: inherit; background: none; padding: 0; font-weight: 400; pointer-events: none; }

/* provenance marks */
.pm { font: 400 0.7rem/1.4 var(--font-mono); color: var(--muted); white-space: nowrap; letter-spacing: 0; }
.pm.long { white-space: normal; }
.legend a.pm.open { margin-left: auto; }
.pm.open { display: inline-block; padding: 0.05rem 0.5rem; border-radius: 999px; background: var(--wash); color: var(--accent); text-decoration: none; font-weight: 500; }
a.pm.open:hover { background: var(--accent); color: var(--ground); }
.h2 .pm, .h3 .pm { font-weight: 400; }

/* figures */
.fig { margin: 1.1rem 0 0.4rem; display: grid; gap: 0.45rem; max-width: none; }
.fig-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.fig-head .button { height: 1.75rem; font-size: 0.85rem; }
.frame { border: 1px solid var(--edge); border-radius: var(--radius); background: var(--ground-2); overflow: hidden; }
.frame.sized { height: 72vh; min-height: 26rem; resize: vertical; }
.frame iframe { display: block; width: 100%; height: 100%; border: 0; background: var(--ground); }
.frame img { display: block; max-width: 100%; }
.fig.missing .ph { border: 1px dashed var(--edge); border-radius: var(--radius); padding: 1.25rem 1.25rem; color: var(--muted); }
.doc > .blk:has(.fig) { max-width: none; }
.doc > .blk:has(.fig) > p { max-width: var(--measure); }

.sec-cur::after { content: ""; position: absolute; left: -1rem; top: 0.2em; bottom: 0.2em; width: 2px; background: var(--accent); border-radius: 1px; }

@media (max-width: 62rem) {
  :root { --gutter: 1.25rem; }
  .layout { grid-template-columns: minmax(0, 1fr); }
  .toc { position: static; max-height: none; padding: 2rem 0 0; display: flex; flex-wrap: wrap; gap: 0.2rem 1rem; }
  .toc > .v-meta { flex-basis: 100%; margin-bottom: 0.2rem; }
  .toc a.h3 { padding-left: 0; }
  .toc a { justify-content: flex-start; gap: 0.35rem; }
  .doc { padding-top: 2rem; }
  .mk { position: static; display: block; width: auto; text-align: left; margin-bottom: 0.1rem; }
  .blk.new::before, .blk.edited::before, .blk.moved::before { left: -0.75rem; }
  li.blk { --bar: calc(-0.75rem - 1.3em); }
  .sec-cur::after { left: -0.75rem; }
}
"""

THEME_JS = """
(() => {
  const t = new URLSearchParams(location.search).get("theme")
  const night = t ? t === "night" : matchMedia("(prefers-color-scheme: dark)").matches
  document.documentElement.dataset.theme = night ? "night" : "day"
})()
"""

COMMON_JS = """
const root = document.documentElement
const reduce = matchMedia("(prefers-reduced-motion: reduce)")
const behavior = () => (reduce.matches ? "auto" : "smooth")
const scheme = document.getElementById("scheme")
const onTheme = []
const setTheme = (night) => {
  root.dataset.theme = night ? "night" : "day"
  scheme.setAttribute("aria-label", night ? "switch to day" : "switch to night")
  onTheme.forEach((f) => f())
}
scheme.addEventListener("click", () => setTheme(root.dataset.theme !== "night"))
setTheme(root.dataset.theme === "night")

const help = document.getElementById("help")
const toggleHelp = (on = help.hidden) => { help.hidden = !on }
document.getElementById("keys").addEventListener("click", () => toggleHelp())
help.addEventListener("click", (e) => { if (e.target === help) toggleHelp(false) })

// diffview's gg: a first g arms, a second within half a second goes to the top
let gArmed = false, gTimer = null
const gg = (go) => {
  if (gArmed) { clearTimeout(gTimer); gArmed = false; go() }
  else { gArmed = true; gTimer = setTimeout(() => (gArmed = false), 500) }
}
const typing = (e) => e.target.matches && e.target.matches("input, textarea, select, [contenteditable]")
const nativeKey = (e) => (e.key === "Enter" || e.key === " ") && e.target.closest && e.target.closest("button, a, summary")
"""

SESSION_JS = """
const blocks = [...document.querySelectorAll("[data-block]")]
const turns = blocks.filter((b) => b.matches(".turn"))
let cur = -1
const mark = () => blocks.forEach((b, n) => b.classList.toggle("cur", n === cur))
const focusBlock = (i) => {
  if (!blocks.length) return
  cur = Math.max(0, Math.min(blocks.length - 1, i))
  mark()
  const b = blocks[cur]
  ;(b.matches("details") ? b.querySelector(":scope > summary") : b).focus({ preventScroll: true })
  b.scrollIntoView({ block: "start", behavior: behavior() })
}
document.addEventListener("focusin", (e) => {
  const b = e.target.closest && e.target.closest("[data-block]")
  if (b) { cur = blocks.indexOf(b); mark() }
})

// a link to a question or turn inside a closed turn opens that turn first
const reveal = (id) => {
  const el = id && document.getElementById(id)
  if (!el) return
  const turn = el.closest("details.turn")
  if (turn) turn.open = true
  el.scrollIntoView({ block: "start", behavior: behavior() })
  const b = el.closest("[data-block]")
  if (b) { cur = blocks.indexOf(b); mark() }
}
document.addEventListener("click", (e) => {
  const a = e.target.closest && e.target.closest('a[href^="#"]')
  if (!a) return
  e.preventDefault()
  history.replaceState(null, "", a.getAttribute("href"))
  reveal(a.getAttribute("href").slice(1))
})
if (location.hash) reveal(location.hash.slice(1))

const toast = document.getElementById("toast")
let toastTimer = null
const say = (text) => {
  toast.textContent = text
  toast.classList.add("on")
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => toast.classList.remove("on"), 2200)
}
const resume = document.getElementById("resume")
const copy = async () => {
  const cmd = resume.dataset.cmd
  try { await navigator.clipboard.writeText(cmd) }
  catch {
    const ta = Object.assign(document.createElement("textarea"), { value: cmd })
    document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove()
  }
  resume.classList.add("copied")
  resume.querySelector("span").textContent = "copied"
  say("copied: " + cmd)
  setTimeout(() => { resume.classList.remove("copied"); resume.querySelector("span").textContent = "copy resume command" }, 1600)
}
resume.addEventListener("click", copy)
const spec = document.getElementById("spec")

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || typing(e)) return
  if (e.key === "?") { toggleHelp(); e.preventDefault(); return }
  if (e.key === "Escape") { toggleHelp(false); return }
  if (nativeKey(e)) return
  if (e.key === "g") { gg(() => { window.scrollTo({ top: 0, behavior: behavior() }); cur = -1; mark(); document.activeElement.blur() }); return }
  const focused = blocks[cur]
  switch (e.key) {
    case "j": focusBlock(cur + 1); break
    case "k": focusBlock(cur < 0 ? 0 : cur - 1); break
    case "G": focusBlock(blocks.length - 1); break
    case "o": case "Enter": if (focused && focused.matches("details")) focused.open = !focused.open; break
    case "O": { const open = !turns.every((t) => t.open); turns.forEach((t) => (t.open = open)); break }
    case "y": copy(); break
    case "S": window.open(spec.href, "_blank", "noopener"); break
    default: {
      if (!/^[1-9]$/.test(e.key)) return
      const turn = focused && focused.matches(".turn") ? focused : turns[0]
      const link = turn && turn.querySelectorAll("a.link")[+e.key - 1]
      if (link) window.open(link.href, "_blank", "noopener")
      else say(`turn ${turn ? turn.id.slice(1) : ""} has no link ${e.key}`)
    }
  }
  e.preventDefault()
})
"""

SPEC_JS = """
const doc = document.querySelector(".doc")
const sections = [...doc.querySelectorAll(".blk.h2, .blk.h3")]
const changes = [...doc.querySelectorAll('.blk[data-state="new"], .blk[data-state="edited"], .blk[data-state="moved"], .blk[data-state="removed"]')]
const tocLinks = new Map([...document.querySelectorAll(".toc a")].map((a) => [a.dataset.for, a]))

// figures follow the page's scheme
const frames = [...document.querySelectorAll("iframe[data-src]")]
const paintFrames = () => frames.forEach((f) => {
  const src = f.dataset.src, sep = src.includes("?") ? "&" : "?"
  const want = `${src}${sep}theme=${root.dataset.theme}`
  if (f.getAttribute("src") !== want) f.setAttribute("src", want)
})
onTheme.push(paintFrames)
paintFrames()

// contents: the section in view is the current one
const here = () => {
  const y = 120
  let at = null
  for (const s of sections) { if (s.getBoundingClientRect().top <= y) at = s; else break }
  return at
}
const paintToc = () => {
  const at = here()
  tocLinks.forEach((a, id) => a.classList.toggle("current", !!at && at.id === id))
}
addEventListener("scroll", paintToc, { passive: true })
paintToc()

// o and Enter, and a click on a mark, show what a change was
const toggleWas = (blk) => {
  const btn = blk.querySelector(":scope > .mk[aria-expanded], :scope > .gone-btn")
  if (!btn) return
  const panel = blk.querySelector(":scope > .was, :scope > .gone-body")
  const open = btn.getAttribute("aria-expanded") !== "true"
  btn.setAttribute("aria-expanded", String(open))
  panel.hidden = !open
}
doc.addEventListener("click", (e) => {
  const btn = e.target.closest(".mk[aria-expanded], .gone-btn")
  if (btn) toggleWas(btn.closest(".blk"))
})

let curChange = -1, curSection = null
const markChange = (i) => {
  changes.forEach((c, n) => c.classList.toggle("cur", n === i))
}
const goChange = (dir) => {
  if (!changes.length) return
  let i = curChange
  const inView = (c) => { const r = c.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight }
  if (i < 0 || !inView(changes[i])) {
    // start from the viewport: the first change below its top, or the last one above it
    const tops = changes.map((c) => c.getBoundingClientRect().top)
    i = dir > 0 ? tops.findIndex((t) => t > 8) : tops.findLastIndex((t) => t < -8)
    if (i < 0) i = dir > 0 ? changes.length - 1 : 0
  } else i = Math.max(0, Math.min(changes.length - 1, i + dir))
  curChange = i
  markChange(i)
  changes[i].focus({ preventScroll: true })
  changes[i].scrollIntoView({ block: "center", behavior: behavior() })
}
document.getElementById("next").addEventListener("click", () => goChange(1))
doc.addEventListener("focusin", (e) => {
  const i = changes.indexOf(e.target.closest(".blk"))
  if (i >= 0) { curChange = i; markChange(i) }
})

const goSection = (dir) => {
  if (!sections.length) return
  const at = curSection && Math.abs(curSection.getBoundingClientRect().top) < 40 ? curSection : here()
  let i = at ? sections.indexOf(at) : -1
  i = dir > 0 ? i + 1 : at && at.getBoundingClientRect().top < -40 ? i : i - 1
  i = Math.max(0, Math.min(sections.length - 1, i))
  showSection(sections[i])
}
const showSection = (s) => {
  sections.forEach((x) => x.classList.toggle("sec-cur", x === s))
  curSection = s
  s.scrollIntoView({ block: "start", behavior: behavior() })
}

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || typing(e)) return
  if (e.key === "?") { toggleHelp(); e.preventDefault(); return }
  if (e.key === "Escape") { toggleHelp(false); return }
  if (nativeKey(e)) return
  if (e.key === "g") { gg(() => { window.scrollTo({ top: 0, behavior: behavior() }); sections.forEach((x) => x.classList.remove("sec-cur")); curSection = null }); return }
  switch (e.key) {
    case "j": goSection(1); break
    case "k": goSection(-1); break
    case "G": window.scrollTo({ top: document.body.scrollHeight, behavior: behavior() }); break
    case "d": goChange(1); break
    case "D": goChange(-1); break
    case "o": case "Enter": if (curChange >= 0) toggleWas(changes[curChange]); break
    default: return
  }
  e.preventDefault()
})
"""


if __name__ == "__main__":
    main()
