
This is my coding agent setup (mainly claude code).
`mx` is a plugin for skills, commands, etc. The rest of my regular setup is in ~/.dotfiles, which will occasionaly be referenced here (./zsh/aliases ./zsh/functions bin/ ./setup interact with my agent setup)

## clankr

[clankr](https://github.com/MaxWolf-01/clankr) (`/home/max/repos/github/MaxWolf-01/clankr`) — run Claude Code in isolated Docker containers. `--dangerously-skip-permissions` without the danger.

Profiles live in `clankr1/` (symlinked to `~/.config/clankr/profiles/clankr1/`). Each profile has:
- `CLAUDE.md` — system prompt for the containerized agent
- `settings.json` — claude code settings
- `init` — runs inside the container before claude starts (plugin installs, extensions, etc.)

Memex cli code loc: /home/max/repos/github/MaxWolf-01/memex
When working on it read its readme & claude.md

# Resources

Some resources that might be useful to consult when brainstorming architectural / design decisions around the workflow etc.

./resources - ls this dir to see what's there

/home/max/repos/github/agenticnotetaking/arscontexta
"Claude Code plugin that generates individualized knowledge systems from conversation. You describe how you think and work, have a conversation and get a complete second brain as markdown files you own."
Very similar to my long-term intent/goals for this project/workflow. See resources/arscontexta-heinrich-on-context-graphs.md for their high-level motivation (more company focused). Their README and repo is worth taking a look at for ideas and inspiration for sure, but I feel the approach can be much more lightweight and bitter-lesson-pilled.

/home/max/repos/github/Dominilk/hacknation-2026 
rushed <1d hackathon project, but had some good brainstorming for a scalable architecture with multiple event streams, conflict resolution, etc., based on the challenge of solving information flow in a large org. overengineered in some ways, esp for single-user, but still some good ideas for updating and refining.

# Prompting Principles

- Don't prompt with a list of dos and don't, but general principles. This helps agents ... generalize better to a range of scenarios. If they know what the motivation is, they can interpret it intelligently, rather than playing whack-a-mole with a list of specific instructions.
- Skills, commands, any prompts you write, these are written for and read by other agents just like you. Empathise with their perspective.
- Remember that agents sometimes take prompts quite literally, so be careful with wording. Again, aim for general principles rather than overspecifying edges cases.
- Before upating or writing skills/commands/any prompt, consult prompt dev/plugin dev/skill dev skills!

