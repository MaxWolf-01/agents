---
status: open
type: legwork
---

# Report mermaid's HTML-label wrap check upstream

Filed from the board-nits work (mx v0.1.49); the board works around it with SVG text labels, and an upstream fix would let HTML labels back in. File with `/mx:upstream-issue`.

mermaid 11.17.0 (`mermaid-js/mermaid`), flowchart HTML labels: `addHtmlSpan` measures the label in a div with `white-space: nowrap; max-width: <wrappingWidth>px` and switches it to wrapping mode only when `bbox.width === width` exactly. Under a fractional device scale factor the measured width comes back a layout unit short (199.9964 and 199.9921875 observed for a wrap width of 200), the comparison fails, and every label longer than the wrap width stays on one line and is clipped by the foreignObject. At scale 1 the measurement is exactly 200 and the bug never shows, which is why screenshots from headless Chromium look fine while a HiDPI or zoomed desktop browser clips every node.

Repro: any flowchart with a node label longer than 200 px, page zoom at 90% or a display scale of 1.25, `htmlLabels: true`. Minimal fix upstream: compare with a tolerance (`bbox.width >= width - 1`), or read the div's `offsetWidth`, which is integral.

Evidence: measured in Brave through the browser extension on 2026-09-09, session notes in the `board-nits` branch commit "SVG text labels, so node titles wrap on a fractional display scale".
