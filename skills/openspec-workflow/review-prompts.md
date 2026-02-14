# OpenSpec Stage 2: Multi-Model Review Prompts

This file defines the standardized review prompt, synthesis logic, and agent dispatch
instructions for the parallel three-model review stage of the OpenSpec workflow.

---

## 1. Review Prompt Template

> Send this prompt **verbatim** to each of the three reviewer agents.
> The only variable is `{{OPENSPEC_DIR}}` — the path to the OpenSpec output directory.

````markdown
You are a senior design reviewer. Your job is to find **real problems** in this
specification — things that will cause bugs, outages, or wasted engineering time
if they ship as-is.

### Artifacts to read

Read every file in `{{OPENSPEC_DIR}}/` — at minimum:

- `proposal.md` — the original problem statement and goals
- `design.md` — architecture, trade-offs, and decisions
- `specs/*.md` — per-component or per-module specifications
- `tasks.md` — implementation plan and task breakdown

Also read the **source code files** referenced by the specs so you can judge
feasibility against the actual codebase.

### Evaluation criteria

Assess the specification against each of these dimensions:

| # | Criterion | What to look for |
|---|-----------|-----------------|
| 1 | **Completeness** | Are all requirements from the proposal covered? Missing scenarios or user flows? |
| 2 | **Consistency** | Do artifacts contradict each other? Does `design.md` promise something `specs/` doesn't specify? |
| 3 | **Cross-component interactions** | Does module A's spec account for module B's behavior? Race conditions, ordering assumptions, shared state? *This is where the most critical bugs hide.* |
| 4 | **Platform / environment gaps** | Does the spec assume things about the runtime, OS, network, or dependencies that may not hold in all target environments? |
| 5 | **Error handling** | Are failure modes specified? What happens on invalid input, timeout, partial failure, retry? |
| 6 | **API contracts** | Are parameter types, return types, error payloads, and status codes fully defined? |
| 7 | **Implementation feasibility** | Can the tasks in `tasks.md` actually implement the specs as written? Are there hidden prerequisites or circular dependencies? |
| 8 | **Performance implications** | Any O(n²) where O(n) is needed? Unbounded allocations? Missing pagination? Resource leaks? |

### Severity categories

Categorize every finding using exactly one of these levels:

- **CRITICAL** — Will cause bugs, data loss, or system failure in production.
- **IMPORTANT** — Significant gap that should be addressed before implementation begins.
- **MINOR** — Nice-to-have improvement; low risk if skipped.
- **SUGGESTION** — Stylistic or optional enhancement.

### Finding format

For each finding, provide:

| Field | Description |
|-------|-------------|
| **Severity** | CRITICAL / IMPORTANT / MINOR / SUGGESTION |
| **Artifact** | File path with the issue (e.g. `specs/auth.md`) |
| **Issue** | What is wrong — be specific and cite evidence from the artifacts |
| **Impact** | What happens in production if this is not fixed |
| **Fix** | Concrete suggestion — not "think about it", but "add X to Y" |

### What NOT to flag

Do **not** comment on:

- Markdown formatting or prose style
- Purely cosmetic changes (heading levels, bullet style)
- Issues already acknowledged in the design trade-offs section of `design.md`
- Hypothetical problems with no plausible trigger in the described system

### Output format

Return your review as a numbered list of findings, ordered by severity
(CRITICAL first, then IMPORTANT, MINOR, SUGGESTION). Use this template:

```
### Finding <N>

- **Severity**: CRITICAL
- **Artifact**: specs/data-sync.md
- **Issue**: The retry logic on L45 retries indefinitely with no backoff...
- **Impact**: Under sustained failure, this will spawn unbounded goroutines...
- **Fix**: Add exponential backoff with a max of 5 retries and a circuit breaker.
```

If you find zero issues at a given severity level, state that explicitly
(e.g. "No CRITICAL findings.").
````

---

## 2. Synthesis Instructions

After all three reviewer agents return their findings, the orchestrating agent
must merge the results into a single consolidated report.

### Merge procedure

1. **Deduplicate** — If two or more reviewers flag the same underlying issue
   (even with different wording), collapse them into one entry. Mark it as
   **consensus** — consensus findings carry higher confidence and should be
   prioritized.

2. **Escalate severity** — If reviewers disagree on severity for the same issue,
   take the **higher** severity. Example: Codex says CRITICAL, Gemini says
   IMPORTANT → final severity is CRITICAL.

