> Created/edited by GitHub Copilot with human review/feedback by avilevin.

# Tri-Review Model Selection

Read this file only when creating a new reviewer cohort, replacing an unavailable reviewer, or refreshing the model table.

Select three reviewers from the four available major families: Anthropic Claude, OpenAI GPT, Google Gemini, and xAI Grok.

AA-backed hardcodings, queried September 5, 2026 via the `aa-pareto` skill:

Normal tri-review uses an approximately 300-second AA elapsed-time budget per reviewer. The reviewers run in parallel, so the slowest reviewer controls workflow latency. Within that budget, select the highest Coding Index point in each family.

| Family | Normal reviewer | Same-family alternate | Maximum-depth reviewer |
|---|---|---|---|
| Claude / Anthropic | `claude-opus-5` at `medium` — 74.3 coding, 58.6 intelligence, ~249s | `claude-opus-5` at `low` — 66.9 coding, 53.0 intelligence, ~121s | `claude-opus-5` at `max` — 78.0 coding, 63.1 intelligence, ~644s |
| GPT / OpenAI | `gpt-5.6-sol` at `xhigh` — 78.3 coding, 59.0 intelligence, ~217s | `gpt-6-astra` at `high` — 77.1 coding, 64.4 intelligence, ~170s | `gpt-5.6-sol` at `xhigh`; Sol `max` is lower on Coding Index |
| Gemini / Google | `gemini-3.8-flash` at `high` — user-selected successor; current AA runtime unavailable | `gemini-3.6-flash` at `high` — 69.2 coding, 55.9 intelligence, ~146s | `gemini-3.8-flash` at `high` |
| Grok / xAI | `grok-4.6` at `high` — 76.8 coding, 60.9 intelligence, ~487s | `grok-4.5` at `high` — 72.4 coding, 57.6 intelligence, ~371s | `grok-4.6` at `high` |

Rules:

- Apply model selection only when creating a new cohort or replacing an unavailable reviewer.
- When the current/root model belongs to one of the four families, exclude that family and use the normal reviewer from each of the other three.
- When the current/root family is unknown or outside these four, use the three highest-scoring normal reviewers: GPT, Claude, and Gemini.
- If the user explicitly asks for a maximum-depth tri-review, preserve the same family exclusion and use the maximum-depth reviewer for each selected family. For an unknown/outside root family, use GPT, Claude, and Grok because they have the three highest maximum Coding Index scores.
- Use a same-family alternate only when fewer than four families are usable and excluding the active family would leave fewer than three reviewers.
- GPT-6 Astra is available in `models.list`. Gemini 3.5, 3.6, and 3.7 Flash passed live inference probes on September 2, 2026, and Gemini 3.8 passed on September 4, 2026. Gemini 3.8 currently has no positive AA runtime measurements, so its `high` selection is an explicit successor policy rather than a latency-budgeted AA pick.
- If a selected model is unavailable or times out, proceed with the remaining reviewers rather than adding the active family back.
- During a refresh, run `python ~/.copilot/skills/aa-pareto/aa_pareto.py --tri-review` and update this table from its normal, alternate, and maximum output.
