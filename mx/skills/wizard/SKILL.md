---
name: wizard
description: Generate an interactive bash wizard that walks a human through steps only they can perform. Use when provisioning infrastructure, setting up credentials or CI secrets, walking an unfamiliar third-party dashboard, or running a one-off migration or cutover.
---

# Wizard

A **wizard** is a bash script that walks a human step by step through a manual procedure: it opens each URL, says exactly what to click and copy, captures the values, writes them where they belong (`.env`, GitHub secrets), confirms at every stage, and shows how much is left.

[template.sh](template.sh) already provides the UX: progress with time remaining, confirmation gates, cross-platform URL opening (including WSL), hidden secret entry, idempotent `.env` upserts, `gh secret`/`gh variable` writes, and a closing summary. **Your job is only to scope the procedure and author its stages.**

By default a wizard is built for one run, saved to `~/Downloads`, and deleted when the job is done. A repeatable procedure (a setup other maintainers will run, a recurring workflow that needs human input) goes in `scripts/` and is committed.

## Process

### 1. Scope the procedure

Work out every manual step the human must take and every value captured along the way, reading the repo before you ask the user anything:

- For setup: `.env`, `.env.example`, `.env.*`, `README`, `docker-compose*`, framework config, and `.github/workflows/*` (every `secrets.*` / `vars.*` reference is a value the wizard must produce).
- For a migration or transition: the current state, the target state, and the irreversible actions between them.

Then show the user the ordered stages and the values each produces, and have them confirm; they may add, drop or reorder.

**Done when:** every stage is named in order, and for each captured value you know (a) where the human gets it, (b) where it's written (`.env`, a GitHub secret, both, or nowhere; some stages are pure actions), and (c) whether it's secret (hidden entry) or public.

### 2. Map each stage's journey

For each stage, write the exact path a human follows: the URL to open, what to do there, where the value is shown, and which variable it fills, e.g. "Dashboard → Developers → API keys → Reveal test key → copy". Where you do not know the current UI or the exact command, say so and ask the user or check the docs, so every step you write exists.

**Done when:** every stage traces to concrete instructions a stranger could follow.

### 3. Author the wizard

Copy `template.sh` to the target path and replace the example stage with one `stage` per step, in dependency order, built from the library helpers (`stage`, `say`/`step`, `open_url`, `ask`/`ask_secret`, `write_env`, `set_secret`/`set_var`, `pause`/`confirm`). Set `TOTAL_STAGES` to the number of stages you wrote.

Hold the bar the template sets: open the URL before asking for its value, use `ask_secret` for anything secret, `write_env` every persisted value, `set_secret` only the values CI actually needs, and `confirm` before any irreversible action. Each `stage` clears the screen, so keep a stage to one focused task whose instructions all fit on it. The library above the `STAGES` marker is identical in every wizard, so it stays as the template has it.

### 4. Verify and hand off

- Trace it statically rather than running it end-to-end, since it opens browsers and blocks on human input: every value from step 1 is captured and lands where step 1 said, and every `set_secret` name exactly matches a `secrets.*` reference in CI.
- If it's a repeatable setup path, commit it and link it from the README so the next person runs the script instead of asking an AI.
