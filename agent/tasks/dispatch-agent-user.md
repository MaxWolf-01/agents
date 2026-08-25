---
status: open
---

# Dispatch workers run as an isolated `agent` user on pc

## Context

Dispatch already supports a remote worker host (`$MX_WORKER_HOST`, currently `pc`), so workers survive the laptop suspending or leaving the network. Today those workers would run as `max` on pc — the machine holding every backup (restic repos, phone, encrypted, yt: 746G on `tank`), the age key decrypted to tmpfs, and the tailnet identity. `max` is also in the `docker` group there, which is root-equivalent (`docker run -v /:/host`), so "workers stay in their worktree" currently has no enforcement and no undo behind it.

This ticket gives workers their own unprivileged user with a real filesystem, privilege, and network boundary, and moves the plugin-freshness mechanism to the pull side.

Cross-repo: NixOS + Home Manager config in `~/.dotfiles`, skill changes in this repo. One session.

## What to build

Dispatching to pc runs every worker as `agent@pc` — a user that cannot reach `max`'s files, the HDD pool, the system config, or the tailnet, and that carries its own declarative toolchain. Dispatch reads what that host can do before planning a wave, and each dispatch run pins one mx plugin version for its workers.

**The `agent` user (NixOS, pc)**

- `users.users.agent`: unprivileged — not in `wheel`, not in `docker`, no `sudo`. Home on the NVMe (`/home/agent`); no access to `/home/max` or `/home/max/data`.
- `linger = true`. Without it the user's tmux server can die with its last session and take every worker with it.
- The laptop's ssh key in `openssh.authorizedKeys.keys`; `MX_WORKER_HOST` becomes `agent@pc` (`nix/home/hosts/zephyrus.nix`, `xmg19.nix`).
- Rootless docker: `virtualisation.docker.rootless.enable` **and** `setSocketVariable = true` — without the latter the `docker` CLI addresses the system daemon, which this user deliberately cannot reach, instead of its own rootless one.

