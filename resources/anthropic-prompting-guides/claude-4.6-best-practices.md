# Claude 4.6 Prompting Best Practices

*Single reference for prompt engineering with Claude Opus 4.6, Sonnet 4.6, and Haiku 4.5.*

## General Principles

### Be clear and direct

Claude responds well to clear, explicit instructions. If you want "above and beyond" behavior, explicitly request it rather than relying on inference from vague prompts.

**Golden rule:** Show your prompt to a colleague with minimal context. If they'd be confused, Claude will be too.

```text
# Less effective
Create an analytics dashboard

# More effective
Create an analytics dashboard. Include as many relevant features and interactions
as possible. Go beyond the basics to create a fully-featured implementation.
```

### Add context to improve performance

Explain *why* behind your instructions. Claude generalizes from the explanation.

```text
# Less effective
NEVER use ellipses

# More effective
Your response will be read aloud by a text-to-speech engine, so never use
ellipses since the text-to-speech engine will not know how to pronounce them.
```

### Use examples effectively

3–5 diverse examples wrapped in `<example>` tags. Make them relevant, diverse (cover edge cases), and structured. You can ask Claude to evaluate or generate more examples from your initial set.

### Structure prompts with XML tags

Use consistent, descriptive tag names (`<instructions>`, `<context>`, `<input>`). Nest for hierarchy. Refer to tags by name ("Using the contract in `<contract>` tags...").

### Give Claude a role

Set role in the system prompt. Even one sentence makes a difference. Put task instructions in the user turn.

### Long context prompting

- **Put longform data at the top** of your prompt, above queries/instructions/examples. Queries at the end can improve response quality by up to 30%.
- **Structure documents with XML**: `<documents><document index="1"><source>...</source><document_content>...</document_content></document></documents>`
- **Ground responses in quotes**: Ask Claude to quote relevant parts before carrying out its task — cuts through noise in long documents.

### Model self-knowledge

```text
The assistant is Claude, created by Anthropic. The current model is Claude Opus 4.6.
```

For API strings: `claude-opus-4-6`

## Output and Formatting

### Communication style

Claude 4.6 models are more concise and direct than previous generations:
- More fact-based, less self-celebratory
- More conversational, less machine-like
- May skip verbal summaries after tool calls

If you want more visibility: `"After completing a task that involves tool use, provide a quick summary of the work you've done."`

### Control format

1. **Tell Claude what to do, not what not to do**: "Write smoothly flowing prose paragraphs" > "Don't use markdown"
2. **Use XML format indicators**: `"Write prose sections in <smoothly_flowing_prose_paragraphs> tags."`
3. **Match prompt style to desired output**: Removing markdown from your prompt reduces markdown in output
4. **Explicit formatting guidance** for detailed control (see full prompt in source doc)

### LaTeX output

Opus 4.6 defaults to LaTeX for math. To override:
```text
Format your response in plain text only. Do not use LaTeX, MathJax, or any
markup notation. Write all math expressions using standard text characters.
```

### Migrating away from prefilled responses

**Prefills on the last assistant turn are no longer supported in Claude 4.6.** Migration paths:

- **Output formatting**: Use Structured Outputs or direct instructions
- **Eliminating preambles**: `"Respond directly without preamble."` or output within XML tags
- **Avoiding refusals**: Claude is much better at appropriate refusals now — clear prompting suffices
- **Continuations**: Move to user message: `"Your previous response was interrupted and ended with [text]. Continue from where you left off."`
- **Context hydration**: Inject reminders into user turns, or hydrate via tools during compaction

## Tool Use

### Explicit action instructions

Claude 4.6 follows instructions precisely. "Can you suggest some changes?" → Claude suggests. "Make these changes" → Claude acts.

For proactive action by default:
```xml
<default_to_action>
By default, implement changes rather than only suggesting them. If the user's
intent is unclear, infer the most useful likely action and proceed, using tools
to discover any missing details instead of guessing.
</default_to_action>
```

