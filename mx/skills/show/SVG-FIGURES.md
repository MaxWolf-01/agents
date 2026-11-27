# Hand-authored SVG figures

A figure whose coordinates you place yourself: one self-contained HTML file, inline SVG and CSS, no build step, and JS only for the scheme toggle. Reach for it when the picture *is* the artifact.

**A chart**, anything where the reader compares quantities (bar, line, scatter, heatmap, stat tile, dashboard), **is `dataviz`'s, painted as `/mx:house-style`'s `PARTS.md` says**. **Mermaid, drawn by Pele (see [`mermaid/SKILL.md`](mermaid/SKILL.md)), solves layout for you**; here you solve it yourself, buying control with effort, a trade worth it under ~9 nodes and usually not above.

This file has two layers and they do not bind equally.

- **Mechanics** are properties of the medium. They hold for any hand-placed SVG, including a deliberately strange one.
- **The skin** is the house style, `/mx:house-style`, worn by a figure: its tokens and type, plus the node treatments and markers below. A figure embedded in a markdown file GitHub renders (a README, a doc page, an issue) wears [`GITHUB-SKIN.md`](GITHUB-SKIN.md) by default: the same ink on a transparent ground, in a light and a dark render. When the figure should look nothing like a systems diagram, keep the mechanics and drop the skin; the register in `SKILL.md` stays either way.

---

## Mechanics

**Draw order is z-order.** SVG paints in document order and has no `z-index`: background → zone rects → connectors → nodes → *all* labels → legend, so a box covers its own line ends and no later line cuts through text. The trap is a zone label emitted alongside its zone rect, which every later connector paints over: every label goes in the label pass, whatever it belongs to.

**Anything sitting over a line needs an opaque backing rect.** SVG gives text no halo, and a translucent node fill lets the line show through: draw a rect in the page background color first, then the real thing on top:

```svg
<rect x="X" y="Y" width="W" height="H" rx="6" fill="{paper}"/>   <!-- mask -->
<rect x="X" y="Y" width="W" height="H" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1"/>
```

**A label never touches its connector.** Leave 6–10px of visible gap between the bottom of the mask rect and the stroke, so the line stays traceable. Beside a vertical segment the label sits at the same gap, never rotated: vertical `writing-mode` text is unreadable at figure sizes.

**Connectors turn at right angles.** Use a plain `<line>` only when the endpoints share an x or a y; otherwise an elbow with a quarter-arc corner:

```svg
<!-- right then down, mid = (x1+x2)/2, corner radius 8 -->
<path d="M x1,y1 H mid-8 Q mid,y1 mid,y1+8 V y2-8 Q mid,y2 mid+8,y2 H x2"
      fill="none" stroke="{stroke}" stroke-width="1.2" marker-end="url(#arrow)"/>
```

The rule is against arbitrary slants, not geometry that carries meaning: in a radial layout, spokes running from a ring of nodes into a shared center stay diagonal, since the diagonal is what says "these all point at the same thing."

**Pick the port that matches the direction of travel.** If the destination is mostly above or below, leave and arrive through a top or bottom edge.

**Crossings get a hop; shared edges get a fan.** Where two connectors must cross, bump only the less important one over the other, with a small arc (`a 8,8 0 0,1 16,0` on a horizontal path, which rises 8px and advances 16px). Where several connectors meet the same edge of a node, give each its own attach point at least 12px from its neighbours, point *k* of *N* at `L·k/(N+1)` along the edge. Two arrows you cannot tell apart at a glance are a failed layout, not a styling problem.

**Route around boxes that are not endpoints.** A line behind an unrelated node implies a relationship that isn't there. Where a box sits on the only straight path, dash that segment as transit and keep the label at the visible end.

**Pick a grid and hold it.** Every coordinate, size, and gap a multiple of one number, with stroke widths and opacities exempt. The house skin uses 4.

**Text is placed by measurement, never by eye.** Every text block sits one inset (12px) from its box on every side, on baselines at fixed offsets from the box top (name +24, role +41, detail +58 in an 80px node), the same in every node. Compute a label's width before placing it (≈0.6em per character in the mono; measure the serif with a hidden span) and check it against its space. An arrow label is centred on its segment, 8px above the line, ≥4px clear of both boxes; a segment too short for its label is widened, never the label pushed onto a box. Text that touches a border, crowds a corner or sits off its neighbour's baseline makes a figure look thrown together, whatever else is right.

**Budget the figure before drawing it.** Past around 9 nodes and 12 connectors a diagram stops reading at a glance: draw two figures, an overview and a detail. Type-specific ceilings bite earlier: 5 sequence lifelines, 5 swimlane lanes, 6 layers, 3 venn circles, 4 tree or org-chart levels, 5 radar axes.

