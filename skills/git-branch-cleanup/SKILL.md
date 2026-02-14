---
name: git-branch-cleanup
description: Clean up stale git branches by identifying and removing local branches tracking deleted remotes, branches with completed/abandoned PRs, and stale branches. Includes worktree management. Use when the user says "clean up branches", "branch cleanup", "prune branches", "delete old branches", or "remove stale branches".
---

# Git Branch Cleanup

Gather ALL branch data upfront — gone status, PR status, ages, worktrees — in a single pass, then present one comprehensive summary so the user makes one decision instead of multiple rounds.

## Quick Start

1. Fetch + prune
2. Gather branch info, worktrees, ages, and PR status for ALL non-main branches
3. Present categorized summary with all data
4. User picks what to delete
5. Remove worktrees, delete branches, verify

## Requirements

- Git repository with configured remote (typically `origin`)
- *Optional*: Azure CLI with `az repos` for ADO PR status checking, OR GitHub CLI (`gh`) for GitHub PR status checking
- Terminal access for git commands

## Instructions

### Step 1: Fetch and Prune

```powershell
git fetch --prune origin
```

### Step 2: Gather Branch Data

Run these in parallel after fetch completes:

```powershell
git --no-pager branch -vv                    # tracking info + gone status
git worktree list                            # worktree associations
git --no-pager branch --show-current         # current branch (never delete)
```

Then get ages:

```powershell
git --no-pager branch --format='%(refname:short)|%(upstream:track)|%(committerdate:relative)|%(subject)' | Sort-Object
```

### Step 3: Query PR Status for ALL Non-Main Branches

**Do this immediately for every branch** that isn't `main`/`master`/current and isn't `[gone]`. Do NOT wait for the user to ask — gather it upfront in a single loop.

**Detect hosting platform** from the remote URL:
```powershell
$remoteUrl = git remote get-url origin
```
- If `$remoteUrl` contains `github.com` → use GitHub CLI (`gh`)
- If `$remoteUrl` contains `dev.azure.com` or `visualstudio.com` → use Azure CLI (`az repos`)
- If neither CLI is available, skip PR status and note it in the summary

**GitHub (gh CLI):**
```powershell
$branches = @("branch1", "branch2", ...)
foreach ($b in $branches) {
  $prs = gh pr list --head "$b" --state all --json number,state 2>$null | ConvertFrom-Json
  if ($prs -and $prs.Count -gt 0) {
    Write-Host "$b => $($prs | ForEach-Object { "PR#$($_.number)($($_.state))" })"
  } else {
    Write-Host "$b => NO PRs"
  }
}
```

**Azure DevOps (az repos):**
```powershell
$repo = "<repo-name>"
$org = "<org-url>"       # e.g., https://dev.azure.com/<org> — parse from remote URL
$project = "<project>"   # parse from remote URL
$branches = @("branch1", "branch2", ...)
foreach ($b in $branches) {
  $prs = az repos pr list --repository $repo --org $org --project $project `
    --source-branch "refs/heads/$b" --status all `
    --query "[].{id:pullRequestId, status:status}" -o json 2>$null | ConvertFrom-Json
  if ($prs -and $prs.Count -gt 0) {
    Write-Host "$b => $($prs | ForEach-Object { "PR#$($_.id)($($_.status))" })"
  } else {
    Write-Host "$b => NO PRs"
  }
}
```

PR status values: `active` (keep), `abandoned` (safe to delete), `completed` (safe to delete).

### Step 4: Present ONE Comprehensive Summary

Categorize every branch and present all categories at once:

**🗑️ Branches with deleted remotes (`gone`) — N branches:**

| Branch | Worktree | Last Activity |
|--------|----------|---------------|
| bugfix/old-fix | `repo.worktrees/old-fix` | 4 days ago |

**🚫 Branches with abandoned/completed PRs — N branches:**

| Branch | PR | Status | Worktree | Last Activity |
|--------|----|--------|----------|---------------|
| feature/done | PR#12345 | completed | `repo.worktrees/done` | 2 weeks ago |

**🕸️ Stale branches (4+ weeks, no active PR) — N branches:**

| Branch | PR | Worktree | Last Activity |
|--------|----|----------|---------------|
| experiment/old | NO PRs | `repo.worktree/old` | 3 months ago |

**✅ Active branches (keeping) — N branches:**

| Branch | PR | Last Activity |
|--------|----|---------------|
| feature/current | PR#67890 (active) | 2 days ago |

### Step 5: One Decision Point

Offer choices based on categories that actually exist. The recommended option should combine all clearly-safe categories:

- "Delete gone + abandoned/completed PRs + stale with no PRs (Recommended)" — if all three categories exist
- "Delete gone + abandoned/completed PRs" — conservative option
- "Delete only gone remotes" — safest
- "Let me select specific ones"

### Step 6: Execute Deletion

Worktrees first, then branches, then verify:

```powershell
# 1. Remove worktrees
foreach ($wt in $worktrees) {
  if (Test-Path $wt) {
    Write-Host "Removing worktree: $wt"
    git worktree remove --force $wt 2>&1
  }
}

# 2. Delete branches one by one for clear feedback
foreach ($b in $branches) {
  Write-Host "Deleting: $b"
  git branch -D $b 2>&1
}

# 3. Prune and verify
git worktree prune
git --no-pager worktree list
```

### Step 7: Final Summary

Report: how many branches + worktrees deleted, what remains, any failures.

## Edge Cases

### File-Locked Worktrees (Windows)

If `git worktree remove --force` fails with "Permission denied":

```powershell
Remove-Item -Recurse -Force "<worktree-path>"
```

If that also fails ("being used by another process"), note the locked path for the user and continue. The branch can still be deleted — the orphaned directory can be removed later after closing editors/terminals in that folder, then running `git worktree prune`.

### Worktree Conflicts

Always remove the worktree before deleting its branch, otherwise you get:
```
error: cannot delete branch 'branch-name' used by worktree at 'path'
```

### Modified Worktrees

Use `--force` flag — worktrees for deleted branches rarely have unsaved work worth keeping.

### Remote Deletion Permissions

Some branches (Copilot-generated) may need ForcePush permission. Local deletion still works. Only attempt remote deletion if the user explicitly requests it.

## Best Practices

- Always start with `git fetch --prune` to get accurate remote state
- Always get user confirmation before deleting anything
- Never delete `main`, `master`, or `develop` without explicit instruction
- Never delete the currently checked-out branch
- Run `git worktree prune` after removing worktrees to clean metadata
- Note any worktrees that couldn't be removed due to file locks
