---
name: house-style
description: "House style for max's own sites and tools: parchment over brown ink by day, charcoal and sand by night, one moss accent, serif text, mono for data. Load before building or styling any page, app, report, board or HTML artefact that is max's own, and when asked for the house style, the palette, or to make something look like mwolf.dev."
---

# House style

The look of [mwolf.dev](https://mwolf.dev) as a floor: a quiet page, separated by space rather than by boxes, on which nothing raises its voice. Copy `tokens.css` and the font link from the head of `demo.html` into the project, then deviate where the project asks for it: the serif that fits, the size and leading that fit that serif, the measure, the spacing. The colours, the muted/strong split and the habits are what make it the house, so those stay.

## Colour

Eleven tokens in `tokens.css`, the colours as `light-dark()` pairs. The page follows the system scheme; `data-theme="day"` or `"night"` on the root pins it, and that attribute is the whole toggle. Any page built on this reads `?theme=day|night` and sets the attribute from it, so a screenshot can pin a scheme.

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
| `wash-ink` | a zone's fill; a banner's ramp is the same mix of muted, 6% to 22% |
| `accent-2` | caution, errors, and the second value of two-valued data |
| `mark` | text selection |

## Type

Newsreader for text; Literata, EB Garamond and Source Serif 4 fit too; a grotesk over a sans reads as a generated page. Sizes are set per family, because x-heights differ by more than a point: a project that swaps the serif re-sets `--size-body` and `--leading-body` in `tokens.css`, and small text ported from a grotesk is re-measured downward, since Newsreader runs wider at the same size. IBM Plex Mono for content that is data: dates, numbers, field labels, table heads, code. Mono as texture reads cheap.

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

1. **Separate with space, not with boxes.** A hairline only where two things would otherwise touch; a filled block only where something must be found. A hairline does what a shadow would, the dimmed backdrop says which layer is in front, and a word does what an icon would, except a brand mark that reads faster than its name.
2. **Labels lowercase, never small caps.** Small type in capitals shouts, and one shouting label makes the whole palette loud.
3. **One accent, one job.** Links and the primary action wear it; nothing else does, so the eye can trust it. One meaning, however many marks carry it: a page whose accent means three things has two too many.

Copy on the page is artefact text: `/mx:writing-for-humans` binds every label and every line of chrome.

## Companions

- `PARTS.md`: one line per part (button, input, table, note, overlay, chart), and the Tailwind v4 mapping.
- `demo.html`: every token, role and part rendered, with the toggle and the `?theme=` reading to copy. Open it to see the floor.

Before presenting anything built on this, `render-lint` the page (text that escapes its box, collides with other text, or is cut off by a box that hides its overflow, with a crop per finding) and look at both schemes.
