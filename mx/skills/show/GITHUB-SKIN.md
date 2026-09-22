# The GitHub skin

Grey paper, one orange accent, Geist: the skin for a figure that sits on GitHub's dark theme (a README, an issue), where the house parchment would clash with the page around it. Night only; day is the house style. Mechanics, type roles and the rules on the accent are the ones in [`SVG-FIGURES.md`](SVG-FIGURES.md); only the values differ.

| Role | Dark |
|---|---|
| `paper`: page background, default node fill | `#2d3142` |
| `paper-2`: secondary surface | `#393e53` |
| `ink`: primary text and stroke | `#f5f5f5` |
| `muted`: secondary text, default arrows | `#bfc0c0` |
| `soft`: legend and zone labels only, never text inside a node | `#8e98ac` |
| `rule`: hairlines | `rgba(245,245,245,0.12)` |
| `accent`: focal only | `#f08a59` |
| `accent-tint`: fill behind accent strokes | `rgba(240,138,89,0.10)` |
| `link`: HTTP/API/external | `#6a95d8` |

Node treatments: focal is `accent-tint` on `accent`; a service or step is `paper` on `ink`; a store is `ink @ 0.05` on `muted`; an external system is `ink @ 0.03` on `ink @ 0.30`; an optional or async node is `ink @ 0.02` on `ink @ 0.20` dashed `4,3`; a security boundary is `accent @ 0.05` on `accent @ 0.50` dashed `4,4`. Three markers: muted for internal flow, accent for the primary path, link-blue for HTTP and external calls.

Type is Geist and Geist Mono at the sizes in the figure type table: title Geist 600 1.5rem, node name Geist 600 12px, role Geist 400 10px, detail Geist Mono 9px when technical, arrow label Geist 500 9px, zone label and tag Geist 600 `soft` 10px, legend Geist Mono 9px. Width ≈0.5em per character in Geist, ≈0.6em in Geist Mono.

```html
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```
