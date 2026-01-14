
### [Memex Workflow](https://github.com/MaxWolf-01/agents/tree/master/memex-workflow) Plugin

Commands: `/mx:task`, `/mx:distill`, `/mx:learnings`, `/mx:align`, `/mx:explain`, `/mx:recap`, `/mx:session-name`

Skills: `handoff`, `pickup`, `implement`

Uses [memex MCP](https://github.com/MaxWolf-01/memex) for knowledge base navigation.

See [memex-workflow/README.md](./memex-workflow/README.md) for details.
Note: This let's you turn off the 40%?! auto-compaction buffer since it's handled by `handoff` + `pickup` which works much, much, much better from many perspectives in my experience.

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

