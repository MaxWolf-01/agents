# Show in the mx workflow

## A landing's show

Every landing (`/mx:dispatch`) comes with its review page and one show, a build that puts no call to the user included, read whenever the user looks. A typo or a rename goes without one, and the landing says so in a line. The show is for the user's understanding of what was built, and where the landing puts calls to the user, it is built around them, as far as their ruling needs it. Demonstrating that the tests are green or that it runs is not the show's job: the tests and the review already did that, and a build that does not run has no show to be made of it. Its reader has the product sense and none of the weeds: technical, did not build it, and wants to understand it, told accurately and never sold.

- **One per landing.** A tree's show covers every child ticket in review, and goes to the parent ticket's directory; a tick that brings another to review rebuilds it rather than adding a second, so it is whole when the user sits down to rule on them with the parent ticket at its close-out. A standalone ticket's goes to its own.
- **Built by a fork** of the session landing the work (invoke `mx:fork`): it holds the conversation the user's questions came from, and its build loop stays out of that session's window.
- **Top down.** It opens with the intent and the change to how the parts fit, a figure where the structure moved; each lower level appears only where the one above needs it, and the code diff, on the review page, comes last. The user reads it from the top and goes a level lower only where the one above looks wrong or needs explaining, so a mistake high up is caught before the diff is read.
- **The few things the user would notice.** Each gets a caption of a sentence or two, the cells the grid picks, and numbered notes on where to look. The commands a run made sit folded under what they produced.

At a landing the per-shape table in `SKILL.md` says what its show holds. A landing's show is usually the output of a run of the full-path checks the change reaches (`/mx:testing`), so the runnable script that makes it (`SKILL.md`, A runnable artifact) is the natural home for one: the check and the demonstration are the same run.

## Who builds it

Every artifact is built by a subagent or a fork, never by the session answering the user, so its render and debug loop stays out of that session's context. A subagent works from a prompt: the artifact, its output path, and the sources on disk to read; it runs at medium effort, since its work is a render-and-fix loop that its own render checks. A fork of the session (invoke `mx:fork`) is taken when the conversation itself is the source the artifact needs and no file carries it. The builder hands back the path once it has done all of Produce and present (`SKILL.md`): looked at its render and passed over its prose.

## Promotion

A figure, or an output, that a README or a PR description needs moves to where that document's assets live, a `docs/` or `assets/` directory the document already reads from: the render, its source, and the script that regenerates it travel together, and every reference is repointed in the same commit. No show directory outlives the work it belongs to, whatever still reads it, so a copy left behind in one is a stale figure waiting to be read as current. What the destination takes varies: a PNG the README embeds, committed with it; an image in an issue or a PR description, pushed with `gh-asset push` for its URL; a script that asserts moved under `make check`. The move is your own call and visible in the diff, so no ruling gates it.
