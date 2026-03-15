<#
.SYNOPSIS
    Auto-bumps marketplace.json patch version for modified skills/agents.
    Designed to run as a pre-commit hook.

.DESCRIPTION
    1. Gets staged files (git diff --cached --name-only)
    2. Maps each skills/<name>/... or agents/<name>/... to its marketplace plugin
    3. For each affected plugin: bumps the patch version (1.0.0 → 1.0.1)
    4. Writes and stages the updated marketplace.json

    If marketplace.json is already staged (user manually edited it), the script
    checks whether the affected plugins already have a bumped version and skips
    those.
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

$ManifestRelPath = '.claude-plugin/marketplace.json'
$ManifestPath = Join-Path $RepoRoot '.claude-plugin' 'marketplace.json'

if (-not (Test-Path $ManifestPath)) {
    # No marketplace.json — nothing to bump
    exit 0
}

# ── Get staged files ───────────────────────────────────────────────────────────
$stagedFiles = git diff --cached --name-only 2>$null
if (-not $stagedFiles) {
    exit 0
}

# ── Identify affected skill/agent directories ─────────────────────────────────
$affectedPaths = @{}  # key = relative dir path (e.g., "./skills/azsafe"), value = type

foreach ($file in $stagedFiles) {
    $normalized = $file -replace '\\', '/'

    if ($normalized -match '^skills/([^/]+)/') {
        $key = "./skills/$($Matches[1])"
        $affectedPaths[$key] = 'skill'
    }
    elseif ($normalized -match '^agents/([^/]+)/') {
        $key = "./agents/$($Matches[1])"
        $affectedPaths[$key] = 'agent'
    }
}

if ($affectedPaths.Count -eq 0) {
    # No skill/agent files staged — nothing to bump
    exit 0
}

# ── Load marketplace.json ──────────────────────────────────────────────────────
$rawJson = Get-Content $ManifestPath -Raw
$manifest = $rawJson | ConvertFrom-Json

if (-not $manifest.plugins) {
    exit 0
}

# ── Check if marketplace.json is already staged (user may have manually bumped)
$manifestStaged = $stagedFiles | Where-Object { ($_ -replace '\\', '/') -eq $ManifestRelPath }

# Load the staged version if available, to detect manual bumps
$stagedVersions = @{}
if ($manifestStaged) {
    try {
        $stagedContent = git show ":$ManifestRelPath" 2>$null
        if ($stagedContent) {
            $stagedManifest = $stagedContent | ConvertFrom-Json
            foreach ($p in $stagedManifest.plugins) {
                $stagedVersions[$p.name] = $p.version
            }
        }
    } catch {
        # If we can't parse staged version, proceed with auto-bump
    }
}

# Load the committed (HEAD) version for comparison
$headVersions = @{}
try {
    $headContent = git show "HEAD:$ManifestRelPath" 2>$null
    if ($headContent) {
        $headManifest = $headContent | ConvertFrom-Json
        foreach ($p in $headManifest.plugins) {
            $headVersions[$p.name] = $p.version
        }
    }
} catch {
    # First commit or file doesn't exist in HEAD yet
}

# ── Find plugins affected by staged changes ────────────────────────────────────
$pluginsToBump = @()

foreach ($plugin in $manifest.plugins) {
    $isAffected = $false

    # Check if any staged skill/agent path matches this plugin
    if ($plugin.skills) {
        foreach ($skillPath in $plugin.skills) {
            if ($affectedPaths.ContainsKey($skillPath)) {
                $isAffected = $true
                break
            }
        }
    }
    if (-not $isAffected -and $plugin.agents) {
        foreach ($agentPath in $plugin.agents) {
            if ($affectedPaths.ContainsKey($agentPath)) {
                $isAffected = $true
                break
            }
        }
    }

    if (-not $isAffected) { continue }

    # Check if version was already bumped (staged version differs from HEAD version)
    $headVer = $headVersions[$plugin.name]
    $currentVer = $plugin.version

    if ($headVer -and $currentVer -ne $headVer) {
        Write-Host "[auto-bump] Skipping '$($plugin.name)' — version already changed ($headVer → $currentVer)."
        continue
    }

    $pluginsToBump += $plugin.name
}

if ($pluginsToBump.Count -eq 0) {
    exit 0
}

# ── Bump patch versions ───────────────────────────────────────────────────────
# Re-read raw JSON to preserve formatting as much as possible
# We'll do targeted regex replacements to avoid ConvertTo-Json reformatting issues

$updatedJson = $rawJson
$bumped = @()

foreach ($pluginName in $pluginsToBump) {
    $plugin = $manifest.plugins | Where-Object { $_.name -eq $pluginName }
    $oldVersion = $plugin.version

    # Parse semver and bump patch
    if ($oldVersion -match '^(\d+)\.(\d+)\.(\d+)$') {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        $patch = [int]$Matches[3] + 1
        $newVersion = "$major.$minor.$patch"
    } else {
        Write-Warning "Plugin '$pluginName' has non-semver version '$oldVersion' — skipping."
        continue
    }

    # Replace version string in JSON — match the specific plugin block
    # Find the plugin's name line and then its version line
    $namePattern = [regex]::Escape("`"name`": `"$pluginName`"")
    $versionPattern = [regex]::Escape("`"version`": `"$oldVersion`"")

    # Find the plugin block and replace version within it
    $pluginBlockPattern = "(?s)($namePattern.+?)`"version`":\s*`"$([regex]::Escape($oldVersion))`""
    $replacement = "`${1}`"version`": `"$newVersion`""

    $updatedJson = [regex]::Replace($updatedJson, $pluginBlockPattern, $replacement, [System.Text.RegularExpressions.RegexOptions]::None)

    $bumped += "$pluginName $oldVersion → $newVersion"
}

if ($bumped.Count -gt 0) {
    # Write updated JSON
    Set-Content -Path $ManifestPath -Value $updatedJson -NoNewline

    # Stage the change
    git add $ManifestPath 2>$null

    Write-Host "[auto-bump] Version bumped and staged:" -ForegroundColor Green
    foreach ($b in $bumped) {
        Write-Host "  ✓ $b" -ForegroundColor Green
    }
}

exit 0
