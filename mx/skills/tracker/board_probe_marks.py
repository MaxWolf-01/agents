# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
"""What the page says of itself once a browser runs it: which scheme it painted, whether the anchor
opened a row, whether the graph beside it came back, whether the briefing is set as prose and says
what it is, and what each mark shows on hover, a copy button's account of what it copies among them.
The side column's own hints are `title` attributes, as the graph's buttons are: a box that scrolls
cuts a tooltip drawn inside it, and that column is the one box on the page that scrolls. A
pseudo-element has no rect of its own, so a tooltip's box is its host's plus the offsets the element
resolves; `clipped` is the ancestor that would hide it, which is how two marks came to carry words
no reader could see."""

import json, os, shutil, sys
from pathlib import Path
from playwright.sync_api import TimeoutError, sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "show"))  # page_cache, beside render_lint
from board_probe_engine import cdn
from page_cache import default_root, serve

page_url = Path(sys.argv[1]).resolve().as_uri()
width, marks = int(sys.argv[2]), sys.argv[3].split(",")
ROW, FOLDED = sys.argv[4].split(",")
TIP = """
(mark) => {
  const el = document.querySelector(mark)
  if (!el) return {missing: true}
  const tip = getComputedStyle(el, "::after")
  // an absolutely positioned box is laid out from the padding box of its nearest positioned
  // ancestor, which is the row, not the mark
  let cb = el
  while (cb.parentElement && getComputedStyle(cb).position === "static") cb = cb.parentElement
  const base = cb.getBoundingClientRect()
  const [w, h] = [parseFloat(tip.width), parseFloat(tip.height)]
  const left = tip.left === "auto" ? base.right - w - parseFloat(tip.right) : base.left + parseFloat(tip.left)
  // what could clip the tip: its containing block and everything under it, up to the first
  // positioned ancestor, which is where an absolutely positioned box is laid out from
  let clipped = null
  for (let a = el; a; a = a.parentElement) {
    if (getComputedStyle(a).overflow !== "visible") clipped = a.className
    if (a !== el && getComputedStyle(a).position !== "static") break
  }
  return {words: tip.content, w, h, left, right: left + w, clipped, viewport: innerWidth}
}
"""
with sync_playwright() as pw:
    # the run it belongs to, as `browsers --help` defines it
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    # the clipboard is what a copy button is for, and a page reaches it only where it is granted
    context = browser.new_context(viewport={"width": width, "height": 1000},
                                  permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    serve(context, default_root())
    failed = []
    page.on("requestfailed", lambda r: failed.append((r.url, r.failure)))
    out = {"schemes": {}, "tips": {}}
    for scheme in ("day", "night"):
        page.goto(f"{page_url}?theme={scheme}#{ROW}")
        page.evaluate("document.fonts.ready")
        out["schemes"][scheme] = page.evaluate("getComputedStyle(document.body).backgroundColor")
    # the row the anchor opened asks for its graph, which is when the engine is fetched: by the end
    # of the wait it has drawn, or the panel says it could not load
    try:
        page.wait_for_selector(".side .mermaid svg, #gunloaded:not([hidden])", timeout=10_000)
    except TimeoutError:
        pass  # counted as no graph below
    out["cdn"] = cdn(failed)

    def toasts() -> int:
        return page.evaluate("+(document.getElementById('toast').dataset.said ?? 0)")

    def after(settled: str) -> None:
        """Wait until the page says what a click started is done: a toast shown, a drawing settled.
        One that never comes is what the checks below are there to catch, so the wait ends quietly."""
        try:
            page.wait_for_function(settled, timeout=30_000)
        except TimeoutError:
            pass
    out["names"] = page.evaluate("""
      () => [...document.querySelectorAll("details.ticket")].map((row) => {
        const clip = row.querySelector(":scope > summary .title .clip"), name = clip.getBoundingClientRect()
        const links = [...row.querySelectorAll(":scope > summary .titleline > a")]
        return {
          row: row.id, text: clip.textContent,
          cut: clip.scrollWidth > clip.clientWidth + 1,
          beside: links.filter((a) => Math.abs(a.getBoundingClientRect().top - name.top) < 4).length,
        }
      })
    """)
    out["opened"] = page.evaluate("document.querySelectorAll('details.ticket[open]').length")
    out["briefing"] = page.evaluate("""
      () => {
        const p = document.querySelector(".btext p"), box = p.getBoundingClientRect()
        return {wraps: getComputedStyle(p).whiteSpace !== "nowrap", over: p.scrollWidth - Math.ceil(box.width),
                says: document.querySelector("#briefing .bwhen").title}
      }
    """)
    out["graphs"] = page.evaluate("document.querySelectorAll('.side .mermaid svg').length")
    out["gname"] = page.evaluate("""
      () => { const g = document.getElementById("gname"), box = g.getBoundingClientRect(), head = g.parentElement
              return {text: g.textContent, cut: g.scrollWidth > g.clientWidth + 1 || box.right > head.getBoundingClientRect().right + 1} }
    """)
    out["unloaded"] = page.is_visible("#gunloaded") and page.inner_text("#gunloaded")
    for mark in marks:
        where = mark if mark.startswith("#") else f"#{ROW} .{mark}"
        page.hover(where)
        out["tips"][mark] = page.evaluate(TIP, where)
    out["questions"] = page.evaluate("""
      ([opened, folded]) => {
        const listed = (id) => {
          const list = document.getElementById(id).querySelector(".qs")
          return list ? list.getBoundingClientRect().height > 0 : null
        }
        const row = document.getElementById(opened)
        // each question of the opened row, as boxes rather than as nodes: a button the markup
        // carries and the style hides is what this run is here to tell from one the reader can click
        const asked = [...row.querySelectorAll(".asked > li")].map((li) => {
          const line = li.getBoundingClientRect()
          const button = li.querySelector(":scope > .copier")?.getBoundingClientRect()
          return {copier: button ? button.width > 0 : false,
                  at_the_end: button ? line.right - button.right < 1 : null}
        })
        return {opened_list: listed(opened), folded_list: listed(folded), asked}
      }
    """, [ROW, FOLDED])
    said = toasts()
    page.click(f"#{FOLDED} .qall")
    after(f"+(document.getElementById('toast').dataset.said ?? 0) > {said}")
    out["copied"] = {
        "clipboard": page.evaluate("navigator.clipboard.readText()"),
        "asked": page.evaluate(f"document.querySelector('#{FOLDED} .qall').dataset.copy"),
        "note": page.inner_text("#toast"),
        "shown": page.evaluate("document.getElementById('toast').classList.contains('on')"),
        "still_folded": page.evaluate(f"!document.getElementById('{FOLDED}').open"),
    }
    # the needs-me group's button with a tree's rows hidden by its pill, then shown again
    GROUP = """
      () => {
        const g = document.getElementById("grp-needs"), c = g.querySelector(".qgroup")
        return {word: c.textContent, copy: c.dataset.copy,
                hidden: [...g.querySelectorAll(":scope > .tickets > .ticket.off")].map((t) => t.dataset.path)}
      }
    """
    before = page.evaluate(GROUP)
    page.click('.treechip[data-tree="saved-views"]')
    said = toasts()
    page.click("#grp-needs .qgroup")
    after(f"+(document.getElementById('toast').dataset.said ?? 0) > {said}")
    out["group"] = {"before": before, "after": page.evaluate(GROUP), "clipboard": page.evaluate("navigator.clipboard.readText()")}
    page.click('.treechip[data-tree="saved-views"]')
    out["scheme_before_switch"] = page.evaluate("document.documentElement.dataset.theme")
    page.click("#scheme")
    after("document.documentElement.dataset.drawing === '0'")
    out["graphs_after_switch"] = page.evaluate("document.querySelectorAll('.side .mermaid svg').length")
    out["unloaded_after_switch"] = page.is_visible("#gunloaded")
    out["scheme_after_switch"] = page.evaluate("document.documentElement.dataset.theme")
    browser.close()
print(json.dumps(out))
