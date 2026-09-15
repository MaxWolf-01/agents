---
status: done
---

# Retiring a ticket or feature retires its show directory and research notes

Slice of `spec.md`, building on Solution (you, r5), Decisions "Retired with the work, promoted deliberately" (you, r5: retire show and research at close; agent's call, r5: the `~/logs` interim), "Promotion is the agent's call, visible in the diff" (you, r5).

## What to build

A session retiring a feature removes its show directory in the same commit as its ticket directory; retiring a standalone ticket takes its show directory with it; a loose branch's show directory goes when the branch merges. The research notes the retired tickets cite leave the tree in the same step: untracked, they move to `~/logs/agent-research/<repo>/` rather than being deleted, until [One tracker for all of a user's repos](../one-tracker-per-user.md) rules on committing them. What a README or a PR needs is copied there in that commit, on the agent's judgment, and kept current where it lands. The tracker's retire step says all of this once; orient's artefact table rows for Show and Research agree with it in a phrase and point at it.

## Acceptance criteria

- [x] The tracker's Retire section names the show directory and the research notes with their destinations, for a feature, a standalone ticket and a loose branch.
- [x] Orient's artefact table gives Show and Research the retire lifecycle in a phrase each; the rule has one home.
- [x] Property, reviewed: no show directory and no research note outlives the ticket or feature it served; a figure a README or PR needs is copied there and kept current there.
- [x] Demo: `agent/show/figures-and-demos/04-retire-with-the-work/demo`, executable, no arguments: a toy repo with one shipped feature, the retire commands run, the tree before and after, and the research note's new path printed.

## Comments

The retire rule landed in `/mx:tracker` (MARKDOWN.md, Retire), with orient's and the README's artefact tables agreeing in a phrase, plus the demo. Nothing is merged: the work sits on `ticket/figures-and-demos/04-retire-with-the-work`, two commits, `654b4af..0e0f6dd`.

**Demo**

```
$ agent/show/figures-and-demos/04-retire-with-the-work/demo

== a toy repo whose one feature, soup, has shipped

  .gitignore
  README.md
  agent/research/07-stock-timings.md
  agent/show/soup/01-stock/demo
  agent/show/soup/02-serve/demo
  agent/show/soup/broth.mmd
  agent/show/soup/broth.png
  agent/show/soup/broth.svg
  agent/tickets/soup/01-stock.md
  agent/tickets/soup/02-serve.md
  agent/tickets/soup/spec.md

  agent/show/soup/broth.png is an untracked render, agent/research/07-stock-timings.md
  an untracked note cited by 01-stock; the README links the figure where it sits

== what the README needs is promoted, and its link repointed, in the retiring commit

  cp agent/show/soup/broth.svg docs/figures/broth.svg
  sed -i 's|agent/show/soup/broth.svg|docs/figures/broth.svg|' README.md

== the tickets and the show directory leave in the same commit

  git rm -r agent/tickets/soup/ agent/show/soup/
  rm 'agent/show/soup/01-stock/demo'
  rm 'agent/show/soup/02-serve/demo'
  rm 'agent/show/soup/broth.mmd'
  rm 'agent/show/soup/broth.svg'
  rm 'agent/tickets/soup/01-stock.md'
  rm 'agent/tickets/soup/02-serve.md'
  rm 'agent/tickets/soup/spec.md'

  git rm -r leaves the ignored render behind, so the directory goes from disk too:
  rm -rf agent/show/soup/

  the commit:

  soup: retired, the broth figure promoted to docs/

    M	README.md
    D	agent/show/soup/01-stock/demo
    D	agent/show/soup/02-serve/demo
    D	agent/show/soup/broth.mmd
    D	agent/show/soup/broth.svg
    D	agent/tickets/soup/01-stock.md
    D	agent/tickets/soup/02-serve.md
    D	agent/tickets/soup/spec.md
    A	docs/figures/broth.svg

== the research notes leave the tree, moved rather than deleted

  mkdir -p ~/logs/agent-research/toy-project/
  mv agent/research/07-stock-timings.md ~/logs/agent-research/toy-project/

  the note now reads at ~/logs/agent-research/toy-project/07-stock-timings.md:

    # Stock timings

    Bones at 90 minutes, skimmed twice.

== the tree after

  .gitignore
  README.md
  docs/figures/broth.svg

== what holds

  ok  no ticket of the feature is left, in the tree or in HEAD
  ok  HEAD carries no figure or demo of the feature, its slice directories included
  ok  the show directory is off disk, the untracked render with it
  ok  no research note is left in the tree
  ok  the note survives the move, at ~/logs/agent-research/<repo>/
  ok  the promoted figure is in the tree and no README link points into the show directory
  ok  removal, promotion and repointing are the same commit
  ok  git history still finds the retired work

```

