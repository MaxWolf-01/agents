---
status: claimed
parent: ticket-file-contract
blocked-by: [tracker-command-and-commit-check]
priority: 1
size: L
---

# The skills and the glossary speak of one kind of ticket

Child ticket of `ticket-file-contract`, building on every call in its Decisions; the one still the agent's: the Properties (r2).

## Brief

Every skill, the worker contract, the always-loaded workflow block and the glossary describe the model the parent ticket settled, in one pass by one worker, since they share one vocabulary and a split would let two workers phrase it two ways. The feature, the spec, the standalone ticket, the gate and the decision ticket leave the prose; so does every branch that chose between them.

This ticket builds on master after board-orients has merged, which reworked the tracker, dispatch and orient; the list below was written against the master before it, so read what board-orients landed first and treat any item it already settled as settled.

What changes, by where it lives:

- `/mx:tracker` (SKILL.md, MARKDOWN.md): one ticket kind, flat, `parent:`, slug ids; the branch a ticket file is committed on; the field for a ticket that needs the user; no decision tickets and no types; one retire rule; research landing in the ticket; the ticket's sections, which is where the spec template's sections now live, as optional ones. `SPEC-FORMAT.md` goes. The skill keeps the concepts and the flow and leaves every mechanism to `tracker`: it shrinks to at most half its size, it never restates what `tracker --help` says, and it may embed that `--help` output so the reference loads with the skill (you, r6).
- `/mx:grilling`: the design lands in the ticket being grilled, marks and all; no draft, no confirmed, no gate; the absorb step goes; questions left open at a session's end become child tickets that need the user.
- `/mx:to-tickets` gets a major overhaul, and may not stay a skill of its own: the user's direction (r4) is that how to cut a ticket into child tickets could be a companion file of the tracker skill, read when a ticket is being split. Your call, recorded as an assumption. Whatever its home, it cuts child tickets with `parent:`; stamps no properties, since they are read through the ancestry; gives `property-coverage` its new meaning; and says that one slice means the grilled ticket is itself the thing built.
- `/mx:dispatch` and `worker-prompt.md`: the standalone paragraphs go; the needs-the-user field replaces routing by type; close-out at every parent ticket, its review one level up; a worker reads its ticket plus its ancestry; light or full review by the diff's size and whether it touches a contract others depend on.
- `/mx:code-review`: the spec source is the ticket's context from `tracker`.
- `/mx:orient`: the artefact table and the flow's step 3 (loose, or a ticket, which gains child tickets when it slices into two or more).
- `/mx:research`: trimmed to its investigation discipline, with the findings landing per the parent ticket's research decision: the gist and sources in the ticket, extra detail in `agent/research/` only when there is some, a `/mx:show` artifact for what the user has to see.
- `/mx:project-setup`: wires the commit check into a project.
- `claude/CLAUDE.md`'s workflow block and its copy in `worker-prompt.md` (the project CLAUDE.md says the two are checked against each other), and `mx/README.md`.
- `CONTEXT.md`, through `/mx:domain-modelling`: Feature, Spec, Standalone ticket, Gate, Build ticket, Decision ticket and Legwork go; Parent ticket (with child ticket) comes in with the parent ticket's wording; every entry that leaned on a removed word (Frontier, Round, Debrief, Call) is re-read against the new model.

`tracker`'s command names come from `tracker-command-and-commit-check`'s `--help`, which is why this ticket waits on it.

## Acceptance criteria

- [x] A grep of `mx/`, `claude/CLAUDE.md` and `CONTEXT.md` for spec, feature, standalone and decision ticket finds only uses in another sense (a spec as in a specification of an external format, say), each read and kept on purpose.
- [x] `ticket-file-contract#P5`, reviewed: no skill distinguishes tickets by kind beyond having child tickets and needing the user.
- [x] The demo is the before and after of what an agent writes, per `/mx:show`'s process-change row: one intent taken through grilling and to-tickets under the old skills and the new ones, role-played where the scripts are not landed.
- [x] The mx plugin version is not bumped here; the release follows the parent ticket's merge.

## Questions

- [D1] **The README's figures still draw the three kinds of file.** The prose around them now reads one way and the pictures draw another: `one-flow`, `full-cycle`, `session-boundary`, `ticket-state` and `landing` under `docs/figures/`, rendered into `mx/assets/`, still show a spec sliced into `NN` tickets, the four decision-ticket types and a standalone ticket. Redrawing them is a re-layout of hand-placed SVG rather than a label sweep, and it is figure work you judge in front of a render, so I left the figure blocks and their alt text describing what the pictures actually show. Either a follow-up ticket takes them (it could ride with `readme-reshoot`, which already waits to re-shoot the README's board screenshots), or another round on this one does.

## Comments

