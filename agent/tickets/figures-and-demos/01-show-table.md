---
status: review
---

# Show carries the shape table: figures for decisions, demos for landings

Slice of `spec.md`, building on Solution (you, r4), Decisions "One table, two media columns" (you, r4), "Trigger by shape, not size, on every artefact" (you, r5), "The rows" (agent's call, r2 to r5; the sample-instance row is yours, r5), "The demo is one file named `demo`" (you, r4, r5), "A heavy artefact goes to a fresh agent with a brief" (you, r4), "File shape of a figure" (you, r4, r5), "Promotion is the agent's call" (you, r5).

## What to build

An agent that opens `/mx:show` with a decision or a delivered change in hand finds one table and needs no judgment call: the row for the shape of the thing names the figure a spec decision of that shape gets and the demo a landed change of that shape gets, and a shape with no row gets nothing. The skill's description fires from the two stations, writing a spec's Decisions and closing a landing, and not only from a struggling explanation.

Around the table, the conventions the rows lean on, each stated once: a figure is a source file with its SVG beside it, the SVG is what gets opened, the PNG is rendered for embedding and stays untracked, and a page holding several figures scales them; a demo is one executable file named `demo`, no arguments, in the show directory of the work it demonstrates (a feature's slice, a standalone ticket, a loose branch), producing what it produces beside itself and opening it when a display is there; a heavy artefact at either station goes to a fresh agent with a brief naming the artefact, its output path and the sources on disk, and a fork is taken only when the conversation itself is the source; a figure or a demo's output that a README or a PR needs is promoted there on the agent's own judgment, visible in the diff, HTML through the share script.

The rest of the skill (register, media notes, pages, SVG guidance) stays where the table does not retire it; what the table retires goes.

## Acceptance criteria

- [x] Given a two-table schema decision, an agent following the skill produces an ER diagram with a sample row beside it, as source plus SVG under the feature's show directory, and opens the SVG.
- [x] Given a landed CLI change, an agent following the skill writes an executable `demo` with no arguments that runs the CLI and pastes that run's output under the command; given a landed page, `demo` opens it.
- [x] The description names both stations, so the skill is reached from a spec's Decisions and from a closing comment (`/mx:writing-for-agents`, context pointers).
- [x] The fork rule is replaced by the fresh-agent-with-a-brief rule, the fork kept as the named exception.
- [x] Property, reviewed: a demo file takes no arguments and runs from its branch on any host where the project is installed; what it produces lands beside it.
- [x] Property, reviewed: a figure's source is committed; its raster render is regenerated and never tracked.
- [x] Property, reviewed: a slot is never padded; the table says so.
- [x] Demo: `agent/show/figures-and-demos/01-show-table/demo`, executable, no arguments, per the table's row for a skill change: a driven session given a two-table schema decision, showing the figure it produces; where the plugin cannot be loaded in that session, the closest render, and the comment says so.

## Comments

**2026-09-16** The table landed in `/mx:show`, with the conventions its rows lean on: where an artifact goes, the file shape of a figure, the demo as one executable `demo` taking no arguments, promotion to a README or a PR, and a heavy artifact going to a fresh agent with a brief instead of a fork. Nothing outside `mx/skills/show/SKILL.md` was rewired: the pointers from the spec format, the grilling round, the worker contract and the retire step belong to the sibling tickets, and two stale copies of show's old placement rule are left standing for the reason in [D1]. Not merged: the branch `ticket/figures-and-demos/01-show-table` is three commits, `0178b40` (the table), `6c01f6e` (the demo), `fe1cd19` (the review round).

**Demo**

```
./agent/show/figures-and-demos/01-show-table/demo
```

No arguments. It drives the same prompt twice, once against the skill as it stood and once against the table, and takes about five minutes and two Sonnet sessions. What one run printed, abridged (the full transcripts and artefacts land in `agent/show/figures-and-demos/01-show-table/out/`, which the run replaces wholesale):

```
== the prompt both runs get
/mx:show We are mid-grilling on the `orders` feature; its spec is at
agent/tickets/orders/spec.md, and this round settled one call: an order's
lines live in their own table. ... Write the Decisions entry, give the
decision what this station gives a decision of its shape, and end your turn
with one line telling me where to look.

== before: the skill as it stood, with no table to look a shape up in
· Read(before/repo/agent/tickets/orders/spec.md)
· Bash(find before/repo/agent -type f | head -100)
· Bash(find plugin-before/skills/show -type f)
· Edit(before/repo/agent/tickets/orders/spec.md)

Look at `agent/tickets/orders/spec.md:14` for the new Decisions entry with its schema table.

== after: the same prompt, the same plugin, this branch's skill
· Read(after/repo/agent/tickets/orders/spec.md)
· Bash(ls -la plugin-after/skills/show/)
· Skill(mx:mermaid)
· Write(after/repo/agent/show/orders/order-lines/diagram.mmd)
· Bash(bash plugin-after/skills/mermaid/tools/validate.sh .../diagram.mmd)
· Bash(npx -y @mermaid-js/mermaid-cli -i diagram.mmd -o diagram.svg)
· Write(after/repo/agent/show/orders/order-lines/sample.json)
· Write(after/repo/agent/show/orders/order-lines/index.html)
· Bash(chromium --headless ... --screenshot=/tmp/order-lines-light.png)
· Read(/tmp/order-lines-light.png)
· Read(/tmp/order-lines-dark.png)
· Edit(after/repo/agent/tickets/orders/spec.md)

Look at `agent/show/orders/order-lines/index.html`.

== what each run left on disk

before
   M agent/tickets/orders/spec.md

after
   M agent/tickets/orders/spec.md
  ?? agent/show/orders/order-lines/diagram.mmd
  ?? agent/show/orders/order-lines/diagram.svg
  ?? agent/show/orders/order-lines/index.html
  ?? agent/show/orders/order-lines/sample.json

== the Decisions entry each run wrote

out/before-spec.md
  - **Lines live in their own table.** One order has many lines; a line belongs
  to exactly one order. `unit_price` is the price at the time of the order, a
  snapshot, never a lookup into the product. `(you, r1)`

    | table | column | note |
    |---|---|---|
    | `orders` | `id` | |
    ... nine more rows, in the spec, where diffview shows them as source ...

out/after-spec.md
  - **An order's lines live in their own table, not a pasted-in column.**
  `orders` holds `id, customer, placed_at, status`; `order_lines` holds `id,
  order_id, sku, qty, unit_price`. One order has many lines; a line belongs to
  exactly one order. `unit_price` is the price at the time of the order,
  captured onto the line, never a lookup into the product, so a later product
  price change never changes what a placed order reads. Schema and a sample
  instance: `agent/show/orders/order-lines/`. `(you, r2)`

== the figures each run wrote, and the sample instance beside them

before
  (no show directory; this run built no figure)

after

out/after-show/orders/order-lines/diagram.mmd
  erDiagram
      ORDERS ||--o{ ORDER_LINES : has
      ORDERS {
          int id PK
          string customer
          datetime placed_at
          string status
      }
      ORDER_LINES {
          int id PK
          int order_id FK
          string sku
          int qty
          decimal unit_price
      }

out/after-show/orders/order-lines/diagram.svg (39840 bytes)
out/after-show/orders/order-lines/index.html (4716 bytes)
out/after-show/orders/order-lines/sample.json
  {
    "orders": [
      { "id": 4821, "customer": "acme-co", "placed_at": "2026-09-14T10:03:00Z", "status": "placed" }
    ],
    "order_lines": [
      { "id": 91177, "order_id": 4821, "sku": "widget-9", "qty": 2, "unit_price": 14.50 },
      { "id": 91178, "order_id": 4821, "sku": "gizmo-2", "qty": 1, "unit_price": 39.00 }
    ]
  }

== opening what the after run produced
no display here, so nothing is opened: .../out/after-show/orders/order-lines/index.html
```

On a machine with a display the last step opens that page instead of printing it: the ER diagram and the sample instance side by side, with the scheme toggle. The before side varies run to run, since it is a live session with no rule to follow. Across the runs I watched it embedded a mermaid diagram in the spec itself three times, wrote a markdown column table into the spec twice, once declined the task as not a show job, and once put a mermaid source under a show directory it named after the decision rather than the feature, embedding it in the spec as well. It never once produced what the first acceptance criterion describes, a source and its render under the feature's show directory, linked from the entry; the after side did that every time.

**I need from you**

- [D1] `mx/skills/orient/SKILL.md:22` and `mx/README.md:74` still say a show artifact lives at `agent/show/<slug>/` and is "committed once approved", which this change contradicts. Both rows are being edited this wave by [Retiring a ticket or feature retires its show directory and research notes](04-retire-with-the-work.md), so I left them rather than collide. Someone has to carry the path and the commit gate into that edit, or into a follow-up after it lands.
- [D2] The demo drives two unattended sessions with unrestricted `Bash` on whatever machine runs it, which under the landing rule is yours. Confining them is not free: the driven session needs `npx`, `chromium` and a shell to render anything, so an allowlist that fits this run breaks the next one. The alternative is that a skill change is never demoed live. Your call on whether a demo may spend a real session on your machine.
- [D3] The rows as they landed (A1): one row per shape serving both stations, four cells reading `none`, and before/after lifted out of the rows into the paragraph under the table. The spec marks "The rows" as mine to settle, so this is the shape it settled into.
- [D4] `agent/show/mx-readme-figures/demo/` is a directory called `demo`, so the fixed-name convention this ticket writes (`fd -t x '^demo$' agent/show`) steps over it. It retires with its own feature, so I left it.

**Details, if you want them**

- [D5] Assumptions:

```
Assumptions
- A1 `mx/skills/show/SKILL.md:12`: the rows and their pairing across the two columns. The spec's "The rows" is the agent's call (r2 to r5, the sample-instance row aside), so this is where it landed: one row per shape, both stations in one lookup; `none` where the spec named no medium; "a long or interactive run" folded into the flow row; before/after as the paragraph under the table, since it crosses every row rather than being one.
- A2 `mx/skills/show/SKILL.md:41`: a demo writes into `out/` beside itself, and `.gitignore:9` ignores it. The spec says "beside itself"; the subdirectory keeps a run's product apart from the demo's committed inputs and lets one glob cover every demo.
- A3 `agent/show/figures-and-demos/01-show-table/demo:13`: the demo's prompt opens the skill by hand. A bare station prompt ("write this Decisions entry") did not reach the skill in a print-mode session, which is what tickets 02 and 03 are for; without them the demo would be measuring a pointer that does not exist yet.
- A4 `agent/show/figures-and-demos/01-show-table/demo:22`: each driven session gets unrestricted `Bash` on the host that runs the demo, stated in the header rather than confined. Declined review finding, raised as [D2].
- A5 `mx/skills/show/SKILL.md:35`: a mermaid render carries the renderer's own colour scheme, and the both-schemes rule binds a page you author. The two rules had been in conflict; a run spent half its tail rendering mermaid twice and hand-theming the SVG before this clause existed.
- A6 `agent/show/figures-and-demos/01-show-table/before-SKILL.md:2`: the superseded-copy marker sits in the frontmatter as a YAML comment, not as a first line of the body, so the before run reads the skill it is standing in for byte for byte. Review asked for the body line.
- A7 `mx/skills/show/SKILL.md:31`: the placement rule keeps a commit gate, as "committed with that work" rather than show's old "once the user has approved the final version": a figure commits with its round and a demo with its ticket, and the old gate contradicted both.
```

- [D6] Findings, review range `654b4af..6c01f6e`, three axes (correctness, standards, spec), reports under `agent/reviews/`, which die with the worktree. Fixed in `fe1cd19` unless marked: a failed session indistinguishable from an empty result; only the after run's artefacts collected; an arbitrary file opened at the end; ANSI bold in text meant to be pasted; chromium found under one name only; toy commits breaking under `commit.gpgsign`; the host's settings loading into both runs; em dashes in the skill, the demo and a commit message; sibling tickets named by number; the placement rule and commit gate lost with the cut; `out/` a convention only `.gitignore` knew; the description restating the table; the demo's cost unstated; ADRs unreached by the table; "a long or interactive run" dropped from the flow row; the sample instance made compulsory for every schema; a figure cell that would have had to be invented; the colour-scheme conflict. Declined: unrestricted `Bash` (A4, [D2]), the marker's placement (A6), the `demo` directory collision ([D4]). Left for their owners: orient and the README ([D1]), and two notes the reports carry for the sibling tickets, that 02 owns "re-rendered, never left standing" beyond the re-render half the skill states, and 03 owns "every landing has one demo" and the pasted-from-a-run rule.
- [D7] Friction. The skill's own rules are only observable by running a session against them, so every wording change costs a five-minute driven run to see; two clauses (A5, and the figure source named for what it shows) exist only because a run was watched, and both came after the reviewers had passed the text. A cheap way to drive one prompt against a branch's plugin and diff what two versions of a skill produce would have paid for itself here. Two reviewers ran the demo concurrently in the same worktree and their runs interleaved in `out/`; the run now publishes `out/` wholesale at the end, which hides the interleaving rather than preventing it. `--setting-sources ""` is what keeps a driven session from reading the host's own `CLAUDE.md`; it is in one prototype in this repo and nowhere in the skills, and the spec review is what surfaced it.

**2026-09-16**

Addressed: C1, C2, C3, C4, C5, C6, C7, C8

`0a6fb22` on the same branch. The skill is no longer framed on judgment: the opening says a thing is understood in front of a render, whether someone is ruling on it, grilling it, reviewing it or learning how it works, and the description leads with what the skill builds and why before the branches that reach it (C1, C2). Three rows gained a figure where they read `none`, since the figure station is reached when the thing does not exist yet: a prompt or skill change gets an excerpt of the session it would produce or that session role-played as a stand-in, a script or CLI gets example invocations or its interface with sample outputs, and a page gets a tutorial or a recording beside the shot (C3, C4, C5). What a demo is for is now stated where the demo is defined: it is built to be read, and a run that prints pass or fail is a test, which needs no audience (C3). The rows are examples, not the boundary, with the learning case and its distill-style page named (C6), and the mermaid default line is gone (C7).

Promotion now moves rather than copies, per the spec's round 7: the render, its source and the script that regenerates it travel together to where the document's assets live, every reference repointed in the same commit, because no show directory outlives its work.

One clause is from a run rather than a comment. The review round had made the sample instance conditional on "a record shape"; the next run read a two-table schema as not one and shipped the ER diagram alone, which is this ticket's first acceptance criterion missed. The cell now names the two halves and what each is for, and the run after it produced both again.

**Demo**

```
./agent/show/figures-and-demos/01-show-table/demo
```

Unchanged since the last round, rerun against this round's skill. What that run printed, abridged:

```
== before: the skill as it stood, with no table to look a shape up in
· Read(before/repo/agent/tickets/orders/spec.md)
· Bash(find / -type d -iname "grilling*" 2>/dev/null)
· Read(plugin-before/skills/grilling/SKILL.md)
· Read(plugin-before/skills/grilling/SPEC-FORMAT.md)
· Bash(which diffview 2>/dev/null; diffview --help 2>&1 | head -20)
· Edit(before/repo/agent/tickets/orders/spec.md)

Look at `agent/tickets/orders/spec.md:14`.

== after: the same prompt, the same plugin, this branch's skill
· Read(after/repo/agent/tickets/orders/spec.md)

No show directory yet. This decision is a schema/record shape: two related
tables plus a sample instance. Per the table that gets an ER diagram and a
sample instance beside it. Let me invoke the mermaid skill before building
the figure.
· Skill(mx:mermaid)
· Write(after/repo/agent/show/orders/order-lines/schema.mmd)
· Bash(bash plugin-after/skills/mermaid/tools/validate.sh .../schema.mmd)
· Bash(npx -y @mermaid-js/mermaid-cli ... -o schema.svg)
· Write(after/repo/agent/show/orders/order-lines/index.html)
· Bash(chromium --headless ... --screenshot=/tmp/light.png)
· Read(/tmp/light.png)
· Edit(after/repo/agent/tickets/orders/spec.md)

Look at `agent/show/orders/order-lines/index.html`.

== what each run left on disk

before
   M agent/tickets/orders/spec.md

after
   M agent/tickets/orders/spec.md
  ?? agent/show/orders/order-lines/index.html
  ?? agent/show/orders/order-lines/schema.mmd
  ?? agent/show/orders/order-lines/schema.svg

== the Decisions entry each run wrote

out/before-spec.md
  - **An order's lines live in their own table, not a text column.** `orders`
  holds `id`, `customer`, `placed_at`, `status`; `order_lines` holds `id`,
  `order_id`, `sku`, `qty`, `unit_price`. One order has many lines, a line
  belongs to exactly one order. A line's `unit_price` is captured at order
  time, not looked up from the product. `(you, r2)`

out/after-spec.md
  - **An order's lines live in their own table, `order_lines`, not a text
  column on `orders`.** ... `unit_price` is the price at the time the order
  was placed, copied onto the line, never a lookup into the product, so a
  later price change on the product cannot alter a past order. `(you, r2)`
  [Figure](../../show/orders/order-lines/index.html)

== the figures each run wrote, and the sample instance beside them

before
  (no show directory; this run built no figure)

after

out/after-show/orders/order-lines/index.html (4214 bytes)

out/after-show/orders/order-lines/schema.mmd
  erDiagram
      orders {
          int id PK
          string customer
          datetime placed_at
          string status
      }
      order_lines {
          int id PK
          int order_id FK
          string sku
          int qty
          decimal unit_price
      }
      orders ||--o{ order_lines : lines

out/after-show/orders/order-lines/schema.svg (39823 bytes)

== opening what the after run produced
no display here, so nothing is opened: .../out/after-show/orders/order-lines/index.html
```

The page that last line opens on your machine carries the ER diagram and, under it, the sample instance: one `orders` row as JSON, its two `order_lines` rows, and one sentence making the snapshot rule concrete ("The product catalog now prices WIDGET-12 at 15.25. The line still reads 14.50, the price on 2026-09-14"). The before run wrote prose into the spec and built nothing.

**I need from you**

- [D8] The promotion rule says "where that document's assets live, `mx/assets/` for this repo's README", not `docs/figures/` as your comment had it: this repo has no `docs/`, and `mx/README.md` embeds `assets/one-flow.png` and its siblings, which is `mx/assets/`. Say the word if `docs/figures/` is where you want them to move to instead, since that is a move of the existing figures, not just a wording change.
- [D9] `status: review` is not one of the four states the tracker's frontmatter lists (`proposed | open | claimed | done`), and nothing in dispatch or the tracker writes it. I set it as you asked; either the board knows the state and `MARKDOWN.md` does not, or the flow means `claimed` here.
- [D1] still stands, and is now sharper: the promotion rule contradicts `mx/skills/orient/SKILL.md:22` and `mx/README.md:74` on two facts rather than one, the path and the retire lifecycle.

**Details, if you want them**

- [D10] Two more assumptions, on top of A1 to A7 above:

```
Assumptions
- A8 `mx/skills/show/SKILL.md:23`: "a shape with no row" now means nothing is owed rather than nothing is built, so it sits beside the rows-are-examples paragraph without contradicting it: the table never compels a slot to be filled, and it never forbids an artifact it does not name.
- A9 `mx/skills/show/SKILL.md:73`: the promotion destination is named as `mx/assets/`, the directory this repo's README actually reads from. Raised as [D8].
```

- [D11] Friction, on top of [D7]. A driven session can read the installed plugin straight off disk, whatever `--plugin-dir` and `--setting-sources ""` load: this round's before run ran `grep -rl station /home/agent/.claude/plugins/marketplaces/.../mx/skills/`. It found nothing that mattered, since the installed copy is the old skill and the before run wanted the old skill, but a run that reads the machine's installed plugin while standing in for a branch's is a hole in the comparison that no flag closes. The other cost is the loop: a wording change in a skill is only observable by driving a session against it, five minutes a go, and the two clauses this round owes to a run rather than to a reader (the sample instance, and the figure source named for what it shows in the last round) are both cases where reading the text did not predict what a session would do with it.