For conservative behavior:
```xml
<do_not_act_before_instructions>
Do not jump into implementation unless clearly instructed. Default to providing
information, research, and recommendations rather than taking action.
</do_not_act_before_instructions>
```

### Overtriggering tools

Opus 4.5 and Opus 4.6 are more responsive to system prompts. Prompts designed to reduce undertriggering on older models may now overtrigger. **Dial back aggressive language.** `"CRITICAL: You MUST use this tool when..."` → `"Use this tool when..."`

### Parallel tool calling

Claude 4.6 excels at parallel execution — multiple searches, file reads, bash commands simultaneously. Boost to ~100% with:

```xml
<use_parallel_tool_calls>
If you intend to call multiple tools and there are no dependencies between them,
make all independent calls in parallel. Never use placeholders or guess missing
parameters in tool calls.
</use_parallel_tool_calls>
```

## Thinking and Reasoning

### Adaptive thinking (new in 4.6)

Replaces manual `budget_tokens` extended thinking:

```python
client.messages.create(
    model="claude-opus-4-6",
    max_tokens=64000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},  # or max, medium, low
    messages=[{"role": "user", "content": "..."}],
)
```

Claude dynamically decides when and how much to think based on `effort` and query complexity. In internal evaluations, adaptive thinking reliably drives better performance than extended thinking.

### Overthinking and excessive thoroughness

Opus 4.6 does significantly more upfront exploration than previous models — this often helps but can be excessive.

- **Replace blanket defaults with targeted instructions**: `"Default to using [tool]"` → `"Use [tool] when it would enhance your understanding"`
- **Remove over-prompting**: Tools that undertriggered before now trigger appropriately. `"If in doubt, use [tool]"` → overtriggering
- **Use effort as a fallback**: Lower effort setting if model remains too aggressive

Constrain reasoning:
```text
When deciding how to approach a problem, choose an approach and commit to it.
Avoid revisiting decisions unless you encounter new information that directly
contradicts your reasoning.
```

### Thinking tips

- **Prefer general instructions over prescriptive steps**: "Think thoroughly" often produces better reasoning than hand-written step-by-step plans
- **Multishot examples work with thinking**: Use `<thinking>` tags in few-shot examples
- **Ask Claude to self-check**: "Before you finish, verify your answer against [test criteria]"

**Note**: When extended thinking is disabled, Opus 4.5 is sensitive to the word "think" — consider alternatives like "consider", "evaluate", "reason through".

## Agentic Systems

### Long-horizon reasoning and state tracking

Claude 4.6 excels at long-horizon tasks with exceptional state tracking. It maintains orientation by focusing on incremental progress — a few things at a time rather than attempting everything at once.

#### Context awareness

Claude 4.6 tracks its remaining context window. If using a harness with compaction:

```text
Your context window will be automatically compacted as it approaches its limit,
allowing you to continue working indefinitely. Do not stop tasks early due to
token budget concerns. Save progress and state to memory before context refreshes.
```

#### Multi-context window workflows

1. **First window = setup**: Write tests, create setup scripts. Future windows iterate on a todo-list
2. **Structured test tracking**: `tests.json` format. Remind: "It is unacceptable to remove or edit tests"
3. **Quality-of-life scripts**: `init.sh` to start servers, run suites, linters — prevents repeated work
4. **Starting fresh vs compacting**: Claude 4.6 is extremely effective at discovering state from the filesystem. Sometimes a fresh context + filesystem discovery beats compaction
5. **Verification tools**: Playwright MCP, computer use for UI testing
6. **Encourage complete usage**: `"Plan your work clearly. Spend your entire output context working on the task."`

#### State management

- **Structured formats (JSON)** for state data (test results, task status)
- **Unstructured text** for progress notes
- **Git** for state tracking and checkpoints — Claude 4.6 performs especially well with git
- **Emphasize incremental progress** explicitly

### Balancing autonomy and safety

Without guidance, Opus 4.6 may take hard-to-reverse actions (deleting files, force-pushing, posting to external services).