The prose speaks of one kind of ticket: `/mx:tracker` with its two companion files, grilling, dispatch and the worker contract, code-review and its briefs, orient, research, project-setup, show, testing, prototype, handoff, recap, transcript, session-name, the always-loaded workflow block and its copy, `mx/README.md` and `CONTEXT.md`, on `ticket/ticket-file-contract/skills-and-glossary-speak-one-ticket-kind`. Nothing is merged, and the README's figures still draw the three kinds (D1).

**Demo**

```
$ /home/agent/repos/dispatch/agents-ticket-file-contract-skills-and-glossary-speak-one-ticket-kind/agent/show/skills-and-glossary-speak-one-ticket-kind/demo
wrote /home/agent/repos/dispatch/agents-ticket-file-contract-skills-and-glossary-speak-one-ticket-kind/agent/show/skills-and-glossary-speak-one-ticket-kind/out/one-ticket-kind-in-the-skills.html
no display here; open the file above to read it
```

One intent, a CSV importer that remembers each bank's column mapping, taken through the old skills and the new ones: the ticket files an agent writes either way, the design's sections before and after, the real `tracker check` reading one set and refusing the other construct by construct, the context a worker and a reviewer are handed, and then this repo's own history for what the pass changed, down to the grep the first acceptance criterion asks for. The `before/` set is role-played, since the skills that wrote that way are gone from the tree; every run on the page is a run. The before-and-after figure is beside it, `/home/agent/repos/dispatch/agents-ticket-file-contract-skills-and-glossary-speak-one-ticket-kind/agent/show/skills-and-glossary-speak-one-ticket-kind/one-ticket-kind.html`: three kinds of file against one with a `parent:` line.

**Details, if you want them**

- [D2] Assumptions
  - A1 `mx/skills/tracker/SLICING.md:1`: how a ticket is cut into child tickets is a companion file of the tracker skill, and `/mx:to-tickets` stops being a skill of its own (r4 left the home to me). With one kind of ticket the cut is a tracker operation, read by an agent that already has the tracker skill open because it is filing tickets; a skill of its own costs a description in every session's context for a step that fires rarely, and that description no longer described anything ("break a grilled spec"). The cost is that `/mx:to-tickets` is gone as a command you can type. `mx/skills/to-tickets/` survives holding `property_coverage.py` and its tests, which the sibling ticket owns and which I left where they are: the directory is named for a skill that no longer exists, and the script belongs beside `SLICING.md` once that sibling has finished with it.
  - A2 `mx/skills/tracker/SKILL.md:10`: the skill points at `tracker --help` rather than embedding its output, which r6 allowed either way. An embedded copy is a second home that goes stale silently and is invisible when it does, and the command is one call away.
  - A3 `mx/skills/tracker/SKILL.md:1`: the half-size measure. `SKILL.md` and `MARKDOWN.md` were 124 lines and 3,116 words; they are 89 and 1,936, which is 62% of the words. Counting the spec format's sections they absorbed (`SPEC-FORMAT.md`, 77 lines and 832 words) it is 49% of the prose they replace, which is the reading I took for "at most half": the mechanism is gone, and what grew is the ticket body's shape moving in. Getting the pair under half without that credit means cutting about 380 more words, which at this point would delete rules rather than restatements. The demo's fifth panel computes all four numbers at run time.
  - A4 `mx/skills/tracker/MARKDOWN.md:13`: the body's sections and their order, from your Decisions. `## What to build`, which the old ticket template carried, is not among the sections you listed, so the Brief holds the intent and the end-to-end behaviour and the acceptance criteria hold what it must do; nothing refuses an extra section on a ticket that wants one.
  - A5 `mx/skills/grilling/SKILL.md:39`: a grilling round's review surface is `agent/diffviews/<slug>-grilling.html`, so it cannot collide with the page `dispatch review` renders for the same ticket's build. Under the old model the two had different paths for free.
  - A6 `CONTEXT.md:17`: **Spec mark** becomes **Call mark**, and **Ticket context** is a fourth entry beyond the three you named. The mark had to be renamed with the spec it sat in; the assembled context is an overloaded word that the worker contract, dispatch and code-review now all use in one sense, and `ticket-file-contract#P4` is what makes it a thing the workflow names.
  - A7 `mx/skills/code-review/SKILL.md:10`: the review's **Spec** axis keeps its name, and step 2 looks for the ticket's context first. The axis judges a diff against whatever ordered the work, which is a ticket here and a PR body or a `docs/` specification elsewhere; the name is also `--axes spec`, `--spec` and `briefs/spec.md`, which the sibling ticket owns. This is the largest group of surviving "spec"s the first criterion's grep finds.
  - A8 `mx/skills/code-review/SKILL.md:33`: light or full is the diff's size and whether it touches a contract others depend on (r1), and what light mode costs is said outright, because `review --light` takes no `--spec` at all: a small ticketed diff runs one reviewer with no Spec axis and no Tests axis. Making light mode read the order is a script change the sibling ticket does not carry (D3).
  - A9 `mx/skills/dispatch/SKILL.md:31`: a ticket's open questions come over to the tracker's own copy as the orchestrator announces them. The old prose left the copy to the agent; naming `tracker rule` made it a refusal, since that command can only answer a question the copy it reads already asks, and the board only shows what the tracker's copy holds.
  - A10 `mx/skills/show/SKILL.md:35`: a show directory is `agent/show/<slug>/` per ticket and a demo is `agent/show/<slug>/demo`, with no directory per slice under a feature. `/mx:show` is not in the ticket's list, but its paths were written in the old model and the first criterion's grep reaches them. Same for `/mx:testing`, `/mx:prototype`, `/mx:handoff`, `/mx:recap`, `/mx:transcript`, `/mx:session-name`, `/mx:writing-for-humans`, `/mx:writing-for-agents` and `.claude/skills/pocock-sync`, whose upstream mapping pointed at two files this branch deletes.
  - A11 `mx/.claude-plugin/plugin.json:4`: the plugin's own description said "File-based specs and tickets", and `.claude-plugin/marketplace.json` said it again; both say tickets now. No version bump, per the last criterion.
