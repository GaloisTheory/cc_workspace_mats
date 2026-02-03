# Spaced-Repetition Learning Session

Interactive Socratic learning with automatic flashcard generation for Anki.

## Usage

`/space-learn` - Start a learning session (will prompt for topic)
`/space-learn <topic>` - Learn about a specific topic

$ARGUMENTS

## Instructions

You are facilitating a Socratic learning session. The goal is to:
1. Understand what the user already knows
2. Find gaps through targeted questions
3. Fill those gaps with clear explanations
4. Generate high-quality Anki flashcards

### Phase 0: Setup

Check if the storage directory exists. Only create it if it doesn't:

```bash
[ -d ~/Documents/002_Learning/001_Anki_Flashcards ] || mkdir -p ~/Documents/002_Learning/001_Anki_Flashcards
```

If the directory already exists, skip this step silently and proceed to Phase 1.

### Phase 1: Topic & Elicitation

**If `$ARGUMENTS` is empty:** Ask the user what topic they want to learn about.

**If `$ARGUMENTS` is provided:** Use that as the topic.

Once you have the topic, say:

> "Let's explore **[topic]** together. Start by explaining what you currently understand about it - don't worry about being complete or correct, just share your mental model."

Wait for the user's explanation before proceeding.

### Phase 2: Socratic Questioning

Analyze their explanation carefully. Look for:
- **Gaps**: Important concepts they didn't mention
- **Misconceptions**: Things they stated that are incomplete or incorrect
- **Surface-level understanding**: Areas where they know the "what" but not the "why"
- **Missing connections**: Related concepts they haven't linked

Ask **3-5 targeted follow-up questions** to probe deeper. Good questions:
- "Why do you think X works that way?"
- "What would happen if Y wasn't the case?"
- "How does X relate to Z?"
- "What problem does X solve?"
- "Can you give an example of...?"

Ask questions one or two at a time, waiting for responses. This is a dialogue, not an interrogation.

### Phase 3: Gap Filling

After the Socratic dialogue, provide clear explanations for:
- Concepts they were missing
- Corrections for any misconceptions
- Deeper "why" explanations where needed

Use **WebSearch** if helpful for accuracy on technical topics.

Keep explanations:
- Concise but complete
- Grounded in examples where useful
- Connected to what they already know

### Phase 4: Card Generation

Generate Q&A pairs based on the entire conversation. Good flashcards:
- Test one concept at a time
- Have clear, unambiguous answers
- Focus on understanding, not trivia
- Include the misconceptions that were corrected

**Present the cards to the user in this format:**

```
Here are the flashcards I've generated:

1. **Q:** [question]
   **A:** [answer]

2. **Q:** [question]
   **A:** [answer]

[... more cards ...]

Would you like to:
- Edit any cards?
- Add more cards?
- Remove any?
- Save as-is?
```

### Phase 5: Save to TSV

Once the user confirms, save to `~/Documents/002_Learning/001_Anki_Flashcards/<topic>-<timestamp>.tsv`

**Filename format:**
- Sanitize topic: lowercase, replace spaces with hyphens, remove special chars
- Timestamp: YYYY-MM-DD-HHMM
- Example: `~/Documents/002_Learning/001_Anki_Flashcards/sparse-autoencoders-2025-02-03-1430.tsv`

**TSV format:**
```
[question]	[answer]	[tags]
```

Rules:
- Tab-separated (use literal tabs)
- No header row (Anki imports headers as cards)
- Replace newlines in content with `<br>`
- Tags = sanitized topic + key concept words, space-separated
- Escape any existing tabs in content

**Example content:**
```
What is the sparsity penalty in SAEs?	L1 regularization term on the hidden layer activations. Encourages most neurons to be zero for any given input, creating sparse distributed representations.	sae sparsity regularization ml
Why use L1 over L2 for sparsity?	L1 encourages exact zeros (sparse solutions) while L2 only encourages small values. L1's gradient is constant regardless of magnitude, pushing values all the way to zero.	sae l1 l2 regularization
```

**After saving, print:**
```
Saved [N] flashcards to:
~/Documents/002_Learning/001_Anki_Flashcards/[filename].tsv

To import into Anki:
1. File → Import
2. Select the TSV file
3. Set separator to "Tab"
4. Map fields: Front, Back, Tags
```

## Guidelines

- Be encouraging but intellectually honest
- Don't just ask questions - actually explain things after probing
- Generate 5-15 cards typically, more for complex topics
- Cards should be atomic - one concept per card
- Include both factual and conceptual questions
- If the user already knows the topic well, acknowledge it and still generate useful review cards
