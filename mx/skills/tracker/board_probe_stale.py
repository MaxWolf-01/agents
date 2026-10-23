# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
"""What an open tab shows while the stamp file beside its page marks the board stale, and once the mark
is gone, and whether it reloaded for either. The tab polls the stamp file on a timer, which the
page's clock runs forward rather than the check waiting it out."""

import json, os, shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "show"))  # page_cache, beside render_lint
from page_cache import default_root, serve

page, stale = Path(sys.argv[1]), sys.argv[2]
stamp = Path(f"{page}.stamp.js")
drawn = stamp.read_text()
NOTE = "[data-absent=board-stale]"

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=shutil.which("chromium"),
                                 args=[f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"])
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    serve(context, default_root())
    tab = context.new_page()
    tab.clock.install()
    tab.goto(page.resolve().as_uri())
    tab.evaluate("window.__loaded = true")  # gone on a reload
    out = {"before": tab.is_visible(NOTE)}
    stamp.write_text(stale)
    tab.clock.run_for(6_000)
    tab.wait_for_selector(f"{NOTE}:not([hidden])")
    out["stale"] = tab.inner_text(NOTE)
    stamp.write_text(drawn)
    tab.clock.run_for(6_000)
    tab.wait_for_selector(f"{NOTE}[hidden]", state="attached")
    out["after"] = tab.is_visible(NOTE)
    out["reloaded"] = not tab.evaluate("window.__loaded === true")
    browser.close()
print(json.dumps(out))
