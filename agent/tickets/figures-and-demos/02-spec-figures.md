---
status: done
blocked-by: [01]
diff: [a1fefa8b24fef7b9eb7d4752c591947a2b4bda4a..ba03de991d6757b974df1bbdca5934c1ca2666de]
---

# A grilling round draws its figures, opens them first, and re-renders them as the design moves

Slice of `spec.md`, building on Solution (you, r2, r5), Decisions "Figures live in `agent/show/<feature>/`" (you, r2), "Re-render with the round" (you, r5), "The figure is opened before the round is read" (you, r5), "The figure is the decision's home" (agent's call, r5, delegated by you), "Trigger by shape, not size, on every artefact" (you, r5).

## What to build

A grilling round whose Decisions gain or move a decision of a shape the table lists produces or re-renders that figure in the same round, commits its source with the round, and opens it in the user's browser before the round's message, whose first line says it is open. The Decisions entry links the figure and carries what the figure cannot: the why and the rejected alternative. The spec format's Decisions section points at the table beside the content types it already lists, and grilling's sentence that the spec stays textual and a visual is a show artefact is replaced by the rule, not joined by it.

## Acceptance criteria

- [x] The spec format's Decisions section points at `/mx:show`'s table where it lists schema changes, API contracts and interactions; the grilling skill's round produces, re-renders, commits and opens the figure, in that order, before the message.
- [x] The sentence "The spec stays textual; a visual that would help a round is a `/mx:show` artefact" no longer exists in any form.
- [x] Property, reviewed: a figure states the decision as it stands; a figure whose decision moved is re-rendered in the same round.
- [x] Property, reviewed: a figure's source is committed; its raster render is never tracked.
- [x] Property, reviewed: a spec with no decision of a listed shape has no figure.
- [x] Demo: `agent/show/figures-and-demos/02-spec-figures/demo`, executable, no arguments: a driven round on a toy spec with a schema decision, showing the figure produced and the message's first line; where the plugin cannot be loaded in that session, the closest render, and the comment says so.

## Comments

**2026-09-18** The rule landed in two places: `/mx:grilling`'s "The spec" section, where a round now draws the figure for a decision whose shape `/mx:show`'s table lists, re-renders it when the decision moves, removes it when the decision goes, puts its source in the round's commit beside the spec, and opens it before the message whose first line says so; and `SPEC-FORMAT.md`'s Decisions, where the entry links that figure and keeps what the figure cannot carry. The sentence that kept the spec textual is gone. Nothing else was rewired: the landing's demo, the retire step and the README belong to the sibling tickets. Not merged: the branch `ticket/figures-and-demos/02-spec-figures` is three commits, `bbf0daa` (the rule), `2a7b934` (the demo), `d5616d1` (the review round).

**Demo**

```
./agent/show/figures-and-demos/02-spec-figures/demo
```

No arguments. It drives the same grilling round twice, once against the skill pair as it stood and once against this branch's, each in a scratch root of its own, and takes about seven minutes and two Sonnet sessions. The prompt is the user's answer to the one question a toy `orders` spec left open, and it never says figure, diagram or show. What the last run printed, abridged (the transcripts, the two specs and the figures land in `agent/show/figures-and-demos/02-spec-figures/out/`, which the run replaces wholesale):

```
== the prompt both runs get
/mx:grilling Round 1 asked how an order keeps its lines: (a) a text column on
`orders`, (b) a table of their own. q1 -> b. `orders` keeps id, customer,
placed_at, status; `order_lines` holds id, order_id, sku, qty, unit_price.
One order has many lines, a line belongs to exactly one order, and a line's
unit_price is the price at the time of the order, never a lookup into the
product. Deliver round 2.

== before: the grilling skill as it stood, with the spec kept textual
· Read(repo/agent/tickets/orders/spec.md)
· Read(plugin/skills/grilling/SPEC-FORMAT.md)
· Bash(which diffview 2>/dev/null; echo "diffview exit: $?"; cat plugin/skills/grilling/*.md)
· Write(repo/agent/tickets/orders/spec.md)
· Bash(git add agent/tickets/orders/spec.md && git commit -m "the spec after round 2")

== after: the same prompt, the same plugin, this branch's grilling skill
· Read(repo/agent/tickets/orders/spec.md)
· Read(plugin/skills/grilling/SPEC-FORMAT.md)
· Bash(which diffview xdg-open claude-browser 2>&1; echo ---; cat plugin/skills/show/SKILL.md)
· Read(plugin/skills/mermaid/SKILL.md)
· Write(repo/agent/show/orders/schema.mmd)
· Bash(timeout 60 bash plugin/skills/mermaid/tools/validate.sh agent/show/orders/schema.mmd)

Rendered. Now the sample instance beside it.
· Write(repo/agent/show/orders/sample.json)
· Edit(repo/agent/tickets/orders/spec.md)

== what each round committed, and what it left uncommitted

before
  b473149 the spec after round 2

    agent/tickets/orders/spec.md

after
  (the round committed nothing)
  uncommitted:
   M agent/tickets/orders/spec.md
  ?? agent/show/orders/sample.json
  ?? agent/show/orders/schema.mmd
  ?? agent/show/orders/schema.svg

== the Decisions entry for the lines, as each round left it

out/before-spec.md
  - **How an order keeps its lines: a table of its own.** `orders` holds `id`,
  `customer`, `placed_at`, `status`; `order_lines` holds `id`, `order_id`,
  `sku`, `qty`, `unit_price`. One order has many lines; a line belongs to
  exactly one order. `(you, r1)`
  ... eight more bullets, all prose, no figure ...

out/after-spec.md
  - **An order keeps its lines in a table of their own, not a text column.**
  `orders` holds `id`, `customer`, `placed_at`, `status`; `order_lines` holds
  `id`, `order_id`, `sku`, `qty`, `unit_price`. One order has many lines, a
  line belongs to exactly one order (`order_id` is required). See
  [schema.mmd](../../show/orders/schema.mmd) for the relation and
  [sample.json](../../show/orders/sample.json) for an instance; the figure
  shows the shape, not why a line can't be reused across orders — an order is a
  point-in-time record of what was bought, so a shared line would let editing
  one order's price silently reprice another. `(you, r1)`

== the figures each round drew

before
  (no show directory; this round drew no figure)

after

out/after-show/orders/sample.json
  {
    "order": { "id": "ord_1042", "customer": "cust_881", "placed_at":
  "2026-09-18T14:03:00Z", "status": "placed" },
    "order_lines": [
      { "id": "ln_2001", "order_id": "ord_1042", "sku": "SKU-BREAD-01", "qty":
  2, "unit_price": 3.50 },
      { "id": "ln_2002", "order_id": "ord_1042", "sku": "SKU-EGGS-12", "qty":
  1, "unit_price": 4.20 }
    ]
  }

out/after-show/orders/schema.mmd
  erDiagram
      ORDERS ||--|{ ORDER_LINES : "has"
      ORDERS {
          id id PK
          string customer
          timestamp placed_at
          string status
      }
      ORDER_LINES {
          id id PK
          id order_id FK
          string sku
          int qty
          decimal unit_price
      }

out/after-show/orders/schema.svg (40186 bytes)

== the first line of each round's message

before
  Applied round 1's answer to the spec and committed it. Here's round 2.

after
  This environment has no browser/`xdg-open` available, so I can't open the
  figure — it's at `agent/show/orders/schema.mmd` / `schema.svg`, ER diagram of
  `orders`→`order_lines` with the sample instance beside it in `sample.json`.

== opening what the after round drew
no display here, so nothing is opened: .../out/after-show/orders/schema.svg
```

On a machine with a display the last step opens that SVG instead of printing it, and the after round opens its own figure rather than reporting that it cannot: the sentence the last line quotes is that rule firing on a headless host. Three runs were watched. The after round drew the ER diagram with a sample instance beside it and linked both from the Decisions entry every time; the before round drew nothing every time, and twice wrote the schema into the spec as prose. What varied is the commit: two runs put the figure in the round's commit beside the spec, this one left both uncommitted, which is [D1].

**I need from you**

- [D1] The round's two commit timings. `mx/skills/grilling/SKILL.md:39` says the round commits "when the answers arrive", and this ticket asks the figure to be committed before the message. I stated no second timing: the figure rides whatever commit the round makes. In a driven round the answers have arrived, and one of three runs still left the figure uncommitted until it heard back. Either the paragraph gains a timing for the figure, or it stays as it is and a round holding its commit holds the figure with it.
- [D2] The demo drives two live sessions with unrestricted `Bash` on the machine that runs it, which under the landing rule is yours; the same call you have on ticket 01's demo, raised again because this one starts two more.
- [D3] `mx/README.md:74` and `mx/skills/orient/SKILL.md:22` still say a show artefact lives at `agent/show/<slug>/` and is "committed once approved". The figure rule contradicts the commit gate outright: a figure commits with the round that drew it, before anyone approves anything. Ticket 01 raised this as its `[D1]` and left it for ticket 04, which landed without it.

**Details, if you want them**

- [D4] Assumptions:

```
Assumptions
- A1 `mx/skills/grilling/SKILL.md:41`: the rule adds a third verb, "removed in the round that drops it", to the ticket's produce and re-render. The Property says a figure is "never left standing", and a figure whose decision was dropped is the exact artefact the problem statement is about.
- A2 `mx/skills/grilling/SKILL.md:41`: no commit timing of its own for the figure, per [D1].
- A3 `mx/skills/grilling/SKILL.md:41`: `(claude-browser, else xdg-open)` is repeated here although `/mx:show` carries it. Written after a run, not from the reading: with the pointer alone the round read the opening as part of the review surface, found `diffview` missing and opened nothing, which is user story 6 missed.
- A4 `mx/skills/grilling/SPEC-FORMAT.md:47`: the figure pointer sits under the "no specific file paths" rule rather than directly under the bullet list it names, so the entry is never told to link a figure and forbidden a path in the same breath. Both the list above and the prototype exception below it keep it in reach.
- A5 `agent/show/figures-and-demos/02-spec-figures/demo:19`: each driven session gets unrestricted `Bash` on the host that runs the demo, stated in the header rather than confined, as ticket 01's demo does. Raised as [D2].
- A6 `agent/show/figures-and-demos/02-spec-figures/before-SKILL.md:2`: the superseded marker is a YAML comment inside the frontmatter, so the before run reads the skill it stands in for byte for byte. Declined review finding, as on ticket 01.
```

- [D5] Findings, review range `a1fefa8..2a7b934`, three axes (correctness, standards, spec), reports under `agent/reviews/`, which die with the worktree. Fixed in `d5616d1` unless marked. The one that mattered: both arms of the demo shared one scratch tree, and the recorded after session ran `diff -u` between the two skill versions before drawing anything, so the run proved less than its header claimed; each arm now gets a root of its own. Three more failure states that read as success: the transcript printed the round's message anyway (the stream carries two near-identical copies and the filter matched by string), the ran-or-not guard tested a file that no longer holds the message, and nothing checked the plugin had loaded at all. Then: the figure's opening had lost its actor (A3), the rule was sentence seven of the skill's longest paragraph, the spec-format sentence garden-pathed and sat above the file-path rule (A4), the toy repo's commits rode the host's git config, the demo header named a table it never named and claimed two prompts where there is one, a bash comment was the only home of a process rule, a step label said the before round wrote something it had not, and the before copies were named as if live. Declined: unrestricted `Bash` (A5), the marker's placement (A6). Left for their owners: the README and orient rows ([D3]).
- [D6] Friction. A skill's wording is only observable by driving a session against it, seven minutes a go, and three of this ticket's clauses exist because a run was watched rather than because a reader objected: the opener (A3), the figure rule as its own paragraph, and the isolation the demo needed. The reviewers found the contamination by reading the committed transcript, which is the argument for a demo that writes its evidence to disk, but a cheap way to drive one prompt against a branch's plugin and diff what two versions of a skill produce would have paid for itself here for the third ticket running. The same 70% of harness now sits in two demos (`01-show-table` and this one) and a third is coming with ticket 03: every fix above was a one-copy fix that should have been a one-place fix, and show's "one executable file named `demo`" is what rules out a shared helper beside them.
