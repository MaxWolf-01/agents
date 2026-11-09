# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown-it-py[linkify]"]
# ///
"""The session page running in a browser. Run: uv run test_page_in_a_browser.py

The seam is the rendered page: the worked example (conftest.py) rendered by `render_session`, its
artefacts written where its links point, and the page driven in headless Chromium. Two oracles:
the Brief of agent/tickets/session-page-lists-its-artefacts.md (a collapsed turn shows its
artefacts as chips, j and k move between turns, and 1 to 9 open the focused turn's artefacts, a
ticket file being none; its A6, that a key clicks the link so a click handler the hub installs
catches it too, is checked with a handler of the test's own), and the Properties of
agent/tickets/session-page-keeps-your-place.md, P1 to P8, read off the DOM and the panes' scroll
positions. P1 to P3 hold only across a reload, so that probe reloads a page whose file changed in
between, a turn added. test_session_page.py checks which artefacts each turn lists; this
checks what the reader sees of them and what the keys do. The page's remote fonts are answered
from copies kept on this machine (show/page_cache.py), so a run after the first touches no network.
"""

import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from session_checks import SESSION, with_write
from live_hook import LIVE, PREFIX
from session_page import PAGE, chat_path, chat_record, read_session, render_session, write_page

# Every check here starts a browser.
pytestmark = pytest.mark.full_path

SHOW = Path(__file__).resolve().parents[1] / "show"

ARTEFACTS = (
    "agent/show/session-page/round-1/index.html",
    "agent/show/session-page/round-2/index.html",
    "agent/show/session-page/round-3/pages.html",
    "agent/show/session-page/round-3/spec.html",
)
# The widths the hub shows a session page at, the first being a wide window's, where the turns still
# have room beside the tasks and the timeline, the last a phone's, where one view shows at a time.
WIDTHS = (2400, 1240, 900, 530)

