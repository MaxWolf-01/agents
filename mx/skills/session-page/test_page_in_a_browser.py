# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro", "pyyaml", "markdown-it-py"]
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
between, a turn added. test_session_page.py checks what the timeline and the chips list; this
checks what the reader sees of them and what the keys do. The page's remote fonts are answered
from copies kept on this machine (show/page_cache.py), so a run after the first touches no network.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from session_checks import SESSION
from session_page import PAGE, render_session

SHOW = Path(__file__).resolve().parents[1] / "show"

ARTEFACTS = (
    "agent/show/session-page/round-1/index.html",
    "agent/show/session-page/round-2/index.html",
    "agent/show/session-page/round-3/pages.html",
    "agent/show/session-page/round-3/spec.html",
)
# The widths the hub shows a session page at, the first being a wide window's, the last the
# hub sidebar's, where the timeline is a sheet.
WIDTHS = (1600, 1240, 900, 530)

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
        page.wait_for_function("document.querySelector('#toast').textContent.startsWith('copied: ')", timeout=5000)
        out["copied"] = page.evaluate("navigator.clipboard.readText()")
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
        page.keyboard.press("n")
        settle(page)
        out["newest"] = {**page.evaluate(PLACE), "control": page.evaluate(CONTROL)}
        # a navigation that arrives with a fragment reveals it
        context, page = open_page(1280, 700, page_url + "#t03")
        settle(page)
        out["arrived"] = page.evaluate(PLACE)

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

    elif scenario == "layout":
        # P3, P7, P8 at one width: the panes, the control at both ends of the turns, the band's rows
        width = args["width"]
        context, page = open_page(width, 800)
        geometry = '''(() => { const box = (s) => { const el = document.querySelector(s), r = el.getBoundingClientRect()
            return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, shown: el.checkVisibility({visibilityProperty: true})} }
          return {bar: box(".bar"), band: box("#open-questions"), pane: box("#turns-pane"), column: box("#artefacts"),
                  sheet: box("#sheet-toggle"), height: innerHeight, width: innerWidth,
                  firstTurnBorder: getComputedStyle(document.querySelector(".turns > .blk")).borderTopWidth,
                  rows: [...document.querySelectorAll("#open-questions .q")].map((q) => ({id: q.id, folded: q.classList.contains("folded"),
                    head: box(`#${q.id} h3`), pickline: q.querySelector(".pickline")?.checkVisibility() ?? false}))} })()'''
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
        for key in ("]", "[", "j", "k", "g", "g", "End", "PageUp", "Home"):
            page.keyboard.press(key)
        settle(page)
        out["window"] = page.evaluate("[scrollX, scrollY, document.scrollingElement.scrollTop, document.body.scrollTop]")
        out["scrollbars"] = page.evaluate('''[...document.querySelectorAll("*")].filter((e) => { const s = getComputedStyle(e)
            return ["auto", "scroll"].includes(s.overflowY) && e.offsetWidth - e.clientWidth - parseFloat(s.borderLeftWidth) - parseFloat(s.borderRightWidth) > 0 })
            .map((e) => e.id || e.className)''')
        if out["top"]["sheet"]["shown"]:
            page.click("#sheet-toggle")
        page.wait_for_timeout(400)
        out["sheet_open"] = page.evaluate(geometry)["column"]
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
    names the keys this page added (P6)."""
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
    for keys in ("n", "t 0 7", "[ ]", "q"):
        assert keys in seen["help"], f"the key list has no {keys}: {seen['help']}"


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


@pytest.mark.parametrize("width", WIDTHS)
def test_the_panes_hold_at_every_width(long_session: tuple[Path, Path], width: int) -> None:
    """P3, P7, P8 and the layout the ticket's Decisions bind, at each width the hub shows the page at: the
    window never scrolls and no pane shows a scrollbar; the band of questions sits over the turns
    with one rule between them, its first question open and every other one folded to its
    headline and the recommended option's words, all in view however long the open one is; the
    timeline runs full height right of the turns, or at the sidebar's width sits in a sheet behind
    the bar's button; the control to the newest turn is in view with the pane at either end."""
    page, _ = long_session
    seen = probe(page, "layout", width=width)
    assert seen["window"] == [0, 0, 0, 0], f"P7: the window scrolled: {seen['window']}"
    assert seen["scrollbars"] == [], f"P7: these show a scrollbar: {seen['scrollbars']}"
    assert seen["pane_at_end"], "the turns never scrolled to their end"
    assert seen["control_top"] and seen["control_top"]["inView"], f"P3 at the top: {seen['control_top']}"
    assert seen["control_bottom"] and seen["control_bottom"]["inView"], f"P3 at the bottom: {seen['control_bottom']}"
    for moment in ("top", "bottom"):
        at = seen[moment]
        band, pane, column = at["band"], at["pane"], at["column"]
        assert band["bottom"] <= pane["top"] + 1 and pane["bottom"] >= at["height"] - 1, f"{moment}: {at}"
        assert at["firstTurnBorder"] == "0px", "the first turn draws a rule of its own under the band's"
        rows = at["rows"]
        assert [r["folded"] for r in rows] == [False, True, True], rows
        assert all(r["pickline"] for r in rows if r["folded"]), "a folded row lacks the recommended option's words"
        for r in rows:
            assert band["top"] <= r["head"]["top"] and r["head"]["bottom"] <= band["bottom"] + 1, f"P8: {r['id']} out of the band: {at}"
        if width > 704:
            assert column["left"] >= pane["right"] - 1 and column["top"] <= at["bar"]["bottom"] + 1, f"{moment}: {at}"
            assert column["bottom"] >= at["height"] - 1 and column["shown"] and not at["sheet"]["shown"], f"{moment}: {at}"
        else:
            assert not column["shown"] and at["sheet"]["shown"], f"{moment}: the timeline is not in a sheet: {at}"
    if width <= 704:
        sheet = seen["sheet_open"]
        assert sheet["shown"] and sheet["right"] <= seen["top"]["width"] + 1 and sheet["left"] >= 0, f"the sheet did not open: {sheet}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
