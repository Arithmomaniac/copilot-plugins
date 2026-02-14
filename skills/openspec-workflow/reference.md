# OpenSpec Format Reference

> This is a detailed format reference for AI agents executing the OpenSpec workflow.
> SKILL.md references this file for artifact format rules, pitfalls, and examples.

---

## 1. OpenSpec Format Rules

You MUST create artifacts in **dependency order**:

```
proposal.md → specs/*.md → design.md → tasks.md
```

**Why this order matters:**

1. **proposal.md** comes first — it defines the scope, motivation, and capabilities. Everything downstream is bounded by the proposal.
2. **specs/*.md** come second — they define the observable behavior and acceptance criteria for each capability. Specs are the source of truth for *what* the system does.
3. **design.md** comes third — it explains *how* the system achieves what the specs require. Design decisions must be informed by and traceable to spec requirements. Writing design before specs leads to contradictions.
4. **tasks.md** comes last — tasks are derived from specs + design. Each task implements specific spec requirements using the architecture defined in design.md.

**Cross-referencing rule:** Each artifact references the previous ones. Specs reference the proposal's capabilities. Design references spec requirements (R1, R2...). Tasks reference both spec requirements and design decisions (D1, D2...).

---

## 2. Artifact Format Specifications

### proposal.md

Keep this to **1 page max**. If a `plan.md` already exists in the workspace, reuse its content as a starting point.

**Required sections:**

```markdown
# Proposal: <Title>

## Motivation
Why this change is needed. What problem it solves. 1-2 paragraphs max.

## What Changes
High-level description of what will be different. No implementation details.

## Capabilities
- Capability 1: brief description
- Capability 2: brief description
- Capability 3: brief description

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
```

**Rules:**
- Capabilities become the basis for individual spec files — one spec per capability.
- Acceptance criteria are project-level (not per-capability — those go in specs).
- Do NOT include architecture or implementation approach here.

---

### specs/*.md (one file per capability)

Name files by capability slug: `command-execution.md`, `user-auth.md`, `error-handling.md`.

**Required format:**

```markdown
# Spec: <Capability Name>

> References: proposal.md — Capability N

## Overview
Brief description of what this capability does.

## Requirements

### R1: <Requirement title>
<Description of the requirement.>

**Scenarios:**

**R1.S1: <Happy path scenario name>**
- GIVEN <precondition>
- WHEN <action>
- THEN <expected outcome>

**R1.S2: <Error/edge case scenario name>**
- GIVEN <precondition>
- WHEN <action with error condition>
- THEN <expected error behavior>

### R2: <Requirement title>
...
```

**Rules:**
- Label requirements sequentially: R1, R2, R3...
- Every requirement MUST have at least one happy-path scenario and one error/edge-case scenario.
- Scenarios use strict GIVEN/WHEN/THEN format.
- Be specific: name exact field names, data types, error messages, HTTP status codes.
- Spec cross-component interactions explicitly (e.g., "THEN module B receives event X with payload Y").
- Define API contracts inline: parameter types, return types, error payloads.

---

### design.md

**Required format:**

```markdown
# Design

> References: proposal.md, specs/*.md

## Architecture Overview
High-level description. ASCII diagram if helpful.

## Key Decisions

### D1: <Decision title>
- **Choice:** What was decided
- **Alternatives considered:**
  - Alternative A: why rejected
  - Alternative B: why rejected
- **Rationale:** Why this choice best satisfies the spec requirements (reference R-numbers)

### D2: <Decision title>
...

## Trade-offs
- Trade-off 1: what was gained vs. what was sacrificed
- Trade-off 2: ...

## Risks and Mitigations
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Risk 1 | High/Med/Low | High/Med/Low | How to mitigate |
```

**Rules:**
- Label decisions sequentially: D1, D2, D3...
- Every decision MUST reference which spec requirements it addresses.
- Include at least one alternative considered per decision (even if it's "do nothing").
- Architecture diagrams should be ASCII art for portability.
- Do NOT introduce capabilities or behaviors not covered by specs.

---

### tasks.md

**Required format:**

```markdown
# Implementation Tasks

> References: proposal.md, specs/*.md, design.md

## Phase 1: <Phase name>

### T1.1: <Task title>
- **Implements:** R1, R2 (from <spec-file>.md)
- **Design:** D1
- **Dependencies:** None
- **Work:** Description of what to build/change.
- **Acceptance criteria:**
  - [ ] Criterion 1 (verifiable)
  - [ ] Criterion 2 (verifiable)

### T1.2: <Task title>
- **Implements:** R3 (from <spec-file>.md)
- **Design:** D1, D2
- **Dependencies:** T1.1
- **Work:** Description of what to build/change.
- **Acceptance criteria:**
  - [ ] Criterion 1

## Phase 2: <Phase name>

### T2.1: <Task title>
...
```

**Rules:**
- Tasks are grouped by phase. Phases represent logical milestones.
- Label tasks as T{phase}.{sequence}: T1.1, T1.2, T2.1, T2.2...
- Every task MUST reference which spec requirement(s) it implements.
- Every task MUST reference which design decision(s) it follows.
- Dependencies between tasks must be explicit. If T1.2 depends on T1.1, say so.
- Acceptance criteria must be verifiable — an agent should be able to check each one programmatically or by inspection.

---

## 3. Common Pitfalls

These are lessons learned from real OpenSpec sessions. Avoid these mistakes:

### Ordering Violations
- **Don't write design.md before specs.** The design will make architectural commitments that contradict or under-specify behaviors later defined in specs. Always let specs drive the design.

### Incomplete Specifications
- **Include negative/error scenarios, not just happy paths.** Every requirement needs at least one error scenario. "What happens when input is invalid?" "What if the dependency is unavailable?" These are where bugs hide.
- **Spec cross-component interactions explicitly.** Don't assume it's obvious. Write: "After module A completes operation X, module B observes state Y via mechanism Z." Vague inter-component behavior leads to integration bugs.
- **Define API contracts completely.** Specify parameter types, return types, error payloads, and status codes. "Returns an error" is insufficient — specify "Returns HTTP 400 with body `{ "error": "invalid_input", "field": "email" }`".

### False Assumptions
- **Don't claim backward compatibility without verifying.** Example from a real session: an agent assumed Python tuple unpacking would auto-default missing values — it doesn't. `a, b, c = (1, 2)` raises `ValueError`. If you claim compatibility, prove it with a specific scenario.
- **Check for contradictions between artifacts after writing.** After completing all artifacts, do a cross-reference pass: does every spec requirement have a task? Does every design decision trace to a spec? Does the proposal scope match what the specs cover?

### Scope Drift
- **Tasks must trace back to specs.** If you find yourself writing a task that doesn't map to any spec requirement, either the spec is missing a requirement or the task is out of scope. Fix the spec first.

---

## 4. Real Examples

### Example: proposal.md

```markdown
# Proposal: CLI Plugin System

## Motivation
Users need to extend the CLI with custom commands without modifying core code.
Third-party integrations are currently hard-coded, creating maintenance burden.

## What Changes
The CLI will support dynamically loaded plugins that register commands at startup.

## Capabilities
- Plugin discovery: CLI finds and loads plugins from a configured directory
- Command registration: Plugins register commands with the CLI's command router
- Plugin lifecycle: Plugins have init/teardown hooks for resource management

## Acceptance Criteria
- [ ] Existing built-in commands work unchanged
- [ ] A sample plugin can be loaded and executed
- [ ] Invalid plugins produce clear error messages
```

### Example: specs/plugin-discovery.md

```markdown
# Spec: Plugin Discovery

> References: proposal.md — Capability 1 (Plugin discovery)

## Overview
The CLI discovers and loads plugin modules from a configured plugin directory
at startup.

## Requirements

### R1: Load plugins from configured directory
The CLI reads the plugin directory path from its configuration and attempts
to load all valid plugin modules found there.

**Scenarios:**

**R1.S1: Plugins loaded successfully**
- GIVEN the config file contains `plugin_dir: "./plugins"`
- AND the directory `./plugins` contains `hello.py` with a valid plugin class
- WHEN the CLI starts
- THEN `hello.py` is loaded and its `PluginMeta.name` appears in the plugin registry

**R1.S2: Plugin directory does not exist**
- GIVEN the config file contains `plugin_dir: "./missing"`
- AND the directory `./missing` does not exist
- WHEN the CLI starts
- THEN the CLI logs warning "Plugin directory not found: ./missing"
- AND the CLI continues startup with zero plugins loaded

**R1.S3: Plugin has syntax error**
- GIVEN `./plugins/broken.py` contains a Python syntax error
- WHEN the CLI starts
- THEN the CLI logs error "Failed to load plugin broken.py: SyntaxError at line N"
- AND all other valid plugins are still loaded

### R2: Plugin module interface
Each plugin module must export a class implementing the `Plugin` interface.

**Scenarios:**

**R2.S1: Valid plugin class**
- GIVEN `hello.py` exports class `HelloPlugin` with methods `init(ctx)` and `teardown()`
- AND `HelloPlugin` has attribute `meta` of type `PluginMeta`
- WHEN the CLI loads `hello.py`
- THEN `HelloPlugin` is instantiated and registered

**R2.S2: Module missing Plugin class**
- GIVEN `utils.py` exists in the plugin directory but exports no `Plugin` subclass
- WHEN the CLI attempts to load `utils.py`
- THEN the CLI logs warning "No Plugin subclass found in utils.py"
- AND `utils.py` is skipped
```

### Example: design.md (excerpt)

```markdown
# Design

> References: proposal.md, specs/plugin-discovery.md, specs/command-registration.md

## Architecture Overview

┌─────────┐     ┌──────────────┐     ┌─────────────┐
│  CLI     │────▶│ PluginLoader │────▶│ Plugin Dir  │
│  Main    │     │              │     │  ./plugins/ │
└────┬─────┘     └──────┬───────┘     └─────────────┘
     │                  │
     │           ┌──────▼───────┐
     └──────────▶│ CommandRouter │
                 │  (registry)  │
                 └──────────────┘

## Key Decisions

### D1: Use importlib for dynamic loading
- **Choice:** Use Python's `importlib.util.spec_from_file_location` to load plugins
- **Alternatives considered:**
  - Entry points (pkg_resources): Requires plugins to be installed packages — too
    heavyweight for a directory of .py files
  - exec()/eval(): Security risk and no proper module semantics
- **Rationale:** importlib gives full module semantics, proper error handling, and
  works with plain .py files. Satisfies R1 (load from directory) without requiring
  plugin packaging.

### D2: Fail-soft plugin loading
- **Choice:** Log errors for broken plugins but continue loading others
- **Alternatives considered:**
  - Fail-fast (abort on any plugin error): Too disruptive for users with many plugins
- **Rationale:** Satisfies R1.S2 and R1.S3 — the CLI must remain functional even
  when individual plugins fail.

## Trade-offs
- Fail-soft loading means a broken plugin could go unnoticed if the user doesn't
  check logs. Accepted because hard failure is worse for user experience.
- importlib ties us to file-based plugins. If we later want remote/packaged plugins,
  we'll need a loader abstraction. Acceptable for v1 scope.

## Risks and Mitigations
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Malicious plugin code execution | High | Low | Document that plugins run with full CLI permissions; add optional allowlist in v2 |
| Plugin load order dependencies | Med | Med | Load in alphabetical order; document that plugins must not depend on load order |
```

### Example: tasks.md (excerpt)

```markdown
# Implementation Tasks

> References: proposal.md, specs/plugin-discovery.md, specs/command-registration.md, design.md

## Phase 1: Core Plugin Infrastructure

### T1.1: Implement PluginLoader
- **Implements:** R1, R2 (from plugin-discovery.md)
- **Design:** D1, D2
- **Dependencies:** None
- **Work:** Create `plugin_loader.py` with `PluginLoader` class. Implement
  `load_all(plugin_dir) -> list[Plugin]` using importlib. Handle missing
  directory (warning + empty list), syntax errors (log + skip), and missing
  Plugin subclass (warning + skip).
- **Acceptance criteria:**
  - [ ] `load_all("./plugins")` returns loaded Plugin instances
  - [ ] Missing directory logs warning, returns empty list
  - [ ] Broken .py file is skipped with error logged
  - [ ] Module without Plugin subclass is skipped with warning

### T1.2: Integrate PluginLoader into CLI startup
- **Implements:** R1.S1 (from plugin-discovery.md)
- **Design:** D1
- **Dependencies:** T1.1
- **Work:** Modify `cli.py` main() to read `plugin_dir` from config, call
  `PluginLoader.load_all()`, and register returned plugins.
- **Acceptance criteria:**
  - [ ] CLI starts with plugins loaded from configured directory
  - [ ] CLI starts normally when no plugin_dir is configured

## Phase 2: Command Registration

### T2.1: Implement plugin command registration
- **Implements:** R1, R2 (from command-registration.md)
- **Design:** D1
- **Dependencies:** T1.1, T1.2
- **Work:** Extend `CommandRouter` to accept commands from plugins via
  `register_plugin_commands(plugin)`. Each plugin's `get_commands()` returns
  a list of `Command` objects added to the router.
- **Acceptance criteria:**
  - [ ] Plugin commands appear in `--help` output
  - [ ] Plugin commands are callable from the CLI
  - [ ] Duplicate command names produce a clear error
```
