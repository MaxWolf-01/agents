One file per session. Its header names the session id, title, project, profile, span, how many messages max wrote, and the models and Claude Code versions it ran. Then, under a heading per day, each line carries its time, UTC:

- `MAX:` what max typed, verbatim, pasted text clipped in the middle. `(queued while the agent worked)`: he typed while the agent was busy. `MAX REWOUND and re-sent`: he rewound to before his previous message and sent a new version; what the abandoned turn did is often why. `MAX INTERRUPTED`: he stopped the agent mid-turn.
- `A:` the model's text. `→ <tool> <input>`: a tool call and its full input; tool output is left out.
- `! ERROR`, `! DENIED`: a failed or refused tool call, in full. `! HOOK → agent`, `! STOP HOOK`: a hook that sent the turn back. `! API ERROR`.
- `(turn took 4m12s)`, `(context compacted)`, and `(left out: …)` where a long session's days before the period were cut.
- `## Session page: …` closes a digest that has them: the session page's records, what max was shown of the session.
