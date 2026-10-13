#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Render a blind test from a pairs file: `index.html`, written beside the file, its path printed.

A blind test puts one decision between two options to the reader as pairs of samples, each pair the
same thing made under both options. The page shows every pair as a row of two cells, the sides
shuffled per row on each load and unlabelled. The reader clicks the cell they prefer in any row, or
leaves a row alone where they can't tell. Reveal labels every cell and shows the tally, the options,
the agent's pick and its why, and one answer line to paste back into the session, naming each row's
pick by its ref:

    Q7 blind: b 4/6 (2e7b14df 997135b9 aa054bd4 24eaab5b), a 1/6 (23e91ec6), unpicked 1/6 (84c94f65)

The pairs file is JSON. `options` are short names for the two sides, `ref` names a pair in the
answer line (its row number where it has none), and every pair holds both sides:

    {"question": "Q7", "title": "Commit subject style",
     "options": {"a": "outcome-phrased", "b": "conventional commits"},
     "pick": "a", "why": "...",
     "pairs": [{"ref": "2e7b14df", "a": "...", "b": "..."}, ...]}

Exits 1, naming every problem, on a file that lacks a field, offers sides other than a and b, picks
neither, or holds a pair without both sides.

Examples:

    blind-test agent/show/commit-style/blind/pairs.json
