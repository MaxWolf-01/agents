# Show: one flow (round 7)

Both figures redrawn against the round-7 spec, rendered to PNG in both schemes with the copied `render.py`, and looked at in both schemes: no overlaps, no clipped text. Nothing committed; nothing outside this directory touched.

Look first: `/home/max/repos/github/MaxWolf-01/agents-one-flow/agent/show/one-flow/one-flow-light.png`

## Files

| File | What changed |
| --- | --- |
| `one-flow.html`, `one-flow-light.png`, `one-flow.png` | The flow. New in the chat column: a `YOU` chip on the intent card (open questions in grilling rounds are a station; ratifying calls is not), and a "speculative build" bar (starts once no question is left, builds the agent's calls unratified, you rule on the result). Row 1: "No agent review", the page is the only gate. Row 2: the worker card says "dispatch, the repo's host" and "the worker prompt is its contract"; the ticket is "written cold, built at once"; light review "reports on disk, fixed or declined by the worker". Row 3: the spec card has no chip any more (the gate no longer holds the build), tickets are "published proposed, on the board", the worker "starts while proposed", the orchestrator bar adds "the integration branch waits for your approval; nothing ships on a guess". Every land card is now "Demo, review page" (row 3: "Demo, page, QA"), the thing first, then the diff. The worker dial reads "this session, a worker on the host". The dek states the speculative rule. |
| `what-changes.html`, `what-changes-light.png`, `what-changes.png` | Eleven rows now (were seven). Corrected: implement (deleted, process in the worker prompt), the gate (strips marks, no longer holds the build), standalone ticket (same scripts and host selection, no "this machine"), the review rule (loose work gets no agent review; its page is its gate), attention (four stations: open questions in grilling rounds, demo and review page, QA, needs-human queue). Added: speculative build, the demo, review delivery, prototypes. Prose rules and best-of-N unchanged. |
| `render.py` | Unchanged; `uv run --script render.py` regenerates all four PNGs. |

All under `/home/max/repos/github/MaxWolf-01/agents-one-flow/agent/show/one-flow/`.

## Sources used

The round-7 spec (`agent/tickets/one-flow/spec.md`) for every claim on the "one flow" side; the orient, dispatch, code-review, prototype and grilling skills for the "today" side.

## Not done

Nothing left out. The `YOU` chips mark exactly the four stations the spec names; the spec gate chip the earlier figure carried is gone.
