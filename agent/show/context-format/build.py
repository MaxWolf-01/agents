#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Writes index.html beside this file: the CONTEXT.md format as it stands, what the glossaries
built on it look like, what the session transcripts say about them, and the shapes it could take.

Numbers come from measure.json (measure.py) and mine.json (mine.py); run both first.
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
M = json.loads((HERE / "measure.json").read_text())
T = json.loads((HERE / "mine.json").read_text())


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def code(s: str) -> str:
    return f"<code>{esc(s)}</code>"


def entry(src: str, cls: str = "") -> str:
    return f'<pre class="entry {cls}">{esc(src.strip())}</pre>'


# ---- 1. the format, beside upstream --------------------------------------------------------

FORMAT_ROWS = [
    ("title and a one- or two-sentence description", "yes", "yes",
     "All seven glossaries have one.", "keep"),
    ("**Term**: then a definition of one or two sentences, saying what it is", "yes", "yes",
     "skilltree has 26 of 35 entries over two sentences. The rule exists; nothing checks it.", "keep, check it"),
    ("_Avoid_: line with the rejected words", "yes", "yes",
     "It is what the challenge step reads. Skilltree, 2026-08-02: an agent caught “tag” because the Avoid line of Group lists it. A grep of Avoid words is useless as a check: see section 5, D.", "keep"),
    ("which terms get in", "“terms specific to this project, not general programming concepts”",
     "“only ambiguous terms earn an entry” (62068d4, 2026-07-24)",
     "The mx rule is the stricter one. Verdict got in anyway: a worker's coinage, entered because the feature exposed it.", "keep, check it"),
    ("no mechanism in a definition", "“totally devoid of implementation details”",
     "“definitions survive redesign”, a per-clause test (a8c9a9a, 2026-08-27)",
     "Written after a failure max reported on 2026-08-27. On 2026-08-07 skilltree's Extended Quiz entry was one edit behind ADR 0007: a mechanism with two homes.", "keep, check it"),
    ("### subheadings for clusters", "yes", "yes",
     "The format's only way to say which area a term belongs to, and a reader outside the glossary never sees the heading. Seven complaints about bare names in the transcripts, section 4.", "not enough alone"),
    ("Relationships, Flagged ambiguities, example dialogue", "removed 2026-05-19 and 2026-05-28 (e7df78b, e3b90b5)",
     "never inherited: mx forked 2026-07-09",
     "Pocock's own CONTEXT.md still carries Relationships and Flagged ambiguities, written to the format before it changed.", "stay out"),
    ("CONTEXT-MAP.md for several contexts", "yes", "yes",
     "Used once: a work repo, the platform plus an architecture map of it, whose terms (node, zone, edge) name what the map draws, not what the platform does.", "keep"),
    ("the qualifier rule", "none", "none",
     "Proposed, section 5, A.", "add"),
    ("the name the code uses", "none", "none",
     "The work glossary wrote it in prose: one entry named the API's record name for the term, another the boolean flag that marks it.", "add as a field"),
    ("a reviewer reads glossary diffs", "no", "added on this branch (3555bd7)",
     "code-review never named CONTEXT.md before it.", "done"),
]


def format_table() -> str:
    rows = "".join(
        f"<tr><td>{esc(a)}</td><td class='muted'>{esc(u)}</td><td class='muted'>{esc(m)}</td>"
        f"<td>{esc(e)}</td><td class='v-meta verdict'>{esc(v)}</td></tr>"
        for a, u, m, e, v in FORMAT_ROWS
    )
    return ("<table class='wide'><thead><tr><th>element</th><th>upstream</th><th>mx</th>"
            "<th>what the repos show</th><th>verdict</th></tr></thead><tbody>" + rows + "</tbody></table>")


# ---- 2. what it is for ----------------------------------------------------------------------

