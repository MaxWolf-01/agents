# ADR Format

ADRs live in `decisions/` (in a repo of several contexts, one beside each context's glossary, as [GLOSSARY-FORMAT.md](GLOSSARY-FORMAT.md) lays out) and use sequential numbering: `0001-slug.md`, `0002-slug.md`, etc.

## Template

```md
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

An ADR can be a single paragraph: its value is in recording *that* a decision was made and *why*, not in filling out sections.

## Optional sections

Most ADRs won't need them.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`): useful when decisions are revisited
- **Considered Options**: only when the rejected alternatives are worth remembering
- **Consequences**: only when non-obvious downstream effects need to be called out

## Numbering

The next number is the highest in `decisions/` plus one.
