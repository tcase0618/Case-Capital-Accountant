$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sqlitePath = if ($env:SQLITE_SNAPSHOT_PATH) { $env:SQLITE_SNAPSHOT_PATH } else { Join-Path $repoRoot "data\accountant.db" }
$postgresUrl = "postgresql+psycopg://accountant:accountant@127.0.0.1:5432/accountant"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$logPath = Join-Path $repoRoot ".run\cutover-handoff.log"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logPath -Value "[$timestamp] $Message"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logPath) | Out-Null
Write-Log "cutover handoff watcher started"

while ($true) {
    $migrationProcesses = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -like "*migrate_sqlite_to_postgres.py*"
    }

    if ($migrationProcesses) {
        Write-Log "migration still running"
        Start-Sleep -Seconds 60
        continue
    }

    & $python "$repoRoot\scripts\check_cutover_ready.py" $sqlitePath $postgresUrl *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Log "cutover counts match; restarting app with loop enabled"
        powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\start-accountant.ps1") | Out-Null
        Write-Log "app restart requested"
        exit 0
    }

    Write-Log "migration exited but counts do not match yet"
    Start-Sleep -Seconds 60
}
