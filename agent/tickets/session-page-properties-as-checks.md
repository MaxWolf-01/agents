---
status: proposed
parent: session-page
priority: 2
size: S
---

# The session page's executable properties, as checks at their three seams

## Brief

The session page's executable properties as checks at their three seams, before the code behind them exists, so each later slice lands against a check it did not write.

Slice of `session-page`, building on its Testing seams (three seams, which properties are executable) and on the turn record and session record shapes in its Decisions. The build starts once `board-orients` has merged (spec, Around it).

## What to build

The checks for every Property the spec marks executable, written against the three seams before the code behind them exists, so each slice lands against a check it did not write. The seams, as `session-page`'s Testing seams name them:

- **The session renderer**: a session directory (`session.md`, `turns/NN.md`) and a transcript in, the session page out.
- **The spec renderer**: a spec, the figures it links and a base commit in, the spec page out.
- **The Stop hook**, at its input: the hook's JSON and the session directory in, its decision out (render; send back, with the reason).

Where a seam does not exist yet, land its interface as a stub transcribed from the spec's Decisions, so the suite collects; each property that cannot hold yet lands as an expected failure naming the slice that lifts it:

| Property | Seam | Lifted by |
| --- | --- | --- |
| The top holds open questions and nothing else; a question a later turn answers or supersedes leaves it | session renderer | `session-renderer` |
| A turn's record is the only source of its section; the page regenerates from the records and the transcript alone | session renderer | `session-renderer` |
| The spec page shows every figure the spec links, and marks exactly what changed since the base commit | spec renderer | `spec-page-renderer` |
| A session that never needed a page writes nothing under `agent/sessions/` | Stop hook | `session-stop-hook` |
| A turn record that does not parse is sent back and never rendered | Stop hook | `session-stop-hook` |

The oracles: the worked example in `agent/prototypes/session-page/sample/` (this session, with a trimmed copy of its transcript as a fixture, since a worker host does not have the original), a spec with one figure and one changed section, and the hook cases listed in the spec's Decisions. Tests sit beside the code they test, as the rest of `mx/` does, and run under `make test`.

## Acceptance criteria

- [ ] Each of the five properties is a check at its seam, over generated or fixture inputs, and `make test` collects all of them.
- [ ] Each check that cannot hold yet is an expected failure naming its lifting slice, and fails only with the not-implemented error at its stub.
- [ ] The stubs' interfaces match the spec's Decisions, and no check reads the prototype's `render.py` as its oracle.
- [ ] Demo: `make test` output showing the five checks collected, each expected failure with the slice that lifts it.
