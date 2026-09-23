---
status: proposed
priority: 2
size: XS
---

# The runner resumes a worker that stopped early

## Brief

A worker whose session exits cleanly while its ticket still says claimed has stopped before finishing; the runner resumes it on its own instead of waiting for the orchestrator to notice.

Filed on the user's rule that a question with no ticket to hang on becomes a proposed ticket (board-orients spec, 2026-09-23). The whole-feature review of figures-and-demos exited twice on 2026-09-22 with exit 0 and its ticket still `claimed`, both times after ending its turn while its own demo runs were going; `run-worker.sh` retries only on a nonzero exit, so the orchestrator resumed it by hand each time.

## What to build

After a clean exit the runner reads the ticket's status; a ticket still `claimed` is resumed with a short message saying the session ended mid-work and must wait on whatever it started before ending its turn. The resume counts against the same attempt budget as a crash, and the worklog says which it was.

## Acceptance criteria

- [ ] A worker that exits 0 with its ticket `claimed` is resumed by the runner, and one that exits 0 with its ticket in `review` is not.
- [ ] A resume after a clean exit spends one attempt, and the worklog line names it as an early stop.
- [ ] Demo: the demo that drives dispatch against a stubbed `claude`, with a stub that exits 0 once before flipping `review`.
