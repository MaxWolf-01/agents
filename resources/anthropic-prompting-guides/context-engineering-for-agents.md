# Effective Context Engineering for AI Agents

*Anthropic Applied AI team — Published Sep 29, 2025*

## Context Engineering vs. Prompt Engineering

**Prompt engineering** focuses on writing and organizing LLM instructions for optimal single-task outcomes. **Context engineering** encompasses broader strategies for curating and maintaining the optimal token set during inference — system instructions, tools, MCP integrations, external data, and message history.

As agents operate across multiple inference turns with longer time horizons, managing entire context state becomes critical. An agent running in loops generates continuously expanding data that *could* prove relevant — context engineering determines what actually enters the limited context window.

## Why Context Engineering Matters

Research on "needle-in-a-haystack" benchmarking has revealed **context rot**: as token count increases, models lose accuracy recalling information from that context.

LLMs have finite "attention budgets." The transformer architecture enables every token to attend to every other token, creating n² pairwise relationships. Larger context windows stretch attention thin, and models have less training data experience with longer sequences. Performance degrades gradually rather than catastrophically, yet the constraints remain real.

## Anatomy of Effective Context

Optimal context engineering finds "the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome."

### System Prompts

System prompts should be extremely clear and operate at the "right altitude" — specific enough to guide behavior effectively, yet flexible enough to let models apply strong heuristics.

Common failure modes:
- **Brittle extremes:** Hardcoded complex logic creating fragility
- **Vague guidance:** High-level instructions that assume shared context

Organize prompts into distinct sections using XML tagging or Markdown headers (`<background_information>`, `<instructions>`, `## Tool guidance`, `## Output description`). Start with minimal prompts on the best available model, then iteratively add instructions and examples based on observed failures.

### Tools

Tools define the contract between agents and their information/action space. They should be:
- Self-contained with minimal functional overlap
- Robust to errors
- Extremely clear about intended use
- Token-efficient in returned information

Bloated tool sets with ambiguous decision points between tools create failure modes. If engineers cannot definitively identify which tool to use in a scenario, agents cannot perform better.

### Examples

Few-shot prompting remains essential. Rather than listing exhaustive edge cases, curate diverse canonical examples that effectively portray expected agent behavior. "For an LLM, examples are the pictures worth a thousand words."

## Context Retrieval and Agentic Search

Agents are defined simply as "LLMs autonomously using tools in a loop."

### Just-In-Time Context

Rather than pre-processing all data upfront, effective agents maintain lightweight identifiers (file paths, queries, links) and dynamically load data at runtime using tools.

**Claude Code** exemplifies this approach: the model writes targeted queries, stores results, and uses Bash commands like `head` and `tail` to analyze large datasets without loading full objects into context. This mirrors human cognition — we organize information externally (file systems, bookmarks) rather than memorizing entire corpuses.

Metadata from references provides powerful signals. In file systems, folder location and naming conventions hint at purpose. Timestamps suggest relevance. Agents discover context progressively through exploration, maintaining only necessary working memory while leveraging note-taking for additional persistence.

### Trade-offs

Runtime exploration is slower than pre-computed retrieval. Agents require proper guidance — correct tools and heuristics — to avoid wasting context through misuse or dead-end pursuit.

### Hybrid Strategies

The most effective agents employ hybrid approaches: some data pre-loaded for speed, further autonomous exploration at the agent's discretion. Claude Code uses this model — CLAUDE.md files load directly, while glob and grep primitives enable just-in-time retrieval.

As model capabilities improve, "agentic design will trend towards letting intelligent models act intelligently, with progressively less human curation."

## Context Engineering for Long-Horizon Tasks

Long-horizon tasks (tens of minutes to multiple hours) require specialized techniques to maintain coherence across context window limits.

### Compaction

Compaction summarizes conversations nearing context limits and reinitializes with distilled summaries, enabling continuation with minimal degradation.

In Claude Code, message history is summarized to preserve architectural decisions, unresolved bugs, and implementation details while discarding redundant outputs. The agent continues with compressed context plus recently accessed files.

The art involves selecting what to preserve versus discard — aggressive compaction risks losing subtle but critical context. Maximize recall initially, then iterate to improve precision by eliminating superfluous content.

Tool result clearing — removing raw tool outputs deep in message history — represents a lightweight, safe compaction approach.

### Structured Note-Taking

Agents regularly write notes persisted outside the context window, retrieving them later. This provides persistent memory with minimal overhead.

Claude Code creates to-do lists; custom agents maintain NOTES.md files. This pattern enables agents to track progress across complex tasks, maintaining critical context that would otherwise dissipate across dozens of tool calls.

**Claude Playing Pokémon** demonstrates memory's transformative power: the agent maintains precise tallies across thousands of game steps, develops maps of explored regions, remembers achievements, and maintains strategic combat notes — all without explicit memory prompting. After context resets, the agent reads its notes and continues multi-hour sequences. This coherence across summarization enables long-horizon strategies impossible when retaining everything in context alone.

### Sub-Agent Architectures

Rather than one agent maintaining state across entire projects, specialized sub-agents handle focused tasks with clean context windows. Main agents coordinate with high-level plans while sub-agents perform deep technical work, returning only 1,000–2,000 token summaries of extensive exploration (potentially tens of thousands of tokens).

This separates concerns: detailed search context remains isolated within sub-agents while lead agents synthesize and analyze results. The pattern demonstrated substantial improvements over single-agent systems on complex research tasks.

### Choosing Approaches

Selection depends on task characteristics:
- **Compaction:** Maintains conversational flow for extensive back-and-forth
- **Note-taking:** Excels for iterative development with clear milestones
- **Multi-agent architectures:** Handle complex research and analysis benefiting from parallel exploration

## Conclusion

Whether implementing compaction for long-horizon work, designing token-efficient tools, or enabling environmental exploration, the principle remains constant: "find the smallest set of high-signal tokens that maximize the likelihood of your desired outcome."

As models get smarter, they require less prescriptive engineering, enabling greater autonomy. Yet treating context as precious and finite remains central to building reliable, effective agents.
