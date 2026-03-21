# Writing Effective Tools for AI Agents

*Ken Aizawa, Anthropic — Published Sep 11, 2025*

Tools represent "a contract between deterministic systems and non-deterministic agents." Unlike traditional software functions, agents can generate varied responses. This requires rethinking how tools are designed — they must accommodate agent behavior including occasional hallucinations or misuse.

The goal: maximize effectiveness by enabling agents to solve diverse tasks through multiple strategies. "Tools that are most ergonomic for agents also end up being surprisingly intuitive to grasp as humans."

## Building and Evaluating Tools

### Prototyping

Start with quick prototypes. Provide documentation for dependencies (libraries, APIs, SDKs). Connect via local MCP servers or Desktop extensions for testing. Test tools yourself, collect user feedback, identify rough edges before formal evaluation.

### Generating Evaluation Tasks

Create realistic, multi-step evaluation tasks based on actual use cases.

**Strong examples** (natural, ambiguous, multi-step):
- "Schedule a meeting with Jane next week to discuss our latest Acme Corp project. Attach the notes from our last project planning meeting and reserve a conference room."
- "Customer ID 9182 reported they were charged three times for a single purchase. Find all relevant log entries and determine if other customers were affected."

**Weaker examples** (over-specified, single-step):
- "Schedule a meeting with jane@acme.corp next week."
- "Search the payment logs for `purchase_complete` and `customer_id=9182`."

Pair each prompt with verifiable outcomes. Avoid overly strict verifiers that reject correct responses due to formatting differences.

### Running and Analyzing Evaluations

- Include reasoning/feedback blocks in agent system prompts before tool calls to trigger chain-of-thought
- Enable interleaved thinking for visibility
- Collect metrics: accuracy, runtime, tool call count, token consumption, error rates

**Analyzing failures** — read between the lines:
- Redundant calls → pagination or parameter adjustment needs
- Invalid parameter errors → unclear descriptions
- Unusual patterns → consolidation opportunities

### Collaborating with Agents on Tool Design

Concatenate evaluation transcripts and paste them into Claude Code. Claude excels at analyzing transcripts and refactoring multiple tools simultaneously while maintaining self-consistency.

Most advice in this article came from iteratively optimizing internal tools with Claude Code using evaluations mirroring actual workflow complexity. Held-out test sets ensured no overfitting and revealed additional performance gains beyond expert implementations.

## Principles for Effective Tools

### Choosing the Right Tools

More tools don't necessarily improve outcomes. Don't just wrap existing API endpoints without considering agent affordances.

Agents have limited context — they can't efficiently process massive datasets token-by-token. Instead of `list_contacts`, build `search_contacts` or `message_contact`.

**Consolidation examples:**
- Replace `list_users`, `list_events`, `create_event` → `schedule_event` (finds availability and schedules)
- Replace `read_logs` → `search_logs` (returns only relevant lines with context)
- Replace `get_customer_by_id`, `list_transactions`, `list_notes` → `get_customer_context` (comprehensive info)

Each tool should have clear, distinct purpose enabling agents to subdivide tasks naturally while reducing context consumption from intermediate outputs. Too many or overlapping tools distract agents from efficient strategies.

### Namespacing Tools

Organize related tools under common prefixes: `asana_search`, `jira_search`, `asana_projects_search`, `asana_users_search`.

Both prefix and suffix-based approaches show non-trivial effects on evaluations — choose based on your own testing.

### Returning Meaningful Context

Return high-signal information prioritizing contextual relevance over flexibility.

**Avoid:** `uuid`, `256px_image_url`, `mime_type`
**Prefer:** `name`, `image_url`, `file_type`

Agents handle natural language identifiers significantly better than cryptic ones. Converting arbitrary UUIDs to semantically meaningful language or 0-indexed ID schemes "significantly improves Claude's precision in retrieval tasks by reducing hallucinations."

For flexibility, expose a `response_format` enum parameter allowing `"concise"` or `"detailed"` responses. Detailed responses enable downstream tool calls requiring IDs; concise responses conserve tokens (⅓ usage in their Slack example).

Response structure impacts performance — XML, JSON, and Markdown produce different results. Optimize based on your evaluation.

### Optimizing for Token Efficiency

Implement pagination, range selection, filtering, and truncation with sensible defaults. Claude Code restricts responses to 25,000 tokens by default.

When truncating, guide agents toward efficient strategies like targeted searches instead of broad queries.

**Error messages matter:**

```
# Bad
Error: Invalid parameter

# Good
Error: 'user' parameter not found. Did you mean 'user_id'? Example: search_user(user_id=12345)
```

### Prompt-Engineering Tool Descriptions

Tool descriptions loaded into agent context powerfully steer tool-calling behavior. Describe tools as you would to new team members — make implicit context explicit.

- Avoid ambiguity with clear descriptions and strict data models
- Use unambiguous parameter names: `user_id` instead of `user`
- Small refinements yield dramatic improvements — Claude Sonnet 3.5 achieved state-of-the-art SWE-bench Verified performance after precise tool description refinements

## Key Takeaway

Building effective agent tools requires reorienting development from deterministic patterns to non-deterministic ones. Through iterative, evaluation-driven improvement, effective tools consistently emerge: they're intentionally defined, use agent context judiciously, combine flexibly, and intuitively solve real-world tasks.