```text
Consider the reversibility and potential impact of your actions. Take local,
reversible actions freely, but for actions that are hard to reverse, affect
shared systems, or could be destructive, ask the user before proceeding.

When encountering obstacles, do not use destructive actions as a shortcut.
Don't bypass safety checks (e.g. --no-verify) or discard unfamiliar files
that may be in-progress work.
```

### Research and information gathering

Claude 4.6 has exceptional agentic search capabilities. For complex research:

```text
Search for this information in a structured way. Develop competing hypotheses.
Track confidence levels in progress notes. Regularly self-critique your approach.
Update a hypothesis tree or research notes file. Break down complex research
tasks systematically.
```

### Subagent orchestration

Claude 4.6 has significantly improved native subagent orchestration — it proactively delegates when beneficial. **Watch for overuse** — Opus 4.6 has a strong predilection for subagents and may spawn them when a direct grep would suffice.

```text
Use subagents when tasks can run in parallel, require isolated context, or involve
independent workstreams. For simple tasks, sequential operations, single-file edits,
or tasks where you need to maintain context across steps, work directly.
```

### Overeagerness

Opus 4.5 and 4.6 tend to overengineer — extra files, unnecessary abstractions, flexibility that wasn't requested:

```text
Avoid over-engineering. Only make changes that are directly requested or clearly
necessary. Keep solutions simple and focused:
- Don't add features, refactor code, or make "improvements" beyond what was asked
- Don't add docstrings, comments, or type annotations to code you didn't change
- Don't add error handling for scenarios that can't happen
- Don't create helpers or abstractions for one-time operations
```

### Minimizing hallucinations

```xml
<investigate_before_answering>
Never speculate about code you have not opened. If the user references a specific
file, you MUST read it before answering. Investigate and read relevant files BEFORE
answering questions about the codebase.
</investigate_before_answering>
```

### Avoid test-gaming and hard-coding

```text
Write a high-quality, general-purpose solution using standard tools. Do not create
helper scripts or workarounds. Implement the actual logic that solves the problem
generally, not just for test cases. If tests are incorrect, tell me rather than
working around them.
```

## Capability-Specific Tips

### Vision

Improved in Opus 4.5/4.6, especially with multiple images. Give Claude a crop tool — consistent uplift when it can "zoom" into relevant image regions.

### Frontend design

Without guidance, models default to "AI slop" aesthetics. Key areas to steer:
- **Typography**: Avoid generic fonts (Arial, Inter). Choose distinctive, beautiful fonts
- **Color**: Commit to a cohesive aesthetic. Dominant colors with sharp accents > timid, evenly-distributed palettes
- **Motion**: Focus on high-impact moments — one well-orchestrated page load > scattered micro-interactions
- **Backgrounds**: Create atmosphere and depth, not solid colors

## Migration Considerations

### From earlier Claude models to 4.6

1. Be specific about desired behavior
2. Use modifiers: "Go beyond the basics to create a fully-featured implementation"
3. Request animations and interactive elements explicitly
4. Update to adaptive thinking (`thinking: {type: "adaptive"}`)
5. Migrate away from prefilled responses (deprecated)
6. **Tune anti-laziness prompting down** — Claude 4.6 is more proactive and may overtrigger

### From Sonnet 4.5 to Sonnet 4.6

Default effort is `high` (Sonnet 4.5 had no effort parameter). Adjust to avoid higher latency:
- **Medium** for most applications
- **Low** for high-volume/latency-sensitive workloads
- Set 64k max output tokens at medium/high effort

Without extended thinking: set effort explicitly. At `low` effort with thinking disabled, expect similar or better performance vs Sonnet 4.5.

With extended thinking: keep ~16k budget_tokens. For coding: start at `medium` effort. For chat: start at `low` effort.

**When to try adaptive thinking**: autonomous multi-step agents, computer use agents, bimodal workloads (mix of easy/hard). Start at `high` effort, scale down if needed.