QUESTIONS = [
    ("What is the one word for this thing?", "an agent writing a ticket, a commit, code, UI copy"),
    ("What does this word mean here?", "a cold reader: a worker, a reviewer, max a month later"),
    ("Which word do I not use, and why?", "the same writer, and the grilling agent challenging a term"),
    ("Are these two words one thing or two?", "grilling, when two names meet"),
]

POINTS = {
    "read": [
        ("claude/CLAUDE.md", "every session: read the glossary before touching your area, use its vocabulary"),
        ("dispatch/worker-prompt.md", "every worker: the same"),
        ("to-tickets", "ticket titles and descriptions"),
        ("grilling/SPEC-FORMAT.md", "the spec is written in its vocabulary"),
        ("testing", "test names"),
        ("recap, wait-what", "the words of a re-pitch"),
        ("diagnosing-bugs, improve-codebase-architecture", "the mental model of the modules"),
        ("codex, codebase-design/DESIGN-IT-TWICE.md", "passed on to another model"),
    ],
    "written": [
        ("domain-modelling", "the one writer; reached from grill-with-docs and grilling"),
        ("improve-codebase-architecture", "adds a term when a deepened module needs a name"),
        ("tracker", "the spec sweep greps a retired claim across CONTEXT.md"),
    ],
    "checked": [
        ("code-review", "since 3555bd7 on this branch: CONTEXT-FORMAT.md is a standards source for a glossary diff"),
    ],
}


def points() -> str:
    cols = []
    for head, items in POINTS.items():
        lis = "".join(f"<li>{code(a)}<span class='muted'> {esc(b)}</span></li>" for a, b in items)
        cols.append(f"<div><h3 class='v-h3'>{head} by</h3><ul class='plain'>{lis}</ul></div>")
    return "<div class='three'>" + "".join(cols) + "</div>"


def questions() -> str:
    rows = "".join(f"<tr><td>{esc(q)}</td><td class='muted'>{esc(w)}</td></tr>" for q, w in QUESTIONS)
    return "<table><thead><tr><th>question</th><th>who asks it</th></tr></thead><tbody>" + rows + "</tbody></table>"


# ---- 3. the glossaries, measured ------------------------------------------------------------


def measured() -> str:
    rows = ""
    for name, r in M.items():
        n = r["entries"]
        rows += (f"<tr><td>{esc(name)}</td>"
                 + "".join(f"<td class='v-num'>{v}</td>" for v in (
                     n, r["median_words"], r["max_words"], r["over_two_sentences"], r["with_code"],
                     r["with_avoid"], r["single_word"]))
                 + "</tr>")
    return ("<table class='wide nums'><thead><tr><th>glossary</th><th>entries</th><th>median words</th>"
            "<th>longest</th><th>over 2 sentences</th><th>code identifier</th><th>avoid line</th>"
            "<th>one-word name</th></tr></thead><tbody>" + rows + "</tbody></table>")


GOOD = [
    ("agents (mx), 7 words", """**Wave**:
The tickets one tick hands to workers together.
_Avoid_: batch, round"""),
    ("work platform, qualified name", """**Contact tag**:
A label on a contact, many per contact, used for campaigns and contact search. Stored in the same table as tags with a different scope.
_Avoid_: tag without the qualifier when contacts are meant"""),
    ("skilltree, a bare word renamed after max's complaint", """**Node Chip**:
The small box drawn for a node on either surface ...
_Avoid_: chip (unqualified), tile, node card (for this)"""),
]

BAD = [
    ("skilltree, 194 words, 6 sentences, first two shown", """**Retention**:
The chance the user would recall a node's cards right now — FSRS retrievability, decaying with neglect (ADR 0018). It is the mean over the cards they have actually answered; a node with no cards, or none answered, has no retention rather than a zero, and is simply untinted. ..."""),
    ("dotfiles, a bare word that relies on its heading", """### diffview

**Server**:
The process `diffview --serve` leaves behind for one directory of rendered pages, so those pages can save their review state.
_Avoid_: daemon, serve process"""),
]

