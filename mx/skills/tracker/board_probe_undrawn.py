# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
# A draw that fails after the engine loaded: the engine and what it imports come from a directory of
# their own, with the network cut off, so the pieces mermaid fetches while it draws do not arrive.
# The copies of those pieces are then put in, and the board draws with them from its next load on:
# the browser keeps a failed import as failed for as long as the page lives, so nothing short of a
# load fetches it again, and the board loads again on every change to the tracker.

import json, os, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "show"))  # page_cache, beside render_lint
from page_cache import copy_of, default_root, serve

page_url, ENGINE = Path(sys.argv[1]).resolve().as_uri(), sys.argv[2].split(",")
own, kept = Path(sys.argv[3]), default_root()
UNDRAWN = "#gundrawn:not([hidden])"
# mermaid is a classic script, its layout a module
LOAD = '''(urls) => Promise.all(urls.map((u) => u.endsWith(".mjs") ? import(u) : new Promise((ok, no) =>
  document.head.append(Object.assign(document.createElement("script"), {src: u, onload: ok, onerror: no})))))
  .then(() => true, () => false)'''

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    # what importing the engine asks for, and nothing its drawing does
    loader = browser.new_context()
    page = loader.new_page()
    serve(loader, kept)
    asked = []
    page.on("request", lambda r: asked.append(r.url))
    if not page.evaluate(LOAD, ENGINE):
        print(json.dumps({"cdn": False}))
        sys.exit()
    own.mkdir()
    for url in asked:
        shutil.copy(copy_of(kept, url), own)
    loader.close()

    os.environ["MX_PAGE_CACHE_OFFLINE"] = "1"
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    page = context.new_page()
    serve(context, own)
    page.goto(f"{page_url}?theme=night#t-map-columns")
    page.wait_for_selector(UNDRAWN)
    out = {"cdn": True, "preview": {"note": page.inner_text("#gundrawn"), "unloaded": page.is_visible("#gunloaded"),
                       "graphs": page.evaluate("document.querySelectorAll('.side .mermaid svg').length")}}
    page.keyboard.press("f")
    page.wait_for_selector("#gfull .gnote:not([hidden])")
    out["overlay"] = page.inner_text("#gfull .gnote")
    page.keyboard.press("Escape")
    with page.expect_popup() as popped:
        page.keyboard.press("w")
    win = popped.value
    win.wait_for_selector(".gfbody .gnote:not([hidden])")
    out["window"] = win.inner_text(".gfbody .gnote")
    win.close()
    # a failed draw, in the preview or at full size, leaves no error drawing of mermaid's own behind
    out["stray"] = page.evaluate("document.querySelectorAll('body > [id^=dm], body > [id^=dgf]').length")

    shutil.copytree(kept, own, dirs_exist_ok=True)
    page.reload()
    page.wait_for_selector(".side .g:not([hidden]) .mermaid svg", timeout=20_000)
    out["next"] = {"graphs": page.evaluate("document.querySelectorAll('.side .g:not([hidden]) .mermaid svg').length"),
                   "note": page.is_visible("#gundrawn")}
    browser.close()
print(json.dumps(out))
