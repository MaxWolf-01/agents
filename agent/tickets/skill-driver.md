---
status: proposed
priority: 3
size: S
---

# A driver runs one prompt against two versions of a skill and diffs what they produce

## Brief

A skill's wording is observable only by driving a session against it, and three demos each carry their own copy of that harness. One script runs a prompt against two versions of a skill and diffs what they produce.

Cut from the closing comments of figures-and-demos tickets 01 and 02 (2026-09-18, their friction entries). A skill's wording is observable only by driving a session against it, five to seven minutes a go, and the demos of both tickets, with a third coming from 03, each carry their own copy of the same harness: a scratch root per arm, a copy of the plugin with one skill swapped, a print-mode session with settings sources off and the plugin dir passed, a stream filter for what the session did and said, and the two arms' artefacts collected side by side. Every fix a review found in that harness was made once per copy. Three clauses of the show skill and three of the grilling skill exist because a run was watched, not because a reader objected, which is the loop worth making cheap.

## What to build

One script, beside the skills it serves, that takes a prompt, a plugin checkout and the path of one skill file to swap in, runs the prompt once against the plugin as it stands and once with the swap, in scratch roots of their own, and writes both arms' transcripts, tool calls and artefacts under an output directory with a diff of the two. The three demos then call it rather than carrying it, and a skill change's demo becomes the driver's invocation and its diff.

## Acceptance criteria

- [ ] One invocation drives one prompt against two versions of one skill and leaves both arms' evidence and their diff under a named directory.
- [ ] A session that never loaded the plugin, or never ran, is reported as such, never as an empty result.
- [ ] The three figures-and-demos demos call the driver and lose their copies of the harness.
- [ ] Demo: the driver run on one of those three prompts, the diff it wrote.
