---
description: Save session transcript for later continuation
allowed-tools: Bash(ccx:*), Skill(*)
---

Save the current session's transcript to `agent/transcripts/` for later pickup.

Session ID: `${CLAUDE_SESSION_ID}`

## Process

1. **Determine session name** (lowercase keywords separated by dashes):
   - If you already generated a session name earlier this session, reuse it.
   - Otherwise, generate one covering all major topics. More detail is better for differentiating sessions. If working on a task, lead with the task name.
   - Examples: `auth-migration-research-jwt-vs-sessions`, `deploy-script-docker-compose-env-vars-debugging`

2. **Save transcript:**
```bash
ccx ${CLAUDE_SESSION_ID} agent/transcripts/$(date +%Y-%m-%d)-<slug>.txt
```
Assume the directory `agent/transcripts/` already exists. Do NOT preemtively use `mkdir -p`.

3. **Report** the session name and the path so user can use it for pickup:
```
/rename <slug>
/mx:task agent/transcripts/<filename>.txt
```

