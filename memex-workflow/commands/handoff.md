---
description: Create session continuation summary for another agent
argument-hint: [purpose]
---

Creates a detailed handoff plan of the conversation for continuing the work in a new session.

The user specified purpose:

<purpose>$ARGUMENTS</purpose>

You are creating a summary specifically so that it can be continued by another agent. For this to work you MUST have a purpose. If no specified purpose was provided in the `<purpose>...</purpose>` tag you must STOP IMMEDIATELY and ask the user what the purpose is.

Do not continue before asking for the purpose as you will otherwise not understand the instructions and do not assume a purpose!

## Goal

Your task is to create a detailed summary of the conversation so far, paying close attention to the user's explicit purpose for the next steps.
This handoff plan should be thorough in capturing technical details, code patterns, and architectural decisions that will be essential for continuing development work without losing context.

## Process

Before providing your final plan, wrap your analysis in <analysis> tags to organize your thoughts and ensure you've covered all necessary points. In your analysis process:

1. Chronologically analyze the ENTIRE conversation with proper weight. Don't compress early discussion into one sentence while elaborating recent work. For each significant section identify:
   - The user's explicit requests and evolving intent
   - How their thinking developed or changed
   - Key decisions and the reasoning behind them
   - Clarifications that refined understanding
   - Technical concepts, code patterns, file changes
2. Capture the WHY behind decisions, not just what was decided.
3. Double-check for technical accuracy and completeness.

Your plan should include the following sections:

1. **Primary Request and Intent**: Capture all of the user's explicit requests and intents in detail
2. **Key Technical Concepts**: List all important technical concepts, technologies, and frameworks discussed.
3. **Files and Code Sections**: Enumerate specific files and code sections examined, modified, or created. Pay special attention to the most recent messages and include full code snippets where applicable and include a summary of why this file read or edit is important.
4. **Problem Solving**: Document problems solved and any ongoing troubleshooting efforts.
5. **Pending Tasks**: Outline any pending tasks that you have explicitly been asked to work on.
6. **Current Work**: Describe in detail precisely what was being worked on immediately before this handoff request, paying special attention to the most recent messages from both user and assistant. Include file names and code snippets where applicable.
7. **Next Step**: The required next step to take, DIRECTLY aligned with the user's explicit handoff purpose. If your last task was concluded, only list next steps if they are explicitly in line with the user's request. Do not start on tangential requests without confirming with the user first.
8. **Related Context**: Wiki-links to task files, knowledge files, and relevant external docs.

## Naming

Create a descriptive slug for this handoff. Use keywords separated by dashes, lowercase. More detail is better for differentiating similar sessions.

Good examples:
- `workflow-design-handoff-pickup-commands-wikilinks`
- `gemini-pdf-extraction-prompt-testing-latex-handling`
- `stripe-webhook-eu-withdrawal-edge-cases`
- `mobile-playback-reconnect-safari-audio-context-fix`

Bad examples (too vague):
- `gemini-integration`
- `stripe-fix`
- `mobile-bug`

## Output Structure

```markdown
---
consumed: false
---

# <Readable Summary>

<analysis>
[Your thought process, ensuring all points are covered thoroughly and accurately]
</analysis>

<plan>

## 1. Primary Request and Intent
[Detailed description of all user requests and intents]

## 2. Key Technical Concepts
- [Concept 1]
- [Concept 2]
- [...]

## 3. Files and Code Sections
### [File Name 1]
- **Why important**: [Summary of why this file is important]
- **Changes made**: [Summary of the changes made to this file, if any]
- **Code snippet**:
```language
[Important Code Snippet]
```

### [File Name 2]
...

## 4. Problem Solving
[Description of solved problems and ongoing troubleshooting]

## 5. Pending Tasks
[Tasks explicitly asked for but not yet done]

## 6. Current Work
[What was being worked on immediately before this handoff]

## 7. Next Step
[Required next step to take, directly aligned with user's explicit handoff purpose]

## 8. Sources

**Task/Knowledge:**
- [[task-file-name]] — the task being worked on (in rare cases multiple)
- [[knowledge-file-name]] — relevant knowledge

**External docs:**
- MUST READ: [Doc title](url) — next agent needs this to continue
- Reference: [Doc title](url) — consulted, key finding was X

</plan>
```

## Final Step

Write the handoff to: `agent/handoffs/YYYY-MM-DD-<slug>.md`

Use today's date and the slug you created.

Then tell the user:
```
Handoff written to agent/handoffs/YYYY-MM-DD-<slug>.md

To continue: /pickup <slug>
```
