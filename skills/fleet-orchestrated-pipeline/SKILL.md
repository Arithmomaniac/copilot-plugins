---
name: fleet-orchestrated-pipeline
description: 'Decompose large work into a DAG and execute across parallel worktrees with fleet agents, multi-model code review, auto-applied fixes, and streaming manual review. Use when the user says "fleet orchestrate", "swarm this work", "parallel worktrees", "decompose and implement", or has a large body of work to split into parallel PR-sized tasks.'
---

# Fleet Orchestrated Pipeline

Orchestrate large bodies of work by decomposing them into a DAG, then executing tasks in parallel across git worktrees using fleet agents, multi-model code review, automatic fix application, and per-layer batch execution with PR creation.

## Reference Files

| File | Contents |
|------|----------|
| [decomposition.md](./references/decomposition.md) | Phase 0: DAG building, layering, deferral rules |
| [inner-loop.md](./references/inner-loop.md) | Steps 1-6: worktrees, fleet, review, auto-apply, manual, PR |
| [state-tracking.md](./references/state-tracking.md) | SQL schema, queries, status flow, resume procedure |
| [worktree-naming.md](./references/worktree-naming.md) | Naming conventions, subfolder structure, gitgraph |
| [consolidation.md](./references/consolidation.md) | Cherry-pick patterns, worktree cleanup |
| [templates/fleet-state-init.sql](./templates/fleet-state-init.sql) | SQL DDL for fleet tables |

## When to Use

- You have a large body of work that can be broken into multiple PR-sized tasks
- Some tasks depend on others, forming a DAG (not just a flat list)
- You want maximum parallelism with human review as the only bottleneck

## Typical Workflow

1. **Plan mode first** — Use plan mode (Shift+Tab) to describe the work and generate a `plan.md` with tasks and `todos`/`todo_deps` in the SQL database
2. **Switch to fleet orchestrator** — The skill reads your existing plan.md and todos table as Phase 0 input, saving decomposition work
3. **Confirm DAG** — Review the generated DAG and dependency layers
4. **Execute** — The pipeline creates worktrees, launches fleet agents, runs multi-model review, and streams tasks for manual approval

## Quick Overview

### Phase 0: Decomposition
1. Check for existing `plan.md` and `todos`/`todo_deps` SQL tables (from plan mode) — use as primary input
2. Otherwise, user describes the work (freetext, ADO work item, or OpenSpec tasks.md)
3. Build a DAG of PR-sized tasks with dependency edges
4. Topologically sort into layers — tasks within a layer are parallel
5. Tasks with multiple antecedents from different branches are **deferred**
6. Present DAG to user for confirmation

### Phase 1: Layer Execution (Outer Loop)
Process layers in order. For each layer, run the Inner Loop on all ready tasks.
After a layer completes, check if deferred tasks are now unblocked.

### Phase 2: Inner Loop (Per-Layer Batch Pipeline)
For each layer, tasks move through **6 sequential batch stages** with barriers between stages. Within each stage, tasks execute in parallel:

1. **Create worktrees** — all at once, in `../<repo>.worktrees/<swarm-slug>/t<N>-<slug>`
2. **Fleet implementation** — one `general-purpose` background agent per worktree, all parallel. **Wait for ALL to complete.**
3. **Multi-model code review** — for each implemented task, launch 3 review models. All 3×N reviews run in parallel. **Wait for ALL to complete.**
4. **Auto-apply findings** — one agent per task applies unambiguous fixes, all in parallel (separate worktrees). **Wait for ALL to complete.**
5. **Manual review** — present tasks one at a time; user reviews refined code with only flagged findings
6. **Create PR** — on approval, push + create PR

Each stage completes fully before the next begins. Agents within a stage fan out internally (parallel tool calls for independent sub-tasks within a worktree).

## Naming Conventions

| Thing | Pattern | Example |
|-------|---------|---------|
| Swarm subfolder | `../<repo>.worktrees/<swarm-slug>/` | `../ZTS.worktrees/auth-refactor/` |
| Worktree dir | `<swarm>/t<N>-<task-slug>` | `auth-refactor/t3-jwt-provider` |
| Branch | `<prefix>/<user>/<swarm>/t<N>-<task-slug>` | `feature/avilevin/auth-refactor/t3-jwt-provider` |

## State Tracking

Track state in the Copilot CLI session SQL database, integrated with the built-in `todos`/`todo_deps` tables:

- **`todos`** — each task is a row (id, title, description, status)
- **`todo_deps`** — DAG edges between tasks
- **`fleet_tasks`** — fleet-specific metadata (layer, worktree, branch, PR URL, work item)
- **`fleet_subtasks`** — per-task checklists
- **`fleet_reviews`** — review findings with auto-apply status

On resume, query `fleet_tasks JOIN todos` to rebuild the full picture.

## Auto-Apply Review Findings

After review synthesis, auto-apply any finding that is:
- **Unambiguous** — only one reasonable fix
- **Localized** — small code region
- **Not contradicted** — no disagreement across models
- **Verifiable** — build + test confirms the fix

Severity does NOT gate auto-apply. A minor whitespace fix and a critical logic bug both get applied if they're clear. Ambiguous or architectural findings are flagged for manual review.

## Key Design Decisions

- **Worktrees** (not branch switching) — parallel agents need separate working directories
- **Layer-by-layer** — later tasks branch FROM earlier tasks' branches, getting their code changes
- **Batch stages with barriers** — each stage (implement, review, auto-apply) completes fully before the next begins; eliminates polling, streaming, and background SQL issues
- **Intra-agent parallelism** — agents with multiple independent sub-tasks parallelize internally via parallel tool calls
- **Defer multi-antecedent** — wait for PRs to merge to main rather than risk merge conflicts
- **3-model review** — different models catch different issue classes; consensus = high confidence
- **Resilience** — model timeouts and failures are handled gracefully (2-of-3 reviews is fine, failed tasks don't block the layer)

## Integration Points

| Skill | Used In | Purpose |
|-------|---------|---------|
| `create-worktree` | Step 1 | Create branch + worktree |
| `git-branch-cleanup` | Step 6 | Clean up completed worktrees |
| `diagnose-ado-build-failures` | Step 2 | When fleet agent's build fails |
| `ado-build-ralph-loop` | Step 2 | Iterate on build failures |