- [D3] Findings, from `/mx:code-review` over `09734b4..c18c564`, three axes, reports in `agent/reviews/09734b4..c18c564/`
  - Fixed in `f9c97a6`, correctness: light mode was made the default for a small ticketed diff while `review --light` refuses the `--spec` that carries the ticket, so a worker following the contract met a refusal whose only way out was a light brief asserting there was no order; the ruling line named `tracker rule`, which refuses a question its copy does not ask; the loose branch's retire rule was lost when the Retire section shrank; `marketplace.json` still said "specs and tickets"; the README kept three lines of the old model and promised a `## What to build` section.
  - Fixed in `f9c97a6`, standards: the figure wore a tracked all-caps zone label with a middle dot and the skin's security-boundary dash; an en dash in `SLICING.md`; the four ruling outcomes written out twice (the tracker skill keeps what they mean, dispatch what each one runs); the tracker skill restating its own command's subcommand list and retire recipe; the demo could not fail (a nonzero `git` and a missing base commit both passed silently), truncated its own evidence unmarked, and hardcoded counts it could compute; its `after/` fixture disposed a property *executable* without the child ticket that builds the checks.
  - Fixed in `f9c97a6`, spec: `tracker new`'s example was missing its two required flags; a grilling's leftover questions were filed `proposed` where you are already waiting on them; the glossary's Parent ticket dropped the close-out clause and Frontier did not exclude a needs-user ticket; **Call mark** and **Ticket context** were coined and never said; research's description lost its trigger branches; `tracker frontier` reads the whole tracker, so dispatch says which tree to read it for; "once per tree" read against close-out at every parent, and is "once per close-out"; the slug rename rule and where a research finding lands had no home.
  - Fixed in `3508f3e`, before the reports landed: the frontmatter fields are `tracker get --help`'s, not `tracker new --help`'s, which has no `diff` or `gh`.
  - Declined: moving `property_coverage.py` out of `mx/skills/to-tickets/` (A1), which my brief told me to leave where it is; and the figure beside the demo, which the review read as a second artefact nobody asked for, where the worker contract asks a change to something already there for both.
  - Noted for the siblings, not fixed here: `dispatch-ctl` still refuses a worker on `type:` in the frontmatter, a field no ticket carries now, so the guard that keeps a needs-user ticket from a worker currently fires on nothing; `property_coverage.py` still requires a feature directory with a `spec.md` and still holds tickets to stamping properties, which `tracker check` refuses; `review --spec` does not yet take a ticket's context; `dispatch --help` still documents `<NN-slug>`; and `tracker`'s transitions have no `claimed → open`, which dispatch's unrecoverable-session path asks for. Neither branch is coherent on master alone: the prose is written to the interfaces the scripts ticket is building, and the two want landing together.
- [D4] Friction
  - The pass is one worker because the vocabulary is one vocabulary, and that is right, but it also means the diff is 30 files of prose with no test that can read it. The only mechanical checks over any of it were `glossary-lint` on `CONTEXT.md`, `make check` on the manifests, and `tracker check` on the ticket files the demo builds. Everything else, including every claim a skill makes about a command, was caught by the review reading prose against source, which is why three axes on a prose diff was worth the 15 minutes.
  - The half-size instruction and the instruction to absorb the spec format's sections pull against each other, and nothing said which wins (A3). A size bound on a document that is also being given new material wants its baseline stated with it.
  - `make test` failed twice on this host with `test_render_lint.py` segfaulting chromium (exit 139, then a driver disconnect), and passed on the next two runs with no change to any Python. `layout-check-flaky` already describes the same shape one layer up. A suite that fails by machine and moment costs a worker a full re-run to tell a real failure from the host.
