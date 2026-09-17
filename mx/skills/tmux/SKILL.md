---
name: tmux
description: "Run commands in tmux whenever they run long or need eyes on them: anything expected to take more than ~30–60s (training runs, ML experiments, builds, servers), anything worth observing mid-run (progress logs, monitoring output), and anything interactive (sudo prompts, REPLs, wizards), locally or on a remote host. Always reach for this instead of a fire-and-forget Bash call in those cases, and before writing any loop or background command that waits for something to finish; the human can attach and step in at any time."
---

# tmux

A command runs in tmux, never as a blocking one-shot Bash call, when any of these hold: it runs longer than ~30–60s, its live output is worth watching (training progress, monitoring), or it's interactive (sudo prompts, REPLs, wizards). The session survives independently, scrollback is readable by agent and human alike, and either can step in mid-run. Quick one-shot commands (`ssh host cat file`, a fast build) stay plain Bash: the criteria decide, not the transport.

Two shapes, and the split is whether you intend to wait on it.

## Start it and be told how it ended: `job`

**Run `job --help` before the first `job` of a session.** It is the single home of the command shapes, the exit code per outcome, and the flags that end a wait; repeating any of that here would be a copy that goes stale the next time the script changes.

Two rules that are not in it:

- **Never hand-write the wait.** A predicate typed inline is where the bugs are: `pgrep -f <pattern>` matches the waiting shell's own command line and loops forever, and a `tail -f | grep` for the success marker stays silent through a crash. `job wait` is that predicate debugged once.
- **Name it `<project>-<activity>`** (`nethack-setup`, `dotfiles-hmswitch`). The name is what shows in `tmux ls`, and it stays taken until `job rm`, so a second agent reaching for `build` gets an error rather than your log.

A job that must finish belongs on a machine that will not suspend; `worker-hosts` names the ones there are, where the environment provides such a command. On a laptop `job run` holds the inhibitor for you, and `--no-awake` drops it for a command that never ends — a server or a watcher otherwise keeps the machine from suspending for as long as it runs.

## Drive it yourself: raw tmux

For a pane you interact with — a REPL, a wizard, a sudo prompt, an app you watch while poking at it — there is no completion event to wait on, so `job` buys nothing.

- One session per job, named for the activity: `tmux new-session -d -s <activity>`; a taken name makes it fail, so pick another. Tell the user the name.
- Kill only what you created, by name: `tmux kill-session -t <name>`. Never `kill-server`: the user's server hosts their shells, editors, and every other agent. Throwaway servers for tests get their own socket, `tmux -L <label> ...`, and die with `tmux -L <label> kill-server`. `TMUX_TMPDIR` is not isolation inside a pane: `$TMUX` already names the socket and wins.
- Send a command: `tmux send-keys -t <session> -l 'command'` then `tmux send-keys -t <session> Enter`
- Read output: `tmux capture-pane -p -J -t <session> -S -50` (`-J` joins wrapped lines)
- Poll for a prompt before sending input; don't race it. Use `bin/tmux-wait-for-text` where available, or loop on `capture-pane` until the expected text appears, then send.

## Remote (SSH)

Always quote the full tmux command so spaces survive the remote shell, one command per ssh call — a chained remote command that starts the tmux server inherits the connection's stdout and holds the call open until it times out.

```
ssh host "tmux send-keys -t <session> -l 'command'"
ssh host "tmux send-keys -t <session> Enter"
ssh host "tmux capture-pane -p -J -t <session> -S -50"
```

Waiting on a remote job is `job` on the remote host, read over ssh. Never `tmux wait-for`: suspend the laptop and the ssh call dies while the remote waiter lives on, the signal wakes that orphan, and a new waiter on the same channel never hears it. Add `-o ServerAliveInterval=15 -o ServerAliveCountMax=2` to collapse dead connections fast.

## Human access

Give the user the command, not the session name: `tmux attach -t job-<name>` for a job, `tmux attach -t <session>` for a pane you made yourself, `ssh host -t "tmux attach -t <session>"` for either on a remote host. A name alone makes them assemble the command from a message that has already scrolled away.