IMPORT_BEFORE = """**Import batch**:
The record of one import, in `import_batch`: who imported what, when, and how many rows it stored. Every survey response names one, whichever survey brought it, and deleting it removes them; that is the repair path for a bad import.
_Avoid_: batch on its own, upload (an upload is what the partner does; the batch is what it leaves behind)

**Verdict**:
What an import made of one row it was handed: imported, duplicate or unmatched. The upload page counts them for the uploader and names the unmatched rows.
_Avoid_: status, result, row outcome"""

IMPORT_AFTER = """### Imports

**Import batch**:
The record of one import of rows from outside the platform: who brought in what, when, and how many rows it stored. The rows it stored belong to it.
_Avoid_: batch on its own, upload (an upload is what the uploader does; the import batch is what it leaves behind)
_In code_: `import_batch`"""


def pairs(items, cls) -> str:
    return "".join(f"<figure class='ex'><figcaption class='v-meta'>{esc(c)}</figcaption>{entry(s, cls)}</figure>"
                   for c, s in items)


# ---- 4. transcripts -------------------------------------------------------------------------

GENERIC = [
    ("2026-07-23", "dotfiles", "activity and archive are kinda ambiguous names"),
    ("2026-08-05", "skilltree", "I wouldn't call that cloud because it's too ambiguous … potentially confuse it with other things that could be cloudy or have in the past been called cloud in the project"),
    ("2026-08-15", "skilltree", "chip ==...? could mean a hundred differnet things … it's not speicif c enoguh i dont like this one"),
    ("2026-09-09", "agents", "the glossary it's too it's too generic like hardened and unmeasured like it can be something that's like words that are used in a million different places not just testing"),
    ("2026-09-09", "agents", "maybe we also shouldnt say synthesis, since that's too generic? … you could ipck a self-documenting name"),
    ("2026-09-14", "dotfiles", "is it unambiguous if you do it with ### section + uhhh very broad terms, or should the terms have a specifier so yk it's abt diffview?"),
    ("2026-09-22", "work platform", "import batch that could be a million different things and a million other different features"),
]
COINED = [
    ("2026-07-29", "skilltree", "signed couplings … L0 to L3. … You need to have studied the glossary and the design documents in order to understand."),
    ("2026-08-02", "skilltree", "if materialize is just add, then we don't need to call it materialize, but just call it add … we don't need to invent bespoke vocabulary for everything"),
    ("2026-08-05", "skilltree", "Instead of coining the term workbench, we just say local view."),
    ("2026-09-22", "work platform", "Verdict, entered by a worker whose own note says “the wording is mine”"),
]
MECHANISM = [
    ("2026-08-07", "skilltree", "CONTEXT.md's Extended Quiz entry is one edit stale (it says “at full difficulty”; ADR 0007 corrected this to “edge-required levels”)"),
    ("2026-08-27", "agents", "here's a common failure mode … that happens when grilling or wayfinding and writing context.md: led to a8c9a9a, definitions survive redesign"),
]
HELPED = [
    ("2026-08-02", "skilltree", "an agent flagged “tag” for a new grouping idea: ADR 0003 and the Avoid line of Group already ruled it out"),
    ("2026-08-06", "skilltree", "max asked whether root and leaf were backwards; Root gained “_Avoid_: leaf” so this confusion can't recur"),
]


def quotes(items) -> str:
    return "<ul class='quotes'>" + "".join(
        f"<li><span class='v-meta'>{d} · {esc(p)}</span><q>{esc(q)}</q></li>" for d, p, q in items) + "</ul>"


# ---- 5. shapes ------------------------------------------------------------------------------

