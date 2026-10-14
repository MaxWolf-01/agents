# What the workflow retro looks for, and how it weighs a finding

The workflow is the mx plugin: its skills, scripts, hooks and checks, run in every repo max works in. A finding is friction that recurs, traced to what produces it. Two lenses, weighted equally, and a standing question.

## max's side

What cost max time, attention or nerves:

- **communication**: a message that did not land, an answer too long or too loose to read, max correcting a frame or an assumption, max asked what he need not be asked;
- **repeating himself**, within a session or across sessions;
- **understanding and observability**: what he could not see or follow (where a thing is, what is running, what changed), and what he was shown on a page he could not read;
- **manual steps**: work he did by hand that the agent or a tool could have done, and waiting;
- **building what got reverted**: work built and then undone or never used, workflow tooling reworked for its own sake;
- **frustration**, in his own words.

His shorthands are signals: `bd` (a brain-dead answer), `tldr`/`tldfr` (far too long), `wf` (wrong frame), `qq` (wanted a short answer), `idk` (he is blank and needs options), `ro` (read-only), `iiuc` (unsure; correct him), `nb` (no-brainer), `ygwim` (infer the rest). He dictates, so an odd word can be a dictation error.

## The agents' side

What made agents slower, costlier or less successful:

- **navigation**: long searches for a file or a fact;
- **automated checks**: a defect a lint, a type, a test or a render check could have caught;
- **rules for the reviewer**: what a reviewer should have held the diff to;
- **always-loaded files** grown past what they earn;
- **tool economy**: expensive or repeated calls, slow or flaky suites;
- **instructions that change nothing**, and skills not invoked when they should have been, or invoked and not followed;
- **access to information**: logs, remote state, a missing tool, a denial, harness and hook trouble.

## Do the mechanisms pull their weight

The checks, hooks, rules and suites the workflow added: how often each fires, on what, at what cost, and whether it still catches anything acted on. A mechanism that went noisy or outlived the bug it was added for is a deletion to propose.

## The weighing

Loosely, on four things together:

1. **What the friction costs**: time and energy, max's first.
2. **What preventing it costs to keep**: code, prose and workflow machinery carry upkeep for as long as they live; a one-time cost amortizes.
3. **How often it happens**, and is expected to.
4. **How robust the available fix is**: whether it simplifies or adds, and whether mechanism can fix it at all, or a better model or the harness's makers will fix the quirk first.

Deletions and narrowings come first. A defect class that recurs and that a tool could catch gets its check proposed, weighed like any other fix. A pattern rooted in the model's own habit, with no line to delete, is reported as that, with what was tried.