**I need from you**

- [D1] The rule now disposes of show directories this repo still holds. `agent/show/one-flow/` and `agent/show/host-per-spawn/` outlived their tickets (retired in `1f26781`); `agent/show/mx-readme-figures/` is the README's figure pipeline and stays under the promotion clause, but `one-flow/render.py` is targeted by the open `render-check.md`, and `host-per-spawn/demo.sh` is the worked precedent ticket 03 cites for its own demo. The sweep is a ruling, not a worker's edit: do those two go now, after 03 lands, or not at all?
- [D2] A1 extends the spec's promotion decision from "a figure a README or PR needs" to the source and the script behind it, and lets a show directory that still feeds a live document stay. Without it the rule deletes this repo's README figure pipeline the next time a loose branch retires; with it, "retired with the work" carries a standing exception. Your call on the wording.

**Details, if you want them**

- [D3] Assumptions:
  - A1 `mx/skills/tracker/MARKDOWN.md:62`: promotion covers the source and the renderer behind a promoted figure, and a directory that goes on feeding a live document stays, its retiring commit naming what it kept.
  - A2 `mx/skills/tracker/MARKDOWN.md:60`: the `~/logs/agent-research/<repo>/` destination is the spec's own agent call (r5), carried here unchanged and named so it reaches your review page.
  - A3 `mx/skills/tracker/MARKDOWN.md:56`: the loose-branch bullet carries no timing condition of its own; it inherits the section's "once the work has shipped", so the removal rides the merge. A demo re-run a week later (user story 13) then needs the pre-merge commit.
  - A4 `mx/skills/orient/SKILL.md:20`: orient and the README say the notes leave the tree and name no path, since the spec marks `~/logs` an interim; the path lives in the tracker alone.
  - A5 `mx/README.md:72`: the README's artefact table is edited too, which the ticket does not ask for; its Ticket row already carries the same lifecycle phrase, and a human-facing table that disagreed would read as a second rule.
  - A6 `agent/show/figures-and-demos/04-retire-with-the-work/demo:103`: a failing run overwrites the committed transcript with its own output, FAIL line included, rather than preserving the last green one: the failure is the state worth seeing.
- [D4] Finding index, `654b4af..697a2e6`, three axes (correctness, standards, spec), all findings disposed:
  - Fixed in `0e0f6dd`: `git rm -r` leaves the gitignored renders, and so the directory, on disk; promotion covered neither the source nor the renderer; the standalone command aborted whole where no show directory exists; the promotion never repointed the references into the removed directory; the "slice directories go with it" sentence said what `-r` already says; `~/logs` was restated in orient and the README; the demo's FAIL line missed the committed transcript, its git read the host's config, its printed commands were hand-written beside the ones it ran, its `HOME` comment described an expansion that never happened, and it carried a dead helper; its toy repo could not exhibit either failure the two central checks claim to catch, and now does (an ignored render, a README linking into the show directory).
  - Declined: the loose-branch timing (A3); "the demo never opens what it produced", since a printed transcript is its own render and this host has no display; "a failed run truncates the committed transcript" (A6).
  - Not this slice: both `(/mx:show)` pointers dangle until ticket 01 lands its promotion and show-directory text. Worth a check at integration that "kept current where it lands" ends up stated once.
- [D5] Friction: the spec links `agent/tickets/one-tracker-per-user.md` twice and the file does not exist, so the interim's successor cannot be read from the ticket. `git rm` aborting on an unmatched pathspec is the kind of thing prose cannot be trusted on; the reviewer caught it by running the command, which is why the demo is worth more here than the rule's wording. Nothing else fought the work: `make check` and the suite (92 tests, 23s) are a fast loop.
