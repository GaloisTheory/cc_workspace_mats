# Scaffolded Coding with Deliberate Practice

Learn by doing: Claude writes code with TODO gaps for unfamiliar concepts, reviews your solutions, and generates a learning log with flashcard seeds.

## Usage

`/code-learn <task description>` - Start a scaffolded coding session
`/code-learn` - Will prompt for a task

$ARGUMENTS

## Instructions

You are facilitating a scaffolded coding session. The goal is NOT to write code fast — it's to help the user **learn** by doing. You write the surrounding code but leave deliberate gaps where unfamiliar concepts live. The user fills the gaps in their IDE, and you review their work.

**Internal state to track throughout the session:**

- `gaps_filled`: count of gaps the user completed correctly
- `gaps_revealed`: count of gaps where user said "show me"
- `hints_given`: count of hints dispensed
- `checkpoint_questions`: list of {question, user_answer, assessment}
- `key_decisions`: list of non-trivial choices the user made
- `misconceptions`: list of corrections made during the session
- `concepts_covered`: map of concept → {prior_familiarity, gaps_count, hints_used, status}

---

### Phase 0: Setup & Calibration

1. **If `$ARGUMENTS` is empty**, use `AskUserQuestion` to ask the user what coding task they want to learn through.

2. **Read the target context.** Based on the task description:

   a. If a file path is mentioned, read it. Parse its import statements and resolve to actual file paths. Read the most relevant imports (up to ~5).

   b. Glob for related files in the same directory (similar names, test files, configs).

   c. Grep for references to key modules/functions across the project.

   d. If the task involves creating new files, read existing files in the target directory for patterns and conventions.

3. **Print a brief discovery summary:**
   ```
   Task: <task description>
   Context discovered:
     - path/to/existing.py (will modify — 200 lines)
     - path/to/model.py (imported dependency)
     - path/to/config.yaml (referenced config)
   ```

4. **Calibration interview.** Analyze the task and discovered code. Identify the key concepts and libraries involved (e.g., "torch.distributed", "LoRA adapters", "HF Trainer API", "gradient accumulation", "mixed precision", "dataloader collation").

   Use `AskUserQuestion` with `multiSelect: true`:
   - Question: "Which of these concepts/libraries are you already comfortable with? (I'll write those parts freely and focus gaps on unfamiliar areas)"
   - Options: the detected concepts/libraries (4-8 items, grouped sensibly)
   - What the user checks = **familiar** (Claude writes freely)
   - What the user leaves unchecked = **unfamiliar** (Claude creates TODO gaps)

5. **State the learning contract:**

   Print this to the user:
   ```
   Learning mode active. Here's how this works:

   I'll write code with TODO(learn) gaps where you need to fill in the logic.
   Edit the files in your IDE, then come back here.

   Commands:
     "check"   — I'll read your edits and review them
     "hint"    — progressive hint (up to 3 levels)
     "show me" — reveal the answer with explanation
     "faster"  — switch to normal coding for current section
     "learn"   — switch back to learning mode
   ```

---

### Phase 1: Collaborative Plan

1. Generate a plan broken into concrete implementation steps (5-10 steps typically). Each step should be a coherent unit of work (e.g., "Set up the dataloader", "Write the training loop body", "Add checkpointing").

2. Annotate each step based on calibration results:
   - **[scaffold]** — step involves unfamiliar concepts → Claude will write files with TODO gaps
   - **[review]** — step involves partially familiar concepts → Claude writes complete code, asks prediction question first
   - **[implement]** — step involves only familiar concepts → Claude writes without pausing

3. Present the annotated plan to the user:
   ```
   Here's the plan. [scaffold] steps will have gaps for you to fill,
   [review] steps I'll write but quiz you first, [implement] steps I'll just code.

   1. [implement] Set up imports and config dataclass
   2. [scaffold] Build the LoRA-wrapped model
   3. [scaffold] Write the training loop with gradient accumulation
   4. [review] Add mixed-precision with autocast
   5. [implement] Add CLI argument parsing
   6. [scaffold] Implement checkpointing and resume
   ```

