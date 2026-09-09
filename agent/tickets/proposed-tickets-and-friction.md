---
status: open
type: grilling
---

# Proposed tickets, and where friction goes

The human wants to read one thing per feature besides the diff: the orchestrator's proposal. Today the orchestrator's readings (a worker's friction from its closing comment, a harden report, the punts dispatch files) either become tickets that look like the user's own or entries on the needs-human queue, and the user cannot tell an orchestrator's suggestion from a decision they made in grilling.

## Question

- Does the tracker get a state or marker for a ticket an agent proposes (an orchestrator, a review session) that the user has not yet ruled worth doing: separate from `open`, never on the frontier until the user says so, never confirmed by default?
- What is the friction pipeline: workers already name friction in their closing comment (`/mx:implement`), dispatch files punts and queues decisions (`/mx:dispatch`, tick step 1); what is missing is the orchestrator's synthesis per feature (proposals with reasons) and one place the user reads it. Is that the needs-human file, the board, or the PR-ready report?
- `/mx:reflect` and the session index are the other candidates for reading friction across sessions; where do they fit, if at all?

Raised from review comment C12 on the testing-workflow implementation.
