> Created/edited by GitHub Copilot with human review/feedback by avilevin.

# Tri-Review Model Selection

Read this file only when creating a new reviewer cohort, replacing an unavailable reviewer, or refreshing the model table.

Select three reviewers from the four available major families: Anthropic Claude, OpenAI GPT, Google Gemini, and xAI Grok.

AA-backed hardcodings, generated September 8, 2026 via the `aa-pareto` skill:

Normal tri-review uses an approximately 300-second AA elapsed-time budget per reviewer. The reviewers run in parallel, so the slowest reviewer controls workflow latency. Within that budget, select the highest Coding Index point in each family.

| Family | Normal reviewer | Same-family alternate | Maximum-depth reviewer |
|---|---|---|---|
| Claude / Anthropic | `claude-opus-5` at `low` — 66.9 coding, 43.8 intelligence, ~172s | No distinct model within budget; reuse the normal reviewer | `claude-opus-5` at `max` — 78.0 coding, 54.1 intelligence, ~896s |
| GPT / OpenAI | `gpt-5.6-sol` at `high` — 77.2 coding, 48.3 intelligence, ~204s | `gpt-6-astra` at `high` — 77.1 coding, 53.4 intelligence, ~227s | `gpt-5.6-sol` at `xhigh` — 78.3 coding, 49.8 intelligence, ~309s |
| Gemini / Google | `gemini-3.8-flash` at `high` — 76.3 coding, 47.1 intelligence, ~244s | `gemini-3.7-flash` at `high` — 76.1 coding, 45.2 intelligence, ~189s | `gemini-3.8-flash` at `high` — 76.3 coding, 47.1 intelligence, ~244s |
| Grok / xAI | `grok-4.6` at `low` — 66.3 coding, 41.6 intelligence, ~183s | No distinct model within budget; reuse the normal reviewer | `grok-4.6` at `high` — 76.8 coding, 50.6 intelligence, ~672s |

Rules:

- Apply model selection only when creating a new cohort or replacing an unavailable reviewer.
- When the current/root model belongs to one of the four families, exclude that family and use the normal reviewer from each of the other three.
- When the current/root family is unknown or outside these four, use the three highest-scoring normal reviewers: GPT, Claude, and Gemini.
- If the user explicitly asks for a maximum-depth tri-review, preserve the same family exclusion and use the maximum-depth reviewer for each selected family. For an unknown/outside root family, use GPT, Claude, and Grok because they have the three highest maximum Coding Index scores.
- Use a same-family alternate only when fewer than four families are usable and excluding the active family would leave fewer than three reviewers.
- GPT-6 Astra and Gemini 3.8 Flash are available in `models.list`; the generated data includes positive runtime measurements for the selected normal reviewers.
- If a selected model is unavailable or times out, proceed with the remaining reviewers rather than adding the active family back.
- During a refresh, use the `aa-pareto` skill when it is installed and discoverable. Run its bundled `aa_pareto.py --tri-review` command from the base directory supplied by that skill, then update this table from its normal, alternate, and maximum output. If `aa-pareto` is unavailable, retain the dated table rather than guessing an installation path.
