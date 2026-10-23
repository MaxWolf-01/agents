# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
# A file of the engine changed at the CDN: the board draws once from this machine's copies, so they
# hold every file it fetches, then loads again from a copy of them in which one file carries a
# byte more than the one its hash was taken of.

import json, os, re, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "show"))  # page_cache, beside render_lint
from page_cache import copy_of, default_root, serve

page = Path(sys.argv[1])
page_url, changed, own, kept = page.resolve().as_uri(), sys.argv[2], Path(sys.argv[3]), default_root()
pinned = sorted(set(re.findall(r'"(https://cdn\.jsdelivr\.net/[^"]+\.m?js)"', page.read_text())))

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    loader = browser.new_context()
    tab = loader.new_page()
    serve(loader, kept)
    tab.goto(f"{page_url}#t-map-columns")
    tab.wait_for_selector(".side .mermaid svg, .gnote[id^=gun]:not([hidden])")
    if not tab.is_visible(".side .mermaid svg"):
        print(json.dumps({"cdn": False}))
        sys.exit()
    loader.close()
    own.mkdir()
    for url in pinned:
        shutil.copy(copy_of(kept, url), own)
    [target] = [url for url in pinned if url.endswith(changed)]
    with copy_of(own, target).open("ab") as f:
        f.write(b"\n;")

    os.environ["MX_PAGE_CACHE_OFFLINE"] = "1"
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    tab = context.new_page()
    serve(context, own)
    errors = []
    tab.on("pageerror", lambda e: errors.append(str(e)))
    tab.goto(f"{page_url}?theme=day#t-map-columns")
    tab.wait_for_selector("#gunloaded:not([hidden]), #gundrawn:not([hidden]), .side .mermaid svg")
    out = {"cdn": True, "pinned": pinned, "graphs": tab.eval_on_selector_all(".mermaid svg", "els => els.length"),
           "notes": [tab.inner_text(n) for n in ("#gunloaded", "#gundrawn") if tab.is_visible(n)]}
    # the rest of the board: the open row folds, and the scheme switches
    tab.click("#t-map-columns > summary")
    tab.keyboard.press("t")
    out["rest"] = {"folded": not tab.evaluate("document.getElementById('t-map-columns').open"),
                   "scheme": tab.evaluate("document.documentElement.dataset.theme"), "errors": errors}
    browser.close()
print(json.dumps(out))
