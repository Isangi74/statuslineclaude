<#
.SYNOPSIS
    statuslineclaude installer for Windows PowerShell.

.DESCRIPTION
    Thin wrapper: locates a Python interpreter and hands over to install.py,
    where the actual logic lives.

.EXAMPLE
    .\install.ps1
    Installs or updates statuslineclaude.

.EXAMPLE
    .\install.ps1 -Uninstall
    Removes the scripts and the settings.json entries.

.EXAMPLE
    .\install.ps1 -DryRun
    Prints the changes without applying them.
#>
[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installer = Join-Path $scriptDir 'install.py'

$python = $null
foreach ($candidate in @('python', 'py', 'python3')) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($command) { $python = $command.Source; break }
}

if (-not $python) {
    Write-Error @'
Python 3.9+ is required but was not found on PATH.
Install it from https://www.python.org/downloads/ or run:
    winget install Python.Python.3.12
Make sure "Add python.exe to PATH" is ticked during setup.
'@
    exit 1
}

$arguments = @($installer)
if ($Uninstall) { $arguments += '--uninstall' }
if ($DryRun) { $arguments += '--dry-run' }

& $python @arguments
exit $LASTEXITCODE
