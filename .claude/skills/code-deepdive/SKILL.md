---
name: code-deepdive
description: Line-level explanatory deep dive into a script or module — data flow stage by stage, every silent choice and implicit default, edge cases, and a line-number reference table, written out as a self-contained HTML onboarding document that is served on localhost so the user gets a clickable link. Use whenever the user asks to deep dive / walk through / explain / break down / understand a specific file, asks "what does this script actually do", "how does this pipeline work", "what are the gotchas in this code", wants an onboarding doc for a module, or wants to understand every decision the author made — even if they don't say "deep dive" explicitly. For an adversarial hunt for problems rather than an explanation, /code-redteam is the sibling; this skill teaches the code, it does not attack it.
---

# Code Deep Dive

Line-level deep analysis of a script: data flow, silent choices, edge cases,
and architectural decisions. The deliverable is a self-contained HTML page,
served on localhost, handed back as a clickable link.

You are producing a thorough, expert-level deep-dive analysis of a code file.
Think "senior engineer onboarding document" — someone should be able to read
your output and understand not just WHAT the code does, but every implicit
decision, every edge case, and every trade-off the author made.

The goal is to explain, not to attack. Finding problems is the job of
`/code-redteam`; here, a silent choice is documented so the reader understands
it, not so it can be scored for severity.

## Phase 1: Read & Discover

1. Identify the target file. If no file path was given, ask the user for one
   (use AskUserQuestion if available, otherwise ask in plain text).

2. **Read the target file** in full.

3. **Auto-discover related files.** Search for ALL of the following:

   a. **Files imported by the target** — parse import statements and resolve to
      actual file paths in the repo. Read each one.

   b. **Alternative implementations** — look in the same directory for files
      with similar names (e.g., if the target is `embed_dataset_vllm.py`, look
      for `embed_dataset.py`, `embed_dataset_hf.py`, etc.). Use a glob pattern
      based on the core name.

   c. **Files that import/call the target** — grep for references to the
      target's module name across the project.

   d. **Config files referenced by the target** — look for config file paths,
      argparse defaults, environment variable references, YAML/JSON/TOML file
      reads.

   Read the most relevant related files (up to ~5). Don't read every transitive
   dependency — use judgment.

4. **Print a brief summary** of what you found:
   ```
   Target: path/to/script.py (N lines)
   Related files discovered:
     - path/to/alternative.py (alternative implementation)
     - path/to/config.yaml (referenced config)
     - path/to/caller.py (imports target)
   ```

## Phase 2: Interview

5. **Present discovered focus areas** based on what's actually in the code.
   Analyze the code structure and identify the major subsystems, patterns, and
   interesting aspects. Examples (adapt to the actual code):
   - "Multi-GPU orchestration and process spawning"
   - "Think-token parsing and text extraction"
   - "Resume/checkpoint system"
   - "API client with retry logic"
   - "Database connection pooling"

   Let the user pick which areas interest them most — multi-select if the
   runtime supports it (AskUserQuestion with `multiSelect: true`), otherwise
   ask in plain text. Include an "All of them — full deep dive" option.

