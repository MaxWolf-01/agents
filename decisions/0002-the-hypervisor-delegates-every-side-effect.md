# The hypervisor delegates every side effect to Claude Code sessions, and gets no sandbox of its own

The hypervisor runs in pi, which has no sandbox and no permission classifier. So it gets no tool that writes a file or runs a command (`lifelong-hypervisor#P4`): every side effect goes through a Claude Code session in auto mode, which it starts or delegates to, and whose permission classifier judges each action. Delegating to orchestrators is the hypervisor's job anyway, so the rule takes nothing from it. The classifier is maintained by Anthropic, and building a sandbox to stand in for it here would only duplicate that work.

## Considered Options

- **A shell in a sandbox:** run the hypervisor in a Docker container, or behind a sandbox, and give it a shell. Rejected: it adds a boundary to build and maintain for no gain, since the hypervisor has nothing it must do itself.
- **A shell with no sandbox:** rejected. Anything the model runs would run with max's full rights, unreviewed.

## Consequences

Each new capability the hypervisor needs arrives as a narrow tool with fixed programs and checked arguments, never as a general one. Examples are waiting on a job (`job wait`, run without a shell) and leaving Jarvis a message (an ssh key whose only command writes an inbox file).
