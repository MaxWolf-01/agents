# Explainer pages

An HTML page as the artifact: side-by-side panels, an interactive figure, prose interleaved with figures the reader can poke at. One self-contained file, inline CSS, JS only where the reader interacts. The register in `SKILL.md` binds; the tokens, type roles, parts and toggle are `/mx:house-style`, inlined; a figure on the page wears the skin in `SVG-FIGURES.md`.

## Page-level additions to the skin

- Body text is the house body role at the measure; a dense comparison page may set `--size-body` down, as the skill allows. Headings are `v-h2` and `v-h3`. Sentence case in prose, lowercase labels.
- One content column, `--page` wide, left-aligned. Everything on the 4px grid. A table wider than the measure takes the page width.
- Structure encodes information. A border, a rule, a number, a label exists because it separates or orders something the reader needs told apart; numbering (`01 / 02`) only when the content is a sequence.
- One emphasized element per page, in the accent. Everything else ink, muted, soft.
- Motion only in answer to the reader's action (open, expand, confirm), and it shows what changed. No entrance animations, no hover transitions on every card.
- Quality floor: usable at 700px wide, visible keyboard focus, `prefers-reduced-motion` honoured, both schemes with the toggle.
- Selector specificity: one class per block, no element selectors that can cancel a class's spacing.

## Ruled out

The default-page kit: a hero with a big number and a small label, gradient washes, identical rounded cards with the same soft shadow, `→` appended to links, tinted near-black standing in for black, entrance fades on every section. The house's mono meta lines, lowercase labels and legend strip are not on this list: they are the skin, chosen, and they stay.

## Build

1. One sentence on what must click for the reader; the sections as a list.
2. Build. `render-lint` the file and fix every fatal finding; then screenshot both schemes, `Read` them, fix what the eye catches.
3. Remove one thing. Then present.