SHAPES = [
    ("A", "Add the qualifier rule", True,
     "A term whose bare word the rest of the system also uses carries its qualifier in the name: Contact tag, Node chip, diffview server. The heading groups terms; the name carries the qualifier, because the name is what a ticket or a commit quotes.",
     "All seven complaints in section 4 were a bare, common word. Chip was already fixed this way; import batch would have been caught at review.",
     "One line in CONTEXT-FORMAT.md. Longer names. It overturns the dotfiles glossary's own stated convention (“inside that subsystem's own artifacts the term is used bare”): Server becomes diffview server.",
     "the reviewer: whether a word is used elsewhere in another sense is a judgement no script makes"),
    ("B", "Add an _In code_ line", True,
     "The identifier the code uses for the term (a table, a type, a status value) moves out of the definition onto its own line.",
     "Nothing in the transcripts by itself. It is what makes C exact: an identifier in the definition is then always a finding.",
     "A format change; each entry that names an identifier moves it.",
     "the script"),
    ("C", "A glossary lint", True,
     "A script that fails an entry over two sentences, over 40 words, or with a code identifier outside _In code_. Run by domain-modelling after an edit, and by code-review.",
     f"Would flag skilltree {sum(1 for e in M['skilltree']['detail'] if e['sentences'] > 2 or e['words'] > 40 or e['code'])} of {M['skilltree']['entries']}, the work architecture map 10 of 40, agents 1 of 28. It catches the mechanism creep that let Extended Quiz drift from ADR 0007. It does not catch Verdict, or import batch's survey clause: those are judgement.",
     "About 60 lines of Python (measure.py is most of it), and a first run that flags most of skilltree.",
     "the script: rung one"),
    ("D", "Grep the Avoid words across the repo", False,
     "Fail a diff that uses a word some entry lists under Avoid.",
     "Nothing usable. The 80 Avoid words of the agents glossary match 711 times in mx/skills, nearly all in the ordinary sense: “project” 73, “question” 67, “report” 52.",
     "A flood of false findings; it would be switched off within a week.",
     "no one"),
    ("E", "A glossary per feature", False,
     "One CONTEXT.md per feature directory, beside the spec.",
     "None of the moments in section 4 is a word meaning two things in two features. A feature retires when it ships, and its glossary would go stale or redefine Helper and Task.",
     "Duplicated shared terms, a file per feature to keep current, and a map to find them.",
     "no one"),
    ("F", "Module docstrings instead of a glossary", False,
     "Define each term in the module that implements it.",
     "Mechanism belongs there and in ADRs, which is already the rule. The glossary's terms are read in specs, tickets and UI copy, often before any module exists.",
     "The ubiquitous language loses its one place.",
     "no one"),
]


def shapes() -> str:
    out = ""
    for key, title, rec, what, prevents, cost, checker in SHAPES:
        tag = "recommended" if rec else "rejected"
        out += (f"<section class='shape {'rec' if rec else ''}'>"
                f"<h3 class='v-h3'><span class='v-num muted'>{key}</span> {esc(title)} "
                f"<span class='tag v-meta'>{tag}</span></h3>"
                f"<p>{esc(what)}</p><dl>"
                f"<dt class='v-meta'>prevents</dt><dd>{esc(prevents)}</dd>"
                f"<dt class='v-meta'>costs</dt><dd>{esc(cost)}</dd>"
                f"<dt class='v-meta'>checked by</dt><dd>{esc(checker)}</dd></dl></section>")
    return out


