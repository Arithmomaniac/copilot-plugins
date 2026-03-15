<#
.SYNOPSIS
    Installs agent skills and agents by creating junctions/symlinks from the repo
    into $env:USERPROFILE\.claude\skills and $env:USERPROFILE\.claude\agents.
    Idempotent - safe to run repeatedly.

.DESCRIPTION
    - Creates junctions for each skill subdirectory → ~/.claude/skills/
    - Copies .agent.md files from agents/ subdirs → ~/.claude/agents/ (flat)
      (Directory junctions don't work for agents — the CLI only discovers
       .agent.md files at the top level, not recursively. File symlinks
       require admin on Windows, so we copy instead.)
    - Cleans stale junctions/copies that pointed into this repo but whose source is gone
    - Installs post-checkout and post-merge git hooks to re-run this script automatically
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── Paths ──────────────────────────────────────────────────────────────────────
$SkillsSource  = Join-Path $PSScriptRoot 'skills'
$AgentsSource  = Join-Path $PSScriptRoot 'agents'
$TargetDir     = Join-Path $env:USERPROFILE '.claude\skills'
$AgentsDir     = Join-Path $env:USERPROFILE '.claude\agents'
$GitHooksDir   = Join-Path $PSScriptRoot '.git\hooks'
$ScriptPath   = $MyInvocation.MyCommand.Path

if (-not (Test-Path $SkillsSource)) {
    Write-Error "Skills source directory not found: $SkillsSource"
    return
}

# ── Ensure target directory exists (real dir, not symlink) ─────────────────────
if (Test-Path $TargetDir) {
    $item = Get-Item $TargetDir -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Write-Warning "Target directory '$TargetDir' is a symlink. Remove it manually before running this script."
        return
    }
} else {
    New-Item -Path $TargetDir -ItemType Directory -Force | Out-Null
    Write-Host "[+] Created target directory: $TargetDir"
}

# ── Create / update junctions ──────────────────────────────────────────────────
$sourceSkills = Get-ChildItem -Path $SkillsSource -Directory
foreach ($skill in $sourceSkills) {
    $junctionPath = Join-Path $TargetDir $skill.Name
    $expectedTarget = $skill.FullName

    if (Test-Path $junctionPath) {
        $existing = Get-Item $junctionPath -Force
        if ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            # It's a junction/symlink - check where it points
            $currentTarget = $existing.Target
            # Target can be an array; normalise to string
            if ($currentTarget -is [array]) { $currentTarget = $currentTarget[0] }

            if ($currentTarget -eq $expectedTarget) {
                Write-Host "[=] Skipped (already correct): $($skill.Name)"
                continue
            } else {
                # Points to wrong location - remove and recreate
                $existing.Delete()
                Write-Host "[-] Removed stale junction: $($skill.Name) -> $currentTarget"
            }
        } else {
            Write-Warning "Target path '$junctionPath' exists but is not a junction. Skipping."
            continue
        }
    }

    New-Item -Path $junctionPath -ItemType Junction -Target $expectedTarget | Out-Null
    Write-Host "[+] Created junction: $($skill.Name) -> $expectedTarget"
}

# ── Clean stale junctions ──────────────────────────────────────────────────────
# Remove junctions in the target dir that point into THIS repo's skills dir
# but whose source directory no longer exists.
$normalizedSource = $SkillsSource.TrimEnd('\') + '\'
$allItems = Get-ChildItem -Path $TargetDir -Force -ErrorAction SilentlyContinue
foreach ($item in $allItems) {
    if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }

    $target = $item.Target
    if ($target -is [array]) { $target = $target[0] }
    if (-not $target) { continue }

    # Only touch junctions that point into our skills source
    if ($target.StartsWith($normalizedSource, [StringComparison]::OrdinalIgnoreCase)) {
        if (-not (Test-Path $target)) {
            $item.Delete()
            Write-Host "[-] Removed stale junction: $($item.Name) -> $target"
        }
    }
}

