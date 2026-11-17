# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
"""What the graph does once a browser runs it, which is the only place it does anything: the side
column's preview, the same graph at full size over the board, and the same again in a window of its
own. Every move a reader makes is made here, and what the board did with it is read off the board:
the two keys and the buttons that do the same, Escape's order, a click on the preview and on a node
in it, a drag that pans and the click it ends with, the switch in each view, a node clicked in each
full size view, the board re-rendering under the window, and the board going away."""

import json, os, shutil, sys
from pathlib import Path
from playwright.sync_api import TimeoutError, sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "show"))  # page_cache, beside render_lint
from board_probe_engine import cdn
from page_cache import default_root, serve

page_url = Path(sys.argv[1]).resolve().as_uri()
ROW, NODE, NEXT = "t-map-columns", "#t-commit-import", "#t-parse-rows"
WIDE = "(sel) => document.querySelector(sel)?.getBoundingClientRect().width ?? 0"
OVER = "(sel) => { const b = document.querySelector(sel); return b.scrollWidth - b.clientWidth }"
OPEN = "document.getElementById('gfull').classList.contains('open')"

def nodes(frame, where):
    return frame.eval_on_selector_all(where + " .pele-node", "els => els.length")

def click_node(frame, where, which):
    """The node for `which`, clicked where the graph is drawn."""
    attr = "els => els.map((a) => a.getAttribute('href') || a.getAttribute('xlink:href'))"
    hrefs = frame.eval_on_selector_all(where + " a", attr)
    assert which in hrefs, f"no node for {which} in {where}"
    frame.locator(where + " a").nth(hrefs.index(which)).click()

def named(frame, where, name):
    frame.wait_for_function("([w, n]) => document.querySelector(w)?.textContent === n", arg=[where, name])

