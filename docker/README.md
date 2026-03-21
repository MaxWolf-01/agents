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
# bare (default) — plain claude code
docker/agents launch https://github.com/user/project

# gsd — structured workflow framework
docker/agents launch -p gsd https://github.com/user/project

# multiple agents on same repo (separate clones)
docker/agents launch -p gsd -s feat1 https://github.com/user/project
docker/agents launch -p gsd -s feat2 https://github.com/user/project

# launch detached (runs in tmux, you can walk away)
docker/agents launch -d -p gsd https://github.com/user/project

# launch detached with a task
docker/agents launch -d -p gsd https://github.com/user/project -- -p '/gsd:execute-phase 1'

# attach to a detached agent
docker/agents attach hello-world  # Ctrl+B D to detach again

# resume previous session — relaunch same slot, then /resume inside
docker/agents launch https://github.com/user/project
```

```
$ docker/agents ls
SLOT                           PROFILE  STATUS
hello-world                    gsd      [detached]
my-project-feat1               gsd      [running]
my-project-feat2               bare

$ docker/agents ps
NAMES               STATUS         CREATED
agent-hello-world   Up 3 minutes   3 minutes ago
```

## commands

```
agents launch, l    launch an agent (-d for detached, -p for profile, -s for slot)
agents attach, a    attach to a detached agent's tmux session
agents ls           list all slots (profile + status)
agents ps           show running containers
agents rm <slot>    remove slot (container + data + repo clone)
agents clean        remove all stopped slots
agents logs <slot>  show container logs
```

## profiles

- `bare` — claude code, skip permissions, no extras
- `gsd` — [get shit done](https://github.com/gsd-build/get-shit-done) workflow framework

add your own: `profiles/<name>/` with `setup`, `CLAUDE.md`, `settings.json`.

## how it works

- each slot gets its own repo clone (`repos/<slot>/`) and claude config (`run/<slot>/.claude/`)
- credentials copied fresh from host `~/.claude/.credentials.json` on each launch
- `-d` wraps the container in a tmux session on the host — survives SSH disconnects
- `--dangerously-skip-permissions` baked into entrypoint
- git identity: `MaxWolf-01-clanker`
- github auth via fine-grained PAT (contents + PRs only)
