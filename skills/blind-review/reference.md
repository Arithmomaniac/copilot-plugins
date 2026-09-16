> Created/edited by GitHub Copilot with human review/feedback by avilevin.

# Blind Review Reference

Read this file when selecting reviewer models or launching a blind-review subagent.

## Model selection

Blind review benefits more from independence and repeatability than maximum single-call depth. The snapshot below was refreshed from `aa-pareto` on September 1, 2026. Use the `coding` profile for code artifacts and the artifact's closest task profile for non-code reviews.

| Mode | GPT reviewer | Effort | Use |
|---|---|---|---|
| Light | `gpt-5.6-sol` | `low` | Quick rechecks and straightforward artifacts |
| Standard | `gpt-5.6-sol` | `high` | Default single blind reviewer and GPT slot in a triple review |
| Maximum depth | `gpt-5.6-sol` | `xhigh` | Especially difficult or high-risk artifacts when explicitly requested |

Do not use Luna or Terra as the normal blind reviewer. Sol provides the strongest current OpenAI coding frontier; use its effort level as the review-depth control.

For a triple blind review, use the current `tri-review` skill's three-family selection, active-family exclusion, and maximum-depth rules, but give each reviewer the blind-review rubric.

## Reviewer prompt

> You are an uninvolved third-party reviewer encountering this artifact for the first time. Review only the supplied primary artifact, audience, purpose, artifact roles, depth boundary, essential domain facts, and rubric. If a reference or answer key is supplied, record your independent interpretation of the primary artifact before comparing it with the reference. Do not infer unstated intent or reward decisions based on authoring history. Identify only material places where an outside reader would misunderstand the artifact, be misled, or be unable to act. Do not ask a proposal or primer to resolve implementation details it explicitly defers. Do not edit the artifact. For each finding, provide its location, the concrete misunderstanding, why it blocks the artifact's purpose, and the smallest preferably subtractive correction. If no material findings remain, return `CLEAR`.
