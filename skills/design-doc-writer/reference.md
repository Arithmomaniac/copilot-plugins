# Reference: Section Formats and Decision Records

## Document Section Order

This order is fixed from Stage 1. Sections are added progressively across stages — never reordered.

```
# Design: <Title>

## Summary                    ← Stage 0
## Scope                      ← Stage 0
## Background                 ← Stage 1 (brief) + Appendix (detailed)
## Problem Statement           ← Stage 0
## Requirements                ← Stage 0
## High-Level Design           ← Stage 1
## Design Decisions            ← Stage 1 (stubs) → Stage 2 (full)
## Phases                      ← Stage 2
## Open Questions              ← Stage 1
## References                  ← Stage 2
## Appendix                    ← Stage 2
```

## Section Formats

### Summary

3–5 sentences covering:
1. What system/codebase this affects
2. What's broken (one sentence)
3. Proposed approach (one sentence)
4. Current status (phase, PR links)

```markdown
## Summary

ZTS integration tests use mode-based attributes that conflate where tests run,
what dependencies get injected, and execution filtering. This document proposes
capability-based declarations: tests state minimum resource fidelity, the
infrastructure provides what it can, and the framework auto-skips mismatches.
Phase 0 (centralized config record) is in review — PR 14870162.
```

### Scope

Two bullet lists. The out-of-scope list is more important — it prevents creep.

```markdown
## Scope

**In scope:** new attribute vocabulary, centralized TestModeConfiguration record,
capability-based execution filtering.

**Out of scope:** xUnit v3 migration, scale-test infrastructure, Aspire hosting model.
```

### Problem Statement

Numbered entries. Each entry is concrete (not abstract), includes evidence where possible, and maps to at least one Design Decision.

```markdown
## Problem Statement

1. **Mode declaration is the wrong abstraction:** Tests declare which modes
   they run in rather than what resources they need. `LocalWithEmulator`
   means different things on DevMachine vs BuildPipeline. *(→ D1)*

2. **Tests run at unintended fidelity without warning:** A component test
   designed for emulator fidelity silently runs against a mock on
   BuildPipeline. *(→ D2, D3)*
```

### Design Decision Record Format

Fixed from Stage 1. Grows across stages:

**Stage 1 (stub):**
```markdown
### D1 — Capability Attribute API Shape

- **Option A — Named params on ConfigurableFact**
- **Option B — New CapabilityFact sibling**
- **Option C — Stackable RequiresServiceBus attributes**
```

**Stage 2 (full):**
```markdown
### D1 — Capability Attribute API Shape

*Solves: Problem 1 (wrong abstraction), Problem 2 (unreadable config chain)*

- **Option A — Named params on ConfigurableFact** ✅
  Single attribute, additive migration, no new types.
  Con: noisy autocomplete with 7 service params.
- **Option B — New CapabilityFact sibling**
  Property initializer syntax; zero risk to existing tests.
  Con: two parallel attribute families.
- **Option C — Stackable RequiresServiceBus attributes**
  Cleanest callsite, zero blast radius per service.
  Con: requires custom IXunitTestCaseDiscoverer.

**Chose A** — additive migration matters more than callsite cleanliness.
```

**Markers:**
- `✅` = decided
- `⚠️` = tentative (state what would resolve)
- *(no marker)* = unresolved (state what information is needed)

### Before/After Comparison Tables

Use identical column structure for current state and proposed state. Place in Background (current) and HLD (proposed).

```markdown
### De-facto test categories (current)

| Category | What it tests | How currently expressed | Problem |
|----------|--------------|------------------------|---------|
| Unit     | In-memory logic | [ConfigurableFact] | None |
| Component | Single adapter | LocalWithEmulator | Silent mock fallback |

### De-facto categories in the new model

| Category | What it tests | Floor declaration | Runs on |
|----------|--------------|-------------------|---------|
| Unit     | In-memory logic | *(none)* | DevMachine + BuildPipeline |
| Component | Single adapter | Emulator or Real | DevMachine + BuildPipeline/DVT |
```

### Phase Format

Each phase names the decisions it implements and includes a status marker.

```markdown
### Phase 1 — Scope vocabulary and attribute model

*Implements: D1-A (named params), D2-A (skip all exclusions)*

Phase 1 implements the capability attribute model — class-level
ConfigurableFact declarations with named capability parameters.

- **Pilot migration.** Convert representative tests. Validate with TestConfigurationReport.
- **LWE pass on BuildPipeline.** Tests with serviceBus: Emulator floor skip automatically.
```

### Open Question Format

OQs are distinct from DDs — they don't yet have option spaces.

```markdown
### OQ1: Scale environment scope

`TestExecutionEnvironments.Scale` exists but is excluded from `Anywhere`.
Should capability declarations address scale scenarios, or is scale testing
a separate concern?

**Status:** Unresolved. No action needed before Phase 1.
```

## Flow Diagram Guidelines

- Use ASCII art or mermaid — both survive markdown rendering and ADO wiki
- Show the two key flows: "does this test run?" and "what does it run against?"
- Label decision points with the DD they relate to
- Keep diagrams ≤25 lines — longer diagrams belong in Appendix
