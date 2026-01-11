
### [Memex Workflow Plugin](https://github.com/MaxWolf-01/agents/tree/main/memex-workflow)     

Commands: `/mx:task`, `/mx:handoff`, `/mx:pickup`, `/mx:distill`, `/mx:learnings`, `/mx:align`, `/mx:explain`

Uses [memex MCP](https://github.com/MaxWolf-01/memex) for knowledge base navigation.

See [memex-workflow/README.md](./memex-workflow/README.md) for details.

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

**Tip:** I recommend turning of auto-compaction when using ths workflow (saves soo much context; and is replaced by a better `/handoff` anyways).


### References

A few things are yoinked and adapted from: https://github.com/mitsuhiko/agent-stuff

