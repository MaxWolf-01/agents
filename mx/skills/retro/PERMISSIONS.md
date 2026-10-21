# Permissions: the data and the entries

What the workflow retro's permissions worker reads, and the shape of an entry it proposes. max works in auto mode, where a classifier judges every shell command outside Claude Code's built-in read-only set and every other call no rule settles. Its mistakes are the permission friction, in two directions, and what fixes them is prose the classifier reads: an `autoMode` entry.

## The data

- **Denials in the digests** are `! DENIED <tool> (<kind>)` lines. `automode-blocked` is the classifier refusing a call, the rule it applied after `Reason:`; `permission-rule`, a deny or ask rule of the settings; `user-rejected`, max saying no at a prompt; `interrupted`, max stopping the call. A digest from before the kind was recorded says `denial`. `/permissions` → Recently denied lists the same classifier denials from the running session's memory alone; the transcripts are the record that lasts.
- **`[classifier allowed]`** after a call's tool name, `→ Bash [classifier allowed] {…}`, marks a call the classifier judged and let run. A call without it ran on a rule, the built-in read-only set or a mode with no classifier, or was denied.
- **`rules.json`** is each settings file's `permissions` and `autoMode`, as the profile sets them; **`auto-mode.json`**, the auto mode config in effect, the shipped defaults where the profile sets none. Where `auto-mode.failed` stands in its place, the config could not be read.

## The two directions

- **A false block** is a denial max wanted through: he approved or retried it, told the agent to go ahead, or let a way around it stand. It becomes an `allow` entry, an exception to the soft-deny rule its `Reason:` names, or an `environment` entry where the classifier lacked a fact: a trusted destination, one of max's own CLIs, a sensitive target.
- **A false allow** is a `[classifier allowed]` call max stopped, undid or corrected afterwards, and an incident nothing blocked: work lost, a commit or push on the wrong branch, a destructive command. A block an agent got past by rephrasing the same action is a false allow of the rephrased call, where the block was right. It becomes a `soft_deny` entry, which max's intent in the conversation can still clear, or a `hard_deny` entry for a line no intent may cross.

## An entry

- **It covers the class of action**, never the one command: what is allowed or blocked, by category, and what clears it. The entries in `rules.json` are the model: a soft-deny rule carries its name and the consent it needs (`[named+specifics — **must name:** …]`), an exception names the rule it clears and where it stops. An existing entry that nearly covers the case is amended rather than joined by a second.
- **It goes in `autoMode` of `~/.claude/settings.json`**, the agents repo's `claude/settings.json`: Claude Code reads `autoMode` from user settings, managed settings and `--settings` alone, never from a project's `.claude/` files.
- **That file is public** (MaxWolf-01/agents): an entry names no work host, database or internal path, and states what it allows or blocks by category, as the Helferline entries there do.
- **A whole tool max wants gone** is a `permissions.deny` entry, as `AskUserQuestion` and `EnterPlanMode` are. A pattern-matched Bash rule, in `allow`, `deny` or `ask`, matches only the text written: `Bash(git push *)` misses `git -C . push`, and `Bash(git -C * status)` also matches `git -C . -c core.fsmonitor=<script> status`, which runs any script.
- **The critique reads it beside the shipped defaults**, not beside max's own entries, since it fails on a rule set as long as his: a clash with one of his is the worker's to find in `rules.json`.
