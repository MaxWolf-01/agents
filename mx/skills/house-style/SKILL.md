---
name: house-style
description: "House style for max's own sites and tools: parchment over brown ink by day, charcoal and sand by night, one moss accent, serif text, mono for data. Load before building or styling any page, app, report, board or HTML artefact that is max's own, and when asked for the house style, the palette, or to make something look like mwolf.dev."
---

# House style

The look of [mwolf.dev](https://mwolf.dev) as a floor: a quiet page, separated by space rather than by boxes, on which nothing raises its voice. Copy `tokens.css` and the font link from the head of `demo.html` into the project, then deviate where the project asks for it: the serif that fits, the size and leading that fit that serif, the measure, the spacing. The colours, the muted/strong split and the habits are what make it the house, so those stay.

## Colour

Ten tokens, each a `light-dark()` pair in `tokens.css`. The page follows the system scheme; `data-theme="day"` or `"night"` on the root pins it, and that attribute is the whole toggle.

| token | job |
| --- | --- |
| `ground` | the page |
| `ground-2` | inputs, figures, code: the only filled surfaces |
| `edge` | hairlines |
| `muted` | secondary text: meta, captions, chrome, summaries |
| `body` | running text |
| `strong` | headings and emphasis |
| `accent` | links, the primary action, the one focal mark |
| `wash` | the fill under an accent stroke, the highlighted row |
| `accent-2` | caution and errors |
| `mark` | text selection |

## Type

Newsreader for text; Literata, EB Garamond and Source Serif 4 fit too; a grotesk over a sans reads as a generated page. Sizes are set per family, because x-heights differ by more than a point; the numbers are in `tokens.css`. IBM Plex Mono for content that is data: dates, numbers, field labels, table heads, code. Mono as texture reads cheap.

Roles, so a page asks for a heading rather than a size:

| class | job |
| --- | --- |
| `v-title` | the page title, one per page |
| `v-h2`, `v-h3` | section, sub-section |
| `v-lead` | the sentence under a title, usually muted |
| body | running text, stopped at the measure; `prose` styles it by tag |
| `v-small` | captions, chrome, asides |
| `v-meta` | the mono line: dates, counts, provenance, field labels; lowercase |
| `v-num` | a number inside text or a cell, tabular |

## Habits

1. **Separate with space, not with boxes.** A hairline only where two things would otherwise touch; a filled block only where something must be found. A hairline does what a shadow would, the dimmed backdrop says which layer is in front, and a word does what an icon would.
2. **Labels lowercase, never small caps.** Small type in capitals shouts, and one shouting label makes the whole palette loud.
3. **One accent, one job.** Links and the primary action wear it; nothing else does, so the eye can trust it. A page with three accented things has two too many.

Copy on the page is artefact text: `/mx:writing-for-humans` binds every label and every line of chrome.

## Companions

- `PARTS.md`: one line per part (button, input, table, note, overlay, chart), and the Tailwind v4 mapping.
- `demo.html`: every token, role and part rendered, with the toggle to copy. Open it to see the floor; `?theme=day` and `?theme=night` pin a scheme for a screenshot.

Look at both schemes before presenting anything built on this.
