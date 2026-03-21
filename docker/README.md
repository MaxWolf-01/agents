# docker agents

run claude code in isolated containers. auth from host, repos on host, agents can't touch anything else.

## setup

```bash
git clone https://github.com/MaxWolf-01/agents
cd agents

# create a fine-grained github PAT: contents + pull requests (read/write)
# https://github.com/settings/personal-access-tokens/new
mkdir -p docker/env
echo "GH_TOKEN=github_pat_..." > docker/env/github.env

# make sure claude is logged in on the host
claude login
```

## usage

```bash
# launch agent on a repo (bare profile)
docker/agents launch https://github.com/user/project

# launch with GSD workflow
docker/agents launch -p gsd https://github.com/user/project

# multiple agents on same repo (separate clones)
docker/agents launch -p gsd -s feat1 https://github.com/user/project
docker/agents launch -p gsd -s feat2 https://github.com/user/project

# resume previous session — just relaunch same slot, then /resume inside
docker/agents launch https://github.com/user/project
```

```
$ docker/agents ls
SLOT                           PROFILE  STATUS
hello-world                    gsd      [running]
my-project-feat1               gsd
my-project-feat2               bare

$ docker/agents ps
NAMES               STATUS         CREATED
agent-hello-world   Up 3 minutes   3 minutes ago
```

## commands

```
agents launch, l    launch an agent (see launch --help)
agents ls           list all slots
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
- `--dangerously-skip-permissions` baked into entrypoint
- git identity: `MaxWolf-01-agent`
- github auth via fine-grained PAT (contents + PRs only)