with sync_playwright() as pw:
    # the run it belongs to, as `browsers --help` defines it
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    page = context.new_page()
    serve(context, default_root())
    failed = []
    page.on("requestfailed", lambda r: failed.append((r.url, r.failure)))
    errors = []
    page.on("pageerror", lambda e: errors.append("board: " + str(e)))

    # ?graph on the address, beside the row's anchor: the state the layout check measures. The
    # overlay paints once the drawing is done, or once the engine has failed to arrive, and every
    # step past this one that needs a drawing runs only where it arrived.
    page.goto(f"{page_url}?theme=night&graph=1#{ROW}")
    page.evaluate("document.fonts.ready")
    page.wait_for_selector("#gfull .gsvg svg, #gfull .gnote:not([hidden])")
    out = {"cdn": cdn(failed),
           "ground": page.evaluate("getComputedStyle(document.body).backgroundColor"),
           "font": page.evaluate("getComputedStyle(document.getElementById('gname')).fontFamily"),
           "node": NODE}
    drawn = out["cdn"]
    PAINTED = ".gsvg svg" if drawn else ".gnote:not([hidden])"
    out["from_the_address"] = {"open": page.is_visible("#gfull"), "nodes": nodes(page, "#gfull .gsvg"),
                               "name": page.inner_text("#gfull .gname"), "note": page.inner_text("#gfull .gnote")}
    if drawn:
        out["preview_width"] = page.evaluate(WIDE, ".side .g:not([hidden]) .mermaid svg")

    # the whole tracker at full size, dragged to pan, then a node
    page.click("#gfull [data-gmode=all]")
    named(page, "#gfull .gname", "whole tracker")
    over = {"name": page.inner_text("#gfull .gname"), "note": page.inner_text("#gfull .gnote")}
    if drawn:
        page.wait_for_selector("#gfull .gsvg .pele-node.cur")
        over |= {"width": page.evaluate(WIDE, "#gfull .gsvg svg"),
                 "nodes": nodes(page, "#gfull .gsvg"), "overflow": page.evaluate(OVER, "#gfull .gfbody"),
                 "marked": page.eval_on_selector_all("#gfull .gsvg .pele-node.cur", "els => els.map((n) => n.dataset.id)"),
                 "titles": page.eval_on_selector_all("#gfull .gsvg .pele-node title", "els => els.length"),
                 "viewbox": page.evaluate("() => { const v = document.querySelector('#gfull .gsvg svg').viewBox.baseVal; return [v.width, v.height] }"),
                 "drawn": page.evaluate("() => { const b = document.querySelector('#gfull .gsvg svg').getBoundingClientRect(); return [b.width, b.height] }")}
        # narrowed first, so the drag has something to move whatever the fixture's
        # labels are as wide as: the check is that a drag pans, not that this
        # tracker's graph happens to overflow the window this probe opens in
        page.set_viewport_size({"width": 700, "height": 950})
        page.wait_for_function("document.querySelector('#gfull .gfbody').scrollWidth > document.querySelector('#gfull .gfbody').clientWidth")
        over["overflow"] = page.evaluate(OVER, "#gfull .gfbody")
        box = page.evaluate("() => { const b = document.querySelector('#gfull .gfbody').getBoundingClientRect(); return {x: b.x, y: b.y, w: b.width, h: b.height} }")
        page.mouse.move(box["x"] + box["w"] * 0.8, box["y"] + box["h"] * 0.5)
        page.mouse.down()
        page.mouse.move(box["x"] + 3, box["y"] + box["h"] * 0.5, steps=12)  # out over the backdrop
        page.mouse.up()
        over["panned"] = page.evaluate("document.querySelector('#gfull .gfbody').scrollLeft")
        over["open_after_pan"] = page.is_visible("#gfull")
        over["grabbing"] = page.evaluate("document.querySelector('#gfull .gfbody').classList.contains('panning')")
        click_node(page, "#gfull .gsvg", NODE)
        over["open_after_node"] = page.is_visible("#gfull")
        over["cursor"] = page.evaluate("document.querySelector('.ticket.kcur')?.id")
    else:
        page.click("#gclose")
        over["open_after_close"] = page.is_visible("#gfull")
    out["overlay"] = over

    # the two keys, and Escape taking the overlay before the open row
    page.keyboard.press("f")
    page.wait_for_selector("#gfull " + PAINTED)
    keys = {"f_opened": page.is_visible("#gfull")}
    page.keyboard.press("Escape")
    keys["esc_closed"] = not page.is_visible("#gfull")
    keys["row_still_open"] = page.evaluate(f"!!document.getElementById('{ROW}')?.open")
    out["keys"] = keys

    # the buttons that do what the two keys do, clicked: the preview's `full` and `window`, and
    # the overlay's `window`, which takes the overlay down as the window comes up
    page.click("#gopen")
    page.wait_for_selector("#gfull " + PAINTED)
    buttons = {"full_opened": page.is_visible("#gfull")}
    with page.expect_popup() as popped:
        page.click("#gwinfull")
    popped.value.wait_for_selector(".gfbody")
    buttons |= {"overlay_closed": not page.is_visible("#gfull"), "from_overlay": popped.value.title()}
    popped.value.close()
    with page.expect_popup() as popped:
        page.click("#gwinopen")
    popped.value.wait_for_selector(".gfbody")
    buttons["from_preview"] = popped.value.title()
    popped.value.close()
    out["buttons"] = buttons

    # the preview: a click opens the full size view, a click on a node in it goes to that row
    page.click(".side .g:not([hidden]) .mermaid" if drawn else "#gunloaded", position={"x": 3, "y": 3})
    page.wait_for_selector("#gfull " + PAINTED)
    preview = {"click_opened": page.is_visible("#gfull")}
    page.keyboard.press("Escape")
    if drawn:
        click_node(page, ".side .g:not([hidden]) .mermaid", NEXT)
        # a preview node is a link, so the board follows it through the address rather than at once
        page.wait_for_function(f"document.querySelector('.ticket.kcur')?.id === '{NEXT[1:]}'")
        preview["node_opened"] = page.is_visible("#gfull")
        preview["node_cursor"] = page.evaluate("document.querySelector('.ticket.kcur')?.id")
    out["preview"] = preview

    # the window of its own, opened with the other key
    with page.expect_popup() as popped:
        page.keyboard.press("w")
    win = popped.value
    win.on("pageerror", lambda e: errors.append("window: " + str(e)))
    win.set_viewport_size({"width": 900, "height": 620})
    win.wait_for_selector(".gfbody .pele-node.cur" if drawn else ".gfbody " + PAINTED)
    window = {"title": win.title(), "scheme": win.evaluate("document.documentElement.dataset.theme"),
              "ground": win.evaluate("getComputedStyle(document.body).backgroundColor"),
              "font": win.evaluate("getComputedStyle(document.querySelector('.gname')).fontFamily"),
              "name": win.inner_text(".gname"), "note": win.inner_text(".gfbody .gnote")}
    if drawn:
        window |= {"width": win.evaluate(WIDE, ".gfbody svg"),
                   "nodes": nodes(win, ".gfbody"), "overflow": win.evaluate(OVER, ".gfbody"),
                   "titles": win.eval_on_selector_all(".gfbody .pele-node title", "els => els.length"),
                   "marked": win.eval_on_selector_all(".gfbody .pele-node.cur", "els => els.length")}
    win.click("[data-gmode=tree]")  # the board is on the whole tracker, so this is a change in both
    named(win, ".gname", "csv-import")
    window["switched"] = win.inner_text(".gname")
    window["board_name"] = page.inner_text("#gname")
    if drawn:
        click_node(win, ".gfbody", NODE)
        page.wait_for_function(f"document.querySelector('.ticket.kcur')?.id === '{NODE[1:]}'")
        window["cursor"] = page.evaluate("document.querySelector('.ticket.kcur')?.id")
        window["still_open"] = not win.is_closed()
        # The window follows the board's cursor without redrawing: the cursor goes straight to the row
        # of another live node in the drawing, which is a row of the tree on show, through the row's
        # anchor. A ghost node can be a row of another tree, whose graph is a different drawing.
        win.evaluate("document.querySelector('.gfbody .gsvg svg').dataset.probe = 'before'")  # gone with a drawing put in its place
        target = win.evaluate("document.querySelector('.gfbody .pele-node:not(.cur):not(.ghost) a')?.getAttribute('href')")
        assert target, "no other live node in the drawing for the cursor to move to"
        page.evaluate("(href) => { location.hash = href }", target)
        page.wait_for_function("(id) => document.querySelector('.ticket.kcur')?.id === id", arg=target[1:])
        win.wait_for_selector(f'.gfbody .pele-node.cur a[href="{target}"]')
        window["follows_cursor"] = win.eval_on_selector_all(".gfbody .pele-node.cur", "els => els.length")
        window["same_drawing"] = win.evaluate("document.querySelector('.gfbody .gsvg svg').dataset.probe") == "before"
    window["html"] = win.evaluate("document.documentElement.outerHTML")
    out["window"] = window

    # the re-render every tracker change triggers, under a window that has to find the board again
    page.reload()
    # the board is the only page that writes to the window, so a message from here on is the reloaded board's
    win.evaluate("() => { window.heardSinceReload = 0; addEventListener('message', () => heardSinceReload++) }")
    page.evaluate("document.fonts.ready")
    page.keyboard.press("Escape")
    page.wait_for_selector(f"#{ROW} > summary")
    page.click(f"#{ROW} > summary")
    if drawn:
        win.wait_for_selector(".gfbody .pele-node.cur")
        click_node(win, ".gfbody", NEXT)
        page.wait_for_function(f"document.querySelector('.ticket.kcur')?.id === '{NEXT[1:]}'")
    else:
        win.click("[data-gmode=all]")
        named(page, "#gname", "whole tracker")
    # The window marks itself orphaned after three seconds of silence and looks again each second,
    # and a loaded host can take that long to draw the reloaded board: what it says once it has
    # heard from that board is the answer. One that never hears from it is orphaned by the end.
    try:
        win.wait_for_function("heardSinceReload > 0 && document.documentElement.dataset.orphan === ''", timeout=30_000)
    except TimeoutError:
        pass
    out["after_reload"] = {"orphan": win.evaluate("document.documentElement.dataset.orphan"),
                           "cursor": page.evaluate("document.querySelector('.ticket.kcur')?.id"),
                           "board_name": page.inner_text("#gname")}

    # the board gone: a window that says so rather than one that looks live
    page.close()
    win.wait_for_function("document.documentElement.dataset.orphan === '1'", timeout=10_000)
    out["orphan_says"] = win.inner_text(".gorphan")
    out["errors"] = errors
    browser.close()
print(json.dumps(out))
