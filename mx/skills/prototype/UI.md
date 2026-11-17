# UI Prototype

Generate **radically different UI variations** on a single route, switchable from a floating bottom bar. The user flips between variants in the browser, picks one or asks for parts of several built whole in the next round, then throws the rest away.

## Two sub-shapes: strongly prefer sub-shape A

A UI prototype is much easier to judge when it's **butting up against the rest of the app**: real header, real sidebar, real data, real density. A throwaway route on its own is a vacuum: every variant looks fine in isolation. Default to sub-shape A whenever there's a plausible existing page to host the variants. Only reach for sub-shape B if the prototype genuinely has no nearby home.

### Sub-shape A: adjustment to an existing page (preferred)

The route already exists. Variants are rendered **on the same route**, gated by a `?variant=` URL search param. The existing data fetching, params, and auth all stay; only the rendering swaps.

If the prototype is for something that doesn't yet have a page but *would naturally live inside one* (a new section of the dashboard, a new card on the settings screen, a new step in an existing flow), that's still sub-shape A. Mount the variants inside the host page.

### Sub-shape B: a new page (last resort)

Only use this when the thing being prototyped genuinely has no existing page to live inside, e.g. an entirely new top-level surface, or a flow that can't be embedded anywhere sensible.

Create a **throwaway route**. Same `?variant=` pattern.

## Process

### 1. State the question and pick N

N is the number of rival whole designs the question holds, with no fixed count: two where it holds two, ten or more where it holds that many, since the reader cycles through them on the switcher.

Write down the plan in one line, in the prototype's location or a top-of-file comment:

> "Three variants of the settings page, switchable via `?variant=`, on the existing `/settings` route."

### 2. Generate radically different variants

Variants must be **structurally different**: different layout, different information hierarchy, different primary affordance, not just different colours. Three slightly-tweaked card grids isn't a UI prototype, it's wallpaper. If two drafts come out too similar, redo one with explicit "do not use a card grid" guidance.

Two more tests every variant passes before it is offered for a pick:

- **Different at rest.** Load each variant and look at it untouched: the difference shows on what a reader sees first, before anything is opened, hovered or expanded. Variants that part ways only once something is opened read as one design, and the pick never happens.
- **Whole.** Each variant is a complete design that could ship as it stands. Where the question has independent axes (where a panel sits, how its rows read), each variant commits to one answer on every axis, so the user never has to assemble a design to pick one. Where it helps the user see more variations or try a combination of their own, the axes can also be exposed beside the wholes (step 4); the wholes stay what the pick is offered from.

### 3. Wire them together

Create a single switcher component on the route:

```tsx
// pseudo-code, adapt to the project's framework
const variant = searchParams.get('variant') ?? 'A';
return (
  <>
    {variant === 'A' && <VariantA {...data} />}
    {variant === 'B' && <VariantB {...data} />}
    {variant === 'C' && <VariantC {...data} />}
    <PrototypeSwitcher variants={['A','B','C']} current={variant} />
  </>
);
```

For sub-shape B (new page): the throwaway route under `/prototype/<name>` mounts the same switcher.

### 4. Build the floating switcher

A small fixed-position bar at the bottom-centre of the screen with three pieces, plus the axis controls below where they are exposed:

- **Left arrow**: cycles to the previous variant (wraps around).
- **Variant label**: shows the current variant key and, if the variant exports a name, that name too. e.g. `B: Sidebar layout`.
- **Right arrow**: cycles forward (wraps around).

Behaviour:

- Clicking an arrow updates the URL search param so the variant is shareable and reload-stable.
- Keyboard: `←` and `→` arrow keys also cycle. Don't intercept arrow keys when an `<input>`, `<textarea>`, or `[contenteditable]` is focused.
- Visually distinct from the page (e.g. high-contrast pill, subtle shadow) so it's obviously not part of the design being evaluated.
- Hidden in production builds: gate on `process.env.NODE_ENV !== 'production'` or an equivalent check, so a stray prototype merge can't ship the bar to users.

Where the axes are exposed beside the wholes (step 2), the bar also carries one control per axis, each kept in its own search param beside `?variant=` (e.g. `?variant=B&panel=left`) so a combination is shareable and reload-stable too. Cycling to a variant resets every axis to that variant's answers.

Put the switcher in a single shared component so both sub-shapes can reuse it.

### 5. Hand it over

Surface the URL (and the `?variant=` keys). The interesting feedback is usually **"I want the header from B with the sidebar from C"**; that's the actual design they want, and the next round offers it built whole.

### 6. Capture the answer and clean up

Once a variant has won, capture the answer (which variant and why), then capture the prototype the way the [SKILL](SKILL.md) describes. Fold the winner into the real code and move the rest out of the app tree, where rule 7 of the [SKILL](SKILL.md) moves a captured prototype:

- **Sub-shape A**: fold the winner into the existing page; move the losing variants and the switcher out of the app tree.
- **Sub-shape B**: promote the winning variant to a real route; move the throwaway route and the switcher out of the app tree.

The full set of variants is kept there, not binned, for as long as the work is built; variant components and the switcher left in the app tree rot fast and confuse the next reader.

## Anti-patterns

- **Sharing too much code between variants.** A shared `<Header>` is fine; a shared `<Layout>` defeats the point. Each variant should be free to throw out the layout.
- **Wiring variants to real mutations.** Read-only prototypes are fine. If a variant needs to mutate, point it at a stub; the question is "what should this look like", not "does the backend work".
- **Promoting the prototype directly to production.** The variant code was written under prototype constraints (no tests, minimal error handling). Rewrite it properly when you fold it in.
