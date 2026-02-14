<#
.SYNOPSIS
    Installs agent skills by creating junctions from the repo's skills directory
    into $env:USERPROFILE\.claude\skills. Idempotent - safe to run repeatedly.

.DESCRIPTION
    - Creates junctions for each skill subdirectory
    - Cleans stale junctions that pointed into this repo but whose source is gone
    - Installs post-checkout and post-merge git hooks to re-run this script automatically
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── Paths ──────────────────────────────────────────────────────────────────────
$SkillsSource = Join-Path $PSScriptRoot 'skills'
$TargetDir    = Join-Path $env:USERPROFILE '.claude\skills'
$GitHooksDir  = Join-Path $PSScriptRoot '.git\hooks'
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

# ── Git hooks ──────────────────────────────────────────────────────────────────
if (Test-Path (Join-Path $PSScriptRoot '.git')) {
    if (-not (Test-Path $GitHooksDir)) {
        New-Item -Path $GitHooksDir -ItemType Directory -Force | Out-Null
    }

    $hookCommand = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""
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
} else {
    Write-Host "[!] No .git directory found - skipping hook installation."
}

Write-Host ""
Write-Host "Install-Skills completed."
