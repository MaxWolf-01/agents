---
status: done
blocked-by: [06]
---

# The flow skills describe one flow

## What to build

The skills that route and gate work say what the spec's Solution says. Orient's main flow: an intent arrives in chat; grilling as deep as it needs; the brief test, stated as the spec's paragraph and not as a table, decides loose, ticket or spec; a fresh worker per ticket; the review page and the demo per landed slice; QA. The size call at the gate ("build here, or to-tickets") is gone; a feature always slices. Loose is defined as the absence of a brief, with no agent review. The standalone ticket path and the speculative build are on the map, and the user's stations (answering open questions, the demo plus review page per slice, QA, the needs-human queue) are named as the only places their attention is asked for. The demo has two parties and the map keeps them apart: the worker specifies it in its closing comment as steps a stranger can run, and the orchestrating session on the user's machine performs them and opens the result, since a worker on a host can open nothing for the user.

Grilling's gate becomes non-blocking: when the frontier is empty the session cuts the tickets and dispatches them with the agent's calls still marked; the spec is confirmed when the user ratifies on the review page or in chat; "do not act before that confirmation" is replaced by that rule. To-tickets cuts from a draft spec whose frontier is empty, publishes the tickets as `proposed`, renders the board, and names in each ticket the spec calls it builds on for the worker to carry as assumptions; its quiz no longer blocks the build. The prototype skill says a prototype is for rival shapes or something that must be seen or driven, and that a single clear design is built. Phase-boundaries and the README's flow prose follow. The README's figures are regenerated from `agent/show/one-flow/` into the plugin's assets and embedded where the old flow figures were.

## Acceptance criteria

- [x] Orient states the brief test as the spec's paragraph; no size call remains at the gate; the standalone path, the speculative build and the user's stations are on the map.
- [x] Grilling's gate section states the non-blocking rule and where confirmation happens; to-tickets cuts from an empty-frontier draft, publishes `proposed`, and stamps the spec calls each ticket builds on.
- [x] The prototype skill routes a single clear design to the build.
- [x] The README's flow prose and figures match orient.
- [x] Property, reviewed: no step blocks on the user reading a brief; a ticket written by an agent is dispatched, not presented.
- [x] Property, reviewed: the build never starts while the agent still has a question for the user; it never waits for the user to ratify a call.
- [x] Assumption to carry, anchored: tickets naming the calls they build on is the agent's call from the spec.
- [x] Demo in the closing comment: the README rendered with the new figures, opened.

## Comments

### Closing comment

The routing and gating skills now describe the spec's flow: orient states the brief test and names the four stations, grilling's gate hands an empty frontier to to-tickets instead of holding the build, to-tickets publishes `proposed` and names the calls each slice rests on, prototype takes the detour only for rival shapes, and the README leads with the one-flow figure. Three commits on `ticket/one-flow/07-flow-skills`, `373ba7b`, `e09c810` and `2af21db`, unmerged.

**Demo.** The README as a reader meets it, with the figures this ticket shipped. From a checkout of this branch:

```
$ uv run --with markdown python -c "
import markdown, pathlib
p = pathlib.Path('mx/README.md')
html = markdown.markdown(p.read_text(), extensions=['tables', 'fenced_code'])
out = pathlib.Path('/tmp/mx-readme.html')
out.write_text('<base href=\"file://' + str(p.resolve().parent) + '/\"><style>body{max-width:1100px;margin:2rem auto;font:16px/1.6 sans-serif;padding:0 1rem}img{max-width:100%}</style>' + html)
print(out)
"
/tmp/mx-readme.html
```

Open `/tmp/mx-readme.html`. What to look for, top to bottom: the lead figure is **One flow, three intensities, four stations for you** (it was the full cycle), with three rows for the brief test's three exits, a `SPECULATIVE BUILD` card in the chat column, and four orange `YOU` chips; the worker card reads "dispatch, on a worker host". Below it, four disclosures: the whole cycle (its ticket card now reads "cut and built before you rule", and the gate label is `FRONTIER EMPTY`), ticket state (`proposed` is "on the frontier, and the claim takes it like an open one", with a **Your ruling, on what it built** card feeding `done`), the session boundary ("Cut the tickets"), the board, and a review page. The figure that was "Who is in the loop at each step" is gone; one-flow carries it.

