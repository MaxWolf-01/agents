---
status: done
diff: [654b4afe75ab39cbc033ab7f1a7dc6fda58299d9..86a77f08521dad5f7f23a93ce1ccaa11ff7056f0]
---

# Retiring a ticket or feature retires its show directory and research notes

Slice of `spec.md`, building on Solution (you, r5), Decisions "Retired with the work, promoted deliberately" (you, r5: retire show and research at close; agent's call, r5: the `~/logs` interim), "Promotion is the agent's call, visible in the diff" (you, r5).

## What to build

A session retiring a feature removes its show directory in the same commit as its ticket directory; retiring a standalone ticket takes its show directory with it; a loose branch's show directory goes when the branch merges. The research notes the retired tickets cite leave the tree in the same step: untracked, they move to `~/logs/agent-research/<repo>/` (superseded while this ticket ran: one `~/logs/agent/<repo>/` root, the Comments below) rather than being deleted, until [One tracker for all of a user's repos](../one-tracker-per-user.md) rules on committing them. What a README or a PR needs is copied there in that commit (superseded by round 7: a promotion moves rather than copies), on the agent's judgment, and kept current where it lands. The tracker's retire step says all of this once; orient's artefact table rows for Show and Research agree with it in a phrase and point at it.

## Acceptance criteria

- [x] The tracker's Retire section names the show directory and the research notes with their destinations, for a feature, a standalone ticket and a loose branch.
- [x] Orient's artefact table gives Show and Research the retire lifecycle in a phrase each; the rule has one home.
- [x] Property, reviewed: no show directory and no research note outlives the ticket or feature it served; a figure a README or PR needs is moved there and kept current there (round 7, ruled after this ticket was cut, which is what the rule as landed says).
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

---

Addressed: C1, C2, C3

Amended on the same branch, `082af6b..2b15d1b`. The promotion rule is a move out of `agent/show/`, one `~/logs/agent/<repo>/` root carries what leaves an untracked tree, and this repo now obeys the rule: `agent/show/` holds `figures-and-demos` alone.

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

== what the README needs moves out, render and source, its link repointed with it

  git mv agent/show/soup/broth.svg agent/show/soup/broth.mmd docs/figures/
  sed -i 's|agent/show/soup/broth.svg|docs/figures/broth.svg|' README.md

== the tickets and the show directory leave in the same commit

  git rm -r agent/tickets/soup/ agent/show/soup/
  rm 'agent/show/soup/01-stock/demo'
  rm 'agent/show/soup/02-serve/demo'
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
    A	docs/figures/broth.mmd
    A	docs/figures/broth.svg

== the research notes leave the tree, moved rather than deleted

  mkdir -p ~/logs/agent/toy-project/research/
  mv agent/research/07-stock-timings.md ~/logs/agent/toy-project/research/

  the note now reads at ~/logs/agent/toy-project/research/07-stock-timings.md:

    # Stock timings

    Bones at 90 minutes, skimmed twice.

== the tree after

  .gitignore
  README.md
  docs/figures/broth.mmd
  docs/figures/broth.svg

== what holds

  ok  no ticket of the feature is left, in the tree or in HEAD
  ok  HEAD carries no figure or demo of the feature, its slice directories included
  ok  the show directory is off disk, the untracked render with it
  ok  no research note is left in the tree
  ok  the note survives the move, at ~/logs/agent/<repo>/research/
  ok  the promoted render and its source are in the tree, and no README link points into the show directory
  ok  removal, promotion and repointing are the same commit
  ok  git history still finds the retired work

```

The repo's own retirement, which the demo models, is in the branch: `677e573` deletes one-flow's and host-per-spawn's directories, `ca707c9` moves the README's figure pipeline to `docs/figures/`, `2b15d1b` sweeps the rest. `./docs/figures/render.py` regenerates the six figures from their new home.

**I need from you**

- [D6] `2b15d1b` goes past the three directories you named: `decision-tickets/`, `dispatch-ctl-absorb/`, `dispatch-hub-churn/` and `harden-greenlet/` are the same case (tickets off the tracker, no reference anywhere, nothing promoted out), so "apply the rule to this repo" took them too. Revert that one commit if you wanted only the three.
- [D7] Three ticket files outside this feature carry repointed references (A7). `03-landing-demo.md` is claimed and in flight, and standalone tickets are yours to commit from the main checkout, so these edits may land twice or conflict at merge.

**Details, if you want them**

- [D8] Assumptions, continuing from A6:
  - A7 `agent/tickets/render-check.md:13`: the references into the moved and deleted directories are repointed in the commits that moved them, `render-check.md` and `dispatch-scripts-under-test.md` and `03-landing-demo.md` included, because the rule this ticket lands says every reference is repointed in that commit. What no longer exists is named as the commit that holds it.
  - A8 `.gitignore:9`: the renders keep their old treatment at the new path (`docs/figures/*.png` ignored), and `mx/assets/` keeps the tracked PNGs the README embeds, so the move changes no PNG's status. Nothing yet regenerates the assets copies from the sources; that gap is `render-check.md`'s, and it predates this move.
  - A10 `agent/tickets/figures-and-demos/spec.md:73`: the spec's Decisions entry is amended in place, marked with what each claim was, rather than left to teach the overturned rule to this feature's other workers; the tracker's spec sweep asks for it in the same session.
  - A9 `docs/figures/board-fixture/build.py:25`: verified as far as this host reaches. `render.py` renders all six figures in both schemes from `docs/figures/`; `build.py` builds its demo repo and runs its suite, then stops at `diffview`, absent here, so its screenshot half is unverified beyond both computed roots resolving.
- [D9] Friction: D5's missing `one-tracker-per-user.md` was not missing, it is on master at c443a6b where standalone tickets are committed and this branch forked before it; a worker reading only its own branch cannot tell those apart. `diffview` is not on this host, so the one script the move touches most cannot be driven end to end here; a worker host that carries the tools the repo's own figures are built with would have closed that gap. Nothing else fought this round.
