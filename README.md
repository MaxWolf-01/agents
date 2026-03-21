
### [mx](https://github.com/MaxWolf-01/agents/tree/master/mx) — Agent Workflow Plugin

Markdown-based issue tracking, research artefacts, knowledge persistence, and session continuity for multi-session agent work. Uses [memex CLI](https://github.com/MaxWolf-01/memex) for wikilink + semantic knowledge base navigation.

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

### [clankr](https://github.com/MaxWolf-01/clankr) — Sandboxed Agent Fleet

Run coding agents in isolated Docker containers. `uvx clankr` — see [clankr repo](https://github.com/MaxWolf-01/clankr).

### References

Inspiration from: https://github.com/mitsuhiko/agent-stuff
