---
name: implement
description: Invoke this skill when you're ready to write code — after exploration and planning. Contains a pre-implementation checklist that prevents common mistakes.
---

# Implement

The task file is clear. Intent is understood. Now write code.
[If that's not the case, STOP, clarify with the user, get their explicit approval on the concrete plan before proceeding.]

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
- Push through an implementation even though unexpected issues arose
- Write useless code comments
- Not writing useful code comments