PROBE = r"""
import json, os, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from page_cache import default_root, serve

scenario, page_url, args = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
BOX = "(el) => { const r = el.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right} }"
# where the reader is: the block at the top of the turns pane and how far into it, as page.js reads it
PLACE = '''(() => {
  const pane = document.getElementById("turns-pane"), top = pane.getBoundingClientRect().top + 6
  const b = [...pane.querySelectorAll("[data-block]")].find((b) => b.getBoundingClientRect().bottom > top + 1)
  return {anchor: b.id, into: pane.getBoundingClientRect().top - b.getBoundingClientRect().top, scrollTop: pane.scrollTop,
          open: [...document.querySelectorAll("details.turn[open]")].map((t) => t.id),
          cur: document.querySelector(".blk.cur")?.id ?? null, row: document.querySelector("#artefacts .group.cur")?.id ?? null}
})()'''
# the control to the newest turn the reader can see, wherever the width puts it
CONTROL = '''(() => {
  const n = [...document.querySelectorAll("[data-newest]")].find((n) => n.checkVisibility({visibilityProperty: true}))
  if (!n) return null
  const r = n.getBoundingClientRect()
  return {inView: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth, fresh: n.classList.contains("fresh"),
          text: n.textContent}
})()'''

with sync_playwright() as pw:
    # the run it belongs to, as `browsers --help` defines it
    # headless Chromium hides every scrollbar unless told not to, which would pass P7's check whatever the page does
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"), ignore_default_args=["--hide-scrollbars"],
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])

    # reduced motion makes the page's own scrolls instant, so a reading after a key needs no wait on an animation
    def open_page(width, height, url=page_url):
        context = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce")
        serve(context, default_root())
        page = context.new_page()
        page.goto(url)
        page.evaluate("document.fonts.ready")
        return context, page

    def settle(page):
        # a wheel scrolls smoothly; the pane is still once it has not moved for a quarter second
        page.wait_for_function('''() => new Promise((done) => { const p = document.getElementById("turns-pane"), at = [p.scrollTop]
            const look = setInterval(() => { at.push(p.scrollTop); if (at.length > 5) { clearInterval(look); done(at.slice(-4).every((y) => y === at.at(-1))) } }, 60) })''',
            timeout=10000)

    def wheel(page, dy):
        box = page.eval_on_selector("#turns-pane", BOX)
        page.mouse.move((box["left"] + box["right"]) / 2, (box["top"] + box["bottom"]) / 2)
        page.mouse.wheel(0, dy)
        settle(page)

    out = {}
    if scenario == "keys":
        context, page = open_page(1280, 800)
        # what a click on the session id leaves on the clipboard
        context.grant_permissions(["clipboard-read", "clipboard-write"])
        page.click("#session-id")
        # the word that says so, over the id
        page.wait_for_function("document.querySelector('.copied-tip')?.textContent === 'copied'", timeout=5000)
        out["copied"] = page.evaluate("navigator.clipboard.readText()")
        # the resume control: on the title's meta line, level with the time the page was rendered
        out["resume_inline"] = page.evaluate('''(() => {
            const r = document.getElementById("resume"), meta = r.closest(".intro > .v-meta")
            if (!meta || !r.checkVisibility()) return false
            const a = r.getBoundingClientRect(), b = meta.querySelector(".nowrap").getBoundingClientRect()
            return Math.abs(a.top + a.height / 2 - (b.top + b.height / 2)) < 4 })()''')
        page.click("#resume")
        out["resume_clicked"] = page.evaluate("navigator.clipboard.readText()")
        page.evaluate("navigator.clipboard.writeText('')")
        page.keyboard.press("R")
        page.wait_for_function("navigator.clipboard.readText().then((t) => t !== '')", timeout=5000)
        out["resume_keyed"] = page.evaluate("navigator.clipboard.readText()")
        out["chips"] = page.evaluate('''[...document.querySelectorAll("details.turn")].map((t) => [t.id,
            [...t.querySelectorAll(":scope > summary .chip-link")].filter((a) => a.checkVisibility()).map((a) => a.textContent)])''')

        def where():
            return page.evaluate('''[document.querySelector(".blk.cur")?.id ?? null,
                                     document.querySelector("#artefacts .group.cur")?.id ?? null]''')

        def opened(key):
            with context.expect_page(timeout=5000) as tab:
                page.keyboard.press(key)
            tab.value.wait_for_load_state()
            url = tab.value.url
            tab.value.close()
            return url

        out["walk"] = []
        for key in ("j", "j", "k"):
            page.keyboard.press(key)
            out["walk"].append([key, *where()])
        # what a click handler of the hub's would see: the artefact each key clicked
        page.evaluate('''window.clicked = []; document.addEventListener("click", (e) => {
            const a = e.target.closest("a[data-artefact]"); if (a) clicked.push(a.dataset.artefact) }, true)''')
        out["opened"] = {"t04 1": opened("1"), "t04 2": opened("2")}
        page.keyboard.press("j")
        out["opened"]["t03 1"] = opened("1")
        out["clicked"] = page.evaluate("clicked")
        page.keyboard.press("2")
        page.wait_for_function("document.querySelector('#toast').textContent.startsWith('turn ')", timeout=5000)
        out["toast"] = page.text_content("#toast")
        out["help"] = page.evaluate('''[...document.querySelectorAll("#help td:first-child")].map((td) =>
            [...td.querySelectorAll("kbd")].map((k) => k.textContent).join(" "))''')
        OPEN = '[...document.querySelectorAll("details.turn")].map((t) => t.open)'
        page.keyboard.press("o")
        out["o"] = page.evaluate(OPEN)
        page.keyboard.press("o")
        out["oo"] = page.evaluate(OPEN)
        OVER = '[...document.querySelectorAll(".key-over")].map((k) => k.textContent)'
        page.keyboard.down("Control")
        page.keyboard.down("Alt")
        out["held"] = page.evaluate(OVER)
        page.keyboard.up("Alt")
        out["let_go"] = page.evaluate(OVER)
        page.keyboard.up("Control")

    elif scenario == "copy-code":
        context, page = open_page(1280, 800)
        context.grant_permissions(["clipboard-read", "clipboard-write"])
        pre, button = "#t04 .code pre", "#t04 .copy-code"
        opacity = lambda: page.eval_on_selector(button, "(b) => getComputedStyle(b).opacity")
        out["hidden"] = opacity()
        page.hover(pre)
        out["over_code"] = opacity()
        before = page.eval_on_selector(button, BOX)
        page.eval_on_selector(pre, "(p) => { p.scrollLeft = 200 }")
        out["scrolled"] = page.eval_on_selector(pre, "(p) => p.scrollLeft")
        # the pointer into the block's top right corner, onto where the button sits
        box = page.eval_on_selector(pre, BOX)
        page.mouse.move(box["right"] - 14, box["top"] + 14)
        out["in_corner"] = opacity()
        out["moved"] = page.eval_on_selector(button, BOX) != before
        out["corner"] = page.evaluate(f'''(() => {{ const b = document.querySelector("{button}").getBoundingClientRect(),
            p = document.querySelector("{pre}").getBoundingClientRect(); return [p.right - b.right, b.top - p.top] }})()''')
        page.click(button)
        page.wait_for_function("document.querySelector('.copied-tip')?.textContent === 'copied'", timeout=5000)
        out["copied"] = page.evaluate("navigator.clipboard.readText()")

    elif scenario == "copy-turn":
        context, page = open_page(1280, 800)
        context.grant_permissions(["clipboard-read", "clipboard-write"])
        clipboard = lambda: page.evaluate("navigator.clipboard.readText()")
        opacity = lambda: page.eval_on_selector("#t03 .copy-turn", "(b) => getComputedStyle(b).opacity")
        page.keyboard.press("y")
        out["m_newest"], out["m_toast"] = clipboard(), page.text_content("#toast")
        page.mouse.move(5, 5)
        out["hidden"] = opacity()
        page.hover("#t03 > summary .hl")
        out["over_turn"] = opacity()
        page.click("#t03 .copy-turn")
        out["clicked"] = clipboard()
        out["opened_by_click"] = page.evaluate("document.getElementById('t03').open")
        # the click put the cursor on turn 03, and j moves it on to 02
        for key in ("j", "y"):
            page.keyboard.press(key)
        out["m_cursor"] = clipboard()
        page.keyboard.press("Y")
        out["M"], out["M_toast"] = clipboard(), page.text_content("#toast")

    elif scenario == "copy-under-pointer":
        context, page = open_page(1280, 800)
        context.grant_permissions(["clipboard-read", "clipboard-write"])
        hint = lambda: page.evaluate("document.querySelector('.key-hint')?.textContent ?? null")
        out["hovered"] = {}
        for target in args["targets"]:
            page.evaluate("navigator.clipboard.writeText('')")
            # a scroll takes the hint away, so the target is brought into view, and its scroll event has fired, first
            page.locator(target).scroll_into_view_if_needed()
            page.evaluate("new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))")
            page.hover(target)
            seen_hint = hint()
            page.keyboard.press("c")
            page.wait_for_function("navigator.clipboard.readText().then((t) => t !== '')", timeout=5000)
            out["hovered"][target] = [seen_hint, page.evaluate("navigator.clipboard.readText()")]
        page.hover(args["in_page"])
        out["hint_in_page"] = hint()
        page.keyboard.press("c")
        out["toast_in_page"] = page.text_content("#toast")
        page.mouse.move(5, 5)
        out["hint_away"] = hint()
        page.keyboard.press("c")
        out["toast"] = page.text_content("#toast")
        page.evaluate("navigator.clipboard.writeText('')")
        page.focus(args["targets"][0])
        page.keyboard.press("c")
        page.wait_for_function("navigator.clipboard.readText().then((t) => t !== '')", timeout=5000)
        out["copied_focused"] = page.evaluate("navigator.clipboard.readText()")

    elif scenario == "reload":
        # P1, P2, P3, P5 across a reload: the reader clicks a turn number in the timeline, which
        # puts its fragment in the address, opens a turn, scrolls on, and the page is reloaded with
        # a turn added
        context, page = open_page(1280, 700)
        page.click("#a03 .turn-ref")
        settle(page)
        out["hash"] = page.evaluate("location.hash")
        page.click("#t05 > summary")
        wheel(page, args["wheel"])
        out["before"] = page.evaluate(PLACE)
        out["control_before"] = page.evaluate(CONTROL)
        shutil.copyfile(args["after"], args["file"])
        page.reload()
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        out["after"] = page.evaluate(PLACE)
        out["hash_after"] = page.evaluate("location.hash")
        out["control_after"] = page.evaluate(CONTROL)
        wheel(page, -200)
        out["control_short_of_it"] = page.evaluate(CONTROL)
        page.keyboard.press("N")
        settle(page)
        out["newest"] = {**page.evaluate(PLACE), "control": page.evaluate(CONTROL)}
        # a navigation that arrives with a fragment reveals it
        context, page = open_page(1280, 700, page_url + "#t03")
        settle(page)
        out["arrived"] = page.evaluate(PLACE)

    elif scenario == "follow":
        # Q1a: a reader inside the newest turn when turn 13 arrives follows it to the top; one
        # reading further back when a chat turn arrives stays, the control marked until n
        context, page = open_page(1280, 700)
        wheel(page, 200)
        out["caught_up"] = page.evaluate(PLACE)
        shutil.copyfile(args["after"], args["file"])
        page.reload()
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        out["followed"] = {**page.evaluate(PLACE), "control": page.evaluate(CONTROL)}
        wheel(page, 2500)
        out["back"] = page.evaluate(PLACE)
        shutil.copyfile(args["chatted"], args["file"])
        page.reload()
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        out["stayed"] = {**page.evaluate(PLACE), "control": page.evaluate(CONTROL)}
        page.keyboard.press("N")
        settle(page)
        out["newest"] = {**page.evaluate(PLACE), "control": page.evaluate(CONTROL)}

    elif scenario == "number":
        # P6: t, then the digits a turn shows
        context, page = open_page(1280, 700)
        out["typed"] = {}
        for keys in (["t", "1", "2"], ["t", "0", "5"], ["t", "9"], ["t", "1"], ["Enter"], ["t", "0", "0"]):
            for key in keys:
                page.keyboard.press(key)
            settle(page)
            out["typed"][" ".join(keys)] = {**page.evaluate(PLACE), "toast": page.text_content("#toast")}
        # P4: the number of a turn that links nothing goes to it, and so does its headline
        for target in ("#a07 .turn-ref", "#a08 .hl"):
            page.click(target)
            settle(page)
            out[target] = page.evaluate(PLACE)
        # a window too short for the timeline to show every row: going to the oldest turn scrolls
        # its row into the timeline's view
        context, short = open_page(1280, 240)
        short.keyboard.press("G")
        try:
            short.wait_for_function('''() => { const c = document.querySelector("#artefacts").getBoundingClientRect(),
                g = document.querySelector("#a01").getBoundingClientRect(); return c.top <= g.top && g.bottom <= c.bottom }''',
                timeout=5000)
        except Exception:
            pass  # the assertion below says where the row was left
        out["short"] = {"column": short.eval_on_selector("#artefacts", BOX), "row": short.eval_on_selector("#a01", BOX),
                        "overflows": short.eval_on_selector("#artefacts", "(el) => el.scrollHeight > el.clientHeight")}

    elif scenario == "prompt_size":
        # the size each turn's prompts show on their folded line, as far as the reader sees it
        context, page = open_page(args["width"], 800)
        if page.locator("#view-toggle").is_visible():
            page.click("#view-toggle")  # a phone opens on the tasks
        out["sizes"] = page.evaluate('''[...document.querySelectorAll(".said > summary .count .size")]
            .filter((el) => el.checkVisibility()).map((el) => [!!el.querySelector("svg"), el.textContent])''')
    elif scenario == "layout":
        # P3, P7, P8 at one width: the columns, the control at both ends of the turns, the tasks' rows
        width = args["width"]
        context, page = open_page(width, 800)
        geometry = '''(() => { const box = (s) => { const el = document.querySelector(s), r = el.getBoundingClientRect()
            return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, shown: el.checkVisibility({visibilityProperty: true})} }
          return {bar: box(".bar"), tasks: box("#open-questions"), pane: box("#turns-pane"), column: box("#artefacts"),
                  toggle: box("#view-toggle"), height: innerHeight, width: innerWidth,
                  firstTurnBorder: getComputedStyle(document.querySelector(".turns > .blk")).borderTopWidth,
                  rows: [...document.querySelectorAll("#open-questions .t-row")].map((r) => r.getBoundingClientRect().height)} })()'''
        out["tasks_view"] = page.evaluate(geometry)
        if out["tasks_view"]["toggle"]["shown"]:
            page.click("#view-toggle")
        out["top"] = page.evaluate(geometry)
        out["control_top"] = page.evaluate(CONTROL)
        for _ in range(3):
            wheel(page, 4000)
        page.keyboard.press("G")
        settle(page)
        out["bottom"] = page.evaluate(geometry)
        out["control_bottom"] = page.evaluate(CONTROL)
        out["pane_at_end"] = page.evaluate('''(() => { const p = document.getElementById("turns-pane")
            return p.scrollTop > 0 && p.scrollTop + p.clientHeight >= p.scrollHeight - 1 })()''')
        out["timeline_at_end"] = page.evaluate('''(() => { const c = document.getElementById("artefacts")
            return c.scrollTop + c.clientHeight >= c.scrollHeight - 1 })()''')
        for key in ("]", "[", "Escape", "j", "k", "g", "g", "End", "PageUp", "Home"):
            page.keyboard.press(key)
        settle(page)
        out["timeline_at_top"] = page.evaluate("document.getElementById('artefacts').scrollTop")
        out["window"] = page.evaluate("[scrollX, scrollY, document.scrollingElement.scrollTop, document.body.scrollTop]")
        out["scrollbars"] = page.evaluate('''[...document.querySelectorAll("*")].filter((e) => { const s = getComputedStyle(e)
            return ["auto", "scroll"].includes(s.overflowY) && e.offsetWidth - e.clientWidth - parseFloat(s.borderLeftWidth) - parseFloat(s.borderRightWidth) > 0 })
            .map((e) => e.id || e.className)''')
        page.keyboard.press("]")
        out["row_heights_focused"] = page.evaluate(geometry)["rows"]
    elif scenario == "crowded":
        # the row ] goes to among many, each with a card longer than a screen, and the card Enter opens on it
        context, page = open_page(args["width"], 800)
        if page.locator("#view-toggle").is_visible() and page.evaluate("document.body.dataset.view") != "tasks":
            page.click("#view-toggle")
        for _ in range(args["presses"]):
            page.keyboard.press("]")
        settle(page)
        out["row"] = page.evaluate('''(() => { const t = document.getElementById("open-questions"), r = t.querySelector(".t-row.at")
          const a = t.getBoundingClientRect(), b = r.getBoundingClientRect()
          return {handle: r.dataset.handle, inView: b.top >= a.top - 1 && b.bottom <= a.bottom + 1, rows: t.querySelectorAll(".t-row.at").length} })()''')
        page.keyboard.press("Enter")
        out.update(page.evaluate('''(() => { const box = (el) => { const r = el.getBoundingClientRect(); return {top: r.top, bottom: r.bottom} }
          const dialog = document.getElementById("card-dialog"), card = dialog.querySelector(".card:not([hidden])")
          return {title: box(card.querySelector("h3")), height: innerHeight, id: card.id,
                  shown: dialog.querySelectorAll(".card:not([hidden])").length, focused: card.contains(document.activeElement)} })()'''))
    elif scenario == "stage":
        # the keys stage an answer on each kind of item, a note stays on the item it was opened on, what is staged
        # outlives a reload, and the review shows the batch, which Enter copies where no hub frames the page
        context, page = open_page(1280, 900)
        context.grant_permissions(["clipboard-read", "clipboard-write"])
        STATE = '''(() => { const t = document.getElementById("open-questions"), r = t.querySelector(".t-row.at")
          const card = document.querySelector("#card-dialog:not([hidden]) .card:not([hidden])")
          return {row: r ? r.dataset.handle : null, picked: r ? [...r.querySelectorAll(".pill.on")].map((p) => p.dataset.pick) : [],
                  act: r ? [...r.querySelectorAll(".ib.on")].map((b) => b.dataset.act) : [],
                  seen: r && r.querySelector(".seen-btn") ? r.querySelector(".seen-btn").textContent : null,
                  note: r ? r.querySelector("[data-act=note]").dataset.tip : null,
                  staged: [...t.querySelectorAll(".t-row.st")].map((x) => x.dataset.handle),
                  badge: t.querySelector(".rv b")?.textContent ?? "", inBand: t.contains(document.activeElement),
                  card: card ? card.id : null,
                  review: document.getElementById("review").hidden ? null : document.querySelector("#review pre")?.textContent ?? "",
                  stays: [...document.querySelectorAll("#review p.left-out")].at(-1)?.textContent ?? null} })()'''
        out["steps"] = []
        def step(*keys):
            for key in keys:
                page.keyboard.type(key[5:]) if key.startswith("type:") else page.keyboard.press(key)
            out["steps"].append([" ".join(keys), page.evaluate(STATE)])
        step("]")                      # into the tasks, on the first row
        step("b")                      # an option of the question's
        step("a")                      # another, over it
        step("a")                      # and again, which takes it back
        step("a")
        step("n", "type:only after Friday]", "Enter")  # a note, a ] typed in it moving nothing
        step("]")                      # the to-do
        step("x")                      # dismissed
        step("d")                      # done, over it
        step("u")                      # cleared
        step("d")                      # done
        step("]", "s")                 # the first artefact, marked seen
        with context.expect_page(timeout=5000) as tab:
            page.keyboard.press("o")   # opened, which marks nothing
        tab.value.close()
        out["steps"].append(["o", page.evaluate(STATE)])
        step("n", "type:the legend is wrong", "Enter")
        step("]", "n", "type:read", "Escape")  # the second artefact: a note opened and dropped
        step("s")                      # and seen
        page.reload()
        page.evaluate("document.fonts.ready")
        step("]", "Enter")             # the reload kept the batch; the question's card opens
        step("r")
        page.evaluate("navigator.clipboard.writeText('')")
        step("Enter")
        page.wait_for_function("navigator.clipboard.readText().then((t) => t !== '')", timeout=5000)
        out["copied"] = page.evaluate("navigator.clipboard.readText()")
        step("Escape")                 # back to the card
        step("Escape")                 # out of the dialog
        step("Escape")                 # out of the tasks
        step("j")                      # the turns' key again
        step("n")                      # a note from the turns, on no item: none is in focus
        step("r")                      # the review, in one key from the turns
    elif scenario == "options":
        # where the first question's option words, leads to, gives and costs sit against each other, at a width
        context, page = open_page(args["width"], 900)
        if page.locator("#view-toggle").is_visible() and page.evaluate("document.body.dataset.view") != "tasks":
            page.click("#view-toggle")
        page.click("#open-questions .t-row .qt")
        out.update(page.evaluate('''(() => { const box = (el) => { const r = el.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right} }
          const row = document.querySelector("#q1 tr[data-option]")
          return {words: box(row.children[1]), leads: box(row.querySelector("td.l")), gives: box(row.querySelector("td.g")), costs: box(row.querySelector("td.c")),
                  card: box(document.querySelector("#q1 .card-main")), labelled: getComputedStyle(row.querySelector("td.g"), "::before").content,
                  shown: !document.getElementById("card-dialog").hidden} })()'''))
    elif scenario == "framed":
        # the page in a frame of a hub tab: what it staged comes from the hub, every change goes back to it, and the
        # send is the hub's, after which the lines it sent leave the tasks
        import http.server, threading
        root = Path(args["root"])
        handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(root), **k)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        SHOWN = '''(() => { const t = document.getElementById("open-questions"), r = t.querySelector(".t-row.at")
          const shown = [...t.querySelectorAll(".t-row")].filter((x) => !x.hidden)
          return {row: r ? r.dataset.handle : null, picked: shown[0] ? [...shown[0].querySelectorAll(".pill.on")].map((p) => p.dataset.pick) : [],
                  note: shown[0] ? shown[0].querySelector("[data-act=note]").dataset.tip : null,
                  shown: shown.map((x) => x.dataset.handle), staged: [...t.querySelectorAll(".t-row.st")].map((x) => x.dataset.handle),
                  badge: t.querySelector(".rv b")?.textContent ?? "", scroll: t.scrollTop, inBand: t.contains(document.activeElement)} })()'''
        try:
            context, page = open_page(1280, 900, f"http://127.0.0.1:{server.server_address[1]}/{args['tab']}")
            # the frame's script runs as it parses; its load waits on fonts, which the page cache answers for the tab alone
            page.wait_for_function("document.querySelector('iframe')?.contentDocument?.getElementById('open-questions')", timeout=10000)
            inner = next(f for f in page.frames if f.url.endswith("/" + Path(page_url).name))
            page.wait_for_function("window.restaged", timeout=10000)  # the page has read what the hub kept
            out["loaded"] = inner.evaluate(SHOWN)
            if args.get("send"):
                inner.focus("#open-questions")
                for key in args["keys"]:
                    page.keyboard.press(key)
                out["typed"] = inner.evaluate("document.querySelector('#review pre').textContent")
                out["reviewing"] = inner.evaluate("window.waitingReviewing()")  # what the box's Enter asks before it sends
                page.evaluate("window.words = 'and go on'")
                inner.evaluate("window.waitingWords()")  # what the hub tab calls as the user types in its box
                out["review"] = inner.evaluate("document.querySelector('#review pre').textContent")
                out["stays"] = inner.evaluate("[...document.querySelectorAll('#review p.left-out')].at(-1).textContent")
                out["before"] = page.evaluate("window.sent")
                page.keyboard.press("Enter")
                inner.wait_for_function("!window.waitingReviewing()", timeout=10000)
                out["sent"] = page.evaluate("window.sent")
                out["saved"] = page.evaluate("window.saved.at(-1)")
                out["after"] = inner.evaluate(SHOWN)
                out["reviewing_after"] = inner.evaluate("window.waitingReviewing()")
        finally:
            server.shutdown()
    elif scenario == "tables":
        # where a turn's tables sit against its text, its edge and the pane, and which cells wrap
        context, page = open_page(args["width"], 800)
        out.update(page.evaluate('''(([which, text]) => { const box = (el) => { const r = el.getBoundingClientRect(); return {left: r.left, right: r.right} }
          const turn = document.querySelector(which), prose = turn.querySelector(text)
          const wraps = (cell) => { const s = getComputedStyle(cell)
            return cell.clientHeight - parseFloat(s.paddingTop) - parseFloat(s.paddingBottom) > 1.5 * parseFloat(s.lineHeight) }
          return {turn: box(turn), text: box(prose.querySelector("p")), pane: box(document.getElementById("turns-pane")),
                  tables: [...prose.querySelectorAll(":scope > table")].map((t) => ({...box(t), wraps: [...t.querySelectorAll("th, td")].some(wraps)}))} })''',
          [args["turn"], args["text"]]))
    elif scenario == "log":
        # the drawer as the reader sees it: open or not, the turn it names, each step's line
        context, page = open_page(1280, 800)
        SHOWN = '''(() => { const log = document.getElementById("log")
          return {open: !!log && log.checkVisibility(), which: log?.querySelector(".which")?.textContent ?? null,
                  steps: [...(log?.querySelectorAll(".step") ?? [])].map((s) => s.classList.contains("thinking")
                    ? ["thinking", s.querySelector(".subject").textContent] : [s.querySelector(".verb").textContent, s.querySelector(".subject").textContent])} })()'''
        LOADED = "'toolCalls' in window"
        STEP = '''(verb) => [...document.querySelectorAll("#log .step")].find((s) => s.querySelector(".verb")?.textContent === verb)'''
        out["closed"] = page.evaluate(SHOWN) | {"loaded": page.evaluate(LOADED)}
        page.keyboard.press("l")
        page.wait_for_function("document.querySelector('#log .log-steps')", timeout=10000)
        out["newest"] = page.evaluate(SHOWN) | {"loaded": page.evaluate(LOADED)}
        page.keyboard.press("j")
        page.keyboard.press("j")
        out["after_jj"] = page.evaluate(SHOWN)
        page.keyboard.press("k")

        def opened(verb):
            page.evaluate(f"(verb) => ({STEP})(verb).querySelector('button').click()", verb)
            return page.evaluate(f'''(verb) => [...({STEP})(verb).querySelectorAll(".detail pre")].map((p) => ({{lang: p.dataset.lang,
                cls: p.className, text: p.textContent, lit: !!p.querySelector("[class^=hljs-]"), more: !!p.nextElementSibling?.matches(".more")}}))''', verb)
        out["bash_size"] = page.evaluate(f'''[...({STEP})('ran').querySelectorAll('.size .amount')]
            .map((a) => [a.querySelector('use').getAttribute('href'), a.textContent])''')
        page.evaluate(f"({STEP})('ran').querySelector('.size').scrollIntoView()")
        page.mouse.move(*page.evaluate(f'''(() => {{ const r = ({STEP})('ran').querySelector('.size').getBoundingClientRect()
            return [r.left + r.width / 2, r.top + r.height / 2] }})()'''))
        page.wait_for_selector(".tip.on", timeout=5000)
        out["bash_tip"] = page.evaluate("document.querySelector('.tip.on').textContent")
        page.mouse.move(0, 0)
        out["bash"], out["edit"], out["read"] = opened("ran"), opened("edited"), opened("read")
        out["read_whole"] = page.evaluate(f'''(() => {{ const s = ({STEP})("read"); s.querySelector(".more").click()
            return s.querySelector(".detail pre").textContent.length }})()''')
        page.keyboard.press("Escape")
        out["escaped"] = page.evaluate(SHOWN)["open"]
        page.click("#log-toggle")
        out["clicked"] = page.evaluate(SHOWN)["open"]
        page.keyboard.press("l")
        out["closed_again"] = page.evaluate(SHOWN)["open"]
    elif scenario == "log_keys":
        # Tab hands the keys to the open log and back: the step they are on, which steps are open, the turn shown
        context, page = open_page(1280, 800)
        SHOWN = '''(() => { const log = document.getElementById("log"), steps = [...log.querySelectorAll(".step")]
          return {which: log.querySelector(".which").textContent.split(" · ")[0], keyed: log.classList.contains("keyed"),
                  cur: steps.findIndex((s) => s.classList.contains("cur")), open: steps.flatMap((s, n) => s.classList.contains("open") ? [n] : []),
                  all: log.querySelector("[data-all]")?.textContent ?? null} })()'''
        page.keyboard.press("l")
        page.wait_for_function("document.querySelector('#log .log-steps')", timeout=10000)
        out["opened"] = page.evaluate(SHOWN)
        for name, keys in (("tab", "Tab"), ("jj", "j j"), ("o", "o"), ("k", "k"), ("O", "O"), ("OO", "O"), ("G", "G"), ("gg", "g g"),
                           ("back", "Tab"), ("O_unkeyed", "O"), ("j_turns", "j j")):
            for key in keys.split():
                page.keyboard.press(key)
            out[name] = page.evaluate(SHOWN)
        page.click("#log .step:nth-child(2) > button")
        out["clicked"] = page.evaluate(SHOWN)
        page.click("#log [data-all]")
        out["all_clicked"] = page.evaluate(SHOWN)
    elif scenario == "live":
        # the turn under way: shown with no turn picked, a call added while open, left for a turn and come back to
        context, page = open_page(1280, 800)
        live = Path(args["live"])
        SHOWN = '''(() => { const log = document.getElementById("log")
          return {which: log.querySelector(".which").textContent, buttons: [...log.querySelectorAll(".log-head button")].map((b) => b.textContent),
                  steps: [...log.querySelectorAll(".step")].map((s) => [s.querySelector(".verb").textContent,
                    s.querySelector(".subject").textContent, s.querySelector(".took").classList.contains("running")])} })()'''
        live.write_text(args["first"])
        page.keyboard.press("l")
        page.wait_for_function("document.querySelector('#log .log-steps')", timeout=10000)
        out["first"] = page.evaluate(SHOWN)
        live.write_text(args["second"])
        page.wait_for_function("document.querySelectorAll('#log .step').length === 2", timeout=10000)
        out["second"] = page.evaluate(SHOWN)
        page.keyboard.press("j")
        out["turn"] = page.evaluate(SHOWN)
        page.keyboard.press("k")
        out["back"] = page.evaluate(SHOWN)
        page.keyboard.press("j")
        out["newest_again"] = page.evaluate(SHOWN)
        live.unlink()
        page.wait_for_function("!document.querySelector('#log .which').textContent.startsWith('under way')", timeout=10000)
        out["ended"] = page.evaluate(SHOWN)
    elif scenario == "phone":
        # a phone: the page opens on the tasks; an artefact opens from its row by a tap, a turn's tool calls by its
        # button; and while the live hook's file is there, the tasks say a turn is running
        context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, reduced_motion="reduce")
        serve(context, default_root())
        page = context.new_page()
        page.goto(page_url)
        out["view"] = page.evaluate("document.body.dataset.view")
        out["working_before"] = page.evaluate("document.getElementById('working').checkVisibility()")
        Path(args["live"]).write_text(args["calls"])
        page.wait_for_function("document.getElementById('working').checkVisibility()", timeout=15000)
        out["working"] = page.text_content("#working .t-txt")
        with context.expect_page(timeout=5000) as tab:
            page.tap("#open-questions .t-row.art a.open")
        out["opened"] = tab.value.url
        tab.value.close()
        page.tap("#view-toggle")
        page.tap("#t01 .turn-log")
        page.wait_for_function("document.querySelector('#log .which')", timeout=10000)
        out["log"] = page.text_content("#log .which")
    browser.close()
print(json.dumps(out))
"""


