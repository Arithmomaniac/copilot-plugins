---
name: openspec-workflow
description: Reference instructions for the OpenSpec spec-driven development workflow. Not invoked directly — use the openspec-planner agent via /agent to run this workflow.
---

# OpenSpec Workflow

A 4-stage specification-driven development workflow that produces high-quality, multi-model-reviewed specs before implementation. The stages are: **Explore → Write → Review → Iterate**. Each stage has a user checkpoint before proceeding.

## Quick Start

When the user says "write an openspec for [feature]":

1. Create `files/openspec/` in the session folder
2. Research the codebase (Stage 0)
3. Generate all four artifacts in order (Stage 1)
4. Launch 3-model parallel review (Stage 2)
5. Present findings and iterate (Stage 3)

## Stages

### Stage 0: Explore

Research the codebase before writing anything.

1. Ask the user for a description of the feature or change (if not already provided)
2. Grep for relevant patterns, interfaces, and existing implementations
3. Read key files: entry points, configuration, related modules
4. Identify constraints: dependencies, platform requirements, existing contracts
5. Summarize findings for the user in a brief report

**Checkpoint:** Present the scope summary and wait for user confirmation before proceeding. The user may refine scope, add constraints, or redirect.

### Stage 1: Write OpenSpec Artifacts

Create the session folder structure and generate artifacts in strict dependency order.

#### Setup

1. Create the directory `files/openspec/` (and `files/openspec/specs/` for spec files)
2. If a `plan.md` exists in the workspace, read it — reuse its content as input for the proposal
3. Back up existing `plan.md` to `files/openspec/plan.md.bak` if present

#### Generate artifacts in dependency order

Produce artifacts **in this exact order** — each depends on the previous:

```
proposal.md → specs/*.md → design.md → tasks.md
```

**1. `proposal.md`** — Read the template from [templates/proposal.md](templates/proposal.md). Fill in from the user's description, existing plan, and Stage 0 findings. Keep to 1 page max. Capabilities listed here become individual spec files.

**2. `specs/*.md`** — One file per capability from the proposal. Read the template from [templates/spec.md](templates/spec.md). Name files by capability slug (e.g., `specs/command-execution.md`). Every requirement MUST have at least one happy-path scenario and one error/edge-case scenario using strict GIVEN/WHEN/THEN format. Be specific: name exact field names, data types, error messages, status codes. Spec cross-component interactions explicitly.

**3. `design.md`** — Read the template from [templates/design.md](templates/design.md). Architecture decisions must be informed by and traceable to spec requirements. Reference R-numbers from specs. Include at least one alternative considered per decision. Do NOT introduce capabilities not covered by specs.

**4. `tasks.md`** — Read the template from [templates/tasks.md](templates/tasks.md). Derive tasks from specs + design. Every task must reference which spec requirement(s) it implements and which design decision(s) it follows. Group by phase. Make dependencies between tasks explicit.

#### Post-generation

- Update SQL todos to match the task structure from `tasks.md`:
  ```sql
  INSERT INTO todos (id, title, description, status) VALUES
    ('t1.1', 'Task title', 'Task description referencing specs', 'pending');
  ```
- Add dependency entries to `todo_deps` matching task dependencies

**Checkpoint:** Tell the user artifacts are ready for review. Wait for the user to review (ctrl+y) before proceeding.

For detailed format rules, pitfalls, and examples, see [reference.md](reference.md).

### Stage 2: Multi-Model Review

Follow the instructions in [review-prompts.md](review-prompts.md) precisely.

#### Launch 3 parallel reviewer agents

Use the `task` tool to launch **three `general-purpose` agents in `background` mode**, all in the same response:

The review panel always includes **Gemini** plus models that differ from the session model. The spec writer should never review their own work, and we avoid redundant models from the same family.

| Session model (spec writer) | Reviewers |
|-----------------------------|-----------|
| Opus (`claude-opus-4.6`) | Gemini (`gemini-3-pro-preview`), Codex (`gpt-5.3-codex`), Sonnet (`claude-sonnet-4`) |
| Codex (`gpt-5.3-codex`) | Gemini (`gemini-3-pro-preview`), Opus (`claude-opus-4.6`), Codex-Mini (`gpt-5.1-codex-mini`) |
| Other | Gemini (`gemini-3-pro-preview`), Codex (`gpt-5.3-codex`), Opus (`claude-opus-4.6`) |

To determine the session model, check the `/model` setting or infer from the model name in the conversation context.

Each agent receives:
- The verbatim review prompt from [review-prompts.md](review-prompts.md) Section 1
- The path to the `files/openspec/` directory
- Instructions to also read relevant source code files referenced by the specs

#### Collect and synthesize

1. Use `read_agent` / `list_agents` to poll until all 3 agents complete
2. Collect the three review outputs
3. Run the synthesis procedure from [review-prompts.md](review-prompts.md) Section 2:
   - Deduplicate findings across models (mark consensus items)
   - Escalate severity on disagreements (take the higher severity)
   - Group by severity: CRITICAL → IMPORTANT → MINOR → SUGGESTION
   - Attribute sources (which model(s) found each issue)
   - Flag contradictions for human resolution
4. Produce the summary table and full findings
5. Write the consolidated report to `files/openspec/review-report.md`

**Checkpoint:** Present the summary table to the user. The user decides which findings to address and which to dismiss.

### Stage 3: Iterate

Update artifacts based on the user's decisions from the review.

1. For each finding the user wants to address:
   - Update the relevant artifact(s) in `files/openspec/`
   - Ensure cross-references remain consistent (specs ↔ design ↔ tasks)
2. Update SQL todos if task structure changed
3. Optionally re-run Stage 2 for another review round if the user requests it

**Checkpoint:** The user confirms "ready to implement" before the workflow ends.

### Stage 4: Verify (future)

After implementation is complete, compare code back to specs:

1. Read implemented source code
2. Compare behavior against GIVEN/WHEN/THEN scenarios in specs
3. Flag drift between specification and implementation
4. Report coverage: which spec requirements are implemented, which are missing

> **Note:** This stage is planned but not yet fully implemented.

## Important Notes

- Artifacts live in the session folder (`files/openspec/`), not in the git repo
- The user controls the spec-writing model by switching session models (e.g., `/model gpt-5.3-codex` or `/model claude-opus-4.6`) — no sub-agent needed
- The 3 review models are chosen dynamically to exclude the session model — see Stage 2 table
- Always generate artifacts in dependency order — writing design before specs leads to contradictions
- See [reference.md](reference.md) for common pitfalls, especially:
  - Cross-component interaction gaps
  - Missing error/edge-case scenarios
  - False backward-compatibility assumptions
  - Scope drift (tasks that don't trace to specs)

## How to Invoke

This skill is **not triggered automatically**. Use the `openspec-planner` agent via `/agent` to run the full workflow. The agent orchestrates the stages and references this skill for detailed instructions.

## Related Skills

- **diagnose-ado-build-failures**: For diagnosing build failures after implementation
- **create-worktree**: For setting up a branch/worktree before starting implementation
- **ado-build-ralph-loop**: For iterating on build failures during implementation
