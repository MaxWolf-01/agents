---
name: implement
description: This skill should be used when moving from planning to coding, when the user says "implement", "code this", "build it", or when the task file is clear and it's time to execute. Provides the mindset and practices for writing code.
---

# Implement

The task file is clear. Intent is understood. Now write code.

Planning mode explores possibilities. Implementation mode commits to one, but escalates issues discovered during coding to the user before resorting to hacks, "quick fixes", breaking assumptions, or deviating from intent.

## Before Writing Code

State assumptions explicitly:
- What is assumed about the input?
- What is assumed about the environment?
- What would break this?
- What would a malicious caller do?
- What would a tired maintainer misunderstand?

Bound the scope:
- This handles X
- This does NOT handle Y
- Outside these conditions, behavior is undefined

## What NOT To Do

- Write code before stating assumptions
- Claim correctness not verified
- Handle only the happy path
- Import complexity not needed
- Solve problems not asked to solve
- Produce code you wouldn't want to debug at 3am
- Create abstractions for one-time operations
- Design for hypothetical future requirements