CSS = """
.page { max-width: var(--page); margin: 0 auto; padding: 0 2rem; }
.row { display: flex; align-items: center; gap: 2rem; padding: 1rem 0; border-bottom: 1px solid var(--edge); }
.row nav { display: flex; gap: 1.25rem; flex-wrap: wrap; }
.row nav a { color: var(--muted); }
.row nav a:hover { color: var(--accent); }
.scheme { margin-left: auto; display: inline-flex; padding: 0.25rem; border: 0; background: none; color: var(--muted); cursor: pointer; }
.scheme:hover { color: var(--accent); }
[data-theme="night"] .sun, [data-theme="day"] .moon { display: none; }
:root:not([data-theme]) .moon { display: none; }
.hero { padding: 3rem 0 1rem; }
.hero .v-title, .hero .v-meta, .hero .v-lead { margin: 0; }
.hero .v-meta { margin-top: 0.75rem; }
.hero .v-lead { margin-top: 1.5rem; }
.muted { color: var(--muted); }
p { margin: 0; max-width: var(--measure); }
p + p { margin-top: 0.9em; }
main > section { padding-top: 3rem; margin-top: 3rem; border-top: 1px solid var(--edge); }
main > section > .v-h2 { margin: 0 0 1rem; }
main > section > p + table, main > section > p + .three, main > section > table + p, main > section > .ex-row + p { margin-top: 1.25rem; }
.num { color: var(--muted); font-weight: 400; margin-right: 0.5rem; }
table { border-collapse: collapse; margin-top: 1.25rem; font-size: 0.86em; line-height: 1.45; width: 100%; }
th { font: 400 0.8125rem/1.5 var(--font-mono); color: var(--muted); text-align: left; padding: 0.4rem 0.75rem 0.4rem 0; border-bottom: 1px solid var(--body); vertical-align: bottom; }
td { padding: 0.55rem 0.75rem 0.55rem 0; border-bottom: 1px solid var(--edge); vertical-align: top; }
.nums td.v-num, .nums th:not(:first-child) { text-align: right; }
td.v-num { font-family: var(--font-mono); font-size: 0.92em; font-variant-numeric: tabular-nums; }
td.verdict { white-space: nowrap; color: var(--body); }
.three { display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: 2rem; margin-top: 1.5rem; }
.three .v-h3 { margin: 0 0 0.5rem; }
ul.plain { list-style: none; padding: 0; margin: 0; font-size: 0.88em; line-height: 1.5; }
ul.plain li + li { margin-top: 0.5rem; }
code { background: var(--ground-2); padding: 0.05em 0.35em; border-radius: 3px; }
.ex-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); gap: 1.5rem; margin-top: 1.5rem; align-items: start; }
.ex { margin: 0; min-width: 0; }
.ex figcaption { margin-bottom: 0.4rem; }
.entry { margin: 0; padding: 0.75rem 1rem; background: var(--ground-2); border-radius: var(--radius); font: 400 0.75rem/1.55 var(--font-mono); white-space: pre-wrap; overflow-wrap: anywhere; color: var(--body); }
.entry.bad { box-shadow: inset 2px 0 0 var(--accent-2); }
.entry.good { box-shadow: inset 2px 0 0 var(--accent); }
.v-h3.sub { margin: 2rem 0 0; }
.counts { display: flex; gap: 2.5rem; flex-wrap: wrap; margin-top: 1.25rem; }
.counts div { display: grid; }
.counts .big { font: 500 1.6rem/1.2 var(--font-mono); color: var(--strong); font-variant-numeric: tabular-nums; }
ul.quotes { list-style: none; padding: 0; margin: 0.75rem 0 0; max-width: 52rem; }
ul.quotes li { display: grid; grid-template-columns: 11rem 1fr; gap: 1rem; padding: 0.5rem 0; border-bottom: 1px solid var(--edge); font-size: 0.92em; }
ul.quotes q { quotes: none; }
.note { border-left: 2px solid var(--edge); padding-left: 1rem; margin-top: 1.5rem; max-width: var(--measure); }
.shape { margin-top: 2rem; max-width: 52rem; }
.shape .v-h3 { margin: 0 0 0.5rem; display: flex; gap: 0.6rem; align-items: baseline; flex-wrap: wrap; }
.shape .tag { padding: 0 0.6rem; border: 1px solid var(--edge); border-radius: 999px; color: var(--muted); }
.shape.rec .tag { border-color: var(--accent); color: var(--accent); }
.shape dl { display: grid; grid-template-columns: 7rem 1fr; gap: 0.4rem 1rem; margin: 0.75rem 0 0; font-size: 0.92em; }
.shape dt { padding-top: 0.2em; }
.shape dd { margin: 0; }
.rec-box { margin-top: 2rem; padding: 1.25rem 1.5rem; background: var(--wash); border-radius: var(--radius); max-width: 52rem; }
.rec-box .v-h3 { margin: 0 0 0.5rem; }
.rec-box ol { margin: 0.5rem 0 0; padding-left: 1.2em; }
.rec-box li + li { margin-top: 0.4rem; }
.rec-box ol + p { margin-top: 0.9em; }
.foot { padding: 4rem 0 3rem; }
@media (max-width: 52rem) { ul.quotes li { grid-template-columns: 1fr; gap: 0.2rem; } .shape dl { grid-template-columns: 1fr; } }
"""


