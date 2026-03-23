---
name: design-doc-writer
description: >-
  Reference formats and quality gate checklists for the design-doc-writer agent.
  Auto-loads when design doc work is active. Provides section templates, decision
  record formats, and per-stage checklists. Use when the user says write a design
  doc, design document, create a design proposal, start a design, new design doc,
  RFC, tech spec, document a design decision, restructure this design doc, improve
  this design doc, review this design doc, or this doc needs work.
---

# Design Doc Writer — Reference Skill

> This skill provides reference formats for the **design-doc-writer agent**. The agent orchestrates the staged workflow (Stage 0–3 with quality gates); this skill provides section templates, decision record formats, and quality gate checklists as progressive-disclosure reference material.

## Style Rules for All LLM-Generated Prose

Every section must be:

- **Succinct** — one sentence where one suffices. No hedge-padding ("it's worth noting that..."), no throat-clearing.
- **Human-readable** — a teammate opening the doc cold understands each section. Define terms on first use. No acronym soup.
- **Unambiguous** — prefer tables and diagrams over narrative. Each sentence has exactly one interpretation. Flag genuine ambiguity explicitly ("this depends on D2 resolution") rather than hiding it in soft language.
- **Churn-aware** — some iteration is healthy. Decisions and open questions evolve. But the *format* they evolve within is stable from the start.

## Anti-Patterns

| ID | Anti-pattern | What happens | How to prevent it |
|----|-------------|--------------|-------------------|
| A1 | Template-first writing | Filling placeholder sections before understanding the domain | Stage 0 writes problem content, not template scaffolding |
| A2 | Premature expansion | Writing 600 lines then deleting 340 | Stage gates prevent detail before validation |
| A3 | Concept elaboration before validation | Elaborate pros/cons for an option nobody questioned | No pros/cons until Stage 2 (after questions validated) |
| A4 | Structure before insight | Reorganizing sections 3× because ordering was imposed too early | Section order is prescribed and stable from Stage 1 |
| A5 | Late stakeholder input | Biggest rewrites came from first reviewer | Stage 0 gate requires review before any HLD |
| A6 | Orthogonal creep | Adjacent concerns sneak in | Scope section names exclusions; Problem → Decision traceability catches orphans |
| A7 | Decision format instability | Dilemmas → merged into Phases → extracted back out | Decision format (`### D1 — Title`) is fixed from Stage 1 |
| A8 | Narrative where structure suffices | 200 lines of prose replaced by one table | Style rule: prefer tables and diagrams |

## Patterns

| ID | Pattern | When to use |
|----|---------|-------------|
| P1 | Evidence-grounded rewrites | Use meeting transcripts, chat logs, PR comments as rewrite inputs |
| P2 | Before/After structural mirroring | Show current and proposed state with identical columns/structure |
| P3 | Flow diagrams (ASCII/mermaid) | For any runtime behavior — stable across rewrites |
| P4 | Multi-model review | Stage 3 — different models catch different blind spots |
| P5 | Problem → Decision traceability | Every problem maps to a decision; every decision traces to a problem |
| P6 | Stable decision record format | `### D1 — Title` + options + choice + rationale |
| P7 | Scope as explicit exclusion | Name what's out, not just what's in |

## Section Formats and Templates

For detailed section formats, decision record templates, and examples, see [reference.md](reference.md).

## Quality Gate Checklists

For per-stage quality gate checklists (Stage 0→1, 1→2, 2→3, and completion), see [checklist.md](checklist.md).