6. **If related files were found**, also ask if the user wants comparison
   sections included (e.g., "I found `embed_dataset.py` which looks like an
   alternative implementation. Want me to include a comparison?").

## Phase 3: Deep Analysis

Analyze the code and produce the following sections. Every section is informed
by actually reading the code — cite specific line numbers throughout.

### Mandatory Core Sections (always include):

7. **Big Picture** — What the script does, in one paragraph. Include: inputs,
   outputs, key dependencies, and the high-level pipeline/flow.

8. **Data Flow** — Trace the shape and structure of data at each major
   transformation stage. Use concrete examples showing actual data structures
   (dicts, tensors, dataframes, etc.) at each stage. Format as numbered stages:
   ```
   Stage 0: Raw input → {shape/structure}
   Stage 1: After X → {shape/structure}
   Stage 2: After Y → {shape/structure}
   ...
   Stage N: Final output → {shape/structure}
   ```

9. **Silent Choices** — This is the most important section. Be EXTREMELY
   aggressive in coverage. Document EVERY implicit decision the code makes. For
   each silent choice, state: (a) what was chosen, (b) what the alternatives
   were, (c) why it matters. Categories to audit:

   - **Truncation/clipping strategies** — what gets cut, from which end, what's lost
   - **Default values** — every hardcoded default, every argparse default, every fallback
   - **What's ignored/discarded** — fields not used, data silently dropped, conditions that skip rows
   - **Ordering effects** — does the order of operations matter? Would reordering change results?
   - **Type conversions** — implicit casts, precision changes (float64→float32, int→str, etc.)
   - **Missing validation** — inputs that aren't checked, assumptions that aren't enforced
   - **Concatenation/formatting choices** — separators, join orders, string formatting
   - **Normalization decisions** — what's normalized, what isn't, which norm
   - **Sampling/selection strategies** — random vs deterministic, stratified vs uniform
   - **Error handling philosophy** — what's caught vs what crashes, silent failures vs loud ones
   - **Resource allocation** — memory limits, batch sizes, GPU utilization percentages
   - **Pooling/aggregation strategy** — mean vs last-token vs CLS, and what that implies

   Do NOT just list the obvious ones. Dig deep. If the code uses `.strip()`,
   note what whitespace is lost. If it uses `.index()` instead of `.rindex()`,
   note that only the first match is found. If a loop breaks early, note what's
   skipped.

10. **Edge Cases & Gotchas** — What breaks, what's silently dropped, what's
    lossy, what produces surprising results. For each edge case: describe the
    scenario, show what happens, and assess severity (cosmetic / data-loss /
    crash).

11. **Key Lines Reference** — A table mapping line numbers (or line ranges) to
    what they do. Cover the most important ~15-25 lines. Format:

    | Lines | What |
    |-------|------|
    | 42 | Model name constant |
    | 86-100 | Extract last assistant message (backward scan) |
    | ... | ... |

### Adaptive Sections (include only when relevant):

12. **Include additional sections based on what's actually in the code.**
    Examples:

    - **Multi-GPU / Distributed Architecture** — only if the code uses multiprocessing, distributed, or multi-device logic
    - **Comparison with Alternative Implementation** — only if a related alternative file was found AND the user wants it
    - **API/Library Usage** — if the code uses a notable library in a non-trivial way (e.g., vLLM, transformers, Ray), explain the specific API calls and their implications
    - **Resume/Checkpoint System** — only if the code has persistence/recovery logic
    - **Configuration & CLI Interface** — if argparse, click, or config file parsing is substantial
    - **Concurrency Model** — if async, threading, or multiprocessing patterns are used
    - **Error Recovery** — if there's substantial error handling logic

    Do NOT force these sections. A 50-line utility script should NOT have a
    "Multi-GPU Architecture" section. Let the code dictate the structure.

13. For sections the user selected in the interview, go deeper. For sections
    the user didn't select, still cover them but more briefly.

## Phase 4: Output

The deliverable is **HTML, not markdown** — written to disk, served over
localhost, and handed to the user as a link. Only write a `.md` file instead
if the invoker explicitly asks for markdown.

14. **Ask the user where to save.** Suggest a default path:
    `<same-directory-as-target>/<SCRIPT_NAME>_DEEPDIVE.html` (e.g., for
    `src/embed.py`, suggest `src/embed_DEEPDIVE.html`). Also offer saving to a
    `deepdive_explanations/` subdirectory if one exists nearby. If the target
    lives in a repo where a stray HTML file would be noise, prefer a
    gitignored/scratch directory and say which one you picked.

15. **Write one self-contained HTML file.** No CDN scripts, no external
    stylesheets, no web fonts, no remote images — everything inline, so the
    page also works over `file://` and can be published as an Artifact later
    without hitting a CSP wall. Required structure:

    - `<title>Deep Dive: <filename></title>` and an `<h1>` to match
    - One-line description under the title, plus a small provenance line:
      absolute path of the target, its line count, and the date
    - A **sticky table of contents** (sidebar on wide screens, collapsed to
      the top of the page on narrow ones) with in-page anchor links to every
      section; give every section an `id`
    - All the Phase 3 sections, each as its own `<section>` with an `<h2>`
    - Code blocks in `<pre><code>` with a monospace stack, preserved
      whitespace, and `overflow-x: auto` so long lines scroll inside the block
      instead of widening the page. Escape `<`, `>`, and `&` in code — an
      unescaped generic or comparison operator silently eats the rest of the
      block.
    - Line-number citations rendered as a distinguishable inline token (e.g. a
      `<code class="ln">line 42</code>` chip) so they scan at a glance
    - Real `<table>` markup for the Data Flow stages and the Key Lines
      Reference, with `overflow-x: auto` on a wrapper div
    - Styling: a readable measure (~72ch) for prose, generous line height, and
      **both light and dark themes** via `@media (prefers-color-scheme: dark)`.
      Keep the CSS short and hand-written; this is a document, not an app.
    - No JavaScript is required. Add it only for a genuinely useful affordance
      (TOC scroll-spy, collapse/expand of long sections) and keep it inline.

    Content rules are unchanged from the markdown era: concrete example data,
    actual code from the file rather than paraphrased pseudocode, and a line
    citation on every claim.

16. **Serve it on localhost and give the user the link.** Start a static
    server rooted at the output *directory* (not the repo root) on a free
    port, bound to loopback:

    ```bash
    PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
    python3 -m http.server "$PORT" --bind 127.0.0.1 --directory <output-dir>
    ```

    Run it as a **background** command so it outlives the turn. Capture the
    port and report `http://localhost:<PORT>/<filename>.html`.

    - Bind to `127.0.0.1`. Only bind `0.0.0.0` if the user explicitly asks —
      that exposes the page to everything that can route to this host.
    - Before starting a new server, check whether one from an earlier deep
      dive is already serving the same directory (`pgrep -af "http.server"`)
      and reuse its port instead of stacking processes.
    - Verify the link actually works before handing it over:
      `curl -sS -o /dev/null -w '%{http_code}' http://localhost:<PORT>/<file>`
      must return `200`. Do not report a URL you have not curled.
    - Tell the user how to stop it (`kill <pid>`), and note that it dies with
      the session.

17. **If the browser can't reach this host, fall back.** The user's browser
    may not run on the machine this skill runs on (workspace boxes, remote
    dev hosts, sandboxed browser tools) — in that case a `localhost` URL is
    dead on arrival even though `curl` succeeds locally. When the user says
    the link doesn't open, offer, in order:

    a. **Publish as an Artifact** — the file is already self-contained, so
       `Artifact` with the HTML path gives a real shareable URL. Redeploy the
       same path on later refreshes to keep the URL stable.
    b. **`SendUserFile` with `display: "render"`** — renders the page inline
       without any server.
    c. An SSH port-forward they can run themselves:
       `ssh -L <PORT>:127.0.0.1:<PORT> <this-host>`.

18. **Print a completion summary:**
    ```
    Deep dive:  <absolute path to .html>
    Link:       http://localhost:<PORT>/<filename>.html  (HTTP 200, pid <pid>)
    Sections: <count>
    Silent choices documented: <count>
    Edge cases documented: <count>
    ```

## Quality Bar

- Every claim references a specific line number
- Silent choices section has 8+ entries minimum (more for complex scripts)
- Edge cases section has 5+ entries minimum (more for complex scripts)
- Data flow section uses concrete example data, not abstract descriptions
- Code blocks show actual code from the file, not paraphrased pseudocode
- For simple scripts (~50 lines), the analysis is proportionally shorter but
  still thorough on silent choices
- The HTML is self-contained: opening it with the network off must look
  identical. Zero external requests.
- Code inside `<pre>` is HTML-escaped; the page renders correctly in both
  light and dark mode; nothing scrolls the page horizontally
- The reported URL was curled and returned 200 — never hand over an
  unverified link
