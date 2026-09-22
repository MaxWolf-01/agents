#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
"""Writes index.html beside this file: the explainer for the board-orients prototype (v4).

The screenshots come from shots.sh; this script only lays out the page and draws the figure
of where each element on the board is read from.
"""

import html
from pathlib import Path

HERE = Path(__file__).parent

# ---- the figure: what the board reads, what it derives, where it shows ----
ROWS = [
    (("frontmatter", "priority · size · name"), None, ("row", "your time · priority · name"), ""),
    (("frontmatter", "status · type"), ("kind", "to rule on · your answer · design · build"), ("row", "the kind tag, and the row's group"), ""),
    (("## Brief", "a section of the ticket body"), None, ("row", "the brief line"), ""),
    (("comments", "I need from you [Dn] · Ruled: Dn"), ("open questions", "asked, less those ruled"), ("under the row", "each question, with copy"), ""),
    (("ticket branch", "ticket/<base>/<stem>: closing comment"), ("open questions", "of a build to rule on"), ("under the row", "the build's calls"), ""),
    (("git log, every branch", "Session: <id> trailers"), ("sessions", "first and last commit of each"), ("opened row", "sessions · copy resume"), ""),
    (("transcripts on this machine", "~/.claude/projects/*/<id>.jsonl"), ("title · directory", "no transcript here: left out"), ("opened row", "session titles"), ""),
    (("show directory", "agent/show/<ticket>/demo, figures"), None, ("opened row", "artefacts · copy path"), ""),
    (("diffview --serve", "agent/diffviews/<ticket>.html"), ("served address", "a page that takes comments"), ("row", "the review page link"), ""),
    (("frontmatter", "blocked-by · gh"), ("blockers · links", "blocked status · dependents"), ("row, groups, graph", "chips · blocked group · graph"), ""),
    (("everything above", ""), ("needs me", "to rule on · your answer · p1–p2 design"), ("side column", "brief · next · total time"), "accent"),
    (("fixture.yaml", "prototype only"), ("fills in", "priority · size · brief · name · why · asks"), ("real tickets", "until they carry the fields"), "dashed"),
]
COLS = [(20, 320), (400, 320), (780, 320)]
TOP, PITCH, H = 46, 56, 46


def box(x: int, w: int, y: int, name: str, detail: str, cls: str) -> str:
    esc = html.escape
    name_y = y + (20 if detail else 28)
    out = f'<g class="node {cls}"><rect x="{x}" y="{y}" width="{w}" height="{H}" rx="4"/>'
    out += f'<text class="name" x="{x + 12}" y="{name_y}">{esc(name)}</text>'
    if detail:
        out += f'<text class="detail" x="{x + 12}" y="{y + 34}">{esc(detail)}</text>'
    return out + "</g>"


def figure() -> str:
    parts = [
        '<text class="head" x="20" y="24">read from</text>',
        '<text class="head" x="400" y="24">derived</text>',
        '<text class="head" x="780" y="24">on the board</text>',
    ]
    for i, (src, mid, dst, cls) in enumerate(ROWS):
        y = TOP + i * PITCH
        mid_y = y + H // 2
        edge_cls = cls if cls == "dashed" else ""  # the accent marks the derived box alone
        parts.append(box(*COLS[0], y, *src, edge_cls))
        if mid:
            parts.append(box(*COLS[1], y, *mid, cls))
            parts.append(f'<line class="{edge_cls}" x1="340" y1="{mid_y}" x2="398" y2="{mid_y}" marker-end="url(#ah)"/>')
            parts.append(f'<line class="{edge_cls}" x1="720" y1="{mid_y}" x2="778" y2="{mid_y}" marker-end="url(#ah)"/>')
        else:
            parts.append(f'<line x1="340" y1="{mid_y}" x2="778" y2="{mid_y}" marker-end="url(#ah)"/>')
            parts.append(f'<text class="asis" x="560" y="{mid_y - 5}">as written</text>')
        parts.append(box(*COLS[2], y, *dst, edge_cls))
    height = TOP + len(ROWS) * PITCH
    return (
        f'<svg class="flow" viewBox="0 0 1120 {height}" role="img" aria-label="Twelve sources the board reads, what it derives from '
        f'each, and the part of the board each lands in.">'
        '<defs><marker id="ah" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="7" markerHeight="7" orient="auto">'
        '<path d="M0,0 L8,4 L0,8 z" fill="currentColor"/></marker></defs>' + "".join(parts) + "</svg>"
    )


