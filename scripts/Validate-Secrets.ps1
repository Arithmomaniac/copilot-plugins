<#
.SYNOPSIS
    Scans git diff for Microsoft-internal content before push.
    Exits non-zero if any blocked pattern is found in added lines.

.DESCRIPTION
    Reads regex patterns from scripts/blocked-patterns.txt and scans
    the diff between the remote tracking branch and HEAD for matches
    in newly added lines (lines starting with '+').

.PARAMETER BaseSha
    Base commit SHA to diff against. Defaults to origin/main.

.PARAMETER HeadSha
    Head commit SHA to diff up to. Defaults to HEAD.
#>
[CmdletBinding()]
param(
    [string]$BaseSha,
    [string]$HeadSha = 'HEAD'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = git rev-parse --show-toplevel 2>$null
if (-not $RepoRoot) {
    Write-Error "Not inside a git repository."
    exit 1
}

$PatternsFile = Join-Path $RepoRoot 'scripts' 'blocked-patterns.txt'
if (-not (Test-Path $PatternsFile)) {
    Write-Warning "No blocked-patterns.txt found at $PatternsFile — skipping secret scan."
    exit 0
}

# Load patterns (skip comments and blank lines)
$patterns = Get-Content $PatternsFile |
    Where-Object { $_ -and $_ -notmatch '^\s*#' -and $_.Trim() -ne '' } |
    ForEach-Object { $_.Trim() }

if ($patterns.Count -eq 0) {
    Write-Host "[secrets] No patterns defined — skipping."
    exit 0
}

# Determine base SHA
if (-not $BaseSha) {
    # Try to find the remote tracking branch
    $remoteSha = git rev-parse 'origin/main' 2>$null
    if ($remoteSha) {
        $BaseSha = $remoteSha
    } else {
        # No remote yet — scan all commits
        $BaseSha = git rev-list --max-parents=0 HEAD 2>$null | Select-Object -First 1
        if (-not $BaseSha) {
            Write-Host "[secrets] No commits to scan."
            exit 0
        }
    }
}

# Get unified diff of added lines only
$diffOutput = git diff --no-color --unified=0 "$BaseSha..$HeadSha" 2>$null
if (-not $diffOutput) {
    Write-Host "[secrets] No diff to scan."
    exit 0
}

# Parse diff: track current file, scan added lines
$currentFile = $null
$lineNumber = 0
$violations = @()

foreach ($line in $diffOutput -split "`n") {
    # Track which file we're in
    if ($line -match '^diff --git a/.+ b/(.+)$') {
        $currentFile = $Matches[1]
        $lineNumber = 0
        continue
    }

    # Track line numbers from hunk headers
    if ($line -match '^@@\s+-\d+(?:,\d+)?\s+\+(\d+)') {
        $lineNumber = [int]$Matches[1] - 1  # will be incremented on next '+'
        continue
    }

    # Only scan added lines (not the +++ header)
    if ($line -match '^\+' -and $line -notmatch '^\+\+\+') {
        $lineNumber++
        $content = $line.Substring(1)  # strip the leading '+'

        # Skip scanning the blocked-patterns.txt file itself
        if ($currentFile -eq 'scripts/blocked-patterns.txt') { continue }

        foreach ($pattern in $patterns) {
            if ($content -match $pattern) {
                $violations += [PSCustomObject]@{
                    File    = $currentFile
                    Line    = $lineNumber
                    Pattern = $pattern
                    Content = $content.Trim()
                }
            }
        }
    }
    elseif ($line -match '^\+\+\+') {
        # skip diff header
    }
    elseif ($line -notmatch '^-') {
        # context line (not removed) — increment line counter
        $lineNumber++
    }
}

if ($violations.Count -gt 0) {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Red
    Write-Host "║  BLOCKED: Microsoft-internal content detected in diff       ║" -ForegroundColor Red
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Host ""

    foreach ($v in $violations) {
        Write-Host "  $($v.File):$($v.Line)" -ForegroundColor Yellow -NoNewline
        Write-Host "  pattern: " -NoNewline
        Write-Host "$($v.Pattern)" -ForegroundColor Cyan
        Write-Host "    $($v.Content)" -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "Push blocked. Remove internal references before pushing." -ForegroundColor Red
    Write-Host "To bypass (emergency only): git push --no-verify" -ForegroundColor DarkGray
    exit 1
}

Write-Host "[secrets] Scan passed — no blocked patterns found."
exit 0
