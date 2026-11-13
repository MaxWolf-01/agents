# The GitHub skin

The skin for a figure embedded in a markdown file GitHub renders: a README, a doc page, an issue. The figure is the house style's ink on a transparent ground, so it sits on GitHub's own page, white or `#0d1117`, where a parchment rectangle would look pasted in. Mechanics, type roles and the rule on the accent are the ones in [`SVG-FIGURES.md`](SVG-FIGURES.md) and `/mx:house-style`; this file holds what differs.

## Tokens

The ink tokens of `tokens.css` as they are: `edge`, `muted`, `body`, `strong`, `accent`, `accent-2`, `wash`, each a `light-dark()` pair. The surfaces are washes of the ink, since a mix with `transparent` reads on either page and `ground` and `ground-2` read on neither:

```css
--fill: color-mix(in srgb, var(--muted) 8%, transparent);            /* a node */
--zone: color-mix(in srgb, var(--muted) 4%, transparent);            /* a zone or a boundary box */
--caution-wash: color-mix(in srgb, var(--accent-2) 10%, transparent); /* under an accent-2 stroke */
```

A node is `fill` on a `strong` stroke; the focal node is `wash` on `accent`; a failure or caution node is `caution-wash` on `accent-2`, dashed; a zone is `zone` on `edge`. Type is the house's, Newsreader and IBM Plex Mono, at the sizes of the figure type table.

## A label sits beside its connector

A transparent page has no colour to mask with, so the opaque backing rect of the mechanics does not exist here. Every label goes beside its line or in clear space, and a connector is routed around a node, never under one.

## Two renders, one source

The figure's page reads three query parameters: `theme=day|night` pins the scheme, `bare` hides the page's chrome and makes its background transparent, and `gh` puts GitHub's page colour behind the figure, to judge it where it will sit.

```css
.bare body { background: transparent; }
.gh body { background: light-dark(#ffffff, #0d1117); }
```

Render the bare figure once per scheme at the size of its `viewBox`, device scale 2, with Chromium's `--default-background-color=00000000`, which keeps the PNG's ground transparent. The markdown embeds both, and GitHub shows the one for the reader's theme:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/out/<name>-dark.png">
  <img alt="<the figure's facts, in sentences>" src="docs/figures/out/<name>-light.png" width="880">
</picture>
```

The alt text states what the figure states, since text in a PNG is neither searched nor read aloud. Look at both renders over `?gh` before presenting: a dark render on a white ground looks faint and is fine.
