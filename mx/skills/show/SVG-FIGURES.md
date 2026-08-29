# Hand-authored SVG figures

A figure whose coordinates you place yourself: one self-contained HTML file, inline SVG and CSS, no JS, no build step. Opens in a browser, screenshots cleanly, diffs as text. Reach for it when the picture *is* the artifact.

Two other tools own neighbouring ground. **Charts belong to `dataviz`** — anything where the reader compares quantities (bar, line, scatter, heatmap, stat tile, dashboard), including all the color decisions. **Mermaid solves layout for you**; here you solve it yourself, buying control and paying in effort. Under ~9 nodes that trade is worth it, above it usually not.

This file has two layers and they do not bind equally.

- **Mechanics** are properties of the medium. They hold for any hand-placed SVG, including a deliberately strange one.
- **The skin** is one house look — good default for structural diagrams, wrong for anything that wants its own visual argument. When the figure should look nothing like a systems diagram, keep the mechanics and drop the skin. A default aesthetic must never outrank the point of the picture.

---

## Mechanics

**Draw order is z-order.** SVG paints in document order and has no `z-index`. Background → zone rects → connectors → nodes → *all* labels → legend. Connectors before nodes is what lets a box cover its own line ends. Labels after connectors is what stops a line drawn later from cutting through text — the trap is a zone label emitted alongside its zone rect, which every subsequent connector then paints over. Keep every label in the label pass, whatever it belongs to.

**Anything sitting over a line needs an opaque backing rect.** SVG gives text no halo, so a label on a connector is unreadable and a translucent node fill lets the line show through. Draw a rect in the page background color first, then the real thing on top:

```svg
<rect x="X" y="Y" width="W" height="H" rx="6" fill="{paper}"/>   <!-- mask -->
<rect x="X" y="Y" width="W" height="H" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1"/>
```

**A label never touches its connector.** Leave 6–10px of visible gap between the bottom of the mask rect and the stroke. The mask stops the bleed-through; the gap is what keeps the line traceable. A label that hides its own arrow has destroyed the information it was annotating. For vertical segments put the label beside the line with the same gap, never rotated — vertical `writing-mode` text is unreadable at figure sizes.

**Connectors turn at right angles.** A diagonal between two off-axis nodes reads as sloppy in a way that is hard to name and easy to see. Use a plain `<line>` only when the endpoints share an x or a y; otherwise an elbow with a quarter-arc corner:

```svg
<!-- right then down, mid = (x1+x2)/2, corner radius 8 -->
<path d="M x1,y1 H mid-8 Q mid,y1 mid,y1+8 V y2-8 Q mid,y2 mid+8,y2 H x2"
      fill="none" stroke="{stroke}" stroke-width="1.2" marker-end="url(#arrow)"/>
```

The exception is a radial layout. Spokes running from a ring of nodes into a shared center are *supposed* to be diagonal — the diagonal is what says "these all point at the same thing." Forcing them orthogonal destroys the shape. The rule is about arbitrary slants, not about geometry that carries meaning.

**Pick the port that matches the direction of travel.** If the destination is mostly above or below, leave through the top or bottom edge and arrive at the top or bottom edge. An arrow arriving at a node's side after travelling vertically looks like it punctured the face rather than landing on it.

**Crossings get a hop; shared edges get a fan.** Where two connectors must cross, bump the less important one over the other with a small arc — `a 8,8 0 0,1 16,0` on a horizontal path, which rises 8px and advances 16px. Never bump both. Where several connectors meet the same edge of a node, give each its own attach point at least 12px from its neighbours, spacing point *k* of *N* at `L·k/(N+1)` along the edge. Two arrows you cannot tell apart at a glance are a failed layout, not a styling problem.

**Route around boxes that are not endpoints.** A line disappearing behind an unrelated node implies a relationship that isn't there. If an intervening box genuinely sits on the only straight path, dash that segment to mark it as transit and keep the label at the visible end.

**Pick a grid and hold it.** Every coordinate, size, and gap a multiple of one number, with stroke widths and opacities exempt. This single constraint does more than any other to stop a figure reading as machine-generated, because near-alignment is what the eye catches. The house skin uses 4.

**Budget the figure before drawing it.** Around 9 nodes and 12 connectors is where a diagram stops being readable at a glance. Past that you have two figures — an overview and a detail — not one dense one. Type-specific ceilings that bite earlier: 5 sequence lifelines, 5 swimlane lanes, 6 layers, 3 venn circles, 4 tree or org-chart levels, 5 radar axes.

**Look at your own render before showing anyone.** This is the step that separates a figure from a plausible-looking pile of coordinates, and no checklist substitutes for it:

```bash
chromium --headless --disable-gpu --hide-scrollbars --window-size=1400,900 \
  --screenshot=/abs/path/out.png /abs/path/figure.html
```

