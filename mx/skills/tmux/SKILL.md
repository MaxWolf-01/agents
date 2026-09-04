---
name: tmux
description: "Run commands in tmux whenever they run long or need eyes on them: anything expected to take more than ~30–60s (training runs, ML experiments, builds, servers), anything worth observing mid-run (progress logs, monitoring output), and anything interactive (sudo prompts, REPLs, wizards), locally or on a remote host. Always reach for this instead of a fire-and-forget Bash call in those cases; the human can attach and step in at any time."
---

# tmux

A command runs in tmux, never as a blocking one-shot Bash call, when any of these hold: it runs longer than ~30–60s, its live output is worth watching (training progress, monitoring), or it's interactive (sudo prompts, REPLs, wizards). The session survives independently, scrollback is readable by agent and human alike, and either can step in mid-run. Quick one-shot commands (`ssh host cat file`, a fast build) stay plain Bash: the criteria decide, not the transport.

## Sessions

- `tms claude`: create or attach the default shared session.
- **Check before sending**: the shared session may be busy with another agent's process. `tmux list-panes -t claude -F '#{pane_current_command}'`: anything but a shell name means occupied. Then create your own session named for the activity (`tmux new-session -d -s <activity>`, e.g. `train-resnet`) and tell the user its name.
- Kill only what you created, by name: `tmux kill-session -t <name>`. Never `kill-server`: the user's server hosts their shells, editors, and every other agent. Throwaway servers for tests get their own socket, `tmux -L <label> ...`, and die with `tmux -L <label> kill-server`. `TMUX_TMPDIR` is not isolation inside a pane: `$TMUX` already names the socket and wins.
- Send a command: `tmux send-keys -t <session> -l 'command'` then `tmux send-keys -t <session> Enter`
- Read output: `tmux capture-pane -p -J -t <session> -S -50` (`-J` joins wrapped lines)

## Long jobs

A job that must finish belongs on a machine that isn't going to suspend; `worker-hosts` names the ones there are, where the environment provides such a command.

For what has to run on a laptop, prefix it with `nosleep`: `nosleep uv run train.py`. Idle suspend counts keyboard and mouse input, not CPU load, so a detached tmux pane crunching for an hour looks exactly as idle as an empty desk and gets suspended out from under you. `nosleep` holds a systemd inhibitor for the job's lifetime (idle, sleep, and the lid switch) and releases it on exit; it is a no-op where there's nothing to inhibit.

## Remote (SSH)

Always quote the full tmux command so spaces survive the remote shell:

```
ssh host "tmux send-keys -t claude -l 'command'"
ssh host "tmux send-keys -t claude Enter"
ssh host "tmux capture-pane -p -J -t claude -S -50"
```

One command per ssh call. A chained remote command that starts the tmux server inherits the connection's stdout and holds the call open until it times out.

Waiting on a remote job (`ssh host tmux wait-for <channel>`) is a hint, not proof. Suspend the laptop and the ssh call dies while the remote `tmux wait-for` lives on; the signal then reaches an orphan and is remembered for nobody. Add `-o ServerAliveInterval=15 -o ServerAliveCountMax=2` to collapse dead connections fast, and ask the host what is running to learn whether the job finished.

## Interactive prompts

Poll for the prompt before sending input; don't race it. Use `bin/tmux-wait-for-text` where available, or loop on `capture-pane` until the expected text (sudo prompt, confirmation, wizard question) appears, then send.

## Human access

The user can always attach directly: `tmux attach -t claude` locally, or `ssh host -t "tmux attach -t claude"` remotely; mention the session name when you start something they might want to watch.