3. **Group by severity** — Present all CRITICAL findings first, then IMPORTANT,
   MINOR, and SUGGESTION.

4. **Attribute sources** — For each finding, note which model(s) identified it
   (e.g. "Gemini + Sonnet" or "Codex only").

5. **Flag contradictions** — If one reviewer says something is a problem and
   another explicitly says it is fine (or the design already handles it), call
   this out as a **contradiction** and include both arguments. The human
   decision-maker resolves contradictions.

6. **Produce the summary table** — The final output must include this table at
   the top of the report:

```markdown
## Review Summary

| # | Severity | Issue (one-line) | Artifact | Found by | Consensus? | Action |
|---|----------|-----------------|----------|----------|------------|--------|
| 1 | CRITICAL | Unbounded retry in data-sync | specs/data-sync.md | Gemini, Codex, Sonnet | ✅ | Add backoff + circuit breaker |
| 2 | CRITICAL | Missing auth check on /admin | specs/api.md | Codex | — | Add middleware guard |
| 3 | IMPORTANT | Task 4 depends on Task 7 | tasks.md | Gemini, Sonnet | ✅ | Reorder tasks |
| … | … | … | … | … | … | … |
```

7. **Append the full findings** — Below the summary table, include the full
   detail of each finding (artifact, issue, impact, fix) from the merge.

8. **Write the report** to `{{OPENSPEC_DIR}}/review-report.md`.

---

## 3. Agent Dispatch Instructions

Use the `task` tool to launch **three parallel `general-purpose` agents** in
`background` mode. Each agent receives the same review prompt (Section 1 above)
with `{{OPENSPEC_DIR}}` replaced by the actual path.

The review panel is **dynamic** — always includes Gemini plus models that
differ from the session model. Avoid redundant models from the same family.

| Session model (spec writer) | Reviewers |
|-----------------------------|-----------|
| Opus (`claude-opus-4.6`) | `gemini-3-pro-preview`, `gpt-5.3-codex`, `claude-sonnet-4` |
| Codex (`gpt-5.3-codex`) | `gemini-3-pro-preview`, `claude-opus-4.6`, `gpt-5.1-codex-mini` |
| Other | `gemini-3-pro-preview`, `gpt-5.3-codex`, `claude-opus-4.6` |

### Orchestration sequence

```
1. Resolve {{OPENSPEC_DIR}} from the user's context or default to .openspec/
2. Launch all 3 agents in parallel (background mode)
3. Use read_agent / list_agents to poll until all 3 complete
4. Collect the three review outputs
5. Run the Synthesis procedure (Section 2) to merge findings
6. Write the consolidated report to {{OPENSPEC_DIR}}/review-report.md
7. Present the summary table to the user
```

### Example task tool calls

```javascript
// Example: Opus session → 3 reviewers (Gemini, Codex 5.2, Sonnet)
task({ agent_type: "general-purpose", mode: "background",
  model: "gemini-3-pro-preview", description: "Gemini spec review",
  prompt: `${REVIEW_PROMPT}\n\nOpenSpec directory: ${openspecDir}` })
task({ agent_type: "general-purpose", mode: "background",
  model: "gpt-5.3-codex", description: "Codex spec review",
  prompt: `${REVIEW_PROMPT}\n\nOpenSpec directory: ${openspecDir}` })
task({ agent_type: "general-purpose", mode: "background",
  model: "claude-sonnet-4", description: "Sonnet spec review",
  prompt: `${REVIEW_PROMPT}\n\nOpenSpec directory: ${openspecDir}` })

// Example: Codex session → 3 reviewers (Gemini, Opus, Codex-Mini)
task({ agent_type: "general-purpose", mode: "background",
  model: "gemini-3-pro-preview", description: "Gemini spec review",
  prompt: `${REVIEW_PROMPT}\n\nOpenSpec directory: ${openspecDir}` })
task({ agent_type: "general-purpose", mode: "background",
  model: "claude-opus-4.6", description: "Opus spec review",
  prompt: `${REVIEW_PROMPT}\n\nOpenSpec directory: ${openspecDir}` })
task({ agent_type: "general-purpose", mode: "background",
  model: "gpt-5.1-codex-mini", description: "Codex-Mini spec review",
  prompt: `${REVIEW_PROMPT}\n\nOpenSpec directory: ${openspecDir}` })
```

After all three return, invoke synthesis in the main conversation context.