# A ticket link ahead of turn 04's artefacts, which no key counts: 1 still opens the first artefact.
TICKET = "- [The ticket](agent/tickets/session-page.md): what this round builds\n"


@pytest.fixture
def rendered(worked_example: Path, transcript: Path) -> tuple[Path, Path]:
    """The worked example's page written beside its records, and the repo root its links resolve
    from, which holds every artefact the records link and the ticket turn 04 links first."""
    root = worked_example.parents[2]
    newest = worked_example / "turns" / "04.md"
    newest.write_text(newest.read_text().replace("## Links\n\n", "## Links\n\n" + TICKET, 1))
    assert TICKET in newest.read_text(), "record 04 has no `## Links` to put the ticket in"
    for path in (*ARTEFACTS, "agent/tickets/session-page.md"):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(f"<title>{path}</title>")
    (worked_example / PAGE).write_text(render_session(worked_example, transcript))
    return worked_example / PAGE, root


def filler(number: int, questions: str = "") -> str:
    """A turn record that links nothing, tall enough that a few of them fill the pane."""
    details = "\n\n".join(f"Paragraph {n} of what turn {number} settled, long enough to wrap across the measure "
                          "once or twice at every width the hub shows the page at." for n in range(1, 7))
    return f"---\ndate: 2026-09-24\n---\n\n# Filler turn {number}: a turn that links nothing\n\n{questions}## Details\n\n{details}\n"


