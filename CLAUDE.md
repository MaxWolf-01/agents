
This is my coding agent setup (mainly claude code).
`mx` is a plugin for skills, commands, etc. `claude/` is the global `~/.claude` config — symlinked live, edits apply everywhere. The rest of my regular setup is in ~/.dotfiles, which will occasionaly be referenced here (./zsh/aliases ./zsh/functions bin/ ./setup interact with my agent setup)

# Resources

Some resources that might be useful to consult when brainstorming architectural / design decisions around the workflow etc.
- ./resources
- ALWAYS consult the "writing for agents" skill when updating anything here / anywhere agents might read it / meant primarily for agent consumption, including skills, docs, ...


# Related Porjects

Always first read readme & claude.md of any repo youre working with / consulting.

[**clankr**](https://github.com/MaxWolf-01/clankr) (`/home/max/repos/github/MaxWolf-01/clankr`) — run Claude Code in isolated Docker containers. `--dangerously-skip-permissions` without the danger.

Profiles live in `clankr1/` (symlinked to `~/.config/clankr/profiles/clankr1/`). Each profile has:
- `CLAUDE.md` — system prompt for the containerized agent
- `settings.json` — claude code settings
- `init` — runs inside the container before claude starts (plugin installs, extensions, etc.)

**Memex cli** /home/max/repos/github/MaxWolf-01/memex

