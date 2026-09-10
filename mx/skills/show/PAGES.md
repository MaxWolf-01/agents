# Explainer pages

An HTML page as the artifact: side-by-side panels, an interactive figure, prose interleaved with figures the reader can poke at. One self-contained file, inline CSS, JS only where the reader interacts. The register in `SKILL.md` binds; the tokens, type table, scheme toggle and render step are the ones in `SVG-FIGURES.md`, reused as they stand.

## Page-level additions to the skin

- Body text: Geist 400, 14px, line length under 80 characters, `line-height` 1.5. Headings: Geist 600 in three steps (1.25rem, 1rem, 0.85rem). Sentence case everywhere outside the skin's eyebrows and arrow labels.
- One content column, at most 1128px, left-aligned. Everything on the 4px grid.
- Structure encodes information. A border, a rule, a number, a label exists because it separates or orders something the reader needs told apart; numbering (`01 / 02`) only when the content is a sequence.
- One emphasized element per page, in the accent. Everything else ink, muted, soft.
- Motion only in answer to the reader's action (open, expand, confirm), and it shows what changed. No entrance animations, no hover transitions on every card.
- Quality floor: usable at 700px wide, visible keyboard focus, `prefers-reduced-motion` honoured, both schemes with the toggle.
- Selector specificity: one class per block, no element selectors that can cancel a class's spacing.

## Ruled out

The default-page kit: a hero with a big number and a small label, gradient washes, identical rounded cards with the same soft shadow, `→` appended to links, tinted near-black standing in for black, entrance fades on every section. The skin's zone labels, mono detail lines and legend strip are not on this list: they are the skin, chosen, and they stay.

## Build

1. One sentence on what must click for the reader; the sections as a list.
2. Build. Screenshot both schemes, `Read` them, fix collisions and overflow.
3. Remove one thing. Then present.
