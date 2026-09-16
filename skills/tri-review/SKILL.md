---
name: tri-review
description: Run an escalated, parallel three-model code review using three families selected from Claude, GPT, Gemini, and Grok, then adjudicate consensus findings. Use only when the user explicitly asks for a tri-review, triple/three-model/multi-model review, or an already-invoked workflow explicitly requires tri-review. Do not infer it merely because a change appears risky, complex, or release-critical.
---

# Tri-Review

Run three parallel code-review subagents with different model families to get diverse perspectives on code changes, then adjudicate the findings into a concise consensus report.

Tri-review is an **escalated code-review workflow**, not the default review path. It requires explicit multi-model-review intent from the user or an explicit instruction from an already-active parent workflow such as `pr-shepherd`.

## When to use

- User says "tri-review", "triple review", "three model review", "multi-model review"
- User asks to review something with multiple models
- User says "do a tri-review of this" or "run the triple review"
- An already-invoked workflow explicitly requires tri-review as one of its steps

## When not to use

- For a normal fast code review, prefer the native `/review` workflow or a single `code-review` subagent.
- Do not activate merely because a change appears important, risky, ambiguous, complex, security-sensitive, or release-critical.
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

### 2. Reuse an existing reviewer cohort when possible

Within the same root session, treat repeated tri-review requests about the same branch, PR, or evolving change set as follow-up rounds.

- If the prior three reviewers are still available as running or idle agents, reuse their recorded `agent_id` values with `write_agent`.
- Send each reviewer the new objective, the exact change since its previous review, the current diff scope, and any findings it should verify. Do not resend the entire development history.
- Keep the original reviewer roster for that review lineage even if the root model changes.
- Reuse reviewers when the user says "tri-review again", asks the same reviewers to inspect fixes, requests reconsideration, or continues reviewing the same PR.
- Launch fresh reviewers when there is no prior cohort in the current session, the scope is unrelated, a prior agent is unavailable, the user asks for a fresh/blind/independent review, or independence is more important than continuity.
- Do not use `list_agents` merely to rediscover known reviewer IDs. Use the IDs retained in the conversation. If a `write_agent` call fails because an agent is unavailable, launch only the missing replacement and give it sufficient standalone context.

Reviewer continuity is session-scoped. Do not claim that reviewer memory survives a new root session.

### 3. Select model families

Read [model-selection.md](model-selection.md) before creating a new reviewer cohort or replacing an unavailable reviewer. It contains the dated model table, active-family exclusion rules, maximum-depth policy, and refresh procedure. Do not load it for follow-up rounds that reuse an existing cohort.

### 4. Launch or resume three parallel code-review subagents

For a new cohort, use the `task` tool with `agent_type: "code-review"` and the three selected family models, all launched in **parallel** in one response. Use `mode: "background"` so the reviewers remain available for later rounds in the same root session. Record each reviewer's family, model, name, and returned `agent_id` in the conversation context.

Each subagent gets the same prompt describing what to review. Include sufficient context: diff scope, base branch, changed file paths, user instructions, and any important task context already known.
Pass the effort listed in the applicable table column as the task's `reasoning_effort`.

**Example prompt for each subagent:**
> Review the specified code changes for bugs, security issues, logic errors, regressions, broken assumptions, race conditions, resource leaks, missing error handling that can crash, public API breaks, and measurable performance problems. Only flag genuine, high-confidence issues. Do not comment on style, formatting, naming, documentation, minor refactors, or best-practice preferences unless they prevent an actual bug. If unsure, do not mention it. Verify concerns by reading surrounding code and, when practical, running focused checks. For each issue, provide file/line, severity (`Critical`, `High`, or `Medium`), problem, evidence, and suggested fix. Do not edit files.

For a follow-up round, send the same follow-up prompt to all available cohort members in one `write_agent` call:

> Continue your previous review of this change set. Since your last review, [describe the exact edits or new question]. Review the current [diff scope], verify whether your earlier findings were resolved or invalidated, and inspect the changed paths for new regressions. Reuse your prior understanding instead of restarting repository discovery, but verify all claims against the current files. Return only new or still-actionable findings, or `CLEAR`. Do not edit files.

Wait for completion notifications, then read each reviewer once with `read_agent`. Do not poll.

### 5. Consolidate results

After all three complete, adjudicate before reporting:

1. Merge duplicate reports across reviewers.
2. Treat consensus as stronger signal, not automatic truth.
3. Discard weak, speculative, stylistic, or unverifiable findings even if multiple reviewers mentioned them.
4. Preserve a single-reviewer finding only when it is concrete, high-confidence, and worth the user's investigation time.
5. Map low-severity nits to "not reportable" for code tri-review unless they are real correctness issues.

Then present a consolidated report:

#### Consensus findings (2+ reviewers agree)

| # | Issue | Severity | Evidence | Reviewer A | Reviewer B | Reviewer C |
|---|-------|----------|----------|:---:|:---:|:---:|
| 1 | Description with file/line | Critical/High/Medium | Why this is a real issue | ✓ | ✓ | |

Replace the reviewer headings with the three selected family names.

#### Notable single-reviewer findings

| # | Issue | Severity | Evidence | Reviewer |
|---|-------|----------|----------|----------|
| 1 | Description with file/line | Critical/High/Medium | Why this is worth investigating | Which model |

### 6. Summary

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
- On a later follow-up round, replace only a reviewer that is no longer available; reuse the remaining cohort.

## Notes

- The three models are chosen from four live families so the family that produced the work can be excluded
- Reusing the cohort preserves reviewer understanding and avoids repeating repository discovery; fresh reviewers remain available when independence is the goal
- Model names should be refreshed periodically from Copilot availability plus Artificial Analysis quality/latency data
- Consensus findings (2+ models flag the same issue) have higher signal than single-reviewer findings
- The consolidator owns judgment: do not forward every reviewer comment mechanically
- This pattern is optimized for post-change code defect review. Use `rubber-duck` for broader design/proposal critique.
