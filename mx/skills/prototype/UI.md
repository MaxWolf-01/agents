# UI Prototype

Generate **radically different UI variations** on a single route, switchable from a floating bottom bar. The user flips between variants in the browser and picks one, or asks for parts of several built whole in the next round.

## Two sub-shapes: strongly prefer sub-shape A

A UI prototype is judged best **butting up against the rest of the app**: real header, real sidebar, real data, real density; on a route of its own, every variant looks fine. Use sub-shape A whenever an existing page could plausibly host the variants, and sub-shape B only when none could.

### Sub-shape A: adjustment to an existing page (preferred)

Variants render **on the existing route**, gated by a `?variant=` URL search param; its data fetching, params and auth stay, and only the rendering swaps.

Something with no page yet that *would naturally live inside one* (a new section of the dashboard, a new card on the settings screen, a new step in an existing flow) is still sub-shape A: mount the variants inside the host page.

### Sub-shape B: a new page (last resort)

For a thing with no existing page to live inside, such as an entirely new top-level surface or a flow that embeds nowhere sensible: a **throwaway route**, with the same `?variant=` pattern.

## Process

### 1. State the question and pick N

N is the number of rival whole designs the question holds, with no fixed count, two or ten or more, since the reader cycles through them on the switcher.

Write the plan in one line, in the prototype's location or a top-of-file comment:

> "Three variants of the settings page, switchable via `?variant=`, on the existing `/settings` route."

### 2. Generate radically different variants

Variants are **structurally different**: in layout, information hierarchy and primary affordance, not just colour. Where two drafts come out too similar, redo one with explicit guidance against the shape they share ("do not use a card grid").

Two more tests every variant passes before it is offered for a pick:

- **Different at rest.** Loaded and left untouched, each variant differs on what a reader sees first, before anything is opened, hovered or expanded. Variants that part ways only once something is opened read as one design, and the pick never happens.
- **Whole.** Each variant is a complete design that could ship as it stands. Where the question has independent axes (where a panel sits, how its rows read), each variant commits to one answer on every axis, so the user never assembles a design to pick one. The axes may also be exposed beside the wholes (step 4) where that helps the user see more variations or try a combination of their own; the pick is still offered from the wholes.

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
- **Variant label**: the current variant's key, and its name where it exports one, e.g. `B: Sidebar layout`.
- **Right arrow**: cycles forward (wraps around).

Behaviour:

- Clicking an arrow updates the URL search param so the variant is shareable and reload-stable.
- Keyboard: `←` and `→` also cycle, except while an `<input>`, `<textarea>` or `[contenteditable]` has focus.
- Visually distinct from the page (a high-contrast pill, a subtle shadow), so nobody takes it for part of the design being judged.
- Hidden in production builds: gate on `process.env.NODE_ENV !== 'production'` or an equivalent check, so a stray prototype merge can't ship the bar to users.

Where the axes are exposed beside the wholes (step 2), the bar also carries one control per axis, each kept in its own search param beside `?variant=` (e.g. `?variant=B&panel=left`) so a combination is shareable and reload-stable too. Cycling to a variant resets every axis to that variant's answers.

### 5. Hand it over

Give the user the URL and the `?variant=` keys. The useful feedback is usually **"I want the header from B with the sidebar from C"**: that is the design they want, and the next round offers it built whole.

### 6. Capture the answer and clean up

Once a variant has won, capture the answer (which variant and why) and the prototype the way the [SKILL](SKILL.md) describes, fold the winner into the real code, and move the rest out of the app tree to where rule 7 of the [SKILL](SKILL.md) moves a captured prototype:

- **Sub-shape A**: fold the winner into the existing page; move the losing variants and the switcher out of the app tree.
- **Sub-shape B**: promote the winning variant to a real route; move the throwaway route and the switcher out of the app tree.

The full set of variants is kept there, not binned, for as long as the work is being built; variants and a switcher left in the app tree rot fast and confuse the next reader.

## Anti-patterns

- **Sharing too much code between variants.** A shared `<Header>` is fine; a shared `<Layout>` is not, since each variant has to be free to throw out the layout.
- **Wiring variants to real mutations.** A variant that has to mutate points at a stub: the question is "what should this look like", not "does the backend work".
- **Promoting the prototype directly to production.** Variant code was written without tests and with minimal error handling; rewrite it properly when you fold it in.