Then Read the PNG and fix what you see — overlaps, collisions, drift, dead space, a label swallowed by a box. Expect to go round two or three times. Done means you have looked at it and it both explains the thing and looks good.

---

## The skin

One accent, two type families, hairlines, no shadows. Everything below is a default to inherit or replace wholesale — but replace it as a set, because the pieces are balanced against each other.

### Tokens

| Role | Light | Dark |
|---|---|---|
| `paper` — page background, default node fill | `#f5f5f5` | `#2d3142` |
| `paper-2` — secondary surface | `#ececec` | `#393e53` |
| `ink` — primary text and stroke | `#2d3142` | `#f5f5f5` |
| `muted` — secondary text, default arrows | `#4f5d75` | `#bfc0c0` |
| `soft` — sublabels | `#7a8399` | `#8e98ac` |
| `rule` — hairlines | `rgba(45,49,66,0.12)` | `rgba(245,245,245,0.12)` |
| `accent` — focal only | `#eb6c36` | `#f08a59` |
| `accent-tint` — fill behind accent strokes | `rgba(235,108,54,0.08)` | `rgba(240,138,89,0.10)` |
| `link` — HTTP/API/external | `#2e5aa8` | `#6a95d8` |

Implement each token as one CSS custom property holding a `light-dark()` pair, under `color-scheme: light dark`:

```css
:root { color-scheme: light dark; --paper: light-dark(#f5f5f5, #2d3142); /* ... */ }
```

The pair resolves against the element's used color scheme, so `color-scheme` alone drives the whole figure and each token keeps one definition. Three consequences:

- **Toggle** — a hairline-bordered `Auto` / `Light` / `Dark` control that sets `document.documentElement.style.colorScheme`; clearing it back to `""` returns to the system setting, so `Auto` stays reachable. It belongs on the page's header row, right-aligned with the content — `position: fixed` to a viewport corner strands it in the margin on a wide window.
- **Render** — headless chromium ignores `--force-dark-mode` and `--blink-settings=preferredColorScheme` once `color-scheme` is declared, so pin it instead: screenshot twice, injecting `<style>:root{color-scheme:light}</style>` and then the `dark` variant, and look at both.
- **Standalone `.svg`** — no scripting, so no toggle; it still carries the `light-dark()` tokens and gets both renders.

**The accent is editorial, not a signalling system.** One or two elements per figure, chosen as the thing the reader should look at first. On five elements it signals nothing. If you want to accent four things, you have not yet decided what the figure is about. Everything else is ink, muted, or soft.

Node treatments: focal is `accent-tint` on `accent`; a service or step is white on `ink`; a store is `ink @ 0.05` on `muted`; an external system is `ink @ 0.03` on `ink @ 0.30`; an optional or async node is `ink @ 0.02` on `ink @ 0.20` dashed `4,3`; a security boundary is `accent @ 0.05` on `accent @ 0.50` dashed `4,4`.

Strokes 0.8 / 1 / 1.2. Radius 4 on tags, 6 on nodes, 8 on containers. Never a `box-shadow` — borders do that job.

### Type

Two families, each with one job. Mono is for content that *is* technical — ports, paths, URLs, field types, state transitions — never as a blanket "developer" texture, which is the single fastest way to make a figure look generated.

| Role | Family | Size |
|---|---|---|
| Title | Geist 600 | 1.25rem |
| Node name | Geist 600 | 12px |
| Sublabel | Geist Mono | 9px |
| Eyebrow / tag | Geist Mono 500, uppercase, 0.18em tracking | 7–8px |
| Arrow label | Geist Mono, 0.06em tracking | 8px, ≤14 chars, all caps |
| Aside | Geist 400, `soft` | 11px |

```html
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

**Chrome text states; it never sells.** The title names what the figure shows; the subtitle, when one exists, is one factual sentence. No slogans, no coined phrases, no pitch-deck cadence — a title that argues or charms instead of naming gets rewritten to just name. The same register holds for asides inside the figure: a fact worth a line, nothing more.

### Markers and page

Define all three markers up front, then reference by role — muted for internal flow, accent for the primary path, link-blue for HTTP and external calls. Dashed (`stroke-dasharray="5,4"`) means optional, async, return, or passive; it changes meaning, not routing.

```svg
<marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
  <polygon points="0 0, 8 3, 0 6" fill="{muted}"/>
