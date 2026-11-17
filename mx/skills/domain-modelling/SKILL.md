---
name: domain-modelling
description: Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a GLOSSARY.md, or recording or editing an ADR.
---

# Domain Modeling

Build and sharpen the project's domain model actively as you design: challenge terms, invent edge-case scenarios, and write terms and decisions down the moment they crystallise.

## File structure

A repo has one context or several; [GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md) gives each layout. With several contexts, work in the one the current topic belongs to; ask when that is unclear.

Create files lazily: `GLOSSARY.md` when the first term is resolved, `decisions/` when the first ADR is needed.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with `GLOSSARY.md`, call it out immediately: "Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?"

### Sharpen fuzzy language

When the user uses a vague or overloaded term, propose a precise canonical one: "You're saying 'account'. Do you mean the Customer or the User?"

### Discuss concrete scenarios

Stress-test domain relationships with invented scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees, and surface a contradiction: "Your code cancels entire Orders, but you just said partial cancellation is possible. Which is right?"

### Update GLOSSARY.md inline

When a term is resolved, update `GLOSSARY.md` right there, in the format of [GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md). An entry is written when `glossary-lint` passes on the file.

`GLOSSARY.md` is a glossary and nothing else: right after a decision settles, the freshly agreed mechanism feels like the definition, so test the entry against the format's **Definitions survive redesign**.

### Offer ADRs sparingly

Offer an ADR only when all three hold:

1. **Hard to reverse**: changing your mind later costs something meaningful
2. **Surprising without context**: a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and you picked one for specific reasons

Use the format in [ADR-FORMAT.md](./ADR-FORMAT.md).
