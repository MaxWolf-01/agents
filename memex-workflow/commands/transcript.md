---
description: Save session transcript for later continuation
argument-hint: <session-id>
allowed-tools: Bash(ccx:*), Skill(*)
---

Save the current session's transcript to `agent/transcripts/` for later pickup.

Session ID: `$1`

## Process

1. **Determine session name:**
   - If you already generated a session name earlier this session, use it.
   - Otherwise, invoke `/mx:session-name` to LEARN how to generate a good session name.
   - **Continue immediately to step 2** after getting the name — don't wait for user input.

2. **Save transcript:**
```bash
ccx <session-id> agent/transcripts/$(date +%Y-%m-%d)-<slug>.txt
```
Assume the directory `agent/transcripts/` already exists. Do NOT preemtively use `mkdir -p`.

3. **Report** the session name and the path so user can use it for pickup:
```
/rename <slug>
/mx:task agent/transcripts/<filename>.txt
```

