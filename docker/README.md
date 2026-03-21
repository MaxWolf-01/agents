# docker agents

run claude code in isolated containers. auth from host, repos on host, agents can't touch anything else.

## setup

```bash
git clone https://github.com/MaxWolf-01/agents
cd agents

# create a classic PAT on the MaxWolf-01-clanker github account
# scope: repo (fine-grained PATs don't cover collaborator repos)
# https://github.com/settings/tokens/new
mkdir -p docker/env
echo "GH_TOKEN=ghp_..." > docker/env/github.env

# make sure claude is logged in on the host
claude login

# per repo: add clanker as collaborator + branch protection
# then accept the invitation (log in as clanker)
docker/setup-repo MaxWolf-01/my-project
```

## usage

```bash
# bare (default)
agents launch user/project

# gsd workflow
agents launch -p gsd user/project

# multiple agents on same repo (separate clones)
agents launch -p gsd -s feat1 user/project
agents launch -p gsd -s feat2 user/project

# detached (runs in tmux, walk away)
agents launch -d -p gsd user/project

# detached with a task
agents launch -d -p gsd user/project -- -p '/gsd:execute-phase 1'

# attach to a detached agent (Ctrl+B D to detach)
agents attach hello-world

# local repo
agents launch /path/to/local/repo

# full URL also works
agents launch https://github.com/user/project

# resume previous session — relaunch same slot, /resume inside
agents launch user/project           # default slot
agents launch -s feat1 user/project  # named slot
```

```
$ agents ls
SLOT                 PROFILE  STATUS       REPO
hello-world          gsd      detached     /home/max/.../repos/hello-world
my-project-feat1     gsd      running      /home/max/.../repos/my-project-feat1
my-project-feat2     bare                  /home/max/.../repos/my-project-feat2
```

## commands

```
agents launch, l    launch an agent (-d for detached, -p for profile, -s for slot)
agents attach, a    attach to a detached agent's tmux session
agents ls           list all slots (profile, status, repo path)
agents rm <slot>    remove slot (warns if unpushed work)
agents clean        remove all stopped slots (skips slots with unpushed work)
agents logs <slot>  show container logs
```

## profiles

- `bare` — claude code, skip permissions, no extras
- `gsd` — [get shit done](https://github.com/gsd-build/get-shit-done) workflow framework

each profile is an isolated claude code config — its own system prompt, settings, hooks, and extensions. create `profiles/<name>/` with:
- `CLAUDE.md` — system prompt / agent instructions
- `settings.json` — hooks, statusline, permissions
- `setup` — script that installs extensions (GSD, custom commands, etc.) into the slot's `.claude/` dir

## how it works

- each slot gets its own repo clone (`repos/<slot>/`) and claude config (`run/<slot>/.claude/`)
- credentials copied fresh from host `~/.claude/.credentials.json` on each launch
- `-d` wraps the container in a tmux session on the host — survives SSH disconnects
- `--dangerously-skip-permissions` baked into entrypoint
- git identity: `MaxWolf-01-clanker`
- github auth via fine-grained PAT (contents + PRs only)
