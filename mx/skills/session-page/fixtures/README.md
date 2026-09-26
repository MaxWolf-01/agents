# The worked example

`session/` is the four grilling rounds this feature was designed in, as the session directory the
Decisions of `agent/tickets/session-page.md` put under `agent/sessions/<session-id>/`. The records
are `agent/prototypes/session-page/sample/`'s, with the prototype's relative links rewritten from
the repo root and `session.md`'s `spec:` dropped with the spec page it named. The sample's
`NN.you.md` files are not here: the user's messages come from the transcript.

`transcript.jsonl` is that session's own, trimmed here from the 12 MB Claude Code wrote at
`~/.claude/projects/-home-max-repos-github-MaxWolf-01-agents/e5ca76dc-3093-419b-aa93-b8eb8f35811f.jsonl`.
It keeps, whole and in order, every line up to the session's fifth prompt — the first the sample
has no record for — that is a user entry whose message is a string, an `attachment` of type
`queued_command`, or a `queue-operation`. The assistant's entries, the tool results and the other
attachments are gone, so the `parentUuid` chain has holes; the page shows none of them.

What it keeps that a reader might take for noise, it keeps on purpose: the first prompt, submitted
and then resubmitted four minutes later with more text and no reply in between; the images, task
notifications and other sessions' hand-backs that Claude Code writes as user entries; and turn 4's
message, queued while the turn before it was still running.