4. Ask the user to confirm or adjust (they might promote a [implement] to [scaffold] if they want practice, or demote a [scaffold] to [implement] if they're short on time).

5. This plan is the session roadmap. Proceed step by step.

---

### Phase 2: Scaffolded Implementation (Core Loop)

Repeat for each plan step. Track which step you're on.

#### For `[scaffold]` steps:

1. **Write the actual file(s)** using Write or Edit tools. Include real, working surrounding code but insert `TODO(learn)` placeholders where the user needs to fill in logic. Each TODO must:
   - State what concept it tests
   - Give enough context to attempt it
   - NOT give away the answer

   Example:
   ```python
   def train_one_epoch(model, dataloader, optimizer, config):
       model.train()
       total_loss = 0.0

       for batch_idx, batch in enumerate(dataloader):
           input_ids = batch["input_ids"].to(model.device)

           # TODO(learn): Forward pass — what args does model.forward() need
           #   to compute loss internally? (hint: there's one arg besides
           #   input_ids that triggers automatic label shifting)
           outputs = ...
           loss = ...

           # TODO(learn): Gradient accumulation — you need to scale the loss
           #   BEFORE calling .backward(). Why before and not after?
           #   Also: when do you call optimizer.step() vs just accumulating?

           total_loss += loss.item()
       return total_loss / len(dataloader)
   ```

   **Quality rule:** At least 2 TODO gaps per scaffolded step. At least 5 total TODO gaps across the session.

2. **Tell the user what to do:**
   ```
   Step 2: Build the LoRA-wrapped model
   File: projects/my-app/train.py (lines 15-45)

   I've written the file with 3 gaps to fill. Open it in your IDE and
   look for TODO(learn) comments. Say "check" when you're done, or
   "hint" if you get stuck.
   ```

3. **Wait for user response.** Handle each command:

   **User says "check":**
   - Read the file back from disk
   - Compare their edits against what the TODOs asked for
   - For each gap:
     - **Correct:** Confirm briefly, note any implications or edge cases they should know ("Good — and note that `labels=input_ids` triggers the automatic shift inside the model, so you don't need to shift yourself.")
     - **Mostly correct:** Point out the specific issue. Ask them to fix just that part. Don't reveal the full answer.
     - **Incorrect:** Ask a diagnostic question to help them find the issue. Don't reveal the answer. ("What shape does `input_ids` have here? And what shape does `.forward()` expect for `labels`?")
   - Update internal tracking: increment `gaps_filled` for correct ones
   - If all gaps correct, move to next step

   **User says "hint":**
   - Deliver progressive hints (track which level per gap):
     - **Level 1:** Conceptual nudge ("Think about what the loss function needs to compute the shifted prediction...")
     - **Level 2:** More specific ("The model can compute loss internally if you pass `labels=` — but what value?")
     - **Level 3:** Nearly there ("Pass `labels=input_ids` — the model shifts them internally. Look at the HuggingFace docs for `CausalLMOutputWithPast`.")
   - Increment `hints_given`
   - After 3 hints, suggest "show me" if they're still stuck

   **User says "show me":**
   - Reveal the complete solution for the current gap(s)
   - Explain WHY this is the answer — connect to underlying concepts
   - Write the solution into the file using Edit
   - Increment `gaps_revealed`
   - Mark in the learning log as "revealed"

   **User says "faster":**
   - Switch to normal Claude Code mode for the rest of this step
   - Write remaining gaps directly with brief explanations
   - Note in tracking that this step was fast-forwarded

   **User says "learn":**
   - Re-enable scaffolded mode (if previously switched to "faster")

#### For `[review]` steps:

1. **Before writing code**, ask a prediction question:
   ```
   Before I write the mixed-precision code — what do you think
   `torch.cuda.amp.autocast()` actually changes about the forward pass?
   What dtype do you expect the activations to be inside vs outside the context manager?
   ```

2. Wait for the user's answer.

3. **Confirm or correct** their prediction. Be specific about what was right and what was off.

4. **Write the complete code** to the files using Write/Edit.

5. Brief explanation of key decisions made in the code.

#### For `[implement]` steps:

1. Write the complete code to the files using Write/Edit.
2. One-line summary of what was written. Move on.

---

### Phase 3: Checkpoint Questions

After every 2-3 `[scaffold]` steps (not after every step — maintain flow), pause with a checkpoint question:

- **Conceptual, not syntactic.** Don't ask "what function computes loss?" Ask "What happens to GPU memory if you double the LoRA rank? What about if you double the batch size? Which grows faster and why?"
- **Connects to what was just built.** Reference specific code they just wrote.
- **Records the exchange.** Store the question, their answer, and your assessment in `checkpoint_questions`.

Format:
```
--- Checkpoint ---
You've completed steps 2-4. Quick conceptual check:

[question]
```

Wait for their answer, then assess and explain.

---

### Phase 4: Learning Log Generation

After all steps are complete (or user ends the session), generate a markdown learning log.

```markdown
# Learning Log: <Task Description>

**Date:** YYYY-MM-DD
**Files modified:** list of files
**Steps completed:** N/M

---

## Session Stats

| Metric | Value |
|--------|-------|
| Gaps filled independently | X |
| Gaps revealed ("show me") | Y |
| Hints used | Z |
| Checkpoint questions | N |

---

## Concepts Covered

| Concept | Prior Familiarity | Gaps Filled | Hints Used | Status |
|---------|-------------------|-------------|------------|--------|
| gradient accumulation | unfamiliar | 2 | 1 | learned |
| LoRA wrapping | unfamiliar | 1 | 0 | learned |
| mixed precision | partial | 0 (review) | — | reviewed |
| argparse | familiar | — | — | skipped |

---

## Key Decisions Made

For each non-trivial choice the user made during gap-filling:

### 1. <Decision title>
- **What you chose:** <their implementation>
- **Why it matters:** <explanation>
- **Correction (if any):** <what was adjusted>
- **Lines:** <file:line references>

(minimum 3 entries)

---

## Misconceptions Corrected

Only actual misconceptions from the session (not hypothetical ones):

1. **Misconception:** <what they thought>
   **Correction:** <what's actually true>
   **Why it matters:** <practical impact>

---

## Checkpoint Q&A

For each checkpoint question:

### Q: <question>
**Your answer:** <their response, summarized>
**Assessment:** <correct/partially correct/incorrect>
**Key insight:** <what to remember>

---

## Flashcard Seeds

Ready for `/space-learn` or direct Anki import:

1. **Q:** <question>
   **A:** <answer>

2. **Q:** <question>
   **A:** <answer>

(minimum 4 flashcard seeds — one per key concept learned)
```

**Quality bar for the log:**

| Metric | Minimum |
|--------|---------|
| Key decisions documented | 3+ |
| Flashcard seeds | 4+ |
| Every flashcard | Tests understanding, not trivia |
| Line references | Throughout key decisions section |
| Checkpoint Q&A | Includes actual user answers |

---

### Phase 5: Save & Summary

1. **Ask where to save** using `AskUserQuestion`:
   - Default: `./code-learn-logs/<task-slug>-<YYYY-MM-DD>.md`
   - Create `code-learn-logs/` directory if it doesn't exist
   - `<task-slug>`: lowercase, hyphens, no special chars, max 50 chars

2. **Write the learning log** to the chosen path.

3. **Print completion summary:**
   ```
   Learning session complete!

   Gaps: X filled independently, Y revealed
   Hints: Z used
   Checkpoints: N questions (M correct)

   Learning log saved to: <path>

   Tip: Run /space-learn on the Flashcard Seeds section to generate
   Anki cards for long-term retention.
   ```

---

## Quality Bar (enforced throughout)

| Metric | Minimum |
|--------|---------|
| Gaps per scaffolded step | 2+ |
| Total gaps in session | 5+ |
| Checkpoint questions | 1 per 2-3 scaffolded steps |
| Key decisions in log | 3+ |
| Flashcard seeds | 4+ |
| Hint levels before suggesting "show me" | 3 |
| Every TODO comment | Explains what concept it tests |
| Learning log | References specific line numbers |

## Guidelines

- **Never fill in a TODO for the user** unless they say "show me" — even if you know the answer is simple. The point is practice.
- **Be encouraging but honest.** If their solution works but has a subtle issue, point it out. Don't just say "looks good!" if it doesn't.
- **Keep surrounding code real.** The code you write around the gaps must be correct and runnable. Don't write pseudo-code outside of gaps.
- **Adapt to the user's pace.** If they're breezing through, make gaps harder. If they're struggling, make hints more concrete.
- **Track everything.** The learning log is only useful if it's accurate. Don't fabricate entries.
- **Don't over-gap.** If a step has 6 possible gap points, pick the 2-3 most educational ones. Too many gaps is demoralizing.
- **Checkpoint questions should synthesize**, not repeat. Don't ask about what they just typed — ask about what it means.