# A session waiting on the user for one item of each kind: a question with an option table, a to-do,
# and two artefacts, every turn's since the transcript holds no message.
WAITING = (
    "---\ndate: 2026-10-29\n---\n\n# Unity's lint baseline cleared\n\n"
    "## Questions\n\n- [Q1] **Force-push devops #4 and #5 now?** nobody has reviewed them\n"
    "  - (a) Push now\n    - Leads to: both PRs rebased\n    - Gives: #4 and #5 carry the rule today\n    - Costs: their old SHAs stop resolving\n"
    "  - (b) Wait for the first review\n\n"
    "## To do\n\n- [A1] **Review devops #3** at `4d7a3b8`\n\n"
    "## Links\n\n- [The six PR texts](agent/show/lint/texts.html): Q1 leans on them\n"
    "- [The stack's diff](agent/show/lint/diff.html): the six layers\n"
)


@pytest.fixture
def waiting_page(tmp_path: Path) -> Path:
    """WAITING's page, in a session directory of an agent repo, beside the artefacts it links."""
    directory = tmp_path / "agent" / "sessions" / SESSION
    (directory / "turns").mkdir(parents=True)
    (directory / "turns" / "01.md").write_text(WAITING)
    for name in ("texts", "diff"):
        (tmp_path / "agent" / "show" / "lint").mkdir(parents=True, exist_ok=True)
        (tmp_path / "agent" / "show" / "lint" / f"{name}.html").write_text(f"<title>{name}</title>")
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("")
    with_write(transcript, "Write", directory / "turns" / "01.md")  # record 01 ends at 2026-09-23T01:36Z
    (directory / PAGE).write_text(render_session(directory, transcript))
    return directory / PAGE


def hub_tab(page: Path, kept: dict) -> str:
    """A hub tab as the page meets one, written beside `page`: `hubWaiting` holding `kept`, the staging the hub
    kept for the page earlier, keeping each change, and a send that leaves out the to-do's line, as one restaged while the send was
    under way would be, and hands the page back the lines it sent, the box's own words after them."""
    tab = page.parent / "tab.html"
    tab.write_text("""<!doctype html><meta charset="utf-8"><script>
window.saved = []; window.sent = null; window.words = "and go";
window.hubWaiting = {
  holds: () => true,
  restaged: () => { window.restaged = true },
  load: async () => ({ ok: true, staged: KEPT }),
  save: async (w, doc) => { window.saved.push(doc); return { ok: true } },
  words: () => window.words,
  send: async (w) => {
    const batch = w.waitingBatch().split("\\n").filter((l) => !l.startsWith("A1:")).join("\\n")
    window.sent = batch + "\\n\\n" + window.words
    w.waitingSent(batch)
    return { ok: true }
  },
};
</script><iframe src="PAGE" style="width: 100%; height: 860px"></iframe>
""".replace("KEPT", json.dumps(kept)).replace("PAGE", page.name))
    return tab.name


