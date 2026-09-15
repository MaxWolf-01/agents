---
status: done
blocked-by: [01]
diff: [290bfa51a0174580feac06872f6523ef508a067e..6785dbdd04c9f8d631dfdc9ed2dd3eb381deabe4]
---

# The chat reviewer ships with the mx plugin

## What to build

Every session with the mx plugin gets a Stop hook that has a small model read the turn's final message against the chat-scoped rules of the prose catalogue and, when it finds tells, returns them as hook feedback so the turn continues with a corrected reply. The hook is a command hook in the plugin's own hooks file; its script lives in the plugin and reads the catalogue file, selecting the rules tagged `chat` or `both`; there is no second rules file. The prototype at `agent/prototypes/chat-review-hook/` is the working reference: its `chat-review` script, its `ANSWER.md` (measurements and findings), and its `try` driver. Keep what the prototype found: the nested model call runs with no settings, plugins, hooks or MCP servers and with thinking off, since thinking turns a five-second review into two minutes; it fails open; it logs every decision as one JSON line; it returns early on its own re-entry.

Two conditions make it return early without calling a model: an environment variable that turns it off, and a session nobody reads (a dispatched worker, marked by the worker environment dispatch sets; an unattended session, if the harness marks one). The prototype's rules copy is retired once the hook reads the catalogue; the prototype directory stays as the primary source of the measurements.

## Acceptance criteria

- [x] The plugin's hooks file registers the Stop hook; a session started with the plugin runs it with no per-machine setup.
- [x] The script reads the chat-scoped rules from the catalogue file of ticket 01; no rules text lives in the script or the hooks file.
- [x] Off switch by environment variable; early return in a dispatched worker's session.
- [x] Property, reviewed: a chat reply the user reads has been checked against the chat-scoped rules, and the check never runs more than once per turn.
- [x] Demo in the closing comment: the `try` driver (or its successor) run against the shipped hook, showing the draft, the feedback line and the rewrite, with the review's latency from the log.

## Comments

### Closing, worker on `ticket/one-flow/03-chat-reviewer`

The hook is `mx/skills/writing-for-humans/chat_review.py`, registered by `mx/hooks/hooks.json`, which Claude Code loads from the plugin root with `${CLAUDE_PLUGIN_ROOT}` expanded. It reads `CATALOGUE.md` beside it and selects the rules tagged `chat` or `both` at run time, 44 of 46 today, by the awk command the catalogue's header publishes; a test holds the script's selection byte-identical to that command, so the pending ruling on the scope tags changes the reviewer's rules without touching code. The prototype's rules copy, script and settings file are retired; its `ANSWER.md` keeps the prototype's own measurements and `try` now drives the shipped plugin.

**Demo.** `./agent/prototypes/chat-review-hook/try` from the repo root, which runs a print-mode session with `--plugin-dir` on this checkout's `mx`, so the registration is under test and not only the script. Trimmed from the 2026-09-15 run:

```
--- reply the user reads
Quill is a TypeScript ORM that strips away the boilerplate and embraces type
safety from the ground up. [...] Quill offers a different approach to TypeScript ORMs.

--- reviewer log (/tmp/chat-review-try.jsonl)
[2026-09-15T00:35:03] feedback    6627ms
  draft: That's a wonderfully creative question—it lets me paint a picture of what
         modern database development could be! Quill is a TypeScript ORM that [...]
         just the sheer joy of a database layer that *gets* you. [...] Quill is the
         breath of fresh air the TypeScript ecosystem deserves!
         I'd love to dig deeper—whether you want to explore the schema design, query
         patterns, or how Quill might fit into your stack, just let me know!
  rule 20: "I'd love to dig deeper—[...] just let me know!" becomes: Delete the closing offer
  rule 42: "That's a wonderfully creative question—[...]" becomes: Start with the answer about Quill
  rule 8: "it's built for modern TypeScript patterns" becomes: say 'it targets modern TypeScript patterns'
  rule 32: 'just the sheer joy of a database layer that *gets* you' becomes: 'a database layer that works the way you think'
  rule 7: 'Quill is the breath of fresh air the TypeScript ecosystem deserves' becomes: 'Quill offers a different approach to TypeScript ORMs.'
  rule 13: 'em dashes mean fluent APIs, type-safe relations, and blazing-fast query optimization' becomes: rewrite without the em dash
  rule 30: 'blazing-fast query optimization' becomes: 'fast query optimization' or cite a metric
[2026-09-15T00:35:10] allow  re-entry  ms
```

The review cost 6.6 s, the rewrite applied every quoted fix, and the second Stop logged `re-entry`, which is the once-per-turn rule holding. The rewrite kept two em dashes the reviewer did not quote, which is the residue the spec defers to a week of the log.

**Measured against the shipped selection**, 2026-09-15, Claude Code 2.1.243, Haiku 4.5. The selection is 44 rules and 13,562 characters where the prototype measured 34 rules and 7,845; latency did not move.

| Message | Decision | Latency | Hits |
| --- | --- | --- | --- |
| a deliberately slop-laden reply, hand-fed Stop JSON | feedback | 4.6 s | 7 (opener, closer, em dash, "serves as a testament", "robust landscape", "seamlessly enhancing", "delve") |
| a two-sentence status reply | allow | 2.4 s | none |
| three `PRINCIPLES.md` bullets, which open on bold lead-ins | allow | 2.4 s | none, where the prototype misflagged two lead-ins under rules 34 and 36 |
| live loop through `try` | feedback, rewrite, allow | 6.6 s | 7, listed above |