</marker>
```

Page is an eyebrow in mono, an H1 in Geist, the SVG sitting directly on the paper with no container chrome, and a legend as a horizontal strip below a hairline at the bottom — never floating inside the drawing, where it collides with the nodes. Add ~60px of `viewBox` height for it. The SVG carries `width:100%; height:auto` and scales with its `viewBox`; a pixel `max-width` only shrinks the figure into a corner of a wide window.

### What the default skin rules out

Dark backgrounds with cyan or purple glow. Shadows. `border-radius` past 10px. Identical boxes for every node, which erases hierarchy. Three equal-width summary cards. Mono everywhere. Accent as a category color.

---

## Composition elements

These compose freely over any node-and-arrow layout, and most good figures are two or three of them stacked. Reach here before inventing a new arrangement.

**Phase banner** — a chevron strip across the top naming the stages the figure moves through, so the horizontal axis carries meaning without a single arrow. Each segment is a polygon `x,4 x+188,4 x+200,18 x+188,32 x,32 x+12,18`, the leading notch omitted on the first. Darken or lighten successive segments slightly to imply direction.

**Boundary box** — a rounded rect with a hairline stroke and a 2%-ink wash enclosing what is inside one cluster, VPC, process, or trust zone, with an eyebrow label sitting in a paper-colored mask on the top edge. Leave ≥16px between the label and the first enclosed node. Three per figure at most; past that you wanted lanes.

**Cross-cutting bar** — a full-width bar for something everything depends on: auth, logging, orchestration, a scheduler. Inside a boundary box it spans the interior; outside and below, it reads as ambient infrastructure. Connect it with dashed arrows, since its relationship to each node is the same and drawing all of them would be noise.

**Step axis × actor lanes** — horizontal lanes for actors, a numbered step axis across the top, each card placed at one (actor, step) cell. Handoffs become visible as the vertical jumps between lanes. Answers *who does what, in what order* in one read.

**Typed handoff chips** — small colored tags in a card's bottom corners, left for what enters and right for what leaves, colored by kind of artifact and decoded in the legend. This is the upgrade over a plain swimlane: a swimlane shows that a handoff happened, chips show *what got handed over*.

**Hub and stations** — steps arranged in a ring with a shared store at the center, solid arrows around the ring for the cycle and dashed spokes inward for writes to shared state. The right shape for any loop that accumulates something rather than just repeating.

---

## Type notes

Everything else is layout convention, a few lines each.

- **Architecture** — group by tier or trust boundary, hold one direction of primary flow, accent the key integration point or store.
- **Flowchart** — diamonds for decisions, label every branch, one entry and one exit unless a second exit is the point.
- **Sequence** — actors across the top, lifelines down, time strictly downward, activation bars for held control. One combined fragment, two `alt` regions, no nesting past one level.
- **State** — filled dot for initial, ringed dot for final, transitions labelled `event [guard] / action`.
- **ER** — entity as a box with a field list, cardinality glyphs at both ends, 8 entities max.
- **Timeline** — one axis, events on alternating sides when they crowd, uneven spacing only if the spacing is to scale.
- **Swimlane** — lanes for actors, flow crossing between them; add a step axis and chips when the handoffs matter more than the order.
- **Nested / layers / tree / org chart** — containment, stacking, and parentage. Depth is the budget: 6 levels nested, 6 layers, 4 for tree and org depth.
- **Quadrant** — two labelled axes with named poles, items as dots with labels outside the plot. The consultant variant names all four cells and drops the dots.
- **Venn** — 3 circles maximum, label the intersections rather than the circles when the overlap is the point.
- **Pyramid / funnel** — ranked tiers or drop-off. Widths to scale when they encode a quantity, equal when they encode rank only.
- **Radar** — 3–5 axes, 5 series max, exactly one in the accent and the rest in the desaturated series palette (sage `#7c8f6f`, dusty blue `#5e7a9b`, mustard `#b8915a`, rust `#9c6b50`, slate `#6e6479`) at 0.18 fill opacity.
- **Gantt** — tasks as rows, bars on a date axis, dependencies as thin elbows. 12 tasks max.

---

## Icons

77 monochrome icons in `icons/`, named after their file. 55 outlined generics from Tabler — server, database, cloud, user, users, lock, key, shield-lock, git-branch, git-merge, terminal, robot, rocket, package, bucket, world, bug, bolt, the `device-*` and `file-type-*` sets, and `brand-{aws,azure,docker,github,terraform}`. 22 filled brand marks from Simple Icons — kubernetes, postgresql, sqlite, oracle, microsoftsqlserver, minio, nginx, keycloak, gitea, googlecloud, python, r, jupyter, trino, redash, tableau, powerbi, qgis, and the Apache set (airflow, hive, nifi, superset). Tabler is MIT, Simple Icons is CC0.

Every Tabler icon is a 24×24 stroked path already set to `currentColor`, so it inherits whatever skin is active. Simple Icons are 24×24 filled paths; set `fill="currentColor"` explicitly, as SVG defaults to black. Paste the paths inline inside a `<g transform="translate(x,y) scale(s)">` — the file stays self-contained, no external images.

An icon earns its place when it names a **third-party system** and the mark reads faster than the word — a Postgres elephant beats the string "PostgreSQL" at 9px. For your own components a name is clearer than a picture. Decoration is not automatically wrong, but decoration that competes with the focal node is.