**Lint the render, then look at it, before showing anyone.** `render-lint figure.html --crops /tmp/lint` writes a PNG per finding, so a 5px overflow that a page-sized screenshot hides is plain in its crop; its `--help` says what it reports. Then the eye, for what geometry cannot judge (rhythm, weight, whether it explains the thing):

```bash
chromium --headless --mx-run="${MX_RUN:-$PWD}" --disable-gpu --hide-scrollbars --window-size=1400,900 \
  --screenshot=/abs/path/out.png /abs/path/figure.html
```

`--mx-run` names the run the browser belongs to, so `browsers kill` takes it when it hangs.

Then Read the PNG and fix what you see: overlaps, collisions, drift, dead space, a label swallowed by a box. Expect to go round two or three times.

---

## The skin

Load `/mx:house-style` and inline its `tokens.css` into the file; the tokens, the type roles and the habits are its, and only what a figure adds is here. Replace the skin as a set: the pieces are balanced against each other.

### Tokens

| Figure role | House token |
|---|---|
| page background, mask rects | `ground` |
| default node fill, code and figure surfaces | `ground-2` |
| primary text and the strongest stroke | `body` |
| secondary text, default arrows, zone and legend labels | `muted` |
| hairlines | `edge` |
| focal only | `accent` |
| fill behind an accent stroke | `wash` |
| zone fill; a banner ramps the same mix 6% to 22% | `wash-ink` |
| a security boundary, a caution | `accent-2` |

The scheme, its `?theme=` reading and the toggle are the house's, copied from its `demo.html`. A standalone `.svg` has no script, so it gets both renders and no toggle.

**The accent goes on the thing the reader should look at first.**

Node treatments: focal is `wash` on `accent`; a service or step is `ground-2` on `body`; a store is `ground-2` on `muted`; an external system is unfilled on `muted`; an optional or async node is unfilled on `edge` dashed `4,3`; a security boundary is unfilled on `accent-2` dashed `4,4`. Four weights come from the stroke colour and from whether the box is filled at all; every stroke is a hairline.

Strokes 0.8 / 1 / 1.2. Radius 4 on tags, 6 on nodes, 8 on containers. Never a `box-shadow`; borders do that job.

### Type

The house roles, at figure sizes. Mono is for content that *is* technical (ports, paths, URLs, field types, state transitions) and for labels; a node's name is not data.

| Role | Family | Size |
|---|---|---|
| Title | `v-title` | as the role sets it |
| Subtitle | serif 400, `muted`, one sentence | 15px |
| Node name | serif 600, `body` (`accent` on the focal node) | 14px |
| Node role | serif 400, `body` | 13px |
| Node detail | mono, `muted`, only when the content is technical; else serif 400 `muted` | 12px / 13px |
| Arrow label | serif 400, `muted`, lowercase | 12px, ≤14 chars |
| Zone label / tag / eyebrow | `v-meta`, lowercase | 13px |
| Legend | `v-meta` | 13px |
| Aside | serif 400, `muted` | 13px |

These are floors, not targets: a label that does not fit gets a wider box, never a smaller size.

A node carries a name, a role, and a detail, one line each, and a label is a name, not a clause: `pc` with the role line `backup hub`, never `pc — backup hub`; `repos, docs, config`, never `repos · docs · config`. Grey is for the one detail line; a card that is mostly grey text reads as unfinished.

The font link is the one in the house-style `demo.html` head.

### Markers and page

Define both markers up front, then reference by role: muted for internal flow, accent for the primary path. An HTTP or external call is muted and labelled; a third colour for it would be a category colour. Dashed (`stroke-dasharray="5,4"`) means optional, async, return, or passive; it changes meaning, not routing.

```svg
<marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
  <polygon points="0 0, 8 3, 0 6" fill="var(--muted)"/>
</marker>
```

Page is an H1 in `v-title`, an optional one-sentence subtitle under it, no eyebrow above it, the SVG sitting directly on the ground with no container chrome, and a legend as a horizontal strip below a hairline at the bottom, never floating inside the drawing, where it collides with the nodes; add ~60px of `viewBox` height for it. The SVG carries `width:100%; height:auto` and scales with its `viewBox`; a pixel `max-width` only shrinks the figure into a corner of a wide window.

### What the skin rules out

Dark backgrounds with cyan or purple glow. Shadows. `border-radius` past 10px. Identical boxes for every node, which erases hierarchy. Three equal-width summary cards. Mono everywhere. Accent as a category color. Italics as decoration, a tagline under the title. A tracked all-caps eyebrow above the title. Middle dots and em dashes inside labels.

---

## Composition elements

These compose freely over any node-and-arrow layout, and most good figures are two or three of them stacked. Reach here before inventing a new arrangement.

**Phase banner**: a chevron strip across the top naming the stages, so the horizontal axis carries meaning without an arrow. Each segment is a polygon `x,4 x+188,4 x+200,18 x+188,32 x,32 x+12,18`, the leading notch omitted on the first. Darken or lighten successive segments slightly to imply direction.