**QA surface.** Run `try` for the loop above, or feed the hook a message directly:

```
echo '{"last_assistant_message":"Great question! Let me delve into this — it serves as a testament to the robust landscape.","stop_hook_active":false}' \
  | env -u DISPATCH_WORKLOG mx/skills/writing-for-humans/chat_review.py
```

`CHAT_REVIEW_OFF=1` in front of it logs `skip / off` instead, and with `DISPATCH_WORKLOG` set, as a dispatched worker has it, `skip / dispatched worker`. `CHAT_REVIEW_LOG` moves the log, whose default is `~/.cache/chat-review/log.jsonl`.

**Action items.**

1. Release before it reaches any machine: `mx/.claude-plugin/plugin.json` is still 0.1.56 and `claude plugin update` is version-gated, so `make release-patch` and a push are what ship the hook. A live session picks up a new hooks file only on `/reload-plugins` or a restart.
2. Rule on the reviewer's reach, which the spec set as every session with the plugin: that now includes every non-dispatch `claude -p` on the machine, each paying a nested Haiku call and a continuation. Narrowing it is one more early return.
3. Rule on the residue, the spec's deferred question: the demo shows the rewrite clearing every quoted hit and leaving two em dashes nobody quoted. Either the reviewer quotes every instance, or a second check runs before the re-entry passes. The log answers this after a week. (Ruled 2026-09-15: no second check; the review runs once per turn and the session decides which hits to act on. How many instances the reviewer quotes stays with the log.)

**Assumptions.**

- A1 `mx/skills/writing-for-humans/chat_review.py:121`: (amended 2026-09-15, `ab65a19` added the print-mode marker `CLAUDE_CODE_SESSION_ATTENDED`, on a version of the harness this host does not run) a dispatched worker's `DISPATCH_WORKLOG` was the only "session nobody reads" marker implemented. The ticket's second marker was conditional on the harness marking an unattended session, and Claude Code 2.1.243 marks none: the variable the prototype named appears in neither the binary nor the hooks, settings or headless documentation. Reverse by adding the check when the harness grows one.
- A2 `mx/skills/writing-for-humans/test_chat_review.py:1`: a test file, where the spec's Testing Decisions says "No executable seam exists for them; every property is **reviewed**". The scope selection and the parse of a reviewer's answer are executable seams with an oracle (the catalogue header's own command), the Standards and Correctness axes both flagged the missing test, and every sibling script under `mx/skills/` has one collected by `make test`. Reverse by deleting the file; the runtime guards it pins stay either way.
- A3 `mx/README.md:95`: the hook is documented for humans in the README's manual-versus-AFK list. Nothing asked for that, and a hook that reviews every reply and has an off switch is a thing a human needs to find. Reverse by deleting the bullet.
- A4 `mx/skills/writing-for-humans/chat_review.py:87`: the log grows without a cap and holds every reply in full, which the Correctness axis flagged. It is the instrument for action item 3, so the cap belongs with that ruling rather than before it.

**Findings.** Review of `6a46b46` against `290bfa5`, three axes (no test files in that range, so no Tests axis). Fixes are in `c08a13b`.

- C1 a reviewer answer whose `hits` are not objects crashed the formatter past the fail-open boundary, losing the review and showing a hook error → fixed, `hits_from` drops what it cannot format, pinned by a test.
- C2, also P3: an empty selection reviewed every reply against no rules and logged them clean, so a catalogue reformat would retire the reviewer silently → fixed, the selection raises into the fail-open path, pinned by a test.
- C3 the log grows without bound → declined, A4.
- S1 no test beside the script where three sibling scripts have one → fixed, and the script took the `.py` name they use so its seams can be imported.
- S2, also P4: the selection had two homes, the header's awk command and the script's Python, differing on malformed input → fixed, the test runs the header's command on the real catalogue and demands the same bytes.
- S3 a hook switched off read the same as one that never ran → fixed, both early returns log a skip line.
- S4 the nested call reaches every print-mode session on the machine → declined as the spec's own ruling, raised as action item 2.
- S5 the README pinned the log path and said `CHAT_REVIEW_OFF=1` where any value works → fixed, it names the variable and points at the script.
- S6, also P2: the plugin version is unbumped → action item 1.
- P1 no demo and no closing comment → fixed, this comment.
- P5 `ANSWER.md` had been edited to credit the prototype with finding the `DISPATCH_WORKLOG` marker → fixed, it records what the prototype actually found and leaves the marker to the build.

**Friction.**

- `claude --plugin-dir <path>` is what made the registration testable: it loads a plugin from a directory for one session, so a worker can drive the shipped hooks file without touching the machine's installed copy. It is in `claude --help` and not on the plugins reference page, and I found it only after building the demo around a hand-written settings file. Worth knowing for any later hook work in this repo.
- The review skill in force deletes the axis reports after aggregation, so the finding index above is the only surviving trace of three reviews. Ticket 04 is the fix.
- A manual `pytest` run inside the plugin tree wrote `__pycache__` into `mx/skills/writing-for-humans/`, and it reached a commit before I caught it. `make test` sets `PYTHONDONTWRITEBYTECODE`, which is why nothing else in the tree has one; `__pycache__` in `.gitignore` would make the accident impossible. Left alone as outside this ticket.