def page() -> str:
    tokens = (HERE / "tokens.css").read_text()
    total_moments = len(GENERIC) + len(COINED) + len(MECHANISM) + len(HELPED)
    nav = "".join(f'<a href="#s{i}">{i}</a>' for i in range(1, 6))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The glossary format</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
{tokens}
{CSS}
</style>
</head>
<body>
<header class="page"><div class="row">
  <span class="v-h3">the glossary format</span>
  <nav class="v-small">{nav}</nav>
  <button class="scheme" id="scheme" aria-label="switch scheme">
    <svg class="sun" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
    <svg class="moon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>
  </button>
</div></header>

<main class="page">
<div class="hero">
  <h1 class="v-title">The glossary format: what it is, what it is for, what the glossaries show</h1>
  <p class="v-meta">mx domain-modelling · CONTEXT-FORMAT.md at mx v0.1.69 · 2026-09-22</p>
  <p class="v-lead muted">The CONTEXT.md format beside the upstream it came from, the seven glossaries built on it measured, the moments in session transcripts where vocabulary caused friction, and six shapes the format could take.</p>
</div>

<section id="s1">
  <h2 class="v-h2"><span class="num v-num">1</span>The format today, beside upstream</h2>
  <p>mx's format is Matt Pocock's with two rules rewritten after failures. Upstream had already dropped the sections that looked like cargo cult (Relationships, Flagged ambiguities, the example dialogue) before mx forked, so none of them came along. Every rule the format has is read only by the agent writing the entry; until this branch, no reviewer read a glossary diff.</p>
  {format_table()}
</section>

<section id="s2">
  <h2 class="v-h2"><span class="num v-num">2</span>What it is for</h2>
  <p>A glossary answers four questions, and the first two are asked far from the file: in a ticket, a commit, a UI string. That is why a term's name has to carry its meaning without the heading it sits under.</p>
  {questions()}
  <p>Where the mx skills and the global CLAUDE.md read, write and check it:</p>
  {points()}
</section>

<section id="s3">
  <h2 class="v-h2"><span class="num v-num">3</span>The glossaries, measured</h2>
  <p>Each entry is a bold term line, its definition, and an optional Avoid line. A code identifier is a backticked span, a snake_case word, a prefixed table name, a file path or an ADR number. Some of those name the term's code identifier, which is useful; section 5, B gives them their own line.</p>
  {measured()}
  <p>agents, soup and the work platform are tight. skilltree is where the rules failed at scale: its median entry is 67 words, and most entries describe a mechanism an ADR or the code already owns. The work architecture map is long but mostly passes.</p>
  <h3 class="v-h3 sub">Entries that work</h3>
  <div class="ex-row">{pairs(GOOD, "good")}</div>
  <h3 class="v-h3 sub">Entries that don't</h3>
  <div class="ex-row">{pairs(BAD, "bad")}</div>
  <h3 class="v-h3 sub">The work platform, before and after its review</h3>
  <div class="ex-row">
    <figure class="ex"><figcaption class="v-meta">before: a worker's two entries</figcaption>{entry(IMPORT_BEFORE, "bad")}</figure>
    <figure class="ex"><figcaption class="v-meta">after: the table predates the survey feature, and another importer writes it too</figcaption>{entry(IMPORT_AFTER, "good")}</figure>
  </div>
