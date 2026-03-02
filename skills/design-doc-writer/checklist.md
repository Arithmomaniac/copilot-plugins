# Design Doc Quality Gates

Verify these before advancing to the next stage. Items are ordered by importance.

## Stage 0 → Stage 1 Gate

- [ ] Problem Statement has 2–5 numbered, concrete entries
- [ ] Each problem is evidenced (link, example, or observable symptom) — not abstract
- [ ] Scope names at least 2 out-of-scope items
- [ ] Summary is ≤5 sentences and a reader can understand the proposal without reading further
- [ ] Requirements are testable (you could verify each one is met after implementation)
- [ ] **Stakeholder has reviewed and agreed the problems are the right problems**
- [ ] No solution detail anywhere — if you catch yourself describing *how*, stop

## Stage 1 → Stage 2 Gate

- [ ] HLD central principle is one paragraph
- [ ] Every Problem Statement entry maps to at least one DD or OQ
- [ ] Every DD has 2–3 named options (no elaboration yet)
- [ ] Before/After comparison exists (if applicable) — same columns for both
- [ ] Flow diagrams are present for runtime behavior
- [ ] Background is ≤15 lines inline (detail in Appendix if needed)
- [ ] No pros/cons tables yet — if you find yourself writing "Pro: ..." you're ahead of stage
- [ ] **Design reviewer has validated the decision questions are the right ones**

## Stage 2 → Stage 3 Gate

- [ ] Each DD has: options with 1–2 sentence descriptions, pros/cons (≤3 each), choice or "unresolved + what resolves it"
- [ ] Each DD links back to Problem Statement entries it solves
- [ ] Phases name which DDs they implement
- [ ] Phase detail is proportional to confidence (uncertain phases = 1–2 sentences, not step tables)
- [ ] References include source files, ADO work items, related docs
- [ ] Appendix has detailed tables/matrices (not inline)
- [ ] No orphaned content — every section traces to a Problem Statement entry

## Stage 3 Completion

- [ ] Multi-model review completed (if available — tri-review or equivalent)
- [ ] All cross-references resolve (Problem → DD → Phase)
- [ ] No duplicate information — if a table says it, the prose doesn't repeat it
- [ ] Status markers present: `[WIP]` in title, ✅/⚠️ on decisions
- [ ] Terms defined on first use
- [ ] A teammate opening this doc cold can understand the Summary + Problem Statement in <2 minutes

## Common Rejection Reasons (things reviewers will flag)

| What they say | What it means | Skill anti-pattern |
|---------------|---------------|-------------------|
| "This is too long" | Premature expansion — detail before validation | A2 |
| "I don't understand why we need this" | Problem statement is abstract, not concrete | Stage 0 gate failed |
| "What about X?" (where X is adjacent) | Scope didn't name exclusions | A6 |
| "Why did you choose A?" | Decision lacks rationale | Stage 2 format incomplete |
| "This section doesn't belong here" | Orthogonal content crept in | A6 — not traceable to Problem Statement |
| "Wait, you already decided this?" | Decision presented as settled without review | A5 — stakeholder input too late |