"""

import html
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import tyro

HERE = Path(__file__).resolve().parent
TOKENS = HERE.parent / "house-style" / "tokens.css"
FIELDS = ("question", "title", "options", "pick", "why", "pairs")


@dataclass
class Args:
    pairs: tyro.conf.Positional[Path]
    """The pairs file, JSON in the shape above."""
    session: str = os.environ.get("MX_ORIGIN_SESSION") or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    """The session the page names, which its resume button copies; none where empty."""


def main(args: Args) -> None:
    try:
        data = json.loads(args.pairs.read_text())
    except (OSError, ValueError) as e:
        sys.exit(f"{args.pairs}: {e}")
    if problems := check(data):
        sys.exit(f"{args.pairs}: " + "; ".join(problems))
    out = args.pairs.resolve().parent / "index.html"
    out.write_text(page(data, args.session))
    print(out)


def check(data: object) -> list[str]:
    """What keeps `data` from being a pairs file; empty where nothing does."""
    if not isinstance(data, dict):
        return ["the file holds a JSON object"]
    if missing := [f"no {key!r}" for key in FIELDS if key not in data]:
        return missing
    problems = []
    options, pairs = data["options"], data["pairs"]
    if not isinstance(options, dict) or set(options) != {"a", "b"}:
        problems.append("options holds exactly a and b")
    if data["pick"] not in ("a", "b"):
        problems.append("pick is a or b")
    if not isinstance(pairs, list) or not pairs:
        problems.append("pairs is a list of at least one pair")
    else:
        problems += [f"pair {i} lacks a or b" for i, p in enumerate(pairs, 1)
                     if not (isinstance(p, dict) and p.get("a") and p.get("b"))]
    return problems


def page(data: dict, session: str) -> str:
    title = html.escape(f"{data['question']} · {data['title']}")
    meta = (f' · session <button class="session" id="session" data-copy="claude --resume {html.escape(session)}" '
            f'title="copy the resume command">{html.escape(session[:8])}</button>') if session else ""
    # JSON inside a <script>: a `</` in a sample would otherwise close the element early.
    embedded = json.dumps(data).replace("</", "<\\/")
    return (TEMPLATE.replace("{{TOKENS}}", TOKENS.read_text()).replace("{{TITLE}}", title)
            .replace("{{META}}", meta).replace("{{DATA}}", embedded))


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}} · blind test</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400;1,6..72,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<script>
  (() => {
    const t = new URLSearchParams(location.search).get("theme")
    const night = t ? t === "night" : matchMedia("(prefers-color-scheme: dark)").matches
    document.documentElement.dataset.theme = night ? "night" : "day"
  })()
</script>
<style>
{{TOKENS}}
  [hidden] { display: none !important; }
  .page { max-width: var(--page); margin: 0 auto; padding: 0 2rem 5rem; }
  .bar { display: flex; align-items: center; padding: 1rem 0; border-bottom: 1px solid var(--edge); }
  .scheme { margin-left: auto; display: inline-flex; padding: 0.25rem; border: 0; background: none; color: var(--muted); cursor: pointer; transition: color 150ms; }
  .scheme:hover { color: var(--accent); }
  [data-theme="night"] .sun, [data-theme="day"] .moon { display: none; }
  .session { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer; text-decoration: underline dotted; }
  .session:hover { color: var(--accent); }
  h1.v-title { margin: 3rem 0 0; }
  .lead { color: var(--muted); max-width: var(--measure); margin: 1rem 0 0; }

  .rows { margin-top: 2.5rem; }
  .row { display: grid; grid-template-columns: 5.5rem 1fr 1fr; gap: 1rem; align-items: stretch; padding: 0.6rem 0; }
  .row + .row { border-top: 1px solid var(--edge); }
  .ref { padding-top: 0.85rem; overflow-wrap: anywhere; }
  .cell { font: inherit; color: inherit; text-align: left; background: none; border: 1px solid transparent; border-radius: var(--radius); padding: 0.7rem 0.9rem; cursor: pointer; white-space: pre-wrap; transition: color 150ms, border-color 150ms, background-color 150ms, opacity 150ms; }
  .cell:hover { border-color: var(--edge); }
  .cell.chosen { border-color: var(--accent); background: var(--wash); color: var(--strong); }
  .cell.passed { opacity: 0.42; }
  .cell .label { display: block; margin-top: 0.35rem; white-space: normal; }
  .cell .label.mine { color: var(--accent); }
  .revealed .cell { cursor: default; }
  .revealed .cell:hover { border-color: transparent; }
  .revealed .cell.chosen:hover { border-color: var(--accent); }

  .button { font: 500 0.95rem / 1 var(--font-body); padding: 0.6rem 1.1rem; border-radius: var(--radius); cursor: pointer; transition: color 150ms, background-color 150ms, border-color 150ms; }
  .solid { background: var(--accent); color: var(--ground); border: 1px solid var(--accent); }
  .solid:hover { background: color-mix(in srgb, var(--accent) 85%, var(--strong)); }
  .quiet { background: none; color: var(--body); border: 1px solid var(--edge); }
  .quiet:hover { color: var(--accent); border-color: var(--accent); }
  .actions { margin-top: 2rem; }

  .reveal { margin-top: 2.5rem; border-top: 1px solid var(--edge); padding-top: 2rem; max-width: var(--measure); }
  .tally { color: var(--strong); margin: 0; }
  .options { list-style: none; padding: 0; margin: 1.5rem 0 0; }
  .options li + li { margin-top: 0.35rem; }
  .options .k { display: inline-block; width: 1.5rem; }
  .why { color: var(--muted); margin: 1rem 0 0; }
  .answer { display: flex; align-items: center; gap: 0.75rem; margin-top: 1.75rem; flex-wrap: wrap; }
  .answer code { background: var(--ground-2); border: 1px solid var(--edge); border-radius: var(--radius); padding: 0.45rem 0.7rem; color: var(--strong); }

  @media (max-width: 40rem) {
    .row { grid-template-columns: 1fr; gap: 0.4rem; }
    .ref { padding-top: 0; }
  }
</style>
</head>
<body>
<div class="page">
  <header class="bar">
    <span class="v-meta">blind test{{META}}</span>
    <button class="scheme" id="scheme" aria-label="switch to night">
      <svg class="sun" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      <svg class="moon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>
    </button>
  </header>
  <h1 class="v-title">{{TITLE}}</h1>
  <p class="lead">Each row is the same thing made two ways. Click the one you prefer, or leave the row alone if you can't tell.</p>
  <div class="rows" id="rows"></div>
  <div class="actions"><button class="button solid" id="reveal-button">reveal</button></div>
  <section class="reveal" id="reveal" hidden>
    <p class="tally" id="tally"></p>
    <ul class="options" id="options"></ul>
    <p class="why" id="why"></p>
    <div class="answer"><code id="answer"></code><button class="button quiet" id="copy">copy</button></div>
  </section>
</div>
<script>
const DATA = {{DATA}}
const root = document.documentElement
const $ = (id) => document.getElementById(id)

const scheme = $("scheme")
const setTheme = (night) => {
  root.dataset.theme = night ? "night" : "day"
  scheme.setAttribute("aria-label", night ? "switch to day" : "switch to night")
}
scheme.addEventListener("click", () => setTheme(root.dataset.theme !== "night"))
setTheme(root.dataset.theme === "night")

const copy = async (text) => {
  try { await navigator.clipboard.writeText(text) }
  catch {
    const ta = Object.assign(document.createElement("textarea"), { value: text })
    document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove()
  }
}
const session = $("session")
if (session) session.addEventListener("click", () => copy(session.dataset.copy))

// Each row: its name in the answer line, its two sides in a random order, and the side the reader chose (null for none).
const rows = DATA.pairs.map((p, i) => ({ ...p, name: p.ref || String(i + 1), order: Math.random() < 0.5 ? ["a", "b"] : ["b", "a"], chose: null }))
let revealed = false

const paint = (r) => r.cells.forEach((c) => {
  const side = c.dataset.side
  c.classList.toggle("chosen", r.chose === side)
  c.classList.toggle("passed", r.chose !== null && r.chose !== side)
  c.setAttribute("aria-pressed", r.chose === side)
})

const rowsEl = $("rows")
rows.forEach((r) => {
  const row = document.createElement("div")
  row.className = "row"
  const ref = document.createElement("span")
  ref.className = "v-meta ref"
  ref.textContent = r.name
  row.append(ref)
  r.cells = r.order.map((side) => {
    const cell = document.createElement("button")
    cell.className = "cell"
    cell.type = "button"
    cell.dataset.side = side
    const text = document.createElement("span")
    text.textContent = r[side]
    const label = document.createElement("span")
    label.className = "v-meta label"
    label.hidden = true
    cell.append(text, label)
    cell.addEventListener("click", () => {
      if (revealed) return
      r.chose = r.chose === side ? null : side
      paint(r)
    })
    row.append(cell)
    return cell
  })
  paint(r)
  rowsEl.append(row)
})

$("reveal-button").addEventListener("click", () => {
  revealed = true
  rowsEl.classList.add("revealed")
  $("reveal-button").hidden = true
  rows.forEach((r) => r.cells.forEach((c) => {
    const side = c.dataset.side, label = c.querySelector(".label")
    label.textContent = `${side} · ${DATA.options[side]}`
    label.classList.toggle("mine", r.chose === side)
    label.hidden = false
    c.disabled = true
  }))

  const n = rows.length
  const count = { a: 0, b: 0 }
  rows.forEach((r) => { if (r.chose) count[r.chose]++ })
  const unpicked = n - count.a - count.b
  const top = count.b > count.a ? "b" : "a", other = top === "a" ? "b" : "a"

  const rowsOf = (k) => `${k} row${k === 1 ? "" : "s"}`
  let tally = `You picked ${top} in ${rowsOf(count[top])} of ${n}`
  if (count[other]) tally += `, ${other} in ${rowsOf(count[other])}`
  if (unpicked) tally += `, and left ${rowsOf(unpicked)} unpicked`
  $("tally").textContent = tally + "."

  for (const side of ["a", "b"]) {
    const li = document.createElement("li")
    const k = Object.assign(document.createElement("span"), { className: "v-meta k", textContent: side })
    li.append(k, DATA.options[side])
    if (DATA.pick === side) li.append(Object.assign(document.createElement("span"), { className: "v-meta", textContent: " · my pick" }))
    $("options").append(li)
  }
  $("why").textContent = `Why ${DATA.pick}: ${DATA.why}`

  // One line, so it pastes into a prompt intact, each group's rows in the pairs file's order.
  const names = (chose) => rows.filter((r) => r.chose === chose).map((r) => r.name).join(" ")
  const groups = [top, other].filter((side) => count[side]).map((side) => `${side} ${count[side]}/${n} (${names(side)})`)
  if (unpicked) groups.push(`unpicked ${unpicked}/${n} (${names(null)})`)
  $("answer").textContent = `${DATA.question} blind: ${groups.join(", ")}`

  $("reveal").hidden = false
  $("reveal").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" })
})

$("copy").addEventListener("click", async () => {
  await copy($("answer").textContent)
  $("copy").textContent = "copied"
  setTimeout(() => ($("copy").textContent = "copy"), 1600)
})
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
