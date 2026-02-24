# Consolidation Patterns

During manual review, the user may decide to **fold** smaller tasks into larger ones. This is a pattern observed in practice where T1 (DVT), T4 (SetWorkloadSegments), and T6 (ARN handler) were all folded into T0 (attr-cleanup).

## When to Consolidate

- A small task's changes are closely related to a larger task
- Two tasks touch overlapping files and would conflict as separate PRs
- A task turns out to be trivial and doesn't merit its own PR
- The user decides during manual review that the scope should be combined

## How to Consolidate

```powershell
# 1. Cherry-pick commits from small worktree onto large worktree
cd $largeWorktreePath
git cherry-pick <commit-hash-from-small-worktree>

# 2. Resolve any conflicts, build, and test
dotnet build && dotnet test

# 3. Delete small worktree
git worktree remove $smallWorktreePath
git branch -D $smallBranchName

# 4. Update SQL tracking
# UPDATE todos SET status = 'consolidated' WHERE id = 'small-task'
# INSERT OR REPLACE INTO fleet_subtasks (task_id, description, done)
#   VALUES ('large-task', 'Consolidated: small-task changes', 1)

# 5. Update PR description and linked work items on the large task's PR
```

## Consolidation in the DAG

When a task is consolidated:
- Its status becomes `consolidated` — a terminal state
- Any tasks that depended on it now depend on the consolidation target
- The consolidation target's PR description should mention the folded work

```sql
-- Redirect dependencies from consolidated task to its target
UPDATE todo_deps
SET depends_on = 'large-task'
WHERE depends_on = 'small-task';

-- Mark consolidated
UPDATE todos SET status = 'consolidated',
  description = description || ' (consolidated into large-task)'
WHERE id = 'small-task';
```