@pytest.fixture
def long_session(rendered: tuple[Path, Path], transcript: Path) -> tuple[Path, Path]:
    """The worked example grown to twelve turns, with a first open question, Q7, long enough to fill
    the band's cap and two more waiting below it; and beside its page, the page rendered once a
    thirteenth turn has arrived."""
    page, _ = rendered
    directory = page.parent
    record = directory / "turns" / "04.md"
    sentence = "It replaces Q5, which assumed a chat reply worth reviewing."
    assert sentence in record.read_text()
    record.write_text(record.read_text().replace(sentence, " ".join([sentence] * 40), 1))
    asked = ("## Questions\n\n"
             "- [Q8] **Which width does the sheet open at?** The sidebar's.\n  - (a) The sidebar's. *my pick*\n  - (b) Any.\n"
             "- [Q9] **Does the band fold by default?** It does not.\n  - (a) It stays open. *my pick*\n  - (b) It folds.\n\n")
    for number in range(5, 13):
        (directory / "turns" / f"{number:02d}.md").write_text(filler(number, asked if number == 6 else ""))
    page.write_text(render_session(directory, transcript))
    (directory / "turns" / "13.md").write_text(filler(13))
    after = directory / "after.html"
    after.write_text(render_session(directory, transcript))
    (directory / "turns" / "13.md").unlink()
    return page, after


@pytest.fixture
def crowded(long_session: tuple[Path, Path], transcript: Path) -> Path:
    """The long session with eleven more questions waiting, Q10 to Q20, each long enough to fill the
    band on its own: fourteen rows, more than the band holds folded."""
    page, _ = long_session
    detail = " ".join(["A sentence of the question's detail, long enough to wrap across the measure."] * 12)
    asked = "## Questions\n\n" + "".join(
        f"- [Q{n}] **Question {n}, one of many waiting at once?** {detail}\n  - (a) Yes.\n  - (b) No.\n"
        for n in range(10, 21))
    (page.parent / "turns" / "12.md").write_text(filler(12, asked + "\n"))
    crowded = page.parent / "crowded.html"
    crowded.write_text(render_session(page.parent, transcript))
    return crowded


@pytest.fixture
def chatted(long_session: tuple[Path, Path], transcript: Path) -> Path:
    """Beside the long session's page, the page rendered once turn 13 and then a chat turn have
    arrived."""
    page, _ = long_session
    turns = page.parent / "turns"
    now = datetime.now(UTC)
    (turns / "13.md").write_text(filler(13))
    chat = chat_path(turns, now)
    chat.write_text(chat_record("A reply that ended a turn in the chat.", now))
    rendered = page.parent / "chatted.html"
    rendered.write_text(render_session(page.parent, transcript))
    (turns / "13.md").unlink()
    chat.unlink()
    return rendered


WIDE_TABLE = """| What runs | Where its key comes from | What it is billed as |
| --- | --- | --- |
| a script run by hand from a shell on the laptop, now and then | the environment the shell exports | usage of the account the key belongs to |
| a scheduled job on the server, once an hour | a file only the job's user can read | the same account's usage, every hour |
"""
NARROW_TABLE = "| Key | Does |\n| --- | --- |\n| j | the next turn |\n"


@pytest.fixture
def tabled(rendered: tuple[Path, Path], transcript: Path) -> Path:
    """The worked example with a fifth turn whose Details hold a table too wide for the text's
    measure and a narrow one."""
    page, _ = rendered
    record = filler(5).replace("## Details\n\n", f"## Details\n\nA paragraph before the tables.\n\n{WIDE_TABLE}\n{NARROW_TABLE}\n", 1)
    (page.parent / "turns" / "05.md").write_text(record)
    page.write_text(render_session(page.parent, transcript))
    return page


@pytest.fixture
def chat_tabled(rendered: tuple[Path, Path], transcript: Path) -> Path:
    """The worked example with a chat turn after its turns, whose reply holds the same two tables."""
    page, _ = rendered
    now = datetime.now(UTC)
    chat_path(page.parent / "turns", now).write_text(
        chat_record(f"A paragraph before the tables.\n\n{WIDE_TABLE}\n{NARROW_TABLE}", now))
    page.write_text(render_session(page.parent, transcript))
    return page


def probe(page: Path, scenario: str, **args: object) -> dict:
    for tool in ("uv", "chromium"):
        if not shutil.which(tool):
            pytest.skip(f"no {tool} to drive the page with")
    done = subprocess.run(
        ["uv", "run", "--quiet", "--with", "playwright", "python", "-", scenario, page.as_uri(), json.dumps(args)],
        input=PROBE, capture_output=True, text=True, timeout=180, env=os.environ | {"PYTHONPATH": str(SHOW)},
    )
    assert done.returncode == 0, f"probe: {done.stderr.strip()[-2000:]}"
    return json.loads(done.stdout)


def test_the_chips_and_keys_work_in_a_browser(rendered: tuple[Path, Path]) -> None:
    """The newest turn, open, shows no chips and each collapsed turn shows its artefacts as chips;
    j and k walk the turns, marking the cursor's turn in the timeline (P5); 1 and 2 open the
    focused turn's first and second artefact, past the ticket file turn 04 links first, by clicking
    its link, and a number the turn has no artefact for opens nothing and says so. The key list
    names the keys this page added (P6). The resume control sits on the title's meta line, and it
    and R copy the resume command. o opens every turn and then closes them all (session-page-keys-and-sizes), and
    Ctrl+Alt held shows each control's key over it, until it is let go."""
    page, root = rendered
    seen = probe(page, "keys")
    assert seen["chips"] == [
        ["t04", []],
        ["t03", ["Round 2 as a hand-built session page"]],
        ["t02", ["The grid, the session page sketch and Q1 to Q3"]],
        ["t01", []],
    ]
    assert seen["walk"] == [["j", "t04", "a04"], ["j", "t03", "a03"], ["k", "t04", "a04"]]
    url = lambda path: (root / path).as_uri()
    assert seen["opened"] == {"t04 1": url(ARTEFACTS[2]), "t04 2": url(ARTEFACTS[3]), "t03 1": url(ARTEFACTS[1])}
    assert seen["clicked"] == [str(root / ARTEFACTS[i]) for i in (2, 3, 1)]
    assert seen["toast"] == "turn 03 has no artefact 2"
    assert seen["copied"] == SESSION, "a click on the session id did not copy it whole"
    assert seen["resume_inline"], "the resume control is not on the title's meta line"
    resume = f"cd /home/max/repos/github/MaxWolf-01/agents && claude --resume {SESSION}"
    assert (seen["resume_clicked"], seen["resume_keyed"]) == (resume, resume)
    for keys in ("N", "n", "t 0 7", "[ ]", "r", "c", "y", "Y", "R", "l", "o", "O", "Ctrl Alt"):
        assert keys in seen["help"], f"the key list has no {keys}: {seen['help']}"
    assert (seen["o"], seen["oo"]) == ([True] * 4, [False] * 4), "o opens every turn, then closes every turn"
    assert {"l", "?", "R", "N", "r"} <= set(seen["held"]), f"Ctrl+Alt held shows each control's key over it: {seen['held']}"
    assert seen["let_go"] == []


def test_a_code_blocks_button_copies_its_code(rendered: tuple[Path, Path], transcript: Path) -> None:
    """A code block in the newest turn shows its copy button only once the pointer is in the
    block's top right corner, not anywhere over the code, and the button stays in that corner while
    a line too long for the block scrolls it sideways. A click copies the code short of the newline
    that ends it, so a pasted command waits for Enter, and says so."""
    page, _ = rendered
    record = page.parent / "turns" / "04.md"
    code = "make test BASE=master\nclaude --resume " + "x" * 200
    record.write_text(record.read_text().replace("## Details\n\n", f"## Details\n\n```sh\n{code}\n```\n\n", 1))
    page.write_text(render_session(page.parent, transcript))
    seen = probe(page, "copy-code")
    assert seen["hidden"] == "0" and seen["over_code"] == "0", f"the button shows outside the corner: {seen}"
    assert seen["in_corner"] == "1", "the pointer in the corner does not show the button"
    assert seen["scrolled"] > 0, "the long line does not scroll the block, so the check proves nothing"
    assert not seen["moved"], "the button scrolled with the code"
    right, top = seen["corner"]
    assert 0 < right < 20 and 0 < top < 20, f"the button is not in the block's top right corner: {seen['corner']}"
    assert seen["copied"] == code


def test_a_turn_copies_as_its_markdown_by_its_button_and_by_y(rendered: tuple[Path, Path]) -> None:
    """A turn's copy button shows only while the pointer is on the turn, and a click copies the turn's record as
    written without opening the turn, the cursor going to it. y copies the newest turn's record while the cursor is on
    no turn, and the cursor's turn once it is on one; Y copies the whole session. Each key says what it copied."""
    page, _ = rendered
    directory = page.parent
    record = lambda n: (directory / "turns" / f"{n}.md").read_text()
    seen = probe(page, "copy-turn")
    assert (seen["hidden"], seen["over_turn"]) == ("0", "1"), f"the button does not show on the turn alone: {seen}"
    assert seen["clicked"] == record("03") and seen["opened_by_click"] is False
    assert (seen["m_newest"], seen["m_toast"]) == (record("04"), "copied turn 04 as markdown")
    assert seen["m_cursor"] == record("02")
    names = ["session.md", *(f"turns/{n:02d}.md" for n in range(1, 5))]
    assert seen["M"] == "\n\n".join((directory / n).read_text().strip() for n in names) + "\n"
    assert seen["M_toast"] == "copied the session as markdown"


