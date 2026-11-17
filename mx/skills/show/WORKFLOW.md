# Show in the mx workflow

What [`SKILL.md`](SKILL.md) leaves to the workflow: what a landing's show holds, where an artifact goes, who builds it, how it is linted and presented on the session page, and how it leaves its show directory.

## A landing's show

Every landing (`/mx:dispatch`) comes with its review page and one show, a build that puts no call to the user included, read whenever the user looks. A typo or a rename goes without one, and the landing says so in a line. The show is for the user's understanding of what was built, and where the landing puts calls to the user, it is built around them, as far as their ruling needs it. Demonstrating that the tests are green or that it runs is not the show's job: the tests and the review already did that, and a build that does not run has no show to be made of it. Its reader has the product sense and none of the weeds: technical, did not build it, and wants to understand it, told accurately and never sold.

- **One per landing.** A tree's show covers every child ticket in review, and goes to the parent ticket's directory; a tick that brings another to review rebuilds it rather than adding a second, so it is whole when the user sits down to rule on them with the parent ticket at its close-out. A standalone ticket's goes to its own.
- **Built by a fork** of the session landing the work (invoke `mx:fork`): it holds the conversation the user's questions came from, and its build loop stays out of that session's window.
- **Top down.** It opens with the intent and the change to how the parts fit, a figure where the structure moved; each lower level appears only where the one above needs it, and the code diff, on the review page, comes last. The user reads it from the top and goes a level lower only where the one above looks wrong or needs explaining, so a mistake high up is caught before the diff is read.
- **The few things the user would notice.** Each gets a caption of a sentence or two, the cells the grid picks, and numbered notes on where to look. The commands a run made sit folded under what they produced.

At a landing the per-shape table in `SKILL.md` says what its show holds, and the code level of every shape is the diff on the review page.

## Where it goes

An artifact goes to the show directory of the work it serves. A ticket's is `agent/show/<slug>/`, committed with that work: that directory is the agent repo's, so `git -C agent` is what commits it, and a landing's show is committed in its main checkout, as a ticket file is. Session work's (`/mx:orient`) is `show/` in the session's directory, the one `session-page` prints, committed with the session's records as it ends. One that serves neither goes to `~/Downloads/show/<slug>/` instead: the user wants it throwaway, there is no repo to keep it in, or the repo is the wrong home for it.

## Who builds it

Every artifact is built by a subagent or a fork, never by the session answering the user, so its render and debug loop stays out of that session's context. A subagent works from a prompt: the artifact, its output path, and the sources on disk to read; it runs at medium effort, since its work is a render-and-fix loop that its own render checks. A fork of the session (invoke `mx:fork`) is taken when the conversation itself is the source the artifact needs and no file carries it.

The builder is done once it has seen the artifact and reviewed its prose. It looks at its own render (Produce and present, in `SKILL.md` and below), then runs one `/mx:writing-for-humans` pass over the artifact's text and fixes what the pass finds, and only then hands back the path.

## Produce and present

- Every page an agent opens is served from one local origin together with every agent directory, so a script changed at its CDN could read them all and send them off: this is why a page pins every script it loads.
- A page names the session the reader resumes to get back to the conversation behind it: `session <first 8 of the id>` in its `v-meta` line, as a button that copies `claude --resume <id>`, the id being `${MX_ORIGIN_SESSION:-$CLAUDE_CODE_SESSION_ID}` read in the shell.
- Before the look `SKILL.md` asks for, `render-lint` an HTML page (its `--help` says what it reports; `--narrow` for an app or a page someone reads in a narrow window or zoomed in) and fix every fatal finding.
- Present it as a link in the turn record that asked for it ([the session page's rules](../session-page/RULES.md)). Opening it with a line and its path is for where there is no page.

## A runnable artifact

The board lists a runnable artifact (`SKILL.md`) with the rest of its show directory and, seeing the executable bit, puts the command that runs it from the code repo's root on a button, so the reader starts it when they want it.

## A figure

A figure a document in the tree embeds is promoted with the script that renders it rather than copied (Promotion, below), since its PNG stays untracked beside its source. A figure that grows as the reader goes (`SKILL.md`, the per-shape table) has a first, rough instance in `docs/figures/story/` in the agents repo.

## Promotion

A figure, or an output, that a README or a PR description needs moves to where that document's assets live, a `docs/` or `assets/` directory the document already reads from: the render, its source, and the script that regenerates it travel together, and every reference is repointed in the same commit. No show directory outlives the work it belongs to, whatever still reads it, so a copy left behind in one is a stale figure waiting to be read as current. What the destination takes varies: a PNG the README embeds, committed with it; an image in an issue or a PR description, pushed with `gh-asset push` for its URL; an output pasted into a PR as a code block; a script that asserts moved under `make check`. The move is your own call and visible in the diff, so no ruling gates it.
