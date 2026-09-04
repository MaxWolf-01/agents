
This is my coding agent setup (mainly claude code).
`mx` is a plugin for skills, commands, etc. `claude/` is the global `~/.claude` config, symlinked live, so edits apply everywhere. The rest of my regular setup is in ~/.dotfiles, which will occasionaly be referenced here (./zsh/aliases ./zsh/functions bin/ ./setup interact with my agent setup)

# Releasing mx

Every machine installs `mx` from the marketplace, and `claude plugin update` is version-gated: it re-copies only when `mx/.claude-plugin/plugin.json` carries a version it doesn't have yet. So shipping skill edits is `make release-patch` (bump + commit; `release-minor|major` when the number should say more) then `git push`; a pre-push hook (`~/.dotfiles/git/hooks/mx-plugin-update-pre-push`) updates the plugin on this machine; a worker host pulls its own version when dispatch sets a run up. Unpushed and untagged edits exist nowhere: no version, no install.

# Resources

Some resources that might be useful to consult when brainstorming architectural / design decisions around the workflow etc.
- ./resources
- ALWAYS consult the "writing for agents" skill when updating anything here / anywhere agents might read it / meant primarily for agent consumption, including skills, docs, ...
- Before changing a skill, a CLAUDE.md, or how the workflow runs, read `PRINCIPLES.md`: the rules every past refinement of this workflow re-learned, with the commits as evidence. A change that strains one says so in its commit message.


# Related Porjects

Always first read readme & claude.md of any repo youre working with / consulting.

[**clankr**](https://github.com/MaxWolf-01/clankr) (`/home/max/repos/github/MaxWolf-01/clankr`): run Claude Code in isolated Docker containers. `--dangerously-skip-permissions` without the danger.

Profiles live in `clankr1/` (symlinked to `~/.config/clankr/profiles/clankr1/`). Each profile has:
- `CLAUDE.md`: system prompt for the containerized agent
- `settings.json`: claude code settings
- `init`: runs inside the container before claude starts (plugin installs, extensions, etc.)

**Memex cli** /home/max/repos/github/MaxWolf-01/memex