def test_c_copies_the_link_or_code_under_the_pointer(rendered: tuple[Path, Path], transcript: Path) -> None:
    """Every link and code span shows the key that copies it while the pointer is on it, and c copies
    it: a path written as code as the turn shows it, `:line` and all; other code, inline or a fenced
    block, as its text short of the newline that ends it; a URL as it is, the pointer on code inside
    its link too; a link to a file on this machine as that file's path. A link to a place on the page,
    or the pointer elsewhere, copies nothing and says so, and a link Tab focused takes the key
    without the pointer."""
    page, root = rendered
    record = page.parent / "turns" / "04.md"
    url = "https://example.org/a?b=1"
    block = "make test BASE=master\nmake check"
    details = (f"See `{ARTEFACTS[0]}:3`, run `make test-all`, read {url}, [`T-12`]({url}12), [the plan]({ARTEFACTS[1]}) and [turn 03](#t03).\n\n"
               f"```sh\n{block}\n```\n\n")
    record.write_text(record.read_text().replace("## Details\n\n", f"## Details\n\n{details}", 1))
    page.write_text(render_session(page.parent, transcript))
    expected = {
        "#t04 a.path": f"{ARTEFACTS[0]}:3",
        '#t04 code:text-is("make test-all")': "make test-all",
        f'#t04 a:text-is("{url}")': url,
        '#t04 a code:text-is("T-12")': f"{url}12",
        '#t04 a:text-is("the plan")': str(root / ARTEFACTS[1]),
        "#t04 .code pre": block,
    }
    seen = probe(page, "copy-under-pointer", targets=list(expected), in_page='#t04 a:text-is("turn 03")')
    assert seen["hovered"] == {target: ["c copy", text] for target, text in expected.items()}
    assert seen["hint_in_page"] is None and seen["toast_in_page"] == "no link or code under the pointer"
    assert seen["hint_away"] is None, "the hint stayed after the pointer left"
    assert seen["toast"] == "no link or code under the pointer"
    assert seen["copied_focused"] == f"{ARTEFACTS[0]}:3"


def test_a_reload_with_a_turn_added_keeps_the_readers_place(long_session: tuple[Path, Path]) -> None:
    """P1, P2, P3, P5: the reader clicks turn 03's number in the timeline, which leaves #t03 in the
    address, opens turn 05 and scrolls on with the wheel, which marks the turn at the top of the
    pane in the timeline. A reload with turn 13 added leaves them on the same block at the same
    offset, with the same turns open and the new one open as rendered, not on turn 03. The control
    is marked until turn 13 has been in view, and n takes the reader to it. A page opened with #t03
    in its address reveals turn 03."""
    page, after = long_session
    seen = probe(page, "reload", file=str(page), after=str(after), wheel=900)
    assert seen["hash"] == "#t03"
    before = seen["before"]
    assert not (before["anchor"] == "t03" and abs(before["into"]) < 20), f"the wheel left the reader on turn 03's top: {before}"
    assert before["anchor"].startswith("t") and before["row"] == "a" + before["anchor"][1:], f"P5: the timeline marks {before['row']}"
    assert seen["control_before"]["fresh"] is False
    now = seen["after"]
    assert seen["hash_after"] == "#t03", "the reload dropped the fragment, so the check proves nothing about it"
    assert now["anchor"] == before["anchor"] and abs(now["into"] - before["into"]) <= 3, f"P1: {before} became {now}"
    assert sorted(now["open"]) == sorted([*before["open"], "t13"]), f"P1: open {before['open']} became {now['open']}"
    assert now["cur"] == before["cur"]
    assert seen["control_after"]["fresh"] is True and "13" in seen["control_after"]["text"], f"P3: {seen['control_after']}"
    assert seen["control_short_of_it"]["fresh"] is True, "P3: the control was cleared before turn 13 was in view"
    newest = seen["newest"]
    assert newest["anchor"] == "t13" and newest["scrollTop"] <= 1 and "t13" in newest["open"], f"n: {newest}"
    assert newest["control"]["fresh"] is False, "P3: turn 13 is in view and the control is still marked"
    arrived = seen["arrived"]
    assert arrived["anchor"] == "t03" and abs(arrived["into"]) <= 7 and "t03" in arrived["open"], f"P2: {arrived}"


def test_a_reader_caught_up_follows_a_new_turn_and_one_reading_back_stays(
    long_session: tuple[Path, Path], chatted: Path
) -> None:
    """A reader scrolled into the newest turn, turn 12, is caught up: a reload with turn 13 added
    takes them to the top, onto turn 13, and leaves nothing marked. A reader further back when a
    chat turn arrives stays on the block they were reading, the control marked and naming the chat
    turn, and n takes them to it."""
    page, after = long_session
    seen = probe(page, "follow", file=str(page), after=str(after), chatted=str(chatted))
    assert seen["caught_up"]["anchor"] == "t12" and seen["caught_up"]["scrollTop"] > 0, seen["caught_up"]
    followed = seen["followed"]
    assert followed["anchor"] == "t13" and followed["scrollTop"] <= 1, f"the caught-up reader stayed: {followed}"
    assert followed["control"]["fresh"] is False, followed
    back, stayed = seen["back"], seen["stayed"]
    assert back["anchor"] not in ("t13", "t12"), f"the wheel left the newest turns in view: {back}"
    assert stayed["anchor"] == back["anchor"] and abs(stayed["into"] - back["into"]) <= 3, f"{back} became {stayed}"
    assert stayed["control"]["fresh"] is True and "chat" in stayed["control"]["text"], stayed["control"]
    newest = seen["newest"]
    assert newest["anchor"].startswith("chat-") and newest["scrollTop"] <= 1, f"n: {newest}"
    assert newest["control"]["fresh"] is False, newest


def test_t_and_a_turns_number_go_to_that_turn(long_session: tuple[Path, Path]) -> None:
    """P6 on a page of twelve turns: t12 and t05 go at once, t9 too since no number extends 9, t1
    waits, as 10 to 12 extend it, until Enter goes to turn 01; t00 names no turn and goes nowhere.
    Each turn it goes to opens. In a window too short for the timeline, its row is scrolled into the
    timeline's view. P4: a click on the number of a turn that links nothing, or on its headline in the
    timeline, goes to that turn."""
    page, _ = long_session
    probed = probe(page, "number")
    seen = probed["typed"]
    for keys, turn in (("t 1 2", "t12"), ("t 0 5", "t05"), ("t 9", "t09")):
        assert seen[keys]["cur"] == turn and turn in seen[keys]["open"], f"{keys}: {seen[keys]}"
        assert seen[keys]["anchor"] == turn or seen[keys]["scrollTop"] > 0, f"{keys} did not scroll to {turn}: {seen[keys]}"
    assert seen["t 1"]["cur"] == "t09" and seen["t 1"]["toast"] == "turn 1…", seen["t 1"]
    assert seen["Enter"]["cur"] == "t01" and "t01" in seen["Enter"]["open"], seen["Enter"]
    assert seen["t 0 0"]["cur"] == "t01" and seen["t 0 0"]["toast"] == "no turn 00", seen["t 0 0"]
    for target, turn in (("#a07 .turn-ref", "t07"), ("#a08 .hl", "t08")):
        at = probed[target]
        assert at["anchor"] == turn and at["cur"] == turn and turn in at["open"], f"P4: {target} went to {at}"
    short = probed["short"]
    assert short["overflows"], "the timeline fits the short window, so nothing there needs scrolling"
    assert short["column"]["top"] <= short["row"]["top"] and short["row"]["bottom"] <= short["column"]["bottom"], short


@pytest.mark.parametrize("width", (WIDTHS[0], WIDTHS[-1]))
def test_a_prompt_shows_its_size_at_a_wide_window_and_in_the_hub_sidebar(rendered: tuple[Path, Path], width: int) -> None:
    """session-page-keys-and-sizes: each prompt shows its size in bytes, in a wide window and at the hub sidebar's width."""
    page, _ = rendered
    sizes = probe(page, "prompt_size", width=width)["sizes"]
    assert sizes and all(not glyph and re.fullmatch(r"\d+(\.\d)? [kM]?B", s) for glyph, s in sizes), sizes


@pytest.mark.parametrize("width", WIDTHS)
def test_the_panes_hold_at_every_width(long_session: tuple[Path, Path], width: int) -> None:
    """P3, P7 and what-waits-on-you-rethought's layout, at each width the hub shows the page at: the
    window never scrolls and no pane shows a scrollbar. Where three columns fit, the turns, the tasks
    and the timeline sit side by side, each full height; narrower, the tasks sit over the timeline
    right of the turns; on a phone the page opens on the tasks and the bar's button shows the turns.
    The control to the newest turn is in view with the pane at either end, G takes the timeline to
    its end and g g to its top, and no row of the tasks changes height when it takes the focus."""
    page, _ = long_session
    seen = probe(page, "layout", width=width)
    assert seen["window"] == [0, 0, 0, 0], f"P7: the window scrolled: {seen['window']}"
    assert seen["scrollbars"] == [], f"P7: these show a scrollbar: {seen['scrollbars']}"
    assert seen["pane_at_end"], "the turns never scrolled to their end"
    assert seen["control_top"] and seen["control_top"]["inView"], f"P3 at the top: {seen['control_top']}"
    assert seen["control_bottom"] and seen["control_bottom"]["inView"], f"P3 at the bottom: {seen['control_bottom']}"
    assert seen["timeline_at_end"] and seen["timeline_at_top"] == 0, "G and g g take the timeline to its ends"
    assert seen["row_heights_focused"] == seen["top"]["rows"], "a row changed height as it took the focus"
    for moment in ("top", "bottom"):
        at = seen[moment]
        tasks, pane, column = at["tasks"], at["pane"], at["column"]
        assert at["firstTurnBorder"] == "0px", "the first turn draws a rule under the title's"
        assert pane["shown"] and pane["bottom"] >= at["height"] - 1, f"{moment}: {at}"
        if width >= 1180:
            assert pane["right"] <= tasks["left"] + 1 and tasks["right"] <= column["left"] + 1, f"{moment}: three columns: {at}"
            assert tasks["bottom"] >= at["height"] - 1 and column["bottom"] >= at["height"] - 1 and not at["toggle"]["shown"], f"{moment}: {at}"
        elif width > 704:
            assert pane["right"] <= tasks["left"] + 1 and abs(tasks["left"] - column["left"]) < 2, f"{moment}: {at}"
            assert tasks["bottom"] <= column["top"] + 1 and column["bottom"] >= at["height"] - 1, f"{moment}: the tasks over the timeline: {at}"
        else:
            assert not tasks["shown"] and not column["shown"] and at["toggle"]["shown"], f"{moment}: the turns alone: {at}"
    if width <= 704:
        first = seen["tasks_view"]
        assert first["tasks"]["shown"] and first["column"]["shown"] and not first["pane"]["shown"], f"the page opens on the tasks: {first}"


