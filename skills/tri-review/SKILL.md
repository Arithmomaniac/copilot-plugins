---
name: tri-review
description: Run an escalated, parallel three-model code review using Claude, GPT, and Gemini reviewers, then adjudicate consensus findings. Use when the user says "tri-review", "triple review", "three model review", "multi-model review", asks for a review with multiple models, or wants extra confidence on high-risk code changes.
---

# Tri-Review

Run three parallel code-review subagents with different model families to get diverse perspectives on code changes, then adjudicate the findings into a concise consensus report.

Tri-review is an **escalated code-review workflow**, not the default review path. Use it when model diversity and consensus are worth the extra latency: high-risk changes, release-critical changes, surprising regressions, security-sensitive edits, complex logic, or cases where a normal single-model review feels insufficient.

## When to use

- User says "tri-review", "triple review", "three model review", "multi-model review"
- User asks to review something with multiple models
- User says "do a tri-review of this" or "run the triple review"
- User wants extra confidence on important, risky, ambiguous, or release-critical code changes

## When not to use

- For a normal fast code review, prefer the native `/review` workflow or a single `code-review` subagent.
- For early plans, designs, proposals, partial work, or "what might go wrong?" critique, prefer `rubber-duck`.
- For security-only review, prefer `/security-review` or the `security-review` agent.
- For PR walkthroughs where the human reviewer drives comments and verdicts, prefer `pr-reviewer`.
- For CLI E2E coverage analysis or test-writing gaps, prefer `e2e-test-coverage`.

## Instructions

### 1. Determine what to review

Ask or infer from context:
- **Staged changes**: `git diff --cached` (default if changes are staged)
- **Unstaged changes**: `git diff`
- **Branch diff**: `git diff main...HEAD` or similar
- **Specific file(s)**: whatever the user points at

Respect explicit user scope. Otherwise follow the same scope order as the native code-review agent: staged changes first, then unstaged changes, then branch diff when the working tree is clean. Do not broaden the review into general repository health unless the user explicitly asks.

### 2. Select model families

Use one reviewer from each major family for diversity: Anthropic Claude, OpenAI GPT, and Google Gemini. Prefer the hardcoded model choices below; they are selected from Artificial Analysis coding/intelligence/speed data and Copilot CLI model availability.

AA-backed hardcodings, queried 2026-07-02 (via the `aa-pareto` skill; run `aa_pareto.py --tri-review` to re-refresh):

| Family | Heavy/default reviewer | Why this heavy model | Light same-family reviewer | Why this light model |
|---|---|---|---|---|
| Claude / Anthropic | `claude-opus-4.8` | Highest Claude AA scores: coding 76.5, intelligence 59.9 (69 tok/s) | `claude-haiku-4.5` | Light Claude speed pick: coding 43.9 at 152 tok/s; same-family diversity/latency, not maximum depth |
| GPT / OpenAI | `gpt-5.5` | Highest GPT AA scores: coding 74.9, intelligence 54.8; strong latency (~22s TTFT) at 82 tok/s | `gpt-5.4-mini` | Best GPT light quality-speed tradeoff: coding 56.1, intelligence 40.0 at 178 tok/s |
| Gemini / Google | `gemini-3.5-flash` | Now the top Gemini on AA coding (70.1) **and** the fastest (219 tok/s) — overtook 3.1 Pro (68.8) this refresh | `gemini-3.1-pro-preview` | Distinct same-family reviewer for echo-reduction (coding 68.8, intelligence 46.5, 140 tok/s); a *diversity* pick, since Flash now leads it on both coding and speed |