# ---- annotated screenshots: marker positions in the crop's own pixels ----
TOP_SHOT = (1600, 700, [
    (1, 125, 89), (2, 196, 112), (3, 318, 237), (4, 318, 287), (5, 853, 208), (6, 907, 208), (7, 1033, 208),
    (8, 975, 318), (9, 1100, 85), (10, 1100, 184), (11, 1100, 364), (12, 240, 52), (13, 1150, 52), (14, 1380, 52),
])
OPEN_SHOT = (1060, 2140, [
    ("a", 316, 98), ("b", 316, 140), ("c", 316, 185), ("d", 316, 281), ("e", 316, 728),
    ("f", 316, 1267), ("g", 316, 1366), ("h", 316, 1462), ("i", 316, 1668),
])


def shot(name: str, spec: tuple, alt: str) -> str:
    w, h, marks = spec
    dots = "".join(f'<span class="mk" style="left:{x / w * 100:.2f}%;top:{y / h * 100:.2f}%">{n}</span>' for n, x, y in marks)
    return (f'<div class="shot"><img class="day" src="shots/{name}-day.png" alt="{html.escape(alt)}">'
            f'<img class="night" src="shots/{name}-night.png" alt="{html.escape(alt)}">{dots}</div>')


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The board, prototype v4</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400;1,6..72,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="tokens.css">
<script>
  (() => {
    const q = new URLSearchParams(location.search).get("theme");
    const night = q ? q === "night" : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = night ? "night" : "day";
  })();
