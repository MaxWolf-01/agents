# The worked example

`session/` is the four grilling rounds this feature was designed in, as the session directory the
Decisions of `agent/tickets/session-page.md` put under `agent/sessions/<session-id>/`. The records
are `agent/prototypes/session-page/sample/`'s, with three changes: the prototype's relative links
are written from the repo root, `session.md`'s `spec:` went with the spec page it named, and
`04.md`'s third link, the one to the record itself, went with it, having no repo-root form. The
sample's `NN.you.md` files are not here either: the user's messages come from the transcript.

`transcript.jsonl` is that session's own, trimmed from the 12 MB Claude Code wrote at
`~/.claude/projects/-home-max-repos-github-MaxWolf-01-agents/e5ca76dc-3093-419b-aa93-b8eb8f35811f.jsonl`.
Whole lines, in order, down to the end of the turn the fourth record covers, which is the last turn
the sample has a record for:

    awk '/"uuid":"d2941f0b-/ {exit} /"type":"queue-operation"/ || /"type":"queued_command"/ ||
         /"message":\{"role":"user","content":"/' <the 12 MB file>

The assistant's entries, the tool results and the other attachments are gone, so the `parentUuid`
chain has holes; the page shows none of them.

What reads as noise it keeps on purpose: the first prompt, submitted and then resubmitted four
minutes later with more text and no reply in between; the images, task notifications and other
sessions' hand-backs that Claude Code writes as user entries; and the message queued while the turn
before the fourth one was still running, which sits in an `attachment` and in no user entry.
