# rm25 validate_feelings handoff

Date: 2026-05-21 UTC

This note captures the follow-up diagnostics for the suspicious Random rm25
`validate_feelings` result so a new agent can continue from `infra/modal`
without reconstructing the chat history.

## Bottom line

The old high Random rm25 `validate_feelings` score is mostly explained by
`openai/gpt-4o-mini` judge behavior, not by the rm25 random adapter suddenly
showing a strong validate-feelings effect.

Key results:

| Run | Same completions? | Judge / prompt | n | mean | stderr |
|---|---:|---|---:|---:|---:|
| Old March eval | yes | `openai/gpt-4o-mini` via `eval_task_fast.py` | 100 | `3.24` | `0.157069` |
| Fixed-output rejudge | yes | Claude with old fast/glitch-ignore prompt | 100 | `1.03` | `0.266839` |
| Fixed-output rejudge | yes | Claude with current standard prompt | 100 | `0.24` | `0.292022` |
| Fresh Claude rerun, persisted | no | Claude current standard prompt | 100 | `0.22` | `0.289402` |
| Fresh Claude variance check, not persisted | no | Claude current standard prompt | 100 | `0.90` | `0.294906` |

The old March completions score `0.24` under the current Claude standard
prompt, essentially matching the first fresh Claude rerun (`0.22`).

## Source artifacts

Old March GPT-mini eval:

```text
projects/dare/experiments/retrain/output/refusal_removal/refuse_then_redirect/random_seed42/rm25/eval_logs/2026-03-06T04-12-44+00-00_c12-valid-feelings-sft_Ei8KKg8bCaj2uvtZPimpQk.eval
```

Persisted Claude rerun used by the graph:

```text
projects/dare/experiments/retrain/output/refusal_removal/refuse_then_redirect/random_seed42/rm25/eval_logs/2026-05-20T23-03-14+00-00_c12-valid-feelings-sft_CnqtbiP9BrYv7xsu6gQq2E.eval
```

HF commit for the persisted Claude validate-feelings rerun:

```text
https://huggingface.co/datasets/GaloisTheory123/dare-results/commit/1d1f2b24d55dfa97115f0b75ff1098c56a6393db
```

Graph-side diagnostic note:

```text
projects/logbook/DL/figures/filter_ladder_claude_v2/validate_feelings_rm25_rejudge_diagnostics.md
```

## Modal stages added

`infra/modal/random_eval_job.py` now has these validate-feelings diagnostic
stages:

```bash
# Persisted Claude rerun for the graph/HF artifact
modal run -m infra.modal.random_eval_job --stage validate_feelings_rm25

# Non-persisted fresh Claude variance check
modal run -m infra.modal.random_eval_job --stage validate_feelings_rm25_check

# Non-persisted fresh March-style fast rerun using eval_task_fast.py and GPT-mini
modal run -m infra.modal.random_eval_job --stage validate_feelings_rm25_fast_check

# Fixed-output Claude rejudge of the old March .eval completions
modal run -m infra.modal.random_eval_job --stage rejudge_validate_feelings_rm25_old
```

The fixed-output rejudge scores the same old March completions twice:

- Claude with the old fast/glitch-ignore prompt.
- Claude with the current standard prompt.

This isolates judge and judge-prompt effects from fresh generation variance.

## Fresh GPT-mini fast rerun blocker

The fresh March-style rerun was attempted:

```bash
modal run -m infra.modal.random_eval_job --stage validate_feelings_rm25_fast_check
```

It failed before producing scores because the Modal OpenAI secret returned:

```text
AuthenticationError: Error code: 401 - Incorrect API key provided
```

So a true fresh `eval_task_fast.py` + `openai/gpt-4o-mini` rerun is blocked
until the OpenAI API key in the Modal secret is refreshed.

## Rejudge command result

Completed command:

```bash
modal run -m infra.modal.random_eval_job --stage rejudge_validate_feelings_rm25_old
```

Modal app run:

```text
https://modal.com/apps/d-lee2176/main/ap-x0nt5dR4yqrWIdn3o3ZiIF
```

Results:

```text
source GPT-mini mean: 3.24, stderr: 0.157069
Claude + fast/glitch-ignore prompt mean: 1.03, stderr: 0.266839
Claude + standard prompt mean: 0.24, stderr: 0.292022
```

Interpretation:

- GPT-mini scored the old March completions much higher than Claude.
- The old fast/glitch-ignore prompt raises Claude from `0.24` to `1.03`,
  but does not recover the GPT-mini `3.24`.
- The plotted value should stay on the persisted Claude rerun unless the
  analysis policy changes to pool multiple fresh Claude runs.

## Files updated for visibility

Graph/reproduction notes now point to the diagnostic:

```text
projects/logbook/DL/figures/filter_ladder_claude_v2/README.md
projects/logbook/DL/figures/filter_ladder_claude_v2/index.html
projects/logbook/DL/figures/filter_ladder_claude_v2/variant_B_REPRODUCE.md
projects/logbook/DL/figures/filter_ladder_claude_v2/validate_feelings_rm25_rejudge_diagnostics.md
```

No graph artifacts or HF uploads were changed by the rejudge diagnostic.