</script>
<style>
  * { box-sizing: border-box; }
  :root {
    --c-teal: light-dark(#1d6f69, #74d0c8); --c-gold: light-dark(#7d5f16, #d9b36f);
    --c-rose: light-dark(#a3453c, #fabeb4); --c-purple: light-dark(#6546b3, #b8a4ff);
  }
  p { margin: 0; }
  .page { max-width: var(--page); margin: 0 auto; padding: 0 2rem; }
  .measure { max-width: var(--measure); }
  header.row { display: flex; align-items: center; gap: 1.5rem; padding: 1rem 0; border-bottom: 1px solid var(--edge); }
  header .v-h3 { margin: 0; }
  .scheme { margin-left: auto; display: inline-flex; padding: .25rem; border: 0; background: none; color: var(--muted); cursor: pointer; transition: color 150ms; }
  .scheme:hover { color: var(--accent); }
  [data-theme="night"] .sun, [data-theme="day"] .moon { display: none; }
  .hero { padding: 3.5rem 0 1rem; }
  .hero .v-title { margin: 0; }
  .hero .v-meta { margin-top: .75rem; }
  .hero .v-lead { margin-top: 1.75rem; color: var(--muted); }
  main > section { margin-top: 4rem; }
  .divider { display: flex; align-items: center; gap: .75rem; margin-bottom: 1.5rem; }
  .divider::after { content: ""; flex: 1; height: 1px; background: var(--edge); }
  section > p + p, section > p + .links { margin-top: 1rem; }
  .links { display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: .92em; }
  .links a { color: var(--accent); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px;
    text-decoration-color: color-mix(in srgb, var(--accent) 40%, transparent); }
  code { background: var(--ground-2); padding: .08em .3em; border-radius: 3px; }

  figure { margin: 1.75rem 0 0; }
  figcaption { margin-top: .75rem; color: var(--muted); font-size: .92em; max-width: var(--measure); }
  .shot { position: relative; border: 1px solid var(--edge); border-radius: var(--radius); overflow: hidden; }
  .shot img { display: block; width: 100%; height: auto; }
  [data-theme="night"] .shot .day, [data-theme="day"] .shot .night { display: none; }
  .mk { position: absolute; transform: translate(-50%, -50%); width: 1.35rem; height: 1.35rem; border-radius: 50%;
    background: var(--accent); color: var(--ground); font: 500 .7rem/1.35rem var(--font-mono); text-align: center; }
  .narrow { max-width: 44rem; }

  ol.legend { list-style: none; margin: 1.5rem 0 0; padding: 0; display: grid; gap: .55rem; max-width: var(--measure); }
  ol.legend li { display: grid; grid-template-columns: 2rem 1fr; }
  ol.legend .n { font-family: var(--font-mono); font-size: .8rem; color: var(--accent); padding-top: .2rem; }

  svg.flow { width: 100%; height: auto; color: var(--muted); }
  svg.flow g.node rect { fill: var(--ground); stroke: var(--edge); }
  svg.flow .name { fill: var(--strong); font-family: var(--font-body); font-size: 14px; }
  svg.flow .detail { fill: var(--muted); font-family: var(--font-mono); font-size: 11px; }
  svg.flow .head, svg.flow .asis { fill: var(--muted); font-family: var(--font-mono); font-size: 11px; }
  svg.flow .asis { text-anchor: middle; font-size: 10px; }
  svg.flow line { stroke: currentColor; stroke-width: 1; }
  svg.flow g.node.accent rect { stroke: var(--accent); fill: var(--wash); }
  svg.flow g.node.dashed rect, svg.flow line.dashed { stroke-dasharray: 4 3; }

  ol.steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 1rem; max-width: var(--measure); }
  ol.steps li { display: grid; grid-template-columns: 2rem 1fr; }
  ol.steps .n { font-family: var(--font-mono); font-size: .9rem; color: var(--muted); padding-top: .15rem; }

  .note { border-left: 2px solid var(--c-purple); padding: .2rem 0 .2rem 1.2rem; max-width: var(--measure); }
  .note .v-meta { color: var(--c-purple); margin-bottom: .6rem; }
  .note ul { margin: 0; padding-left: 1.1em; display: grid; gap: .55rem; }
  .note li::marker { color: var(--muted); }

  table { border-collapse: collapse; width: 100%; font-size: .92em; }
  th { text-align: left; font: 400 .8125rem/1.5 var(--font-mono); color: var(--muted); padding: 0 1rem .5rem 0; border-bottom: 1px solid var(--edge); }
  td { padding: .6rem 1rem .6rem 0; border-bottom: 1px solid var(--edge); vertical-align: top; }
  td:first-child { width: 15rem; color: var(--strong); }
  td.state { width: 6rem; font-family: var(--font-mono); font-size: .8rem; white-space: nowrap; }
  .done { color: var(--c-teal); } .partly { color: var(--c-gold); } .not { color: var(--c-rose); } .prop { color: var(--c-purple); }
  tr.group td { border-bottom: 0; padding-top: 1.75rem; font: 400 .8125rem/1.5 var(--font-mono); color: var(--muted); }
  td .muted, .muted { color: var(--muted); }

  ul.wrong { margin: 0; padding-left: 1.1em; display: grid; gap: .6rem; max-width: var(--measure); }
  ul.wrong li::marker { color: var(--muted); }
  footer { padding: 5rem 0 4rem; }
</style>
</head>
<body>
<header class="row page">
  <span class="v-h3">board-orients</span>
  <button class="scheme" id="scheme" title="switch colour scheme">
    <svg class="sun" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
    <svg class="moon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>
  </button>
</header>
<main class="page">
  <section class="hero">
    <h1 class="v-title">The board, prototype v4</h1>
    <p class="v-meta">23 september 2026 · branch board-orients · a prototype, not the build</p>
    <p class="v-lead measure">What each mark on the board is and where the board reads it, how the brief picks what comes next, the proposal for what "needs me" holds, and what is done, partly done or still open.</p>
  </section>

  <section>
    <p class="divider v-meta">the board, on a demo tracker</p>
    <p class="measure">A tracker for a made-up bookkeeping tool, built so every element appears: two features, a standalone ticket of each decision type, two builds waiting for a ruling, a ticket stopped on a question, and sessions recorded in its commits.</p>
    <p class="links"><a href="file:///var/tmp/board-orients-demo/board.html">open the demo board</a><span class="muted">rebuild it with <code>bash /var/tmp/board-orients-demo/build.sh</code></span></p>
    <figure>
      {{TOP_SHOT}}
      <figcaption>The top of the demo board. The page follows your colour scheme; the switch at the top right of this page swaps the screenshot too.</figcaption>
    </figure>
    <ol class="legend">
      <li><span class="n">1</span><span>The <strong>needs me</strong> group: builds to rule on, tickets stopped on your answer, design sessions at p1 or p2. Below it: frontier, claimed, blocked, proposed, done.</span></li>
      <li><span class="n">2</span><span>What the row asks of you, always in this column: <em>to rule on</em>, <em>your answer</em>, <em>design session</em>, <em>prototype</em>, <em>research</em>, <em>legwork</em>, or a plain <em>build</em>. Hovering says what each means.</span></li>
      <li><span class="n">3</span><span>The short name, then the review page (green, one link per row) and any GitHub references.</span></li>
      <li><span class="n">4</span><span>The brief: the ticket's <code>## Brief</code>, one line, in full once the row is open.</span></li>
      <li><span class="n">5</span><span>Your time on the ticket, not the agent's: reading, trying the demo, deciding.</span></li>
      <li><span class="n">6</span><span>Priority, the agent's reading: p1 now, p2 next, p3 soon, p4 later, p5 someday. The tooltip says so.</span></li>
      <li><span class="n">7</span><span>What the ticket waits on; a struck-through number is done.</span></li>
      <li><span class="n">8</span><span>The open questions, under the ticket they belong to. <em>copy</em> puts the tag, the ticket's path and the question on the clipboard, to answer in any session.</span></li>
      <li><span class="n">9</span><span>The brief of the whole board: what waits on you, what is running.</span></li>
      <li><span class="n">10</span><span>Next: three picks, with the reason each is picked.</span></li>
      <li><span class="n">11</span><span>The dependency graph: the whole tracker until you move onto a row, then that row's feature.</span></li>
      <li><span class="n">12</span><span>Feature filters, a count of done over all tickets on each.</span></li>
      <li><span class="n">13</span><span>A filter box, the <code>/</code> key.</span></li>
      <li><span class="n">14</span><span>The graph switch, then keys help and the colour scheme.</span></li>
    </ol>
  </section>

  <section>
    <p class="divider v-meta">two rows, opened</p>
    <p class="measure">The ticket stopped on a question, and a build waiting for your ruling.</p>
    <figure class="narrow">
      {{OPEN_SHOT}}
    </figure>
    <ol class="legend">
      <li><span class="n">a</span><span>The one question still open: D2 was answered, so only D1 shows.</span></li>
      <li><span class="n">b</span><span>The ticket's full title, under the short name.</span></li>
      <li><span class="n">c</span><span>Each question in full, with the reasoning the row line leaves out.</span></li>
      <li><span class="n">d</span><span>The sessions that changed this ticket, newest first, each with its title and a command that resumes it.</span></li>
      <li><span class="n">e</span><span>The line that cleared D2: <code>Ruled: D2</code>, written by the session that passed your answer on.</span></li>
      <li><span class="n">f</span><span>Two sessions here, not three: the worker that built this ran on another machine, so it is left out.</span></li>
      <li><span class="n">g</span><span>The demo's path, with a copy button, and the figures in the ticket's show directory.</span></li>
      <li><span class="n">h</span><span>The ticket text, read from its branch while the build waits for your ruling.</span></li>
      <li><span class="n">i</span><span>The worker's closing comment, which lives on that branch until the build merges.</span></li>
    </ol>
  </section>

  <section>
    <p class="divider v-meta">where each element comes from</p>
    <p class="measure">Every mark is read from a file or from git; nothing is typed into the board. The last row is the prototype's stand-in: your real tickets carry no priority, size or brief yet, so <code>fixture.yaml</code> supplies them.</p>
    <figure>
      {{FIGURE}}
    </figure>
  </section>

  <section>
    <p class="divider v-meta">how the brief and next are made</p>
    <ol class="steps">
      <li><span class="n">1</span><span>A ticket waits on you when it is a build to rule on (status <code>review</code>), when questions under its last "I need from you" are still open after its <code>Ruled:</code> lines, or when it is a design session or prototype at p1 or p2 that nobody has started.</span></li>
      <li><span class="n">2</span><span>The brief counts those: builds to rule on, design sessions, tickets stopped on an answer, then the builds in progress.</span></li>
      <li><span class="n">3</span><span>The total adds up your time on every waiting ticket: XS 10 min, S 20, M 60, L 240, XL 480.</span></li>
      <li><span class="n">4</span><span>Next orders the waiting tickets by priority. Within one priority, a ticket with a reason goes first, then the one that takes least of your time. The top three show.</span></li>
      <li><span class="n">5</span><span>The reason under a pick: "the last open ticket of a feature: accepting it lets the feature merge", else "N tickets wait on it", else none. In the prototype a <code>why</code> in the fixture overrides both.</span></li>
    </ol>
  </section>

  <section>
    <p class="divider v-meta">needs me: a proposal</p>
    <div class="note">
      <p class="v-meta">waiting for your word</p>
      <ul>
        <li><code>review</code> stays a ticket status: a build that waits for your ruling.</li>
        <li>The board's separate "needs my review" group goes. One <strong>needs me</strong> group holds builds to rule on, tickets stopped on your answer, and design sessions at p1 or p2.</li>
        <li>Every question belongs to a ticket: a build's questions sit in its closing comment, a question that stops a ticket sits in that ticket's comments. <code>needs-human.md</code> retires. A question with no ticket to hang on becomes a proposed ticket, and your ruling on it is the answer.</li>
        <li>An answer clears when the session that passes it on writes <code>Ruled: D2</code> into the ticket.</li>
        <li>You said this would make sense. Nothing in the skills changes until you rule.</li>
      </ul>
    </div>
  </section>

  <section>
    <p class="divider v-meta">done, partly, not yet</p>
    <table>
      <thead><tr><th>item</th><th>state</th><th>in the prototype, and what is missing</th></tr></thead>
      <tbody>
        <tr class="group"><td colspan="3">the five tickets folded into this feature</td></tr>
        <tr><td>priority-and-size</td><td class="state partly">partly</td><td>Read from frontmatter, shown with words and colours, and sorted by; size is your time. Missing: the fields in the tracker skill and the glossary; nothing sets them on real tickets, so the fixture does.</td></tr>
        <tr><td>ticket-brief-and-artefacts</td><td class="state partly">partly</td><td>The <code>## Brief</code> shows under the name; the show directory's files and the demo path show on the opened row. Missing: which skill writes the brief, and the short <code>name</code> field is undecided.</td></tr>
        <tr><td>board-carries-what-needs-you</td><td class="state partly">partly</td><td>One needs-me group, questions under their ticket, copy buttons, clearing through <code>Ruled:</code>. Missing: your ruling on the proposal above, and the skill edits it implies.</td></tr>
        <tr><td>ticket-sessions</td><td class="state partly">partly</td><td>Sessions from <code>Session:</code> trailers on every branch, titles and directories from transcripts, other machines left out, copy resume. Missing: nothing writes the trailer yet; the git hook is not installed, so your real tickets fall back to a scan of transcripts.</td></tr>
        <tr><td>gh-live-state</td><td class="state not">not yet</td><td>GitHub references link out; whether a PR is open, merged or has changes requested is not fetched.</td></tr>
        <tr class="group"><td colspan="3">your rulings in this session</td></tr>
        <tr><td>size is your time</td><td class="state done">done</td><td>The sizes and the tooltip say so.</td></tr>
        <tr><td>priority is the agent's call</td><td class="state partly">partly</td><td>Shown as the agent's reading, with p1 to p5 explained. No agent writes it yet.</td></tr>
        <tr><td>no input box; copy buttons</td><td class="state done">done</td><td>Each question copies with its tag and the ticket's path.</td></tr>
        <tr><td>sessions from commit trailers</td><td class="state partly">partly</td><td>The board reads them. The hook that writes them is not built.</td></tr>
        <tr><td>titles from transcripts</td><td class="state done">done</td><td>Your <code>/rename</code> name, else Claude Code's own title.</td></tr>
        <tr><td>one page, not two</td><td class="state done">done</td><td>The separate briefing page is gone; the brief lives in the board's side column.</td></tr>
        <tr><td>one review link per row</td><td class="state done">done</td><td>The row keeps "review page"; the opened row no longer repeats it.</td></tr>
        <tr><td>colours and distinct marks</td><td class="state done">done</td><td>Kind, time and priority each in their own column and colour, from your site's callouts.</td></tr>
        <tr><td>tooltips that explain</td><td class="state done">done</td><td>Priority, time, each kind and each copy button say what they mean.</td></tr>
        <tr><td>every question on a ticket</td><td class="state prop">proposal</td><td>See above.</td></tr>
        <tr class="group"><td colspan="3">still open</td></tr>
        <tr><td>the spec</td><td class="state not">not yet</td><td>No <code>spec.md</code> for board-orients; the decisions live in this conversation and this page.</td></tr>
        <tr><td>short names and themes</td><td class="state not">not yet</td><td>Whether a ticket gets a short <code>name</code>, and whether standalone tickets get themes, is undecided.</td></tr>
        <tr><td>workflow edits</td><td class="state not">not yet</td><td>The tracker skill (priority, size, brief, <code>Ruled:</code>, no queue file), dispatch writing <code>Ruled:</code> when it relays an answer, the worker prompt.</td></tr>
        <tr><td>the build</td><td class="state not">not yet</td><td>All of this is in <code>agent/prototypes/board-orients/board.py</code>; the real <code>board.py</code> is unchanged.</td></tr>
      </tbody>
    </table>
  </section>

  <section>
    <p class="divider v-meta">what the demo found in the prototype</p>
    <ul class="wrong">
      <li>Open: the whole-tracker graph is too small to read in the side column once a tracker has more than a few edges.</li>
      <li>Fixed since: the brief's sentence counts a ticket stopped on a question read from its file; an opened build in review shows its branch's text, closing comment included; the brief shows once; the full title renders its markdown; a cross-feature blocker keeps to one line; a GitHub reference stays on the name's line; a feature's ticket branch is read as <code>ticket/&lt;feature&gt;/&lt;NN-slug&gt;</code>, as dispatch names it.</li>
    </ul>
  </section>
</main>
<footer class="page v-meta">
  sources: page.py writes this page · shots.sh regenerates the screenshots · /var/tmp/board-orients-demo/build.sh builds the demo tracker · the prototype is agent/prototypes/board-orients/board.py
</footer>
<script>
  document.getElementById("scheme").addEventListener("click", () => {
    const root = document.documentElement;
    root.dataset.theme = root.dataset.theme === "night" ? "day" : "night";
  });
</script>
</body>
</html>
"""


if __name__ == "__main__":
    page = (PAGE.replace("{{TOP_SHOT}}", shot("top", TOP_SHOT, "The top of the demo board: the needs me group and the side column"))
                .replace("{{OPEN_SHOT}}", shot("open", OPEN_SHOT, "Two rows of the demo board, opened"))
                .replace("{{FIGURE}}", figure()))
    (HERE / "index.html").write_text(page)
    print(HERE / "index.html")
