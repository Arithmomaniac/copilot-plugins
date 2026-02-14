---
name: create-worktree
description: Create a new git branch and worktree from context. Use when starting work on a task - given an ADO Work Item URI, ADO comment, or freetext description, auto-selects branch prefix (feature/bugfix/experiment) based on context, creates branch like feature/<username>/<slug>, and sets up worktree at ../<repo>.worktrees/<slug>. Triggers on "create worktree", "new branch for", "start work on", or when user provides an ADO WI link and wants to begin coding.
---

# Create Worktree

Create a new git branch and worktree from context (ADO Work Item, comment, or freetext).

## Username Detection

Determine the user's short username for branch naming. Try in order:
1. `git config user.name` — use first token, lowercased
2. `$env:USERNAME` (Windows) or `$env:USER` (Unix)
3. Fall back to `user`

Store as `$username` for use in branch names below.

## Workflow

### Step 1: Gather Context

Obtain one of:
- **ADO Work Item URI** *(optional, requires Azure CLI)*: e.g., `https://dev.azure.com/<org>/<project>/_workitems/edit/12345678`
- **ADO comment/description**: Text describing the work
- **Freetext**: Brief description of the task

### Step 2: Extract/Generate Slug

**From ADO Work Item URI (if Azure CLI is available):**
```powershell
# Extract WI ID and org from URI
$wiId = "12345678"  # parsed from URI
$org = "https://dev.azure.com/<org>"  # parsed from URI

# Query ADO for title using az cli
az boards work-item show --id $wiId --org $org --query "fields.\"System.Title\"" -o tsv
```

If `az` is not available or the command fails, ask the user for a freetext description instead.

**From freetext/comment:**
- Generate a semantic, kebab-case slug (no numbers, no IDs)
- Keep it short (2-4 words max)
- Example: "Fix authentication timeout issue" → `fix-auth-timeout`

### Step 3: Auto-Select Branch Prefix

Choose prefix based on context:

| Context Signal | Prefix |
|----------------|--------|
| ADO WI type = Bug, or words like "fix", "bug", "issue", "broken" | `bugfix/<username>/<slug>` |
| Words like "experiment", "try", "test", "spike", "poc" | `experiment/<username>/<slug>` |
| Default (new feature, enhancement, task) | `feature/<username>/<slug>` |

Present the auto-selected branch and allow user to confirm or provide alternative prefix.

### Step 4: Confirm Branch Source

Before creating, ask user which source to use for the branch:

```
Suggested branch: bugfix/<username>/fix-auth-timeout
Worktree: ../<repo>.worktrees/fix-auth-timeout

Create branch from:
  [1] origin/main (recommended) - ensures branch starts from latest remote
  [2] current HEAD

Enter your choice [1]:
```

Default is **origin/main** to ensure the branch always starts from the latest remote state.

### Step 5: Create Branch and Worktree

**Default behavior (origin/main):**

```powershell
# Get git root and repo name
$gitRoot = git rev-parse --show-toplevel
$repoName = Split-Path $gitRoot -Leaf

# Define paths
$branch = "feature/$username/fix-auth-timeout"
$slug = "fix-auth-timeout"
$worktreePath = Join-Path (Split-Path $gitRoot -Parent) "$repoName.worktrees" $slug

# Create worktree directory if needed
$worktreeParent = Split-Path $worktreePath -Parent
if (!(Test-Path $worktreeParent)) { New-Item -ItemType Directory -Path $worktreeParent -Force }

# Fetch latest from remote to ensure we have latest main
git fetch origin main

# Resolve to a detached commit so the new branch has NO upstream tracking
$startCommit = git rev-parse origin/main

# Create branch from that commit — no implicit remote tracking
git worktree add -b $branch $worktreePath $startCommit

# Verify
git worktree list
```

**Alternative (current HEAD):**

If user selects option [2], use `git worktree add -b $branch $worktreePath` without specifying a source (branches from current HEAD). No remote push — the branch stays local until explicitly pushed.

### Step 6: Report Success

```
✅ Created branch: feature/<username>/fix-auth-timeout
✅ Worktree ready at: ../<repo>.worktrees/fix-auth-timeout

To start working:
  cd ../<repo>.worktrees/fix-auth-timeout
```

## Slug Generation Guidelines

Generate semantic slugs from context:

| Input | Slug |
|-------|------|
| "Fix the authentication timeout bug" | `fix-auth-timeout` |
| "Add retry logic to API calls" | `add-api-retry` |
| "Implement caching for user sessions" | `user-session-cache` |
| ADO WI: "Bug 123: Login fails after 30min" | `login-timeout-fix` |

Rules:
- Kebab-case, lowercase
- No numbers or IDs
- 2-4 words, descriptive
- Omit articles (a, the, an)

## Error Handling

| Error | Resolution |
|-------|------------|
| Branch already exists | Suggest alternative slug or ask user |
| Worktree path exists | Check if it's the same branch; if not, suggest alternative |
| ADO query fails | Fall back to asking user for slug |
| Not in a git repo | Error and exit |