Then `mx/skills/orient/SKILL.md`, "The main flow: intent → ship", is the same flow in prose, and it is what the figure should agree with.

Rendered here headless: all seven images resolve, and both colour schemes were looked at for overlaps. From the repo root, `uv run --script agent/show/mx-readme-figures/render.py` regenerates every figure; `cp` of the four the README embeds into `mx/assets/` is what ships them.

**I need from you**

1. `[D1]` The board hides a feature's unbuilt slices now. Every slice a breakdown cuts is `proposed`, and `board.py` leaves `proposed` out of all three denominators (`:648`, `:667`, `:750`) and out of the wave lanes (`:566`), so a fresh feature reads `spec draft · 0/0 done · 6 proposed` with one `proposed — awaiting ruling` lane and no waves. Ticket 02's A6 already asked you about the lane; this is the same surface, so both halves come together: should a breakdown's slices count and lane as ordinary work, which needs the board to tell them from an agent's own proposal (provenance, not `status`), or should the header say something else? I left the script alone rather than pre-empt A6. A8.
2. `[D2]` The glossary and the spec now disagree on **brief**. `CONTEXT.md:121` defines Brief as "the prompt a subagent is started with", avoid-list "brief for anything filed on the tracker"; the spec's brief test, ratified in round 3, makes the brief the thing on disk and its exits a ticket and a spec. `intent`, `brief test` and `loose` are load-bearing across five files with no entries. Glossary language is yours, so I changed nothing. A11.
3. `[D3]` Speculation's depth now counts an agent's own readings, not a breakdown's slices. Without that, a feature whose every slice is `proposed` puts each worker's friction proposal at level two, and nothing a feature finds about itself is ever built. It is my call from the spec's "Speculation is one level deep", not yours. A3.
4. `[D4]` I kept the full-cycle figure, repaired, as a disclosure instead of deleting it with main-flow: it carries harden, the debrief, the review session and the feedback rails, which one-flow does not. Say the word and it goes. A7.

**Details, if you want them**

5. `[D5]` **Assumptions.**

   - A1 `mx/skills/to-tickets/SKILL.md:53`: each ticket names the spec calls its slice rests on, in the provenance line the tracker already asks of a `proposed` ticket, and its worker carries them as anchored assumptions. The spec marks this `(my call)`; it is the ticket's stated assumption to carry.
   - A2 `mx/skills/tracker/MARKDOWN.md:25`: the tracker no longer counts a to-tickets breakdown as a ruling already. Ticket 02 wrote that line while the spec's Solution says a feature's tickets are published `proposed` `(you, r6)`; with to-tickets publishing `proposed`, the two contradicted. The tracker was outside this ticket's file list.
   - A3 `mx/skills/dispatch/SKILL.md:46`: what the one-level bound counts. See `[D3]`.
   - A4 `mx/skills/dispatch/SKILL.md:44`: a needs-human entry per landed proposal is scoped back to proposals an agent filed on its own reading. A breakdown's slices take the ordinary landing announcement, since their ruling is the QA of the slice; otherwise the queue grows one entry per slice of every feature, against its own entry criterion.
   - A5 `mx/skills/dispatch/worker-prompt.md:21`: a worker gives an anchored id to the spec calls its ticket names, not only to its own. Without it the chain from a `(my call)` mark to the user's ruling stops at the ticket header, and a spec can never reach `confirmed`.
   - A6 `mx/skills/to-tickets/SKILL.md:77`: a decision ticket stays `open` where a build ticket is `proposed`. Its answer is the ruling, and `proposed` would put a question on the build frontier.
   - A7 `mx/README.md:10`: the full-cycle figure kept and demoted. See `[D4]`.
   - A8 `mx/skills/tracker/board.py:750`: declined finding, the board's counts. See `[D1]`.
   - A9 `mx/skills/orient/SKILL.md:47`: declined finding, "a ticket an agent wrote is dispatched, not presented" stays a binary contrast. It is the spec's property wording, and the prior it fights (present the ticket, wait for approval) is exactly what this feature retires. The other six contrasts went positive.
   - A10 `agent/show/mx-readme-figures/one-flow.html:199`: the worker card reads "dispatch, on a worker host", true both under today's per-repo record and under ticket 08's per-spawn choice. The figure as drawn said "the repo's host", which the spec's round-10 decision supersedes; naming either policy would date the figure within the week.
   - A11 `CONTEXT.md:121`: the glossary left as it is. See `[D2]`.
   - A12 `agent/show/mx-readme-figures/one-flow.html`: the README's lead figure moved out of the feature's show directory into the one that holds the README's figures and its renderer, so `render.py` there regenerates all of them; `agent/show/one-flow/` keeps `what-changes.html`, which is the feature's before-and-after and not a README figure, and its REPORT.md says where the file went.

