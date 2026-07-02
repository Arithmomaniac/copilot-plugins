---
name: aa-pareto
description: Pareto search over Artificial Analysis model benchmarks (quality / speed / price), restricted to Copilot CLI–available models, to choose the best default model for a task. Use when picking or refreshing model defaults per role (heavy reasoner vs fast/mechanical, reduce vs map, proposer vs rater), refreshing the tri-review model table, or answering "which model should I use / what's the quality-speed tradeoff". Triggers on "artificial analysis", "AA pareto", "model pareto", "quality/speed tradeoff", "best model for", "which model should I use", "refresh model table", "fastest model above quality X".
---

# Artificial Analysis Pareto Search (Copilot models)

Pick the best Copilot CLI model for a job by querying the [Artificial Analysis](https://artificialanalysis.ai)
benchmark API and reasoning over the **quality vs speed** Pareto frontier. Because Copilot models are
effectively free on an unlimited plan, optimize on **quality and speed, not price** (price is still
reported as a tiebreaker/context).

## When to use

- Choosing a default model for a pipeline **step/role**: a heavy single-call reasoner vs a fast,
  parallel, mechanical step (e.g. map vs reduce; proposer vs batch rater).
- Refreshing a hardcoded model table (e.g. the `tri-review` skill's heavy/light picks).
- Answering "which model should I use for X", "what's faster but still good", or "fastest model
  above quality N".

Do **not** use for: generic Copilot CLI usage, litellm call mechanics (structured output, tool
calling — that's `litellm-copilot`), or non-model questions.

## Prerequisites

- Env var **`AA_API_KEY`** (or `ARTIFICIAL_ANALYSIS_API_KEY`) — sent as the `x-api-key` header.
- Endpoint: `https://artificialanalysis.ai/api/v2/data/llms/models` (returns `{ "data": [ ... ] }`).
- Relevant fields per model:
  - `name` (includes the **reasoning effort**, e.g. `GPT-5.5 (xhigh)`, `... Max Effort`)
  - `evaluations.artificial_analysis_coding_index` — coding quality (primary metric)
  - `evaluations.artificial_analysis_intelligence_index` — general intelligence
  - `median_output_tokens_per_second` — throughput (speed)
  - `median_time_to_first_token_seconds` — latency (TTFT)
  - `pricing.price_1m_input_tokens` / `price_1m_output_tokens`

## Quick use

Run the bundled script (from this skill's directory):

```bash
python aa_pareto.py                    # coding metric: full table + Pareto frontier + role picks
python aa_pareto.py --metric intelligence
python aa_pareto.py --min-quality 60   # raise the floor for the "fast/light" pick
python aa_pareto.py --models "gpt-5.5,gemini-3.5-flash,claude-opus-4.8"
python aa_pareto.py --json             # machine-readable
python aa_pareto.py --all              # every AA model, not just Copilot ids
python aa_pareto.py --tri-review       # per-family heavy/light candidates (refreshes tri-review's table)
python aa_pareto.py --refresh          # bypass the 24h cache and re-query the API
```

Results are cached per user for **24h** (the free API tier allows only **100 requests/day**), so
repeat runs are free; use `--refresh` to force a live re-query. On an exhausted quota (HTTP 429) or
a rejected key (HTTP 401/403) the script prints a clear message instead of a stack trace, and it
falls back to a stale cache on transient network errors. All data is provided by **Artificial
Analysis**; attribution (printed in the output footer) is required per their API terms.

It prints, restricted to Copilot ids: all candidates sorted by the chosen metric, the **Pareto
frontier** (maximize quality & tok/s), and three role picks:

| Role | Rule | Typical result |
|------|------|----------------|
| **heavy reasoner** | max quality (coding, tie-break intelligence) | `claude-opus-4.8` |
| **quality-at-speed** | Pareto knee (max normalized quality × speed) | `gemini-3.5-flash` |
| **fast / light** | fastest above `--min-quality` | `gemini-3.5-flash` / `gpt-5.4-mini` |

## How to choose per role (the reasoning that matters)

- **Single, hard, quality-critical call** (a synthesis/reduce, a proposer, an adjudicator):
  speed barely matters, so take the **max-quality** point — even if slow. Then set a **high
  reasoning effort** (see below) to realize the headline score.
- **Many parallel or mechanical calls** (a per-item map, a batch rater), especially when a later
  step re-checks the output: take the **quality-at-speed knee** — near-top quality at much higher
  throughput. A fast model at high effort usually beats a slow model at low effort here.
- **Latency-sensitive interactive** work: weigh **TTFT** (`median_time_to_first_token_seconds`),
  not just tok/s — some high-throughput models have very high TTFT.

## Reasoning effort & context tier (don't forget these)

The AA quality number is measured **at a specific reasoning effort** — it's in the model `name`
(e.g. `(xhigh)`, `Max Effort`, `(high)`). To actually get that quality, set the matching effort on
the call (`SessionConfig.ReasoningEffort` in the Copilot SDK; a string like `low|medium|high|xhigh|max`).
Caveats:

- More effort ≠ strictly better: returns diminish and can go negative (overthinking) past a point.
  For the hard step, `xhigh`/`max` is justified; for a mechanical step, the model's mid/high is fine.
- A model can only go as high as its supported ceiling (e.g. Gemini Flash tops out at `high`).
- **Context tier** (`SessionConfig.ContextTier` = `default` | `long_context`): use the *smallest
  tier that fits, with headroom*. `long_context` adds latency (and a higher billing tier even when
  the base model is "free"), so reserve it for steps whose per-call input is genuinely large. Note
  an agent's own tool-reads/reasoning roughly double effective usage, so escalate below the raw
  default window.

## Refresh the Copilot set

The script maps Copilot CLI ids → AA `name` substrings in `COPILOT_MODELS` (top of `aa_pareto.py`).
When Copilot's available models change, refresh that map: get the current ids from the Copilot CLI
(the `/model` picker or the SDK `CopilotClient.ListModelsAsync`) and add/rename entries. Use `--all`
to see every AA model when hunting for the right `name` substring.

## Related skills

- **`litellm-copilot`** — how to *call* the chosen model (structured output, tool calling, the
  `github_copilot/<id>` provider). It defers model *selection* to this skill.
- **`tri-review`** — its "refresh" step runs `aa_pareto.py --tri-review` to regenerate the
  per-family heavy/light reviewer candidates (apply judgment for pro-vs-flash heavy tiers).