# ── Install agent files (.agent.md) ────────────────────────────────────────────
# Copy .agent.md files directly into ~/.claude/agents/ (flat).
# Directory junctions don't work — the CLI only discovers .agent.md files at
# the top level of the agents directory, not recursively.
# File symlinks require admin on Windows, so we copy instead.
if (Test-Path $AgentsSource) {
    if (-not (Test-Path $AgentsDir)) {
        New-Item -Path $AgentsDir -ItemType Directory -Force | Out-Null
        Write-Host "[+] Created agents directory: $AgentsDir"
    }

    # Clean up old directory junctions from previous install approach
    $normalizedAgentsSource = $AgentsSource.TrimEnd('\') + '\'
    $allItems = Get-ChildItem -Path $AgentsDir -Force -ErrorAction SilentlyContinue
    foreach ($item in $allItems) {
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
        if (-not ($item.PSIsContainer)) { continue }  # only remove directory junctions

        $target = $item.Target
        if ($target -is [array]) { $target = $target[0] }
        if (-not $target) { continue }

        if ($target.StartsWith($normalizedAgentsSource, [StringComparison]::OrdinalIgnoreCase)) {
            $item.Delete()
            Write-Host "[-] Removed old agent directory junction: $($item.Name) -> $target"
        }
    }

    # Find all .agent.md files recursively and copy to agents dir
    $sourceAgentFiles = Get-ChildItem -Path $AgentsSource -Filter '*.agent.md' -Recurse -File
    $installedNames = @()

    foreach ($agentFile in $sourceAgentFiles) {
        $destPath = Join-Path $AgentsDir $agentFile.Name
        $installedNames += $agentFile.Name

        if (Test-Path $destPath) {
            $srcHash = (Get-FileHash $agentFile.FullName -Algorithm MD5).Hash
            $dstHash = (Get-FileHash $destPath -Algorithm MD5).Hash
            if ($srcHash -eq $dstHash) {
                Write-Host "[=] Skipped agent (already current): $($agentFile.Name)"
                continue
            }
        }

        Copy-Item -Path $agentFile.FullName -Destination $destPath -Force
        Write-Host "[+] Installed agent: $($agentFile.Name) (from $($agentFile.Directory.Name)/)"
    }

    # Clean stale agent copies: files in agents dir that match a source pattern
    # but whose source no longer exists. Only remove files we previously installed
    # (i.e., files whose name matches an .agent.md in our source tree).
    $allAgentFiles = Get-ChildItem -Path $AgentsDir -Filter '*.agent.md' -File -ErrorAction SilentlyContinue
    foreach ($installed in $allAgentFiles) {
        # Check if this file has a corresponding source anywhere in our agents tree
        $matchingSource = Get-ChildItem -Path $AgentsSource -Filter $installed.Name -Recurse -File -ErrorAction SilentlyContinue
        if (-not $matchingSource) {
            # Only remove if this file's content was likely from us (heuristic: skip
            # files that were never in our source — they belong to the user)
            # We can't know for sure, so we leave unknown files alone.
            continue
        }
    }
}

# ── Git hooks ──────────────────────────────────────────────────────────────────
if (Test-Path (Join-Path $PSScriptRoot '.git')) {
    if (-not (Test-Path $GitHooksDir)) {
        New-Item -Path $GitHooksDir -ItemType Directory -Force | Out-Null
    }

    $hookCommand = "pwsh -NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""
    $hookMarker  = "# copilot-plugins Install-Skills hook"

    foreach ($hookName in @('post-checkout', 'post-merge')) {
        $hookFile = Join-Path $GitHooksDir $hookName

        if (Test-Path $hookFile) {
            $content = Get-Content $hookFile -Raw -ErrorAction SilentlyContinue
            if ($content -and $content.Contains($hookMarker)) {
                Write-Host "[=] Git hook already configured: $hookName"
                continue
            }
            # Append to existing hook
            $snippet = "`n$hookMarker`n$hookCommand`n"
            Add-Content -Path $hookFile -Value $snippet -NoNewline
            Write-Host "[+] Appended to existing git hook: $hookName"
        } else {
            $snippet = "#!/bin/sh`n$hookMarker`n$hookCommand`n"
            Set-Content -Path $hookFile -Value $snippet -NoNewline
            Write-Host "[+] Created git hook: $hookName"
        }
    }

    # ── Validation hooks (pre-commit, pre-push) ────────────────────────────────
    $ScriptsDir = Join-Path $PSScriptRoot 'scripts'

    # Pre-commit: auto-bump marketplace versions for modified skills/agents
    $preCommitMarker = "# copilot-plugins auto-bump hook"
    $preCommitFile   = Join-Path $GitHooksDir 'pre-commit'
    $preCommitCmd    = "pwsh -NoProfile -ExecutionPolicy Bypass -File `"$ScriptsDir\Auto-BumpVersion.ps1`""

    if (Test-Path $preCommitFile) {
        $content = Get-Content $preCommitFile -Raw -ErrorAction SilentlyContinue
        if ($content -and $content.Contains($preCommitMarker)) {
            Write-Host "[=] Git hook already configured: pre-commit"
        } else {
            $snippet = "`n$preCommitMarker`n$preCommitCmd`n"
            Add-Content -Path $preCommitFile -Value $snippet -NoNewline
            Write-Host "[+] Appended to existing git hook: pre-commit"
        }
    } else {
        $snippet = "#!/bin/sh`n$preCommitMarker`n$preCommitCmd`n"
        Set-Content -Path $preCommitFile -Value $snippet -NoNewline
        Write-Host "[+] Created git hook: pre-commit"
    }

    # Pre-push: secret scan + marketplace validation
    $prePushMarker = "# copilot-plugins validation hook"
    $prePushFile   = Join-Path $GitHooksDir 'pre-push'
    $prePushScript = @"
#!/bin/sh
$prePushMarker
pwsh -NoProfile -ExecutionPolicy Bypass -File "$ScriptsDir\Validate-Secrets.ps1"
if [ `$? -ne 0 ]; then exit 1; fi
pwsh -NoProfile -ExecutionPolicy Bypass -File "$ScriptsDir\Validate-Marketplace.ps1"
if [ `$? -ne 0 ]; then exit 1; fi
"@

    if (Test-Path $prePushFile) {
        $content = Get-Content $prePushFile -Raw -ErrorAction SilentlyContinue
        if ($content -and $content.Contains($prePushMarker)) {
            Write-Host "[=] Git hook already configured: pre-push"
        } else {
            Add-Content -Path $prePushFile -Value "`n$prePushScript" -NoNewline
            Write-Host "[+] Appended to existing git hook: pre-push"
        }
    } else {
        Set-Content -Path $prePushFile -Value $prePushScript -NoNewline
        Write-Host "[+] Created git hook: pre-push"
    }
} else {
    Write-Host "[!] No .git directory found - skipping hook installation."
}

Write-Host ""
Write-Host "Install-Skills completed."
