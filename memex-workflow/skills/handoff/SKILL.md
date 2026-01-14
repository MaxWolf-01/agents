---
name: handoff
description: This skill should be used when the user asks to "hand off", "create a handoff", "end session", "save progress for later", or when the agent decides to create session continuation for another agent to pick up.
---

# Handoff

Create a detailed handoff summary of the conversation for continuing work in a new session.

A handoff requires a **purpose** — what the next agent should do. If no purpose is clear, ask the user before proceeding.

## Goal

Create a detailed summary capturing technical details, code patterns, and architectural decisions essential for continuing development without losing context.

## Process

The handoff file includes an `<analysis>` section (written to the file, not chat) where you:

1. Chronologically analyze the ENTIRE conversation with proper weight. Don't compress early discussion while elaborating recent work. For each significant section identify:
   - The user's explicit requests and evolving intent
   - How their thinking developed or changed
   - Key decisions and the reasoning behind them
   - Clarifications that refined understanding
   - Technical concepts, code patterns, file changes
2. Capture the WHY behind decisions, not just what was decided.
3. Double-check for technical accuracy and completeness.

## Sections

The handoff should include:

1. **Primary Request and Intent**: All user requests and intents in detail
2. **Key Technical Concepts**: Important technical concepts, technologies, and frameworks discussed
3. **Files and Code Sections**: Specific files examined, modified, or created. Include code snippets where applicable and why each file matters.
4. **Problem Solving**: Problems solved and ongoing troubleshooting efforts
5. **Pending Tasks**: Tasks explicitly requested but not yet done
6. **Current Work**: What was being worked on immediately before this handoff
7. **Next Step**: Required next step, DIRECTLY aligned with the handoff purpose
8. **Sources**: Wiki-links to task files, knowledge files, and relevant external docs

## Naming

Create a descriptive slug using keywords separated by dashes, lowercase. More detail is better.

Good examples:
- `workflow-design-handoff-pickup-commands-wikilinks`
- `gemini-pdf-extraction-prompt-testing-latex-handling`
- `stripe-webhook-eu-withdrawal-edge-cases`

Bad examples (too vague):
- `gemini-integration`
- `stripe-fix`

## Output Structure

```markdown
---
consumed: false
---

# <Readable Summary>

<analysis>
[Thought process, ensuring all points are covered]
</analysis>

<plan>

## 1. Primary Request and Intent
[Detailed description of all user requests and intents]

## 2. Key Technical Concepts
- [Concept 1]
- [Concept 2]

## 3. Files and Code Sections
### [File Name 1]
- **Why important**: [Summary]
- **Changes made**: [Summary]
- **Code snippet**:
```language
[Code]
```

## 4. Problem Solving
[Solved problems and ongoing troubleshooting]

## 5. Pending Tasks
[Tasks requested but not done]

## 6. Current Work
[What was being worked on before handoff]

## 7. Next Step
[Required next step aligned with purpose]

## 8. Sources

**Task/Knowledge:**
- [[task-file-name]] — the task being worked on (can be multiple if session grouped related work)
- [[knowledge-file-name]] — relevant knowledge

**External docs:**
- MUST READ: [Doc title](url) — next agent needs this before working
- Reference: [Doc title](url) — consulted, key finding was X

**Key code files:**
- MUST READ: `path/to/file.py` — why this file matters
- Reference: `path/to/other.py` — related context

Bias toward MUST READ. You have context that shaped your thinking — the next agent doesn't. When in doubt, mark it MUST READ.

</plan>
```

## Final Step

Write the handoff to: `agent/handoffs/YYYY-MM-DD-<slug>.md`

Then tell the user:
```
Handoff written to agent/handoffs/YYYY-MM-DD-<slug>.md

To continue: /mx:task agent/handoffs/YYYY-MM-DD-<slug>.md
```