Rules:
- Keep three distinct families whenever possible.
- For normal tri-review, use the heavy/default reviewer for families that did **not** produce the work.
- If the current/root agent is from one of the families above, use that family's **light same-family reviewer** instead of its default reviewer. This keeps the same-family perspective while reducing echo-chamber risk and latency.
- If the user explicitly asks for a maximum-depth or heavy tri-review, use the heavy/default reviewer for all three families even when one family produced the work.
- If a listed model is unavailable, choose the best available model in the same family using the same AA criteria: heavy/default reviewer = highest coding score, breaking ties with intelligence and latency; light reviewer = best coding-weighted quality-per-second among small/fast models available in Copilot.
- During a refresh, run the `aa-pareto` skill's script from this skill's directory: `python ../aa-pareto/aa_pareto.py --tri-review` (it queries the AA API with `AA_API_KEY`, restricts to Copilot ids, and emits per-family heavy = max-coding and light = fastest-with-floor candidates from `artificial_analysis_coding_index`, `artificial_analysis_intelligence_index`, `median_output_tokens_per_second`, and `median_time_to_first_token_seconds`). Apply judgment for "pro vs flash" heavy tiers — a fast model can out-score the pro model on coding yet you may still want the pro tier as the heavy reviewer — then update the table below and the "queried" date.

### 3. Launch three parallel code-review subagents

Use the `task` tool with `agent_type: "code-review"` and three different models, all launched in **parallel** (all three calls in a single response):

```
Model 1: selected Claude reviewer
Model 2: selected GPT reviewer
Model 3: selected Gemini reviewer
```

Each subagent gets the same prompt describing what to review. Include sufficient context: diff scope, base branch, changed file paths, user instructions, and any important task context already known.

**Example prompt for each subagent:**
> Review the specified code changes for bugs, security issues, logic errors, regressions, broken assumptions, race conditions, resource leaks, missing error handling that can crash, public API breaks, and measurable performance problems. Only flag genuine, high-confidence issues. Do not comment on style, formatting, naming, documentation, minor refactors, or best-practice preferences unless they prevent an actual bug. If unsure, do not mention it. Verify concerns by reading surrounding code and, when practical, running focused checks. For each issue, provide file/line, severity (`Critical`, `High`, or `Medium`), problem, evidence, and suggested fix. Do not edit files.

### 4. Consolidate results

After all three complete, adjudicate before reporting:

1. Merge duplicate reports across reviewers.
2. Treat consensus as stronger signal, not automatic truth.
3. Discard weak, speculative, stylistic, or unverifiable findings even if multiple reviewers mentioned them.
4. Preserve a single-reviewer finding only when it is concrete, high-confidence, and worth the user's investigation time.
5. Map low-severity nits to "not reportable" for code tri-review unless they are real correctness issues.

Then present a consolidated report:

#### Consensus findings (2+ reviewers agree)

| # | Issue | Severity | Evidence | Claude | GPT | Gemini |
|---|-------|----------|----------|:---:|:---:|:---:|
| 1 | Description with file/line | Critical/High/Medium | Why this is a real issue | ✓ | ✓ | |

#### Notable single-reviewer findings

| # | Issue | Severity | Evidence | Reviewer |
|---|-------|----------|----------|----------|
| 1 | Description with file/line | Critical/High/Medium | Why this is worth investigating | Which model |

### 5. Summary

End with a brief assessment:
- How clean the changes are overall
- Whether any consensus findings need immediate attention
- Whether any single-reviewer findings warrant investigation
- If no findings survive adjudication, say: "No significant issues found in the tri-reviewed changes."

## Model fallback

If a model fails or times out:
- **Proceed with the models that succeeded** — a 2-model consensus is still high-signal
- Note the failure in the output so the user knows
- Adjust the consensus table: 2-of-2 agreement is equivalent to 2-of-3
- Do not retry automatically unless the user asks
- Do not block the review waiting for an unavailable model

## Notes

- The three models are chosen for diversity: Claude (Anthropic), GPT (OpenAI), Gemini (Google)
- Model names should be refreshed periodically from Copilot availability plus Artificial Analysis quality/speed data
- Consensus findings (2+ models flag the same issue) have higher signal than single-reviewer findings
- The consolidator owns judgment: do not forward every reviewer comment mechanically
- This pattern is optimized for post-change code defect review. Use `rubber-duck` for broader design/proposal critique.