@pytest.mark.parametrize("width", WIDTHS)
def test_the_row_gone_to_is_in_view_and_its_card_opens_alone_in_a_crowded_column(crowded: Path, width: int) -> None:
    """With fourteen questions waiting, each with a card longer than a screen, ] goes into the tasks
    on the first row and on through them: the sixth is in the column's view, and Enter opens its
    card alone, holding the keys, its headline in view."""
    seen = probe(crowded, "crowded", width=width, presses=6)
    assert seen["row"]["inView"] and seen["row"]["rows"] == 1, seen["row"]
    assert (seen["id"], seen["shown"], seen["focused"]) == (seen["row"]["handle"].lower(), 1, True), seen
    assert seen["title"]["top"] >= 0 and seen["title"]["bottom"] <= seen["height"], f"out of view: {seen}"


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("kind", ["record", "chat"])
def test_a_wide_table_spreads_past_the_text_and_stays_in_its_turn(
    kind: str, width: int, request: pytest.FixtureRequest
) -> None:
    """A table too wide for the text's measure spreads past the text rather than wrap its cells, as
    far as the room the turn has: never left of the turn's edge, where the current turn's mark runs,
    nor past the pane's. At a wide window it fits on one line a row, having spread left of the text
    too. A narrow table stays at the text's start. A chat turn's reply lays its tables out the same
    as a turn record's Details."""
    if kind == "record":
        seen = probe(request.getfixturevalue("tabled"), "tables", width=width, turn="#t05", text=".turn-body .prose")
    else:
        seen = probe(request.getfixturevalue("chat_tabled"), "tables", width=width, turn=".turn.chat", text=".reply")
    (wide, narrow), turn, text, pane = seen["tables"], seen["turn"], seen["text"], seen["pane"]
    assert wide["left"] >= turn["left"] - 1, f"the table runs over the current turn's mark: {seen}"
    assert wide["right"] <= pane["right"] + 1, f"the table runs past the pane: {seen}"
    if width == WIDTHS[0]:
        assert not wide["wraps"] and wide["left"] < text["left"] - 1, f"the table did not spread past the text: {seen}"
    assert abs(narrow["left"] - text["left"]) <= 1, f"the narrow table left the text's start: {seen}"


READ_LINES = [f"def line_{n}(): return {n}\n" for n in range(1, 400)]  # far more than a step shows before "show all"


def worked(transcript: Path, out: Path) -> Path:
    """The worked example's transcript with turn 04's work: a Bash call, an Edit of a CSS file and a
    long Read of a Python file; and in turn 03 a thinking block that kept its text and one that did not."""
    def did(at: str, *blocks: dict) -> str:
        return json.dumps({"type": "assistant", "timestamp": at, "message": {"content": list(blocks)}})

    def came_back(at: str, id: str, text: str) -> str:
        return json.dumps({"type": "user", "timestamp": at, "message": {"content": [{"type": "tool_result", "tool_use_id": id, "content": text}]}})

    edit = {"file_path": "/repo/page.css", "old_string": ".bar { color: red; }", "new_string": ".bar { color: green; }"}
    lines = [
        did("2026-09-22T22:05:00Z", {"type": "thinking", "thinking": "", "signature": "x"}),
        did("2026-09-22T22:06:00Z", {"type": "thinking", "thinking": "The grid wants a leading word.", "signature": "x"}),
        did("2026-09-23T01:21:00Z", {"type": "tool_use", "id": "b", "name": "Bash", "input": {"command": "make test BASE=master", "description": "Run the suite"}}),
        came_back("2026-09-23T01:21:09Z", "b", "321 passed"),
        did("2026-09-23T01:22:00Z", {"type": "tool_use", "id": "e", "name": "Edit", "input": edit}),
        came_back("2026-09-23T01:22:01Z", "e", "The file /repo/page.css has been updated."),
        did("2026-09-23T01:23:00Z", {"type": "tool_use", "id": "r", "name": "Read", "input": {"file_path": "/repo/lines.py"}}),
        came_back("2026-09-23T01:23:01Z", "r", "".join(f"{n:6}→{line}" for n, line in enumerate(READ_LINES, start=1))),
    ]
    out.write_text(transcript.read_text() + "".join(line + "\n" for line in lines))
    return out


def test_the_log_opens_on_demand_on_the_focused_turns_tool_calls(rendered: tuple[Path, Path], transcript: Path, tmp_path: Path) -> None:
    """show-a-turns-tool-calls-on-demand: closed, the page shows no log and has loaded none of it. l
    opens the newest turn's calls in order, one line each, and the log follows j and k. A Bash call
    shows its command highlighted as shell, an Edit its old and new text as a diff highlighted by
    the file's extension, a long Read is cut short, its line numbers dropped, and shows whole on
    demand. Thinking shows where the transcript kept its text. A call shows the bytes of the request it wrote and of the result it read, their tokens on hover. Esc
    closes it, the control opens it, l closes it."""
    page, _ = rendered
    write_page(read_session(page.parent, worked(transcript, tmp_path / "t.jsonl")), datetime.now())
    seen = probe(page, "log")
    assert seen["closed"] == {"open": False, "which": None, "steps": [], "loaded": False}
    newest = seen["newest"]
    assert newest["open"] and newest["loaded"] and newest["which"].startswith("turn 04 · "), newest
    assert newest["steps"][:3] == [["ran", "Run the suite"], ["edited", "/repo/page.css"], ["read", "/repo/lines.py"]]
    assert [verb for verb, _ in newest["steps"][3:]] == ["wrote"], "the Write of record 04 comes last"
    assert seen["after_jj"]["which"].startswith("turn 03 · ")
    assert [s for s in seen["after_jj"]["steps"] if s[0] == "thinking"] == [["thinking", "The grid wants a leading word."]]
    bash, ran = seen["bash"]
    assert (bash["lang"], bash["text"], bash["lit"], ran["text"]) == ("bash", "make test BASE=master", True, "321 passed")
    assert seen["bash_size"] == [["#g-wrote", "65 B"], ["#g-read", "10 B"]], "the result it consumed and the request it produced, as compact JSON"
    assert seen["bash_tip"] == "the request it wrote: 65 bytes, ≈17 tokens\nthe result it read: 10 bytes, ≈3 tokens", "the detail, on hover"
    old, new, _ = seen["edit"]
    assert (old["cls"], old["lang"], old["text"], old["lit"]) == ("code del", "css", ".bar { color: red; }", True)
    assert (new["cls"], new["lang"], new["text"], new["lit"]) == ("code add", "css", ".bar { color: green; }", True)
    [read] = seen["read"]
    assert (read["lang"], read["more"]) == ("python", True) and read["text"].startswith(READ_LINES[0])
    assert len(read["text"]) < len("".join(READ_LINES)) / 2
    assert seen["read_whole"] == len("".join(READ_LINES))
    assert (seen["escaped"], seen["clicked"], seen["closed_again"]) == (False, True, False)

def test_the_log_shows_the_turn_under_way_as_its_calls_come_in(rendered: tuple[Path, Path], transcript: Path, tmp_path: Path) -> None:
    """With no turn picked, the open log shows the turn under way's calls, a running one's time
    still moving, and a call the live hook adds shows without a reload. A picked turn shows its own; k on the newest
    turn goes on to the turn under way, j back, and the head holds no button for either, nor one to close it; once
    the turn ends, the log falls back."""
    page, _ = rendered
    write_page(read_session(page.parent, worked(transcript, tmp_path / "t.jsonl")), datetime.now())
    at = datetime.now(UTC).isoformat()

    def calls(*steps: tuple[str, str | None]) -> str:
        return PREFIX + json.dumps({"prompt": "make the log live", "steps": [
            {"kind": "command", "tool": "Bash", "verb": "ran", "subject": what, "input": {"command": what}, "output": "",
             "failed": False, "at": at, "done": done, "id": what} for what, done in steps]}) + "\n"

    seen = probe(page, "live", live=str(page.parent / LIVE), first=calls(("make test", at)),
                 second=calls(("make test", at), ("make check", None)))
    assert seen["first"] == {"which": "under way · make the log live", "buttons": ["open all"], "steps": [["ran", "make test", False]]}
    assert seen["second"]["steps"] == [["ran", "make test", False], ["ran", "make check", True]]
    assert seen["turn"]["which"].startswith("turn 04 ") and seen["turn"]["buttons"] == ["open all"]
    assert seen["back"] == seen["second"], "k on the newest turn goes on to the turn under way"
    assert seen["newest_again"]["which"] == seen["turn"]["which"], "and j goes back to the newest turn"
    assert not seen["ended"]["which"].startswith("under way")



