---
name: fleet-parallel-implementation
description: Parallelize large implementations across multiple sub-agents. Use when there are 4+ independent todos, wave-based work, or when the user says "fleet parallel", "parallel implementation", "dispatch agents", "swarm this", or has many independent todos to implement simultaneously.
---

# Fleet Parallel Implementation

Parallelizes large implementations across multiple sub-agents to reduce wall-clock time. Prevents sequential bottlenecks when work can be decomposed into independent units.

## When to Use

- When there are 4+ independent todos that don't depend on each other
- Especially for 'wave-based' work: implement wave 1 in parallel, wait for completion, dispatch wave 2
- When test writing, CLI commands, web routes, and markdown exporters all need updating for the same feature
- Don't use when todos have tight sequential dependencies — the overhead of coordination exceeds the benefit

## Instructions

1. Break the work into atomic todos and insert into the SQL todos table with dependency tracking.
2. Query for todos with no pending dependencies ('ready' query) to find what can be dispatched immediately.
3. Dispatch all ready todos as parallel background agents (mode: 'background'). Provide each agent with full context including file paths, expected behavior, and test requirements.
4. Wait for all agents in the current wave to complete before dispatching the next wave.
5. Read each completed agent's output. Verify the changes were actually made (spot-check key files).
6. If an agent failed or made incorrect changes, retry with a refined prompt — don't silently accept wrong output.
7. After all waves complete, run the full test suite to catch integration issues between parallel changes.
8. Do a tri-review of the combined diff before creating the PR.

## Best Practices

- Do give each agent complete context — agents are stateless and can't read previous agents' output
- **Avoid:** Don't dispatch more than 6-8 agents simultaneously — coordination overhead increases
- Do verify agents actually made changes before marking todos done — they sometimes fail silently
- Do run the full test suite after all waves complete, not after each wave

## Common Pitfalls

| Problem | Solution |
|---|---|
| Agent completes but made no changes | Always spot-check key files after agent completion, not just trust the success message |
| Agents cause merge conflicts in shared files | Assign non-overlapping file ownership — one agent per file or clearly delineated sections |
| Agent forgets to run tests or open VS Code before committing | Remind in the task that 'for each commit you are supposed to run a dual review and open VS Code first' |

## Key Constraints

- Always wait for all agents in a wave to complete before dispatching the next wave
- Full test suite must pass after all waves complete before PR creation
