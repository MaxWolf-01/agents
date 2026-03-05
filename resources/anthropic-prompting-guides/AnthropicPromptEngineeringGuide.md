# Comprehensive Prompt Engineering Guide for LLMs

*A complete guide extracted from Anthropic's Interactive Prompt Engineering Tutorial*

## Table of Contents

- [Introduction](#introduction)
- [Beginner Level](#beginner-level)
  - [Chapter 1: Basic Prompt Structure](#chapter-1-basic-prompt-structure)
  - [Chapter 2: Being Clear and Direct](#chapter-2-being-clear-and-direct)
  - [Chapter 3: Assigning Roles (Role Prompting)](#chapter-3-assigning-roles-role-prompting)
- [Intermediate Level](#intermediate-level)
  - [Chapter 4: Separating Data from Instructions](#chapter-4-separating-data-from-instructions)
  - [Chapter 5: Formatting Output & Speaking for Claude](#chapter-5-formatting-output--speaking-for-claude)
  - [Chapter 6: Precognition (Thinking Step by Step)](#chapter-6-precognition-thinking-step-by-step)
  - [Chapter 7: Using Examples (Few-Shot Prompting)](#chapter-7-using-examples-few-shot-prompting)
- [Advanced Level](#advanced-level)
  - [Chapter 8: Avoiding Hallucinations](#chapter-8-avoiding-hallucinations)
  - [Chapter 9: Building Complex Prompts](#chapter-9-building-complex-prompts)
- [Appendix: Beyond Standard Prompting](#appendix-beyond-standard-prompting)
  - [Appendix 10.1: Chaining Prompts](#appendix-101-chaining-prompts)
  - [Appendix 10.2: Tool Use](#appendix-102-tool-use)
  - [Appendix 10.3: Search & Retrieval](#appendix-103-search--retrieval)

---

## Introduction

This guide compiles all the prompt engineering lessons from Anthropic's interactive tutorial. It's designed to help LLMs and humans understand the best practices for creating effective prompts. Each chapter builds upon the previous ones, progressing from basic concepts to advanced techniques.

---

## Beginner Level

### Chapter 1: Basic Prompt Structure

#### Key Concepts

**Messages API Structure**: The Messages API requires specific parameters:
- `model`: The API model name to use
- `max_tokens`: Maximum number of tokens to generate (hard stop)
- `messages`: Array of input messages with alternating `user` and `assistant` roles

**Message Format Rules**:
- Messages MUST start with a `user` role
- `user` and `assistant` messages MUST alternate
- Each message needs a `role` and `content`

**System Prompts**: 
- Provide context, instructions, and guidelines before the main task
- Exist separately from the messages array in a `system` parameter
- Can improve Claude's performance and ability to follow rules

#### Examples

Basic prompt:
```python
messages = [
  {"role": "user", "content": "Hi Claude, how are you?"}
]
```

System prompt example:
```python
system_prompt = "Your answer should always be a series of critical thinking questions that further the conversation (do not provide answers to your questions). Do not actually answer the user question."
prompt = "Why is the sky blue?"
```

#### Common Errors
- Missing role/content fields → API error
- Non-alternating user/assistant messages → API error
- Starting with assistant role → API error

#### Exercise Hints
- Exercise 1.1 (Counting to Three): Ask Claude directly to count to three
- Exercise 1.2 (System Prompt): Tell Claude to act like a 3-year-old child in the system prompt

---

### Chapter 2: Being Clear and Direct

#### Key Concepts

**Claude responds best to clear and direct instructions**. Think of Claude like a new employee who has no context beyond what you literally tell them.

**Golden Rule of Clear Prompting**: Show your prompt to a colleague and have them follow the instructions. If they're confused, Claude will be confused.

#### Techniques

1. **Be explicit about what you want**:
   - Want no preamble? Say "Skip the preamble"
   - Want a specific format? Describe it exactly
   - Want Claude to make a definitive choice? Tell it to pick one

2. **Small details matter**:
   - Fix typos and grammatical errors
   - Claude is sensitive to patterns
   - Claude is more likely to make mistakes when you make mistakes

#### Examples

Getting straight to the point:
```
Prompt: "Write a haiku about robots. Skip the preamble; go straight into the poem."
```

Forcing a definitive answer:
```
Prompt: "Who is the best basketball player of all time? Yes, there are differing opinions, but if you absolutely had to pick one player, who would it be?"
```

#### Exercise Hints
- Exercise 2.1 (Spanish): Simply ask Claude to respond in Spanish
- Exercise 2.2 (One Player Only): Tell Claude to respond with ONLY the name, no other words
- Exercise 2.3 (Write a Story): Ask for a very long story and specify word count (aim for >1000 words since LLMs aren't great at counting)

---

### Chapter 3: Assigning Roles (Role Prompting)

#### Key Concepts

**Role prompting** means giving Claude a specific role with all necessary context. This can improve Claude's performance in various fields and change the style, tone, and accuracy of responses.

**Benefits**:
- Improves performance in specialized domains
- Changes response style and tone
- Can make Claude better at math and logic tasks
- Works like telling a human to "think like a [role]"

**Note**: Role prompting can happen in either the system prompt or user message.

#### Examples

Basic role prompting:
```
System: "You are a cat."
User: "What do you think about skateboarding?"
```

Role prompting for improved accuracy:
```
System: "You are a logic bot designed to answer complex logic problems."
User: [Complex logic puzzle]
```

#### Key Insight
There are many prompt engineering techniques to achieve similar results. Experiment to find your own style!

#### Exercise Hints
- Exercise 3.1 (Math Correction): Give Claude a role that would be good at math (e.g., math teacher, mathematician)

---

## Intermediate Level

### Chapter 4: Separating Data from Instructions

#### Key Concepts

**Prompt templates** allow you to create reusable prompts with variable substitution. This is crucial when you want Claude to perform the same task with different data.

**XML tags** are the recommended way to separate data from instructions:
- Use tags like `<email></email>` or `<document></document>`
- Claude was specifically trained to recognize XML tags
- Prevents Claude from confusing data with instructions
- No "special sauce" tags - use whatever makes sense

#### Common Issues and Solutions

Problem: Claude confuses where data ends and instructions begin
```python
# Bad - unclear boundaries
prompt = f"Yo Claude. {EMAIL} <----- Make this email more polite"

# Good - clear XML boundaries  
prompt = f"Yo Claude. <email>{EMAIL}</email> <----- Make this email more polite"
```

Problem: Misleading formatting in data
```python
# Bad - hyphen makes Claude think the instruction is part of the list
prompt = f"""Tell me the second item:
- Each is about an animal
{SENTENCES}"""

# Good - XML tags clarify boundaries
prompt = f"""Tell me the second item:
- Each is about an animal
<sentences>
{SENTENCES}
</sentences>"""
```

#### Best Practices
- Always use XML tags for variable data
- Scrub prompts for typos and errors
- Test with different inputs to ensure robustness

#### Exercise Hints
- Exercise 4.1 (Haiku Topic): Use f-string with `{TOPIC}` variable
- Exercise 4.2 (Dog Question): Wrap the question in XML tags like `<question>{QUESTION}</question>`
- Exercise 4.3 (Dog Question Part 2): Remove gibberish words like "jkaerjv" and "jklmvca"

---

### Chapter 5: Formatting Output & Speaking for Claude

#### Key Concepts

**Output formatting** - Claude can format its output in many ways:
- XML tags for structured output
- JSON for data interchange
- Custom formats as specified

**Speaking for Claude** (Prefilling):
- Start Claude's response by putting text in the `assistant` role
- Claude will continue from where you left off
- Useful for enforcing format compliance
- Can use opening XML tag or JSON bracket to guide format

#### Examples

XML output formatting:
```python
prompt = "Please write a haiku about cats. Put it in <haiku> tags."
# Claude outputs: <haiku>[poem here]</haiku>
```

Prefilling for format enforcement:
```python
prompt = "Please write a haiku about cats. Put it in <haiku> tags."
prefill = "<haiku>"
# Claude continues from <haiku> and completes the tag
```

JSON formatting with prefill:
```python
prompt = 'Write a haiku about cats. Use JSON format with keys "first_line", "second_line", "third_line".'
prefill = "{"
# Claude completes the JSON object
```

#### Advanced Tip
Use `stop_sequences` parameter with closing XML tags to save tokens and time by stopping generation after your desired content.

#### Exercise Hints
- Exercise 5.1 (Steph Curry): Prefill with text praising Stephen Curry
- Exercise 5.2 (Two Haikus): Ask for two haikus instead of one
- Exercise 5.3 (Two Animals): Use two variables `{ANIMAL1}` and `{ANIMAL2}` in the prompt

---

### Chapter 6: Precognition (Thinking Step by Step)

#### Key Concepts

**Giving Claude time to think step-by-step makes it more accurate**, especially for complex tasks. However, thinking only works when it's "out loud" in the output.

**Implementation**:
- Explicitly ask Claude to think through the problem
- Use XML tags like `<thinking>` or `<brainstorm>`
- Must output the reasoning, not just think internally

**Ordering sensitivity**: Claude can be sensitive to the order of options presented. It often favors the second of two options.

#### Examples

Improving sentiment analysis:
```python
# Without thinking - Claude misses nuance
prompt = "Is this review positive or negative? [review text]"

# With thinking - Claude catches subtleties
prompt = """Is this review sentiment positive or negative? 
First, write the best arguments for each side in <positive-argument> and <negative-argument> XML tags, then answer."""
```

Fixing errors through thinking:
```python
prompt = """Name a famous movie starring an actor born in 1956.
First brainstorm about actors and their birth years in <brainstorm> tags, then give your answer."""
```

#### Best Practices
- Place thinking instructions after the main question
- Be specific about what to think about
- Use structured tags for different reasoning steps

#### Exercise Hints
- Exercise 6.1 (Email Classification): Include the categories in the prompt, tell Claude to output only the classification, use prefilling
- Exercise 6.2 (Email Formatting): Ask Claude to wrap just the letter in `<answer>` tags

---

### Chapter 7: Using Examples (Few-Shot Prompting)

#### Key Concepts

**Giving Claude examples is extremely effective** for:
- Getting the right answer
- Getting the answer in the right format
- Showing edge cases
- Demonstrating tone and style

**Terminology**:
- Zero-shot: No examples
- One-shot: One example
- Few-shot: Multiple examples
- Generally, more examples = better performance

#### Best Practices

1. **Wrap examples in XML tags**: Use `<example>` tags
2. **Make examples diverse**: Cover different cases
3. **Match desired format exactly**: Examples should look exactly like desired output
4. **Include edge cases**: Show Claude how to handle tricky situations

#### Example Structure

```python
prompt = """Please complete the conversation by writing the next line, speaking as "A".

<example>
Q: Is the tooth fairy real?
A: Of course, sweetie. Wrap up your tooth and put it under your pillow tonight.
</example>

Q: Will Santa bring me presents on Christmas?"""
```

#### Power of Examples
Examples can be more effective than lengthy explanations. Instead of describing tone, format, and style, just show Claude what you want.

#### Exercise Hints
- Exercise 7.1 (Email Examples): Create examples for different categories showing exact format wanted

---

## Advanced Level

### Chapter 8: Avoiding Hallucinations

#### Key Concepts

Claude sometimes makes claims that are untrue or unjustified. Techniques to minimize hallucinations:

1. **Give Claude an out**: Tell Claude it's okay to say "I don't know"
2. **Ask for evidence first**: Make Claude find quotes/evidence before answering
3. **Use lower temperature**: Reduces creativity but increases consistency

#### Techniques in Detail

**Giving Claude an Out**:
```python
# Bad - Claude tries too hard to be helpful
prompt = "Who is the heaviest hippo of all time?"

# Good - Claude can decline if uncertain
prompt = "Who is the heaviest hippo of all time? Only answer if you know the answer with certainty."
```

**Evidence-First Approach**:
```python
prompt = """<question>What was Matterport's subscriber base on May 31, 2020?</question>
Please read the below document. Then, in <scratchpad> tags, pull the most relevant quote 
and consider whether it answers the question. Then write your answer in <answer> tags.

<document>[document text]</document>"""
```

#### Temperature Settings
- Temperature 0: Most consistent, nearly deterministic
- Temperature 1: Most creative, more variable
- Lower temperature generally reduces hallucinations

#### Exercise Hints
- Exercise 8.1 (Beyoncé): Add "only answer if you're certain" or similar
- Exercise 8.2 (Prospectus): Ask Claude to find and cite specific quotes first

---

### Chapter 9: Building Complex Prompts

#### Key Concepts

Complex prompts combine multiple techniques for sophisticated tasks. Not all prompts need every element - start with many elements, then refine and slim down.

#### Recommended Structure (in order)

1. **Task Context**: Role and goals
2. **Tone Context**: How Claude should communicate
3. **Detailed Task Description**: Specific tasks and rules
4. **Examples**: Ideal responses to emulate
5. **Input Data**: Information to process
6. **Immediate Task**: What to do right now
7. **Precognition**: Think step-by-step instruction
8. **Output Formatting**: How to structure the response
9. **Prefilling**: Starting Claude's response

#### Complex Prompt Template

```python
# 1. Task Context
TASK_CONTEXT = "You will be acting as an AI career coach named Joe..."

# 2. Tone Context  
TONE_CONTEXT = "You should maintain a friendly customer service tone."

# 3. Task Description & Rules
TASK_DESCRIPTION = """Here are important rules:
- Always stay in character
- If unsure, say "Sorry, I didn't understand..."
- If irrelevant, redirect to career questions"""

# 4. Examples
EXAMPLES = """<example>
Customer: Hi, how were you created?
Joe: Hello! My name is Joe, created by AdAstra Careers...
</example>"""

# 5. Input Data
INPUT_DATA = f"""<history>{HISTORY}</history>
<question>{QUESTION}</question>"""

# 6. Immediate Task
IMMEDIATE_TASK = "How do you respond to the user's question?"

# 7. Precognition
PRECOGNITION = "Think about your answer first before you respond."

# 8. Output Formatting
OUTPUT_FORMATTING = "Put your response in <response></response> tags."

# 9. Prefilling
PREFILL = "[Joe] <response>"
```

#### Industry-Specific Examples

**Legal Services**:
- Parse long documents
- Complex multi-step analysis
- Specific citation formats
- Extract evidence before concluding

**Financial Services**:
- Analyze regulatory documents
- Answer compliance questions
- Cite specific sections
- Provide clear, concise answers

**Coding Assistance**:
- Read and analyze code
- Act as teaching assistant
- Provide guided corrections
- Socratic method responses

#### Best Practices
- Start with all elements, refine later
- Test with multiple scenarios
- Order matters for some elements
- Keep trying different structures

#### Exercise Solutions

**Exercise 9.1 (Financial Services)**:
```python
TASK_CONTEXT = "You are a master tax accountant."
TASK_DESCRIPTION = f"""Answer questions using the provided tax code.
<docs>{TAX_CODE}</docs>"""
PRECOGNITION = "First gather relevant quotes in <quotes> tags."
OUTPUT_FORMATTING = "Answer in <answer> tags. If unsure, say you don't have enough information."
```

**Exercise 9.2 (Coding Assistant)**:
```python
TASK_CONTEXT = "You are Codebot, a helpful AI assistant who finds issues with code."
TONE_CONTEXT = "Act as a Socratic tutor who helps the user learn."
TASK_DESCRIPTION = """1. Identify issues in <issues> tags
2. Invite user to revise the code themselves"""
```

---

## Appendix: Beyond Standard Prompting

### Appendix 10.1: Chaining Prompts

#### Key Concepts

**Claude can improve its responses when asked to revise**. This technique involves:
- Multiple conversation turns
- Asking Claude to check or improve its work
- Using previous outputs as inputs for next prompts

#### Techniques

1. **Self-Correction**:
```python
# First turn
user: "Name ten words ending in 'ab'"
assistant: [list with errors]

# Second turn  
user: "Please find replacements for all 'words' that are not real words."
# Claude fixes the errors
```

2. **Iterative Improvement**:
```python
# First turn
user: "Write a three-sentence story about a girl who likes to run."
assistant: [basic story]

# Second turn
user: "Make the story better."
# Claude enhances the story
```

3. **Giving Claude an Out** (preventing over-correction):
```python
user: "Replace any fake words. If all words are real, return the original list."
```

#### Use Cases
- Function calling (using output of one call as input to another)
- Multi-step processing
- Quality improvement
- Error correction

---

### Appendix 10.2: Tool Use

#### Key Concepts

**Tool use (function calling)** expands Claude's capabilities by letting it:
- Request specific functions to be called
- Use results of those functions
- Handle complex multi-step tasks

**Implementation requires**:
1. System prompt explaining tool use
2. Tool definitions in specific format
3. Control logic to execute requests

#### Tool Use Format

System prompt structure:
```python
system_prompt = """You have access to functions you can use to answer questions.

You can invoke functions by writing:
<function_calls>
<invoke name="$FUNCTION_NAME">
<parameter name="$PARAMETER_NAME">$PARAMETER_VALUE</parameter>
</invoke>
</function_calls>

Results will appear in <function_results> tags."""
```

Tool definition format:
```xml
<tools>
<tool_description>
<tool_name>calculator</tool_name>
<description>Calculator for basic arithmetic</description>
<parameters>
<parameter>
<name>first_operand</name>
<type>int</type>
<description>First operand</description>
</parameter>
<!-- more parameters -->
</parameters>
</tool_description>
</tools>
```

#### Implementation Steps

1. Claude outputs function call
2. Parse parameters from Claude's XML
3. Execute the actual function
4. Format results in `<function_results>` tags
5. Send results back to Claude
6. Claude incorporates results into final response

#### Example Tools
- Calculator
- Database queries
- API calls
- File operations
- Web searches

---

### Appendix 10.3: Search & Retrieval

#### Key Concepts

**RAG (Retrieval-Augmented Generation)** enhances Claude's responses with:
- External data retrieval
- Vector database searches
- Real-time information
- Domain-specific knowledge

#### Applications

1. **Wikipedia Search**: Find and retrieve articles
2. **Document Search**: Search your own documents
3. **Vector Databases**: Semantic search with embeddings
4. **Internet Search**: Current information retrieval

#### Resources

- [RAG Cookbook Examples](https://github.com/anthropics/anthropic-cookbook/blob/main/third_party/Wikipedia/wikipedia-search-cookbook.ipynb)
- [Embeddings Documentation](https://docs.anthropic.com/claude/docs/embeddings)
- [Claude 3 RAG Architecture Slides](https://docs.google.com/presentation/d/1zxkSI7lLUBrZycA-_znwqu8DDyVhHLkQGScvzaZrUns/edit)

#### Benefits
- Supplements Claude's knowledge
- Improves accuracy with specific data
- Enables domain-specific applications
- Provides up-to-date information

---

## Key Takeaways

1. **Start simple, add complexity as needed**
2. **Clear communication is paramount** - if a human would be confused, Claude will be too
3. **Examples are incredibly powerful** - often more effective than explanations
4. **Structure matters** - use XML tags to separate concerns
5. **Let Claude think** - step-by-step reasoning improves accuracy
6. **Give Claude an out** - it's okay to say "I don't know"
7. **Iterate and refine** - prompt engineering is experimental

## Next Steps

- Practice with real-world use cases
- Experiment with different techniques
- Join the [Anthropic Discord](https://anthropic.com/discord)
- Explore the [Prompt Library](https://anthropic.com/prompts)
- Read the [full documentation](https://docs.anthropic.com/claude/docs/prompt-engineering)

---

*Remember: You are now in the top 0.1% of prompt engineers. Use your powers wisely!*