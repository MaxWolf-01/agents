# docker agents

run claude code in isolated containers. auth from host, repos on host, agents can't touch anything else.

## setup

```bash
# github PAT (contents + pull requests, read/write)
mkdir -p docker/env
echo "GH_TOKEN=github_pat_..." > docker/env/github.env
```

## usage

```bash
# launch with default (bare) profile
docker/launch https://github.com/user/project

# launch with GSD workflow
docker/launch -p gsd https://github.com/user/project

# named slot (multiple agents on same repo)
docker/launch -p gsd -s feat1 https://github.com/user/project

# pass args to claude
docker/launch -p gsd https://github.com/user/project -- -p "/gsd:new-project"

# resume previous session
docker/launch https://github.com/user/project  # then type /resume inside
```

## profiles

- `bare` — claude code, no extras
- `gsd` — [get shit done](https://github.com/gsd-build/get-shit-done) workflow framework

add your own: create `profiles/<name>/setup` + `profiles/<name>/CLAUDE.md` + `profiles/<name>/settings.json`.

## how it works

- `repos/<slot>/` — host-side clones, one per slot. use `-s` to run multiple agents on the same repo
- `run/<slot>/.claude/` — per-slot claude config (credentials, settings, sessions)
- credentials copied fresh from `~/.claude/.credentials.json` on each launch
- `--dangerously-skip-permissions` baked into entrypoint
- git identity: `MaxWolf-01-agent`
- github auth via fine-grained PAT (scoped to contents + PRs only)
