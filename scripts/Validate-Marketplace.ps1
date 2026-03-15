<#
.SYNOPSIS
    Validates marketplace.json coverage and integrity.
    Every skill and agent on disk must be referenced; all referenced paths must exist.

.DESCRIPTION
    1. Coverage: Every skills/*/SKILL.md and agents/*/*.agent.md must appear in
       at least one plugin entry in marketplace.json.
    2. Path validity: Every path in skills[] and agents[] arrays in marketplace.json
       must exist on disk.
    3. JSON validity: marketplace.json must be well-formed JSON.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = git rev-parse --show-toplevel 2>$null
if (-not $RepoRoot) {
    Write-Error "Not inside a git repository."
    exit 1
}

$ManifestPath = Join-Path $RepoRoot '.claude-plugin' 'marketplace.json'
if (-not (Test-Path $ManifestPath)) {
    Write-Host "ERROR: marketplace.json not found at $ManifestPath" -ForegroundColor Red
    exit 1
}

$errors = @()

# ── 1. Parse JSON ──────────────────────────────────────────────────────────────
try {
    $manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
} catch {
    Write-Host "ERROR: marketplace.json is not valid JSON: $_" -ForegroundColor Red
    exit 1
}

if (-not $manifest.plugins) {
    $errors += "marketplace.json has no 'plugins' array."
}

# ── 2. Collect all skills and agents on disk ───────────────────────────────────
$skillsDir = Join-Path $RepoRoot 'skills'
$agentsDir = Join-Path $RepoRoot 'agents'

$diskSkills = @()
if (Test-Path $skillsDir) {
    $diskSkills = Get-ChildItem -Path $skillsDir -Directory |
        Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') } |
        ForEach-Object { "./skills/$($_.Name)" }
}

$diskAgents = @()
if (Test-Path $agentsDir) {
    $diskAgents = Get-ChildItem -Path $agentsDir -Directory |
        Where-Object {
            @(Get-ChildItem -Path $_.FullName -Filter '*.agent.md' -File -ErrorAction SilentlyContinue).Count -gt 0
        } |
        ForEach-Object { "./agents/$($_.Name)" }
}

# ── 3. Collect all referenced skills and agents from marketplace ───────────────
$referencedSkills = @()
$referencedAgents = @()

if ($manifest.plugins) {
    foreach ($plugin in $manifest.plugins) {
        $hasSkills = $plugin.PSObject.Properties['skills'] -and $plugin.skills
        $hasAgents = $plugin.PSObject.Properties['agents'] -and $plugin.agents
        if ($hasSkills) {
            $referencedSkills += @($plugin.skills)
        }
        if ($hasAgents) {
            $referencedAgents += @($plugin.agents)
        }
    }
}

# ── 4. Check coverage: disk → marketplace ─────────────────────────────────────
foreach ($skill in $diskSkills) {
    if ($skill -notin $referencedSkills) {
        $errors += "Skill on disk not in marketplace: $skill"
    }
}

foreach ($agent in $diskAgents) {
    if ($agent -notin $referencedAgents) {
        $errors += "Agent on disk not in marketplace: $agent"
    }
}

# ── 5. Check path validity: marketplace → disk ────────────────────────────────
foreach ($skillPath in $referencedSkills) {
    $fullPath = Join-Path $RepoRoot ($skillPath -replace '^\./', '')
    if (-not (Test-Path $fullPath)) {
        $errors += "Marketplace references missing skill path: $skillPath"
    }
}

foreach ($agentPath in $referencedAgents) {
    $fullPath = Join-Path $RepoRoot ($agentPath -replace '^\./', '')
    if (-not (Test-Path $fullPath)) {
        $errors += "Marketplace references missing agent path: $agentPath"
    }
}

# ── 6. Check required fields per plugin ────────────────────────────────────────
if ($manifest.plugins) {
    foreach ($plugin in $manifest.plugins) {
        $name = $plugin.name
        $hasSkills = $plugin.PSObject.Properties['skills'] -and $plugin.skills
        $hasAgents = $plugin.PSObject.Properties['agents'] -and $plugin.agents
        if (-not $name)    { $errors += "Plugin missing 'name' field." }
        if (-not $plugin.version) { $errors += "Plugin '$name' missing 'version' field." }
        if (-not $plugin.description) { $errors += "Plugin '$name' missing 'description' field." }
        if (-not $hasSkills -and -not $hasAgents) {
            $errors += "Plugin '$name' has neither 'skills' nor 'agents'."
        }
    }
}

# ── Report ─────────────────────────────────────────────────────────────────────
if ($errors.Count -gt 0) {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Red
    Write-Host "║  BLOCKED: Marketplace validation failed                     ║" -ForegroundColor Red
    Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Host ""

    foreach ($err in $errors) {
        Write-Host "  ✗ $err" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Fix the issues above before pushing." -ForegroundColor Red
    exit 1
}

Write-Host "[marketplace] Validation passed — all skills/agents covered, paths valid."
exit 0
