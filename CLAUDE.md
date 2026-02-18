
This is my coding agent setup (mainly claude code).
`mx` is a plugin for skills, commands, etc. The rest of my regular setup is in ~/.dotfiles, which will occasionaly be referenced here (./zsh/aliases ./zsh/functions bin/ ./setup interact with my agent setup)

Memex cli code loc: /home/max/repos/github/MaxWolf-01/memex
When working on it read its readme & claude.md

# Prompting Principles

- Don't prompt with a list of dos and don't, but general principles. This helps agents ... generalize better to a range of scenarios. If they know what the motivation is, they can interpret it intelligently, rather than playing whack-a-mole with a list of specific instructions.
- Skills, commands, any prompts you write, these are written for and read by other agents just like you. Empathise with their perspective.
- Remember that agents sometimes take prompts quite literally, so be careful with wording. Again, aim for general principles rather than overspecifying edges cases.
- Before upating or writing skills/commands/any prompt, consult prompt dev/plugin dev/skill dev skills!

