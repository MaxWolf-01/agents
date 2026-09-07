---
name: session-name
description: Generate a descriptive session name for /rename
user_invocable: true
---

Generate a descriptive name for this session based on what was discussed/accomplished.

Output a `/rename` command the user can run:

```
/rename <descriptive-name>
```

Guidelines:
- Use keywords separated by dashes, lowercase
- Include all major topics; more detail is better for differentiating similar sessions
- If working on a ticket or spec, lead with its name
- Add what was specifically worked on, especially if the work wasn't fully completed
- Examples:
  - `workflow-design-verify-subagent-session-rename-cmd`
  - `memex-search-pagination-bug-fix-tests`
  - `auth-migration-research-jwt-vs-sessions-decision`
  - `deploy-script-docker-compose-env-vars-debugging`
