---
name: design-doc-writer
description: >-
  Guide writing design documents through a staged workflow — problem validation, design skeleton,
  decision resolution, editorial hardening. Prevents premature expansion and structural churn.
  Use when the user says "write a design doc", "design document", "create a design proposal",
  "start a design", "new design doc", "RFC", "tech spec", or "document a design decision".
---

# Design Doc Writer

A staged workflow for writing design documents that minimizes unnecessary churn. Not a template — the skill tells you **when** to add detail, not just **where**.

## Core Insight

> Documents get rewritten because the author didn't know when to add detail — not because the design changed. The idea is usually stable from the first sketch. What churns is: how much context to front-load, when to elaborate options, what format to use for decisions, and what to exclude.

## Style Rules for All LLM-Generated Prose

Every section the LLM writes must be:

- **Succinct** — one sentence where one suffices. No hedge-padding ("it's worth noting that..."), no throat-clearing.
- **Human-readable** — a teammate opening the doc cold understands each section. Define terms on first use. No acronym soup.
- **Unambiguous** — prefer tables and diagrams over narrative. Each sentence has exactly one interpretation. Flag genuine ambiguity explicitly ("this depends on D2 resolution") rather than hiding it in soft language.
- **Churn-aware** — some iteration is healthy. Decisions and open questions evolve. But the *format* they evolve within is stable from the start.

## Stages

### Stage 0 — Problem Validation (≤1 page)

Write **only** these sections:

1. **Summary** — 3–5 sentences: what's broken, proposed approach, current status.
2. **Scope** — In-scope / Out-of-scope. Name adjacent concerns explicitly so they don't creep in later.
3. **Problem Statement** — Concrete, numbered. No solutioning. Each problem must later map to a Design Decision or Open Question.
4. **Requirements** — 3–5 bullets. Functional + non-functional.

**Rules:**
- No HLD, no phases, no diagrams yet.
- The ServiceBus `FullyQualifiedName!~` YAML hack is a good example of a concrete problem statement entry — specific, evidenced, motivating.
- Share with 1–2 stakeholders. Get sign-off on the problem before writing solutions.

**Gate:** Stakeholder confirms the problems are the right problems. Do NOT proceed to Stage 1 until this gate passes.

### Stage 1 — Design Skeleton (2–3 pages)

Add these sections:

5. **Background** — ≤15 lines of causal narrative. Why the current system is broken. Detailed current-system diagrams go in Appendix.
6. **HLD** — Central principle (1 paragraph) + one paragraph per major component.
7. **Design Decision stubs** — Question title + 2–3 option names. No elaboration yet (prevents concept elaboration before validation).
8. **Open Questions** — Things you know you don't know. Separate from Design Decisions (DDs have options; OQs don't yet).
9. **Before/After comparison** — Show current state and proposed state using the same table/diagram structure. This pattern survives every rewrite.
10. **Flow diagrams** — ASCII art or mermaid for runtime behavior. Diagrams resist narrative drift.

**Rules:**
- No prose longer than 3 sentences per subsection.
- No pros/cons tables yet.
- Each Problem Statement entry maps to exactly one DD or OQ. If a problem doesn't motivate a decision, cut it. If a decision has no problem, add the problem or cut the decision.
- Decision format is stable from this point: `### D1 — <Question Title>` with options listed as bullets.

**Gate:** Review with design reviewers. Validate the decision *questions* are the right ones. Validate the option space is complete.

### Stage 2 — Decision Resolution (full doc)

Expand these sections:

11. For each **Design Decision**:
    - 1–2 sentence description per option
    - Compact pros/cons (max 3 each, one line per item)
    - Choice + rationale (or: "Unresolved — needs X to decide")
    - Link back to the Problem Statement entry it solves

12. **Phases** — Implementation sequence. Each phase names which decisions it implements. Include rollback/independence notes where relevant.

13. **References** — Source files, ADO work items, related docs, prior art.

14. **Appendix** — Detailed tables, matrices, old-system diagrams, compatibility matrices. Things that support but don't drive.

**Rules:**
- Appendix-first for background detail. Readers shouldn't wade through 150 lines of history before reaching the design.
- Narrative is connective tissue only; structure carries information.
- No content unrelated to an in-scope problem. If it's not in the Problem Statement, it doesn't belong.
- Phase implementation detail should be proportional to confidence. High-confidence phases get step-level detail. Low-confidence phases get 1–2 sentence summaries that will be expanded when the phase begins.

### Stage 3 — Editorial Hardening

15. Remove orphaned content (sections that no Problem Statement entry motivates).
16. Verify before/after mirroring is consistent.
17. Run multi-model review for coherence and internal consistency (use tri-review skill if available).
18. Add status markers: `[WIP]`, decided/tentative/open per decision.
19. Compress: if a table says it, delete the prose that says the same thing.
20. Verify every cross-reference resolves (Problem → Decision → Phase links).

## Anti-Patterns to Prevent

| ID | Anti-pattern | What happens | How the skill prevents it |
|----|-------------|--------------|--------------------------|
| A1 | Template-first writing | Filling placeholder sections before understanding the domain | Stage 0 writes problem content, not template scaffolding |
| A2 | Premature expansion | Writing 600 lines then deleting 340 | Stage gates prevent detail before validation |
| A3 | Concept elaboration before validation | Elaborate pros/cons for an option nobody questioned | No pros/cons until Stage 2 (after questions validated) |
| A4 | Structure before insight | Reorganizing sections 3× because ordering was imposed too early | Section order is prescribed and stable from Stage 1 |
| A5 | Late stakeholder input | Biggest rewrites came from first reviewer | Stage 0 gate requires review before any HLD |
| A6 | Orthogonal creep | Adjacent concerns sneak in | Scope section names exclusions; Problem → Decision traceability catches orphans |
| A7 | Decision format instability | Dilemmas → merged into Phases → extracted back out | Decision format (`### D1 — Title`) is fixed from Stage 1 |
| A8 | Narrative where structure suffices | 200 lines of prose replaced by one table | Style rule: prefer tables and diagrams |

## Patterns to Apply

| ID | Pattern | When to use |
|----|---------|-------------|
| P1 | Evidence-grounded rewrites | Use meeting transcripts, chat logs, PR comments as rewrite inputs |
| P2 | Before/After structural mirroring | Show current and proposed state with identical columns/structure |
| P3 | Flow diagrams (ASCII/mermaid) | For any runtime behavior — stable across rewrites |
| P4 | Multi-model review | Stage 3 — different models catch different blind spots |
| P5 | Problem → Decision traceability | Every problem maps to a decision; every decision traces to a problem |
| P6 | Stable decision record format | `### D1 — Title` + options + choice + rationale |
| P7 | Scope as explicit exclusion | Name what's out, not just what's in |

## Section Reference

For detailed section formats, decision record templates, and examples, see [reference.md](reference.md).

For per-stage quality gate checklists, see [checklist.md](checklist.md).