**Its environment (Home Manager, `home-manager.users.agent` in the flake's pc entry, own host file)**

A fresh user on pc starts with nothing: `tmux`, `git`, `uv`, `gh`, `node` all live in *max's* per-user profile today, only `rsync` is system-wide. The agent needs its own: tmux (+ config), git, uv, node, gh, rsync, chromium, `xvfb-run`.

- git identity = the clanker account (`MaxWolf-01-clanker`, noreply email), so worker commits are attributable in `git log`.
- `home.file."HOST.md"` — the host capability record dispatch reads at setup (see below). Written by the same config that installs the capabilities, so it cannot drift from them.
- No GitHub credentials. The bare repo is created empty (`git init --bare`) and the history arrives by push from the orchestrator, so nothing on pc ever authenticates to GitHub. A project needing GitHub (private git dependency, `gh` in a ticket) is a blocker to escalate, not a capability to provision.

**Network boundary (firewall, pc)**

Tailscale ACLs are per-node and cannot separate unix users, so the uid does it: reject the agent's *outgoing* connections over `tailscale0`.

pc runs the default iptables-backed NixOS firewall (`networking.nftables` is inactive, no `nft` in the system path), so this goes in `networking.firewall.extraCommands` as owner-match rules in the `OUTPUT` chain — not an nftables ruleset, and not worth switching the backend of a working server for.

- The rule must exempt established connections. The orchestrator's ssh is inbound, but sshd's session process runs as `agent`, so its reply packets carry that uid — a rule without the conntrack exemption kills dispatch itself.
- Write both `iptables` and `ip6tables` rules: tailscale is dual-stack, and `extraCommands` does not mirror v4 rules to v6. Matching the interface rather than `100.64.0.0/10` keeps the two rules identical.
- Reject rather than drop, so a blocked worker fails immediately instead of hanging until a timeout.
- Verified assumptions, worth re-checking if pc's network config changes: DNS is the LAN router (`192.168.0.1`), not MagicDNS on `100.100.100.100`, and pc uses no exit node. Either would route the agent's ordinary traffic over `tailscale0` and break it.

**Permission mode**

Workers spawn with `--dangerously-skip-permissions` on this host. The isolation is the boundary, and the permission classifier — which has intermittent availability — stops gating workers nobody is watching. Accepted, named risks: the agent holds a valid OAuth credential for the account; sibling worktrees share its home.

**Skill changes (this repo)**

- `/mx:implement` — the blast-radius rule, applying on every host: everything a worker creates, installs, or modifies lives inside its worktree; a missing system dependency, global tool, or absent service is a **blocker** to report, not a task to solve. The orchestrator routes it to the needs-human queue.
- `/mx:dispatch` — read `HOST.md` from the worker host during setup and report the host's limits alongside the reachability check, so tickets needing a missing capability are planned around instead of discovered by a worker. Update the mx plugin on the worker host **once at setup**, before the first wave: per-worker updates race on the plugin cache, per-wave updates mutate it under running workers that load skills lazily. One version per dispatch run.
- Worker spawn uses the skip-permissions mode above when the host record says the workers are isolated.

**Dotfiles hook**

`git/hooks/mx-plugin-update-pre-push` loses its remote branch — freshness is now pulled by dispatch at setup, not pushed by whoever happens to push. It keeps updating the local machine, and logs the resulting version so "did it land" is a `tail`, not an investigation.

## Acceptance criteria

- [ ] `ssh agent@pc` works from the laptop; that user cannot read `/home/max` or `/home/max/data`, has no `sudo`, and is not in `docker`.
- [ ] `ssh agent@pc tmux new-session -d -s t` works, and the session survives logout (linger).
- [ ] `ssh agent@pc claude --version` and `uv`, `git`, `node`, `gh`, `chromium` all resolve for that user.
- [ ] `claude` is authenticated as the agent user (interactive login, human step).
- [ ] `sudo -u agent ssh <laptop-tailnet-ip>` fails, while an orchestrator ssh session and `git push agent@pc:…` keep working.
- [ ] Rootless docker: `ssh agent@pc docker run --rm hello-world` succeeds, and the container cannot write to `/home/max`.
- [ ] A dispatch run on a repo with one ticket completes end to end on `agent@pc`: bare repo created empty, feature branch pushed, worktree cut, setup target run, worker spawned skip-permissions, ticket branch fetched back and merged.
- [ ] Dispatch's setup output names the host and its limits, sourced from `HOST.md`.
- [ ] `HOST.md` content is generated by the agent's HM config, not hand-written.
- [ ] The pre-push hook no longer touches a remote host, and logs the resulting local version.
- [ ] A worker that hits a missing system dependency reports a blocker instead of installing anything.

## Out of scope

- Interactive browser driving on pc (Chrome extension, hover/drag) — headless only; those tickets stay on the laptop.
- GPU work and training runs — separate instructions per project, not dispatch.
- clankr containers as an alternative isolation mechanism.
- A standalone script to add the clanker account as a `pull` collaborator on a repo — useful for clankr, unnecessary here.

## Comments

### Implementation, 2026-08-25

The host exists and every acceptance criterion above is verified except the
end-to-end dispatch run, which waits on the plugin release that carries these
skill changes to the worker host.

**Decided in session, beyond what this ticket asked for.** Each came out of
working the ticket and was ruled on by max as it came up:

- Workers get their own system prompt (`mx/skills/dispatch/worker-prompt.md`)
  instead of the user CLAUDE.md, which is written for a human at a terminal.
  Delivered on every host by `claudeMdExcludes` plus `--append-system-prompt`,
  so a local worker gets it too. Auto memory off with it.
- `$DISPATCH_WORKLOG`: a per-run line log the worker writes and the
  orchestrator reads when a worker stops early, replacing pane scrollback as
  the source for *why*.
- Worker friction routes to the dispatcher, which fixes it or files it — the
  reading half of a rule whose writing half already existed.
- `/mx:mermaid` calls the validator it ships; `bin/validate-mermaid` is gone.
- Six tools past the list in "What to build" — `curl`, `fd`, `jq`, `rg`,
  `make`, `ast-grep` — because a worker without them reports blockers instead
  of working.
- Host selection by registry rather than `$MX_WORKER_HOST` is filed separately
  as `dispatch-host-registry.md`.

**Assumptions.** Mine, not decisions — reverse them freely:

- A1 `nix/nixos/pc/agent-user.nix:44` — only zephyrus's key is authorized, so
  dispatch from xmg19 falls back to local until its key is added. That host was
  offline throughout.
- A2 `mx/skills/dispatch/SKILL.md:19` — the plugin update and the permission
  mode name `claude` explicitly, in a skill the repo asks to keep
  harness-agnostic. Mechanics already names it throughout; the two setup steps
  now do too.

**Deviations from the ticket, both forced by what the host turned out to be:**

- `virtualisation.docker.rootless.setSocketVariable` is *not* set, though the
  ticket calls for it. Upstream exports `DOCKER_HOST` from `/etc/profile` for
  every user, which would have moved max's docker CLI off the system daemon
  silently. The agent gets it per-user instead, and the rootless daemon is
  pinned to that user with `ConditionUser`.
- The bare repo on the worker host is created empty rather than cloned. A user
  with no GitHub credentials cannot clone a private repo, and shouldn't
  authenticate for a public one.
