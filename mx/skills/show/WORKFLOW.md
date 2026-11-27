# Show in the mx workflow

## A landing's show

Every landing (`/mx:dispatch`) comes with its review page and one show, a build that puts no call to the user included, read whenever the user looks; a typo or a rename goes without one, and the landing says so in a line. The show is for the user's understanding of what was built; where the landing puts calls to the user, it is built around them, as far as their ruling needs. Whether the tests are green or it runs is not the show's to demonstrate: the tests and the review did that, and a build that does not run has no show. Its reader has the product sense and none of the weeds: technical, did not build it, wants to understand it, told accurately and never sold.

- **One per landing.** A tree's show covers every child ticket in review, and goes to the parent ticket's directory; a tick that brings another to review rebuilds it rather than adding a second, so it is whole when the user rules on them with the parent ticket at its close-out. A standalone ticket's goes to its own.
- **Built by a fork** of the session landing the work (invoke `mx:fork`): it holds the conversation the user's questions came from, and its build loop stays out of that session's window.
- **Top down.** It opens with the intent and the change to how the parts fit, a figure where the structure moved; each lower level appears only where the one above needs it, and the code diff, on the review page, comes last. The user goes a level lower only where the one above looks wrong or needs explaining, so a mistake high up is caught before the diff is read.
- **The few things the user would notice.** Each gets a caption of a sentence or two, the cells the grid picks, and numbered notes on where to look. The commands a run made sit folded under what they produced.

The per-shape table in `SKILL.md` says what a landing's show holds. It is usually the output of a run of the full-path checks the change reaches (`/mx:testing`), so the runnable script that makes it (`SKILL.md`, A runnable artifact) is the natural home for those checks: the check and the demonstration are one run.

## Who builds it

Every artifact is built by a subagent or a fork, never by the session answering the user, so its render and debug loop stays out of that session's context. A subagent's prompt names the artifact, its output path, and the sources on disk to read; it runs at medium effort, since its own render checks its work. A fork of the session (invoke `mx:fork`) is taken when the conversation itself is the source the artifact needs and no file carries it. The builder hands back the path once it has done all of Produce and present (`SKILL.md`).

## Committing a show

A ticket's show is committed with the round or the landing that made it, in the agent repo's main checkout as a ticket file is, and leaves with the ticket (`/mx:tracker`, Retire).

## Promotion

A figure or an output that a README or a PR description needs moves to the `docs/` or `assets/` directory that document already reads from: the render, its source and the script that regenerates it travel together, and every reference is repointed in the same commit. No show directory outlives the work it belongs to, whatever still reads it, so a copy left behind in one is a stale figure waiting to be read as current. The destination decides what moves: a PNG the README embeds is committed with it; an image in an issue or a PR description is pushed with `gh-asset push` for its URL; a script that asserts moves under `make check`. The move is your own call, visible in the diff, and no ruling gates it.
