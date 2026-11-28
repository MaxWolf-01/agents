---
name: house-style
description: "House style for max's own sites and tools: parchment over brown ink by day, charcoal and sand by night, one moss accent, serif text, mono for data. Load before building or styling any page, app, report, board or HTML artefact that is max's own, and when asked for the house style, the palette, or to make something look like mwolf.dev."
---

# House style

The look of [mwolf.dev](https://mwolf.dev) as a floor: a quiet page, separated by space rather than by boxes, on which nothing raises its voice. Copy `tokens.css` and the font link from the head of `demo.html` into the project, then fit the serif, its size and leading, the measure and the spacing to the project. The colours, the muted/strong split and the habits make it the house, so they stay.

## Colour

`tokens.css` holds sixteen tokens, each colour a `light-dark()` pair. The page follows the system scheme; `data-theme="day"` or `"night"` on the root pins it, and that attribute is the whole toggle. Every page built on this sets the attribute from `?theme=day|night`, so a screenshot can pin a scheme.

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
| `series-1` to `series-5` | the series of a chart that has three or more, taken in order |

A colour the tokens lack (a status, a variant, a code token) comes from [Flexoki 2.0](https://github.com/kepano/flexoki/blob/2.0.0/css/flexoki.css) at half its chroma rather than from an invented hex: its hues are calibrated as a set, and halved they sit as quietly as the series, which are made the same way; at full chroma they read as neon on parchment. Flexoki's steps are set for its lighter paper, so start from these on the house grounds: by day a mark (a line, a bar, an icon, 3:1) from 600 and text (4.5:1) from 700, yellow one step darker for each; by night both from 400, red text from 300. Halve the chroma in OKLCH, then move the lightness only as far as the contrast needs.

## Type

Newsreader for text; Literata, EB Garamond and Source Serif 4 fit too; a grotesk over a sans reads as a generated page. Sizes are set per family, because x-heights differ by more than a point: a project that swaps the serif re-sets `--size-body` and `--leading-body` in `tokens.css`, and re-measures small text ported from a grotesk downward, since Newsreader runs wider at the same size. IBM Plex Mono is for content that is data (dates, numbers, field labels, table heads, code) and nothing else; as texture it reads cheap.

Roles, so a page asks for a heading rather than a size:

| class | job |
| --- | --- |
| `v-title` | the page title, one per page |
| `v-h2`, `v-h3` | section, sub-section |
| `v-lead` | the sentence under a title, usually muted |
| body | running text, stopped at the measure; `prose` styles it by tag |
| `v-small` | captions, chrome, asides |
| `v-meta` | the mono line: dates, counts, provenance, field labels |
| `v-num` | a number inside text or a cell, tabular |

## Habits

1. **Separate with space, not with boxes.** A hairline only where two things would otherwise touch; a filled block only where something must be found. A hairline does what a shadow would, and the dimmed backdrop says which layer is in front.
2. **Labels in sentence case, never small caps.** Small type in capitals shouts, and one shouting label makes the whole palette loud. A figure's labels may go lowercase.
3. **One accent, one job.** Links and the primary action wear it and nothing else does, so the eye can trust it: one meaning, however many marks carry it.
4. **The screen holds what is read every time.** An explanation, a rare detail, a label the styling already carries: each sits one hover, click or key away, where the reader is. Decluttering moves a needed fact to a better place rather than deleting it.
5. **Show a state rather than label it, and show each fact once.** A mark that says it needs no word beside it, and the good state needs no mark at all.
6. **Each thing sits beside what it is about**: a status with the item it describes, an action next to its subject, a control where its effect shows.
7. **Every word reads cold**, in words the user already has. A tooltip says what the thing means and when it matters, which its name alone cannot.
8. **The content gets the room.** Margins as wide as reading needs and no wider, no horizontal scroll, full names wherever the space allows.
9. **A dashboard leads with what the user can act on**, in the user's scales (days, gigabytes left) rather than the system's counters. A chart earns its place by showing change over time; a count nobody acts on goes. Every status page is a small dashboard.
10. **A page opens on what it is for.** A tool or a dashboard is no report: no preamble, no large header, no summary ahead of the thing itself.
11. **Reuse what already works.** One component and one icon set per job across every surface of a project, and the best surface it already has as the reference for the next.

Copy on the page is artefact text: `/mx:writing-for-humans` binds every label and every line of chrome.

## Companions

- `PARTS.md`: one line per part (button, icon, tooltip, keys, input, table, note, overlay, chart, motion), and the Tailwind v4 mapping. Read it before building anything the user clicks or types into.
- `demo.html`: every token, role and part rendered, with the toggle and the `?theme=` reading to copy.

Before presenting anything built on this, lint it, look at both schemes and drive it, as `/mx:show` says under Produce and present.