</section>

<section id="s4">
  <h2 class="v-h2"><span class="num v-num">4</span>What the transcripts show</h2>
  <p>mine.py read the user and assistant text of every session in the agents, skilltree, soup and dotfiles projects, and searched it for the glossary by name, for corrections of a word, and for “too generic” and its relatives. The keyword hits are mostly noise: pasted diffs, skill bodies, briefs that list CONTEXT.md among files to read. Reading the hits by hand left {total_moments} moments where a word caused friction. The work platform's sessions run under a separate account and are not in this store, except one.</p>
  <div class="counts">
    <div><span class="big">{T['sessions']}</span><span class="v-meta">sessions scanned</span></div>
    <div><span class="big">{T['glossary_edit_sessions']}</span><span class="v-meta">sessions that edited a CONTEXT.md</span></div>
    <div><span class="big">{sum(T['counts'].values())}</span><span class="v-meta">keyword hits</span></div>
    <div><span class="big">{total_moments}</span><span class="v-meta">real moments, read by hand</span></div>
  </div>
  <h3 class="v-h3 sub">A bare word that means too much: {len(GENERIC)}</h3>
  {quotes(GENERIC)}
  <h3 class="v-h3 sub">A coined word nobody needed: {len(COINED)}</h3>
  {quotes(COINED)}
  <h3 class="v-h3 sub">Mechanism in an entry, then drift: {len(MECHANISM)}</h3>
  {quotes(MECHANISM)}
  <h3 class="v-h3 sub">The glossary doing its job: {len(HELPED)}</h3>
  {quotes(HELPED)}
  <div class="note"><p class="v-small muted">Keyword search finds what was said in the words searched for; how much friction went unsaid, or was said differently, this cannot count. The first group is the one that recurs, across four repos and two months, and three of its seven are max asking the same question about the glossary itself.</p></div>
</section>

<section id="s5">
  <h2 class="v-h2"><span class="num v-num">5</span>Shapes it could take</h2>
  <p>Each shape is judged by the failures above it would have stopped and by who checks it. A rule a script checks holds; a rule a reviewer checks against a finished diff mostly holds; a rule only the writer reads is the one that already failed.</p>
  {shapes()}
  <div class="rec-box">
    <h3 class="v-h3">Recommendation</h3>
    <p>Keep the shape, which works where it is followed (agents, soup, the work platform). Make it hold where it is not:</p>
    <ol>
      <li>A, the qualifier rule, in CONTEXT-FORMAT.md. It covers the one failure that recurs.</li>
      <li>The reviewer check already on this branch, which reads A and the existing rules against every glossary diff.</li>
      <li>B and C together: the <code>_In code_</code> line and a lint script, run by domain-modelling after an edit and by code-review. It moves the length and mechanism rules to rung one and makes skilltree's debt visible.</li>
    </ol>
    <p>Pruning skilltree's glossary is its own ticket in that repo, once the lint exists to show what to cut.</p>
  </div>
</section>
</main>

<footer class="page foot">
  <p class="v-small muted">Built by build.py from measure.py and mine.py beside this file. Glossaries read at mx v0.1.69; the work platform's before its review.</p>
</footer>

<script>
  const root = document.documentElement
  const q = new URLSearchParams(location.search).get("theme")
  const night = q ? q === "night" : matchMedia("(prefers-color-scheme: dark)").matches
  root.dataset.theme = night ? "night" : "day"
  document.getElementById("scheme").addEventListener("click", () => {{
    root.dataset.theme = root.dataset.theme === "night" ? "day" : "night"
  }})
</script>
</body>
</html>
"""


if __name__ == "__main__":
    (HERE / "index.html").write_text(page())
    print(HERE / "index.html")
