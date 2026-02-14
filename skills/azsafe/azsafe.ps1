<#
.SYNOPSIS
    Safe Azure CLI proxy - only allows read-only commands.

.DESCRIPTION
    azsafe is a proxy for the Azure CLI that only allows read-only verbs.
    Destructive operations (create, delete, update, etc.) are blocked.
    Unknown verbs are blocked and logged for review.

.EXAMPLE
    .\azsafe.ps1 group list
    .\azsafe.ps1 vm show --name myvm --resource-group myrg
    .\azsafe.ps1 storage account list --query "[].name"

.NOTES
    Blocked commands are logged to ~/.az-proxy-blocked.log
    Edit allowed-verbs.txt to add/remove allowed verbs.
#>

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = 'Stop'

# Get the directory where this script lives
$ScriptDir = $PSScriptRoot

# Load allowed verbs from config file
$AllowedVerbsFile = Join-Path $ScriptDir 'allowed-verbs.txt'
if (-not (Test-Path $AllowedVerbsFile)) {
    Write-Error "azsafe: Config file not found: $AllowedVerbsFile"
    exit 1
}

$AllowedVerbs = Get-Content $AllowedVerbsFile | 
    Where-Object { $_ -and -not $_.StartsWith('#') } | 
    ForEach-Object { $_.Trim().ToLower() } |
    Where-Object { $_ }

$AllowedVerbsSet = @{}
foreach ($v in $AllowedVerbs) {
    $AllowedVerbsSet[$v] = $true
}

# Log file for blocked commands
$LogFile = Join-Path $HOME '.az-proxy-blocked.log'

function Write-BlockedLog {
    param([string]$Command, [string]$Reason)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $logEntry = "[$timestamp] BLOCKED: $Reason | Command: az $Command"
    Add-Content -Path $LogFile -Value $logEntry
}

function Get-HttpMethod {
    # Extract --method, -m, or --http-method value from arguments
    param([string[]]$CmdArgs)
    
    for ($i = 0; $i -lt $CmdArgs.Count; $i++) {
        $arg = $CmdArgs[$i]
        if ($arg -in @('--method', '-m', '--http-method')) {
            if ($i + 1 -lt $CmdArgs.Count) {
                return $CmdArgs[$i + 1].ToLower()
            }
        }
        # Handle --method=value or --http-method=value format
        if ($arg -match '^(--method|-m|--http-method)=(.+)$') {
            return $Matches[2].ToLower()
        }
    }
    return $null  # Not specified, will use default (GET)
}

function Get-Verb {
    param([string[]]$CmdArgs)
    
    # Azure CLI structure: az [global-options] <group> [subgroup...] <verb> [options]
    # We need to find the verb, which is the last positional argument before options start
    # Options are anything starting with - and their values
    
    $positionalArgs = @()
    $i = 0
    while ($i -lt $CmdArgs.Count) {
        $arg = $CmdArgs[$i]
        
        # If it starts with -, it's a flag - skip it and potentially its value
        if ($arg.StartsWith('-')) {
            $i++
            # If there's a next arg and it doesn't start with -, it's likely the flag's value
            if ($i -lt $CmdArgs.Count -and -not $CmdArgs[$i].StartsWith('-')) {
                # Check if current flag is a known boolean flag (no value)
                $booleanFlags = @('--help', '-h', '--verbose', '--debug', '--only-show-errors', '--yes', '-y', '--no-wait')
                if ($arg -notin $booleanFlags) {
                    $i++ # Skip the value
                }
            }
            continue
        }
        
        # Not a flag and not a key=value pair - it's a positional argument
        if (-not $arg.Contains('=')) {
            $positionalArgs += $arg
        }
        $i++
    }
    
    # The verb is the last positional argument
    # In "az vm disk attach", positionalArgs would be [vm, disk, attach], verb is "attach"
    if ($positionalArgs.Count -gt 0) {
        return $positionalArgs[-1].ToLower()
    }
    
    return $null
}

# Handle empty arguments (just show help)
if (-not $Arguments -or $Arguments.Count -eq 0) {
    & az
    exit $LASTEXITCODE
}

# Handle global flags that don't need verb checking
$firstArg = $Arguments[0].ToLower()
if ($firstArg -in @('--version', '-v', '--help', '-h')) {
    & az @Arguments
    exit $LASTEXITCODE
}

# Extract the verb from arguments
$verb = Get-Verb -CmdArgs $Arguments

# If no verb found (e.g., just "az group"), allow it (will show help)
if (-not $verb) {
    & az @Arguments
    exit $LASTEXITCODE
}

# Special handling for REST-style commands - allow if method is GET (or not specified)
# "az rest" uses --method (default: GET)
# "az devops invoke" uses --http-method (default: GET)
# NOTE: Other invoke commands (az vm run-command invoke, az aks command invoke) are NOT REST-style
#       and always execute code - they remain blocked by the normal verb check
$isRestCommand = ($verb -eq 'rest') -or 
                 ($verb -eq 'invoke' -and 'devops' -in $Arguments)

if ($isRestCommand) {
    $method = Get-HttpMethod -CmdArgs $Arguments
    # Allow if method is GET, HEAD, OPTIONS, or not specified (defaults to GET)
    if (-not $method -or $method -in @('get', 'head', 'options')) {
        & az @Arguments
        exit $LASTEXITCODE
    }
    else {
        # Blocked - non-GET method
        $commandString = $Arguments -join ' '
        $reason = "REST command with method '$method' is not allowed (only GET/HEAD/OPTIONS permitted)"
        
        Write-BlockedLog -Command $commandString -Reason $reason
        
        Write-Host "azsafe: BLOCKED - $reason" -ForegroundColor Red
        Write-Host "azsafe: Command: az $commandString" -ForegroundColor Red
        Write-Host "azsafe: For REST commands (az rest, az devops invoke), only read-only methods are allowed" -ForegroundColor Yellow
        Write-Host "azsafe: This attempt has been logged to $LogFile" -ForegroundColor Yellow
        
        exit 1
    }
}

# Check if verb is allowed
if ($AllowedVerbsSet.ContainsKey($verb)) {
    # Allowed - pass through to real az
    & az @Arguments
    exit $LASTEXITCODE
}
else {
    # Blocked - write error and log
    $commandString = $Arguments -join ' '
    $reason = "Verb '$verb' is not in the allowed list"
    
    Write-BlockedLog -Command $commandString -Reason $reason
    
    Write-Host "azsafe: BLOCKED - $reason" -ForegroundColor Red
    Write-Host "azsafe: Command: az $commandString" -ForegroundColor Red
    Write-Host "azsafe: Allowed verbs: $($AllowedVerbs -join ', ')" -ForegroundColor Yellow
    Write-Host "azsafe: This attempt has been logged to $LogFile" -ForegroundColor Yellow
    Write-Host "azsafe: To allow this verb, add it to: $AllowedVerbsFile" -ForegroundColor Yellow
    
    exit 1
}
