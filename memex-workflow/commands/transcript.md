---
description: Save session transcript for later continuation
argument-hint: <session-id>
allowed-tools: Bash(ccx:*), Bash(mkdir:*), Skill(*)
---

Save the current session's transcript to `agent/transcripts/` for later pickup.

Session ID: `$1`

## Process

1. **Ensure directory exists:**
```bash
mkdir -p agent/transcripts
```

2. **Determine session name:**
   - If you already generated a session name earlier this session, use it
   - Otherwise, invoke `/mx:session-name` to generate one

3. **Save transcript:**
```bash
ccx <session-id> agent/transcripts/$(date +%Y-%m-%d)-<slug>.txt
```

4. **Report** the path so user can use it for pickup:
```
/mx:task agent/transcripts/<filename>.txt
```
