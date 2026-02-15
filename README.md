
### [mx](https://github.com/MaxWolf-01/agents/tree/master/mx) — Agent Workflow Plugin

Commands: `/mx:task`, `/mx:transcript`, `/mx:distill`, `/mx:learnings`, `/mx:explain`, `/mx:recap`

Skills: `handoff`, `implement`, `session-name`

Uses [memex CLI](https://github.com/MaxWolf-01/memex) for knowledge base navigation (optional — workflow works without it).

See [mx/README.md](./mx/README.md) for details.

**Installation**

```bash
/plugin marketplace add MaxWolf-01/agents
```

```bash
/plugin install mx@MaxWolf-01
```

**Per-project enable/disable**

```
/plugin disable mx@MaxWolf-01 --scope project
/plugin enable mx@MaxWolf-01 --scope project
```

Or, in project's `.claude/settings.json`:
```json
{
  "enabledPlugins": {
    "mx@MaxWolf-01": true
  }
}
```

### References

Inspiration from: https://github.com/mitsuhiko/agent-stuff
