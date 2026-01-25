
### [Memex Workflow](https://github.com/MaxWolf-01/agents/tree/master/memex-workflow) Plugin

Commands: `/mx:task`, `/mx:transcript`, `/mx:distill`, `/mx:learnings`, `/mx:align`, `/mx:explain`, `/mx:recap`

Skills: `handoff`, `pickup`, `implement`, `session-name`

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

**Rule file (recommended)**

The plugin includes `memex-workflow/rules/memex.md` with basic workflow context. Symlink it globally:

```bash
mkdir -p ~/.claude/rules
ln -s /path/to/agents/memex-workflow/rules/memex.md ~/.claude/rules/memex.md
```

**Per-project MCP config (optional)**

The workflow works without memex MCP — you just lose wikilink navigation (`explore`, `search`, `rename`) and optional semantic search.
```json
{
  "mcpServers": {
    "memex": {
      "command": "uvx",
      "args": ["memex-md-mcp@latest"],
      "env": { "MEMEX_VAULTS": "./agent" }
    }
  }
}
```

### References

Inspiration from: https://github.com/mitsuhiko/agent-stuff