6. `[D6]` **Finding index.** `/mx:code-review` since `a554d0a` (merge-base with `one-flow`), three axes, no Tests axis since the diff touches no test file; reports under `agent/reviews/a554d0a..e09c810/`. Fixes in `2af21db`.

   - Correctness 1: the board hides unbuilt slices → declined, A8, `[D1]`.
   - Correctness 2: the spec's unratified calls stop at the ticket header, so the review page never carries them → fixed, A5.
   - Correctness 3: one needs-human entry per landed slice → fixed, A4.
   - Correctness 4, Spec 7: to-tickets stamped `proposed` on decision tickets, which the tracker calls rulings already → fixed, A6.
   - Spec 1: the ticket's own closing was absent → fixed, this comment.
   - Spec 2: "no size at which the session that grilled it builds it itself" wrote out the spec's own escape hatch → fixed, the session can build a slice as that slice's worker.
   - Spec 3, Standards H4: the figure asserted ticket 08's host policy → fixed, A10.
   - Spec 4, Standards J9: the depth rule was an agent call living only in a commit message, buried in a ten-sentence paragraph → fixed, its own paragraph, A3.
   - Spec 5: edits outside the ticket's file list (the tracker, three figures) → no action; ticket 02's closing comment assigned the ticket-state figure and orient's ticket row to this ticket, and A2 covers the tracker line.
   - Spec 6: dispatch still called the `blocked-by` DAG "human-approved" after the breakdown quiz went → fixed.
   - Standards H1: `brief` against the glossary → declined here, A11, `[D2]`.
   - Standards H2: binary contrasts at seven sites (catalogue rule 47) → six fixed, one kept, A9.
   - Standards H3: to-tickets' description carried body its own first step states → fixed, the trigger only.
   - Standards J5: prototype and orient each cited the other for one sentence → fixed, the reason lives in prototype.
   - Standards J6: orient reproduced the worker contract's demo paragraph verbatim → fixed, the map names the two parties and stops.
   - Standards J7: the lead figure sat outside the README-figures directory beside a duplicate renderer → fixed, A12.
   - Standards J8: step 5's prose slot was paddable where the deleted quiz had a checkable criterion → fixed, the step is done when the board is on disk and dispatch holds the frontier.
   - Standards: the README rotated "idea" and "intent" for one flow → fixed.

7. `[D7]` **Friction.**

   - The pane died mid-review: the tmux server on this host went down at about 01:52, during `make test`, and took the session with it. The worktree, the three commits and the staged figure renames survived, and so did the reviewers' reports on disk, which is the only reason the restart cost minutes: nothing had to be re-reviewed. A review that had reported to chat would have been lost whole.
   - The installed plugin here is 0.1.56, so `/mx:code-review` loaded the pre-04 skill: reports to `agent/research/`, one chat message, word caps. I wrote the briefs from the branch's file and moved the reports to `agent/reviews/<range>/`. Ticket 06 filed this; every worker on this feature meets it, and it stays until the plugin is released.
   - A committed PNG has no check that it matches the HTML beside it. I shipped `mx/assets/one-flow.png` rendered before the last edit to its source, and caught it only because I rendered the README by hand for the demo. `render.py --check`, rendering to a temp file and diffing, would turn that into a one-second test; nothing else in this repo has the same shape.
   - Judging the board question `[D1]` took longer than any edit in the ticket, because the fix is cheap and the call is not mine. The signal the board needs (an agent's proposal against a breakdown's slice) is one the tracker does not record anywhere, which is the same gap A3 works around in prose.
   - `make test` is 23s and `make check` 1s, and the figure loop is one command: nothing here fought the work.