**Boundary box**: a rounded rect with a hairline stroke and a `wash-ink` fill enclosing what is inside one cluster, VPC, process, or trust zone, with a zone label (see Type) sitting in a `ground` mask on the top edge. Leave ≥16px between the label and the first enclosed node. Three per figure at most; past that you wanted lanes.

**Cross-cutting bar**: a full-width bar for something everything depends on: auth, logging, orchestration, a scheduler. Inside a boundary box it spans the interior; outside and below, it reads as ambient infrastructure. Connect it with dashed arrows, since its relationship to each node is the same and drawing all of them would be noise.

**Step axis × actor lanes**: horizontal lanes for actors, a numbered step axis across the top, each card placed at one (actor, step) cell. Handoffs show as vertical jumps between lanes; it answers *who does what, in what order* in one read.

**Typed handoff chips**: small colored tags in a card's bottom corners, left for what enters and right for what leaves, colored by kind of artifact and decoded in the legend. Where a swimlane shows that a handoff happened, chips show *what got handed over*.

**Hub and stations**: steps arranged in a ring with a shared store at the center, solid arrows around the ring for the cycle and dashed spokes inward for writes to shared state. The shape for a loop that accumulates something rather than just repeating.

---

## Type notes

- **Architecture delta** (a concept diff of a structure): a before panel, a ledger of the changes, an after panel. The after panel copies the before panel's coordinates for every part that stayed, so the reader's map holds and only what moved looks new.
- **Hub and spoke**: the platform in the middle, sources plugging in on one side and readers out on the other, each wire labelled with how it connects (the protocol, the file, the call).
- **Sequence**: actors across the top, lifelines down, time strictly downward, activation bars for held control. A return is a dashed line with a filled arrowhead, an async message an open arrowhead. One combined fragment, its operator in a small tab at its top left, two `alt` regions, no nesting past one level.
- **State**: filled dot for initial, ringed dot for final, transitions labelled `event [guard] / action`. A transition from any state is one note (`* → error on timeout`), never an arrow from each.
- **ER**: entity as a box with a field list, `#` before a primary key and `→` before a foreign key, cardinality glyphs at both ends 10–12px from the box edge, 8 entities max. A **schema** view is the same boxes with SQL types and constraint chips, each foreign key drawn from its column to the column it references.
- **Fishbone** (a diagnosis): the effect at the head, causes along ribs grouped by category, every cause investigated drawn and the confirmed one in the accent, so the figure shows what was ruled out as well as what was found.
- **Journey**: stages across, a sentiment curve above them, a marker on each pain point where the curve drops.
- **Swimlane**: lanes for actors, flow crossing between them; add a step axis and chips when the handoffs matter more than the order.
- **Nested / layers / tree / org chart**: containment, stacking, and parentage. Depth is the budget: 6 levels nested, 6 layers, 4 for tree and org depth.
- **Quadrant**: two labelled axes with named poles, items as dots with labels outside the plot. The consultant variant names all four cells and drops the dots.
- **Venn**: 3 circles maximum, label the intersections rather than the circles when the overlap is the point.
- **Pyramid / funnel**: ranked tiers or drop-off. Widths to scale when they encode a quantity, equal when they encode rank only.
- **Radar**: 3–5 axes, 5 series max, exactly one in the accent and the rest in the house's `series-1` onward, at 0.18 fill opacity.
- **Gantt**: tasks as rows, bars on a date axis, dependencies as thin elbows. 12 tasks max.
- **Exploded view**: one physical thing with its parts pulled apart along the axis they assemble on, each labelled outside the part on a leader line.
- **A module's depth, before and after** (a deepening): side by side, and varied across a page of them. A **mass diagram** gives each module one rectangle for the interface and one for the implementation: shallow is nearly the same height, deep a short interface over a tall implementation. A **cross-section** stacks the layers a call passes through: many thin bands become one thick band named for the responsibility. A **call-graph collapse** nests a tree of calls as boxes, and after shows one box with the now-internal calls faded inside it. A **graph** marks the leaking edges when the point is who calls whom.

---

## Icons

Monochrome icons in `icons/`, one per file and named by it: outlined generics from Tabler and filled brand marks from Simple Icons, their licences in `icons/LICENSES.md`.

Every Tabler icon is a 24×24 stroked path already set to `currentColor`, so it inherits whatever skin is active. Simple Icons are 24×24 filled paths; set `fill="currentColor"` explicitly, as SVG defaults to black. Paste the paths inline inside a `<g transform="translate(x,y) scale(s)">`, so the file stays self-contained.

An icon earns its place when it names a **third-party system** and the mark reads faster than the word: a Postgres elephant beats the string "PostgreSQL" at 9px. Your own components get a name, not a picture. Decoration is wrong only where it competes with the focal node.
