param(
    [string]$TaskName = "Case Capital Accountant Automation",
    [string]$Time = "06:15"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $repoRoot "scripts\run-accountant-automation.ps1"

if (-not (Test-Path $runner)) {
    throw "Automation runner not found: $runner"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $repoRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Imports SEC filings, refreshes stale Accountant reports, rebuilds facts/statements, and exports bottleneck summaries." `
    -Force | Out-Null

Write-Host "Installed scheduled task '$TaskName' to run daily at $Time."
