# Ralph Specs - Interactive Requirements Gathering

Phase 1 of the Ralph workflow: Define what to build through conversation.

## Instructions

You are helping the user define specifications for their project. This is an
interactive conversation - ask questions, understand deeply, then generate specs.

### Phase 1: Understand the Job To Be Done (JTBD)

Start by asking:

> **What do you want to build?**
> Describe the main goal or problem you're solving. What should exist when we're done?

Listen for:
- The core outcome they want
- Who/what benefits from this
- Why this matters

### Phase 2: Clarifying Questions

Ask 3-5 targeted questions to understand scope and constraints. Examples:

1. **Scope**: "What's explicitly OUT of scope? What should this NOT do?"
2. **Users/Consumers**: "Who or what will use this? (humans, other code, APIs)"
3. **Constraints**: "Are there specific technologies, patterns, or dependencies to use or avoid?"
4. **Success Criteria**: "How will you know this is working correctly?"
5. **Edge Cases**: "What are the tricky scenarios or error cases to handle?"

Adapt questions to what they're building. Don't ask irrelevant questions.

### Phase 3: Decompose into Topics

Break the JTBD into distinct topics of concern. Each topic should:

- **Pass the "one sentence without 'and'" test** - if you need "and" to describe it, split it
- Be independently testable
- Have clear boundaries

Example decomposition for "build a CLI tool that fetches and caches API data":
- `cli-interface` - Command-line argument parsing and user interaction
- `api-client` - Fetching data from the external API
- `cache-layer` - Caching responses for performance
- `error-handling` - Error cases and user feedback

### Phase 4: Generate Spec Files

For each topic, create `specs/<topic-name>.md` with this structure:

```markdown
# <Topic Name>

## Description
[1-2 paragraphs explaining this topic's purpose and scope]

## Requirements
- [ ] Requirement 1 (behavioral - WHAT it should do)
- [ ] Requirement 2
- [ ] Requirement 3

## Acceptance Criteria
- [ ] Given X, when Y, then Z
- [ ] Given A, when B, then C

## Non-Goals
- Thing this topic explicitly does NOT handle
- Another out-of-scope item

## Technical Considerations
- Relevant libraries, patterns, or constraints
- Dependencies on other topics
- Known challenges or risks
```

### Guidelines for Good Specs

**DO:**
- Write behavioral requirements (WHAT to verify)
- Use Given/When/Then for acceptance criteria
- Be specific about edge cases
- Include non-goals to prevent scope creep

**DON'T:**
- Prescribe implementation details (HOW to build)
- Include code snippets or architecture decisions
- Overlap between topics
- Leave requirements vague or untestable

### Phase 5: Summary

After generating all specs, provide:

1. **Summary table** of specs created:
   | File | Description | # Requirements |
   |------|-------------|----------------|
   | specs/topic-1.md | ... | 5 |
   | specs/topic-2.md | ... | 3 |

2. **Next steps**:
   ```
   Specs generated! Next:
   1. Review the specs in specs/ and refine if needed
   2. Run /ralph-launch to verify everything is ready
   3. Run 'ralph plan' in a separate terminal to generate the implementation plan
   ```

3. **Ask**: "Want to review or refine any of these specs before proceeding?"

## Example Interaction

**User**: I want to build a Python library for retrying failed function calls with exponential backoff.

**Claude**: Great! A retry library. Let me ask a few questions:
1. Should this work with both sync and async functions?
2. What customization do users need? (max retries, backoff strategy, etc.)
3. Should it handle specific exception types differently?
4. Any existing libraries to be compatible with or avoid duplicating?

**User**: [answers]

**Claude**: Based on that, I see these topics:
- `core-retry-logic` - The retry loop and backoff calculation
- `decorator-api` - The @retry decorator interface
- `configuration` - Customization options and defaults
- `async-support` - Async function handling

Let me generate specs for each...
