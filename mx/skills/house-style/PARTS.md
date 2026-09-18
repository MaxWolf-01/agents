# Parts

How each part wears the tokens; `demo.html` renders every line, and its stylesheet carries the heights and paddings, which are the project's to change.

- **Page**: one column, `--page` wide, air at the sides. The header is a row with a hairline under it. A page opens with `v-title`, a `v-meta` line, and a `v-lead` in muted.
- **Divider**: a hairline, or a lowercase `v-meta` word with the hairline running on from it.
- **Link**: in running text, accent with a 1px underline at 40% accent that fills on hover; in chrome (nav, back, next), muted text that turns accent on hover.
- **Button**: quiet (hairline, body ink) is the default; solid (accent fill, ground text) for the one primary action on the page; ghost (muted text) for the rest. Hover turns the accent; radius `--radius`; disabled at 45% opacity.
- **Pill**: a lowercase mono word in a hairline capsule, the only fully rounded shape; active is accent fill with ground text. A filter row is pills that stay visible, so three words on the page beat a dropdown that hides two.
- **Input, textarea, select**: hairline on `ground-2`, radius `--radius`, focus turns the border accent. Label and hint are `v-meta`; an error is `v-meta` in accent-2.
- **Switch**: a hairline track and a hollow dot; checked is an accent dot on a wash track. A filled track would be the loudest thing on the page.
- **Scheme toggle**: one icon in muted, a sun by day and a moon by night, accent on hover; no label and no switch. It sets `data-theme` on the root.
- **Table**: a rule under the head, hairlines between rows, nothing vertical. Heads are `v-meta`; numbers `v-num`, right-aligned. A table wider than the measure leaves the column and takes the page width at full size.
- **Note**: a 2px bar on the left (edge; accent-2 for caution), `v-small` muted text, and a `v-meta` title only when the note has a name.
- **Figure, code**: the filled boxes: hairline on `ground-2`, radius `--radius`; the caption `v-small` muted, its source in `v-num`. Code dims comments to muted and does no other highlighting.
- **Heading anchor**: a `¶` in accent that appears on hover, so the margin stays clean while reading.
- **Contents**: the `v-meta` word "contents" over `v-small` muted links, the current one in accent.
- **Steps, definitions, footnotes**: step numbers in `v-num` muted, in a margin column beside the text; a term in `v-h3` with its definition in muted under a hairline; footnotes as a list under a hairline, numbers in accent.
- **Overlay** (dialog, menu, tooltip, toast): the same ground, a hairline, radius `--radius`. The dialog backdrop is strong at 40% and does the layering; a highlighted menu item is wash with accent text.
- **Chart**: hand-drawn SVG in the page's ink. Grid lines are edge, the baseline muted, the data body ink, and the one series that carries the point accent with the wash under it.
- **Two-valued data** (hit and miss, added and removed): the first value sits on `wash`, the second on accent-2 at 18%, its line number or marker in accent-2 at weight 500. Green and red stay outside the palette, for the one case where a convention outranks it, such as a diff.
- **Diagram**: node names in the serif, a detail line in mono only when it is data (a path, a command, a value). Every box is a hairline; weight comes from the stroke colour (edge, muted, body) and from whether the box is filled with `ground-2` at all. A zone is a hairline filled with `wash-ink`, its label in a ground-coloured mask; a phase banner ramps the same mix from 6% to 22%; one node wears the accent.
- **Motion**: colour transitions at 150ms, overlays fade at 200ms, nothing else moves.
- **Focus**: a 2px accent outline, 3px off the element.

## Tailwind v4

`@import "tailwindcss"; @import "./tokens.css";` in that order, so the token rules land after preflight in the same layers, then expose the tokens as utilities:

```css
@theme inline {
  --color-ground: var(--ground);
  --color-ground-2: var(--ground-2);
  --color-edge: var(--edge);
  --color-muted: var(--muted);
  --color-body: var(--body);
  --color-strong: var(--strong);
  --color-accent: var(--accent);
  --color-accent-2: var(--accent-2);
  --color-wash: var(--wash);
  --color-mark: var(--mark);
  --font-body: var(--font-body);
  --font-mono: var(--font-mono);
  --spacing-measure: var(--measure);
  --spacing-page: var(--page);
  --radius-soft: var(--radius);
}
```

Base UI (`@base-ui/react`) supplies the behaviour for field, switch, toggle group, dialog, menu, tooltip, toast and collapsible; the lines above are the paint. The bundler rewrites `light-dark()` into a polyfill keyed on `color-scheme` declarations, which is why the theme is switched by setting `data-theme` on the root and never by writing `style.colorScheme`.
