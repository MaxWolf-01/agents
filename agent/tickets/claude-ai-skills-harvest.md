---
status: open
---

# Take in the kept claude.ai skills: document skills listed by name only, struktogramm as a show companion, a harvest of the rest

Asked for by the user in chat, 2026-09-23. The claude.ai skill sync is off (`13acff5`, `syncClaudeAiSkills: false`): its 14 skills cost ~3k tokens on every request and none were used (`agent/research/09-skill-token-usage.md`). The user kept six in `~/tmp/claude-ai-synced-skills-2026-09-23/`, a scratch directory: docx, pdf, pptx, xlsx, skill-creator, struktogramm.

## 1. docx, pdf, pptx, xlsx on hand at ~5 tokens each

They stay invocable while their listing entry shrinks to `- <name>`. The mechanism is `skillOverrides: {"<name>": "name-only"}` in `claude/settings.json`, and it holds only for skills outside a plugin: Claude Code lists every plugin skill in full whatever the override says (verified by capture, research 09). So they are user skills in `~/.claude/skills/`, not mx skills.

Their `LICENSE.txt` reads "© 2025 Anthropic, PBC. All rights reserved", with use governed by the user's agreement with Anthropic, so they stay out of this public repo. `~/.dotfiles/secrets/skills/`, symlinked into `~/.claude/skills/` as `leistung` and `lifelog` already are, is one private home; any private home counts.

skill-creator is Apache-2.0: whether it is installed the same way or only read for part 3 is the user's call.

Done when a capture (`agent/research/09-skill-token-usage/capture`, then `compose.py`) lists each installed one as a bare `- <name>` line, and invoking one loads its body with a base directory its scripts resolve against.

## 2. struktogramm, redone as a companion of show

struktogramm is the user's own (`"source": "custom"` in the manifest): Nassi-Shneiderman diagrams as HTML/CSS, with `examples/`, `references/` and `scripts/`. It becomes a companion file of `mx/skills/show/` beside `SVG-FIGURES.md` and `PAGES.md`, reached from one line in show's SKILL.md, so it adds nothing to the listing. The Diagram bullet there already names Nassi-Shneiderman; a row in the Shape table is the other candidate. It is rebuilt to show's conventions (house style, `render_lint.py`) rather than copied.

Done when show points to it in one line, its example renders through `render_lint.py` with no findings, and the user has ruled on a render.

## 3. What the others teach

Read skill-creator, docx, pdf, pptx and xlsx for what mx could take:
- skill mechanics for `mx/skills/writing-for-agents/SKILL-MECHANICS.md`: skill-creator's eval loop, description tuning and `eval-viewer/`; how the document skills split scripts from prose;
- anything for skilltree (`~/repos/github/MaxWolf-01/skilltree`). The claude.ai `learn` skill, the obvious candidate there, was not kept; its full body survives in the load at `~/.claude/projects/-home-max--dotfiles/e88646e1-4060-48af-ab71-6e569d0a785b.jsonl`.

Done when a research note under `agent/research/` gives each of the five a verdict (take, adapt, or nothing), with the source file for every claim, and each "take" or "adapt" is filed as a proposed ticket in the repo it lands in.
