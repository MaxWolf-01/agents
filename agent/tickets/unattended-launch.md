---
status: open
type: grilling
---

# How every unattended `claude` run is launched: model, effort and context

## Brief

Asked for by the user on 2026-09-23 (D115), while ruling on review-launcher: Opus 5.5 everywhere by default, steered by effort (low to max) rather than by switching models, and every unattended launch declaring what it inherits from the machine it runs on. This grilling settles the rule, where it is written (the user's `claude/CLAUDE.md` subagents line, a skill, or both), and then every call site below changes at once.

What a launch inherits today depends on the host. A `claude -p` on zephylux picks up the user's output style, their global `CLAUDE.md` files, their allowlist and hooks, the skill list, and, when they have loaded in time, the claude.ai connectors (Gmail, Calendar, alphaXiv, Claude Docs: up to 89 tools, a 234 KB first request). The same launch on agent@pc gets none of the user's files. Captured requests and the capture script: `~/Downloads/show/review-launcher-calls/` (its `demo` regenerates them; D114 section of its page).

Settled already, and the pattern to reuse: code-review's reviewers launch with `--setting-sources "" --strict-mcp-config --disable-slash-commands --settings '{"autoMemoryEnabled": false}' --tools …`, Opus, `--effort high` (review-launcher, D114, D115). Dispatch workers drop the output style once branch `dispatch/worker-no-output-style` lands (D128).

## The call sites

| Launch | Where | Model today | Context today |
| --- | --- | --- | --- |
| subagents | `claude/CLAUDE.md`, `<subagents>` | Opus; Fable for large work, Sonnet for lookups | the harness's |
| dispatch workers | `mx/skills/dispatch/run-worker.sh`, `dispatch/SKILL.md` step 3 | Opus; Sonnet for a small ticket | user `CLAUDE.md` and output style excluded; skills, allowlist, hooks and connectors inherited |
| board briefing | `mx/skills/tracker/briefing.py` (board-orients) | Opus 5.5, medium (board-orients 16) | user `CLAUDE.md` and output style excluded; the run replaces the system prompt, so the style is out of the request either way (board-orients 16) |
| chat-review hook | `mx/skills/writing-for-humans/chat_review.py` | Haiku, thinking off | none (`--setting-sources ""`) |
| diffview summary | `~/.dotfiles/bin/diffview` | Sonnet | everything |
| session naming | `~/.dotfiles/bin/session-index` | Sonnet | none (`--system-prompt`, `--setting-sources ""`) |

The chat-review hook's own audit (`reviewer-ablation.md`) measured Haiku at 9% valid findings and Opus 5.5 at 47%, at about $0.02 against $0.10 a review.

## Acceptance criteria

- [ ] The rule is recorded where the user decides, with the default model and how effort is chosen; options outside this brief count.
- [ ] Each call site above launches by the rule, or its row records why it deviates.
- [ ] A worker's and the briefing's context is decided: which of the project's settings, skills and MCP servers they keep. A worker running the mx skills needs the plugin; a project's own `.mcp.json` may be one it needs.
- [ ] A check fails when a `claude -p` in mx does not state what it inherits (`--setting-sources`), so a new launch cannot inherit by accident.
