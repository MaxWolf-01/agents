"""What the checks of render-lint and of `browsers` both launch: the script, the page a check's
body is set in, and a page that never comes to rest."""

from pathlib import Path

LINT = Path(__file__).parent / "render_lint.py"

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>body {{ font-family: serif; margin: 0 }}</style></head>
<body>{}</body></html>
"""

# A page that never comes to rest, so there is no moment at which measuring it means anything.
RESTLESS = """
<div style="position:relative;height:200px">
  <span id="pacer" style="position:absolute;left:20px;top:10px">A label that never stops</span>
</div>
<script>let n = 0; setInterval(() => document.getElementById("pacer").style.top = (10 + (n = (n + 13) % 90)) + "px", 60)</script>
"""
