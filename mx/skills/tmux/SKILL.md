---
name: tmux
description: "Run commands in tmux whenever they run long or need eyes on them: anything expected to take more than ~30–60s (training runs, ML experiments, builds, servers), anything worth observing mid-run (progress logs, monitoring output), and anything interactive (sudo prompts, REPLs, wizards), locally or on a remote host. Always reach for this instead of a fire-and-forget Bash call in those cases, and before writing any loop or background command that waits for something to finish; the human can attach and step in at any time."
---

# tmux

Run a command in tmux rather than as a blocking Bash call when it takes more than ~30-60s, when its output is worth watching, or when it is interactive. The session outlives the command, the scrollback is readable by agent and human alike, and either can step in. Quick one-shot commands stay plain Bash.

## Anything you will wait on: `job`

Read `job --help` before the first job of a session. It is the only home of the commands, the exit codes and the wait flags.

Never hand-write the wait. An inline predicate is where the bugs are: `pgrep -f <pattern>` matches the waiting shell's own command line and loops forever, and a `tail -f | grep` for the success marker stays silent through a crash.

Name jobs `<project>-<activity>`, like `nethack-setup`. The name shows up in `tmux ls`, and it stays taken until `job rm`.

## A pane you drive yourself

A REPL, a wizard, a sudo prompt, an app you poke at while watching it. Nothing here ends, so there is no completion to wait on and `job` buys nothing.

- One session per job, named for the activity: `tmux new-session -d -s <activity>`. A taken name fails the command, so pick another.
- Kill only what you created: `tmux kill-session -t <name>`. Never `kill-server`; that server holds the user's shells, editors and every other agent. A throwaway server for a test gets its own socket, `tmux -L <label> ...`, and dies with `tmux -L <label> kill-server`. Inside a pane `$TMUX` already names the socket and beats `TMUX_TMPDIR`.
- Send: `tmux send-keys -t <session> -l 'command'`, then `tmux send-keys -t <session> Enter`.
- Read: `tmux capture-pane -p -J -t <session> -S -50`, where `-J` joins wrapped lines.
- Poll before you type. `bin/tmux-wait-for-text` waits for a prompt to appear; racing it sends input into nothing.

## Remote

Quote the whole tmux command so spaces survive the remote shell, one command per ssh call. A chained remote command that starts the tmux server holds the call open until it times out.

```
ssh host "tmux send-keys -t <session> -l 'command'"
ssh host "tmux send-keys -t <session> Enter"
ssh host "tmux capture-pane -p -J -t <session> -S -50"
```

Wait on a remote job with `job` on that host, read over ssh. Never `tmux wait-for`. Suspend the laptop and the ssh call dies while the remote waiter lives on, the signal wakes that orphan, and the next waiter on the channel hears nothing. `-o ServerAliveInterval=15 -o ServerAliveCountMax=2` collapses dead connections fast.

## Attaching

Give the user the command, not the session name: `tmux attach -t job-<name>`, `tmux attach -t <session>` for a pane you made yourself, or `ssh host -t "tmux attach -t <session>"` for either on a remote host.
