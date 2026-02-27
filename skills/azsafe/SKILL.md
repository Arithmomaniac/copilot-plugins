---
name: azsafe
description: Safe Azure CLI proxy that only allows read-only commands. Use azsafe.ps1 for read-only operations (list, show, get, etc.) and use az directly for write operations when needed. MUST be loaded before making any az CLI calls — invoke proactively whenever Azure CLI or ADO API queries are needed.
---

# azsafe - Safe Azure CLI Proxy

This skill provides a safe way to run read-only Azure CLI commands by proxying through `azsafe.ps1`.

## When to Use

- **Use `azsafe.ps1`** for read-only operations: listing, showing, querying, exporting data
- **Use `az` directly** when you need to perform write operations (create, delete, update, etc.)

## How to Use

The script is located at: `{USER_HOME}\.claude\skills\azsafe\azsafe.ps1`

**CRITICAL: You MUST inline the full literal path!** PowerShell doesn't expand `$HOME` or `~` in command paths. Before invoking azsafe.ps1, determine the user's home directory (e.g., via `$HOME` or `$env:USERPROFILE`) and construct the full literal path with that value inlined.

**PowerShell rules:**
1. **Inline the resolved home path** - e.g., if `$HOME` is `C:\Users\jsmith`, use `C:\Users\jsmith\.claude\skills\azsafe\azsafe.ps1`
2. **Use `--output` not `-o`** - the short form conflicts with PowerShell's `-OutVariable`

```powershell
# ✅ CORRECT - full inlined path with resolved home directory:
C:\Users\jsmith\.claude\skills\azsafe\azsafe.ps1 group list --output table
C:\Users\jsmith\.claude\skills\azsafe\azsafe.ps1 vm show --name myvm -g myrg --output json

# ❌ WRONG - variables don't expand in command paths:
$HOME\.claude\skills\azsafe\azsafe.ps1 group list  # FAILS - $HOME not expanded
~\.claude\skills\azsafe\azsafe.ps1 group list  # FAILS - ~ not expanded

# ❌ WRONG - -o conflicts with PowerShell:
C:\Users\jsmith\.claude\skills\azsafe\azsafe.ps1 group list -o table  # Use --output instead

# For write commands, use az directly:
az group create -n newRG -l eastus
az vm delete -g myRG -n myVM --yes
```

## Shell Execution Guidance

The Copilot CLI's shell tool defaults to a 10-second timeout (`initial_wait`). Most `az` commands — especially `az devops invoke` — take 15-30 seconds. **Always specify `initial_wait: 30` minimum** for any `azsafe.ps1` call.

| Operation | `initial_wait` | Notes |
|-----------|----------------|-------|
| `az group list`, `az vm show` | 30s | Standard ARM queries |
| `az devops invoke` (timeline, logs) | 30-60s | ADO API is slower than ARM |
| `az account get-access-token` | 30s | Token acquisition |
| `az devops invoke` (large log fetch) | 60s | Logs can be 5000+ lines |

**Example with correct timeout:**
```powershell
# Mode: sync, initial_wait: 30
C:\Users\jsmith\.claude\skills\azsafe\azsafe.ps1 devops invoke `
    --area build --resource timeline `
    --route-parameters project=One buildId=12345 `
    --org https://msazure.visualstudio.com `
    --output json
```

## Allowed Verbs(via azsafe.ps1)

Read from [allowed-verbs.txt](allowed-verbs.txt):

| Verb | Description |
|------|-------------|
| `list` | Enumerate resources |
| `show` | Get resource details |
| `describe` | Alias for show |
| `get` | Retrieve info |
| `exists` | Check existence |
| `export` | Export config/templates |
| `download` | Download content |
| `check` | Validate without modifying |
| `validate` | Validate configuration |
| `wait` | Wait for a condition |
| `browse` | Open in browser |
| `find` | Search for resources |
| `preview` | Preview changes |
| `query` | Run read-only queries (WIQL, KQL, ARG, etc.) |
| `login` | Azure authentication |
| `account` | Account management |
| `version` | Show version |
| `search` | Search extension/command index |

## Special Handling: REST-style Commands

The `az rest` and `az devops invoke` commands are allowed **only when the HTTP method is GET** (or not specified, since GET is the default):

```powershell
# These are ALLOWED (GET is default or explicit) - remember to inline the full path:
{USER_HOME}\.claude\skills\azsafe\azsafe.ps1 rest --url "https://management.azure.com/subscriptions?api-version=2020-01-01"
{USER_HOME}\.claude\skills\azsafe\azsafe.ps1 rest --method get --url "https://..."
{USER_HOME}\.claude\skills\azsafe\azsafe.ps1 devops invoke --area git --resource repositories

# These are BLOCKED (non-GET methods):
{USER_HOME}\.claude\skills\azsafe\azsafe.ps1 rest --method post --url "https://..."
{USER_HOME}\.claude\skills\azsafe\azsafe.ps1 devops invoke --http-method DELETE --area git --resource repositories
```

**Note:** Other `invoke` commands like `az vm run-command invoke` and `az aks command invoke` are **always blocked** because they execute arbitrary code (not REST-style).

## Examples

```powershell
# Read-only operations via azsafe (inline full path, use --output not -o)
{USER_HOME}\.claude\skills\azsafe\azsafe.ps1 group list --output table
{USER_HOME}\.claude\skills\azsafe\azsafe.ps1 vm show -g myRG -n myVM --output json
{USER_HOME}\.claude\skills\azsafe\azsafe.ps1 storage account list --query "[].name" --output tsv
{USER_HOME}\.claude\skills\azsafe\azsafe.ps1 account show --output json

# Write operations via az directly
az group create -n newRG -l eastus
az vm start -g myRG -n myVM
```

## Logging

Blocked commands are logged to `~/.az-proxy-blocked.log` for review.

## Adding Allowed Verbs

Edit [allowed-verbs.txt](allowed-verbs.txt) to add new read-only verbs.