def test_the_log_takes_the_keys_to_walk_open_and_close_its_steps(rendered: tuple[Path, Path], transcript: Path, tmp_path: Path) -> None:
    """Tab hands the keys to the open log: j and k walk its steps, o opens the one they are on, O
    opens or closes them all, g g and G go to the first and last; Tab hands them back, O still opens or closes the
    steps, and j moves the turns again. A click on a step hands the keys over on that step; the head's control opens or
    closes them all."""
    page, _ = rendered
    write_page(read_session(page.parent, worked(transcript, tmp_path / "t.jsonl")), datetime.now())
    seen = probe(page, "log_keys")
    n = len(seen["O"]["open"])
    assert n == 4 and seen["opened"] == {"which": "turn 04", "keyed": False, "cur": -1, "open": [], "all": "open all"}
    assert (seen["tab"]["keyed"], seen["tab"]["cur"]) == (True, 0)
    assert seen["jj"]["cur"] == 2 and seen["jj"]["which"] == "turn 04", "j walks the steps, not the turns"
    assert seen["o"]["open"] == [2]
    assert (seen["k"]["cur"], seen["k"]["open"]) == (1, [2])
    assert seen["O"]["all"] == "close all" and seen["OO"] == {**seen["OO"], "open": [], "all": "open all"}
    assert (seen["G"]["cur"], seen["gg"]["cur"]) == (n - 1, 0)
    assert (seen["back"]["keyed"], seen["back"]["cur"], seen["back"]["which"]) == (False, -1, "turn 04")
    assert (seen["O_unkeyed"]["keyed"], seen["O_unkeyed"]["open"]) == (False, list(range(n))), "O opens them all with the keys on the turns too"
    assert seen["j_turns"]["which"] == "turn 03"
    assert (seen["clicked"]["keyed"], seen["clicked"]["cur"], seen["clicked"]["open"]) == (True, 1, [1])
    assert seen["all_clicked"]["all"] == "close all"



def test_the_keys_stage_each_kind_of_item_and_the_review_shows_the_batch(waiting_page: Path) -> None:
    """work-through-what-waits-one-item-at-a-time#P2, #P4 and #P5, in the tasks of
    what-waits-on-you-rethought, on a page no hub frames: ] goes into the tasks, a letter picks and
    takes it back, d and x a to-do's, u clears, s marks an artefact seen and o opens it, marking
    nothing; n a note that stays on the row it was opened on even with a ] typed in it, Esc in a note
    drops the edit; a reload keeps it all; Enter opens a card; r reviews the batch, an artefact named
    by its record's path and `seen`, and Enter copies it, since no hub sends it; Esc leaves the
    review, the dialog, then the tasks; n with no item in focus says so; and r from the turns opens
    the review in one key."""
    seen = probe(waiting_page, "stage")
    (into, picked, over, unpicked, taken, noted, todo, dismissed, done, cleared, redone, looked, opened, looked_noted, dropped,
     seen_too, reloaded, review, copied, back, left, out, turns, no_item, reviewed) = (s for _, s in seen["steps"])
    assert [s["row"] for s in (into, picked, over, unpicked, taken, noted)] == ["Q1"] * 6 and into["inBand"], seen["steps"][:6]
    assert (picked["picked"], over["picked"], unpicked["picked"], taken["picked"]) == (["b"], ["a"], [], ["a"])
    assert noted["note"] == "Your note\nonly after Friday]", noted
    assert todo["row"] == "A1" and [s["act"] for s in (dismissed, done, cleared, redone)] == [["dismissed"], ["done"], [], ["done"]]
    assert looked["row"] == "agent/show/lint/texts.html" and looked["seen"] == "Seen", looked
    assert opened["seen"] == "Seen" and opened["inBand"], opened
    assert looked_noted["note"] == "Your note\nthe legend is wrong", looked_noted
    assert dropped["row"] == "agent/show/lint/diff.html" and dropped["note"].startswith("Add a note"), "Esc kept the note it was to drop"
    assert seen_too["seen"] == "Seen"
    assert reloaded["staged"] == ["Q1", "A1", "agent/show/lint/texts.html", "agent/show/lint/diff.html"] and reloaded["badge"] == "4", reloaded
    assert reloaded["card"] == "q1", reloaded
    batch = "Q1: a, only after Friday]\nA1: done\nagent/show/lint/texts.html: seen, the legend is wrong\nagent/show/lint/diff.html: seen"
    assert review["review"] == batch and seen["copied"] == batch, (review, seen["copied"])
    assert review["stays"] == "Every item has an answer, or was seen.", review["stays"]
    assert back["review"] is None and back["card"] == "q1", back
    assert left["card"] is None and left["inBand"], left
    assert not out["inBand"] and not turns["inBand"], (out, turns)
    assert reviewed["review"] == batch, reviewed


def test_in_a_hub_tab_the_staging_is_the_hubs_and_the_send_takes_the_lines_it_sent_off_the_tasks(waiting_page: Path) -> None:
    """#P2 and #P3 at the page's seam with the hub tab: what the hub kept is staged on load, a note on
    an item this render no longer shows among it; nothing goes before the review's Enter, which shows
    the batch with the box's words below it, as they stand when the box last changed; once the hub
    sent it, the lines it sent leave the tasks and the staging, and one it left out (A1's) stays
    staged; the tasks start again at the first item still waiting, the keys in them."""
    staged = {"Q1": {"pick": "b", "note": "kept by the hub"}, "agent/show/old/fig.html": {"note": "the axis is off"}}
    kept = {"staged": staged, "seen": [], "sent": {}}
    seen = probe(waiting_page, "framed", root=str(waiting_page.parent), tab=hub_tab(waiting_page, kept), send=True, keys=["]", "]", "d", "r"])
    assert seen["loaded"]["picked"] == ["b"] and seen["loaded"]["note"] == "Your note\nkept by the hub", seen["loaded"]
    message = "Q1: b, kept by the hub\nA1: done\nagent/show/old/fig.html: the axis is off\n\nand go on"
    assert seen["typed"] == message[: -len(" on")] and seen["review"] == message and seen["before"] is None, seen
    assert seen["reviewing"] and not seen["reviewing_after"], "the hub's box reads whether the review is open to send what it shows"
    assert seen["stays"] == "Not answered, so they stay: The six PR texts, The stack's diff", seen["stays"]
    assert seen["sent"] == "Q1: b, kept by the hub\nagent/show/old/fig.html: the axis is off\n\nand go on", seen["sent"]
    assert seen["saved"]["staged"] == {"A1": {"act": "done"}} and set(seen["saved"]["sent"]) == {"Q1"}, seen["saved"]
    after = seen["after"]
    assert (after["shown"], after["staged"], after["row"], after["badge"]) == (
        ["A1", "agent/show/lint/texts.html", "agent/show/lint/diff.html"], ["A1"], "A1", "1"), after
    assert after["inBand"] and after["scroll"] == 0, after


def test_a_sent_item_comes_back_once_a_turn_ended_after_its_send(waiting_page: Path) -> None:
    """A sent item stays off the tasks until a turn that ended after the send is on the page, which
    says whether it settled: Q1, sent before record 01 ended, waits again; A1, sent after, stays off."""
    page = waiting_page.read_text()
    assert 'data-at="' in page, "record 01 carries no time it ended"
    sent = {"Q1": 1790000000000, "A1": 1890000000000}  # 2026-09-21 and 2029-11-23, around 2026-09-23T01:36Z
    tab = hub_tab(waiting_page, {"staged": {}, "seen": [], "sent": sent})
    loaded = probe(waiting_page, "framed", root=str(waiting_page.parent), tab=tab)["loaded"]
    assert loaded["shown"] == ["Q1", "agent/show/lint/texts.html", "agent/show/lint/diff.html"], loaded


def test_on_a_phone_an_artefact_and_a_turns_tool_calls_open_by_touch_and_the_tasks_say_a_turn_runs(waiting_page: Path) -> None:
    """what-waits-on-you-rethought: no key reaches anything on a phone, so an artefact opens by a tap
    on its row and a turn's tool calls by its button; the page opens on the tasks, which say a turn
    is running while the live hook's file is there."""
    calls = PREFIX + json.dumps({"prompt": "make the log live", "steps": []}) + "\n"
    seen = probe(waiting_page, "phone", live=str(waiting_page.parent / LIVE), calls=calls)
    assert seen["view"] == "tasks" and not seen["working_before"], seen
    assert seen["working"] == "A turn is running: make the log live", seen
    assert seen["opened"].endswith("agent/show/lint/texts.html"), seen
    assert seen["log"].startswith("turn 01"), seen


@pytest.mark.parametrize("width", WIDTHS)
def test_a_questions_options_read_at_every_width(waiting_page: Path, width: int) -> None:
    """On a phone an option's leads to, gives and costs, each named, stack under its words, which keep
    the card's width; wider, they sit beside the words in columns of their own. A row's tag opens the card."""
    seen = probe(waiting_page, "options", width=width)
    words, leads, gives, costs = seen["words"], seen["leads"], seen["gives"], seen["costs"]
    assert seen["shown"], "the row's tag did not open its card"
    if width <= 704:
        assert words["bottom"] <= leads["top"] + 1 and leads["bottom"] <= gives["top"] + 1 and gives["bottom"] <= costs["top"] + 1, seen
        assert words["right"] - words["left"] >= 0.8 * (seen["card"]["right"] - seen["card"]["left"]) and "gives" in seen["labelled"], seen
    else:
        assert abs(words["top"] - gives["top"]) < 2 and words["right"] <= leads["left"] + 1 <= gives["left"] + 1 <= costs["left"], seen


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
