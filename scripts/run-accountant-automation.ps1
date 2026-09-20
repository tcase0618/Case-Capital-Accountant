param(
    [switch]$RefreshAllScores,
    [switch]$SkipImport,
    [switch]$SkipStaleRefresh,
    [string]$FromDate = "",
    [string]$ToDate = "",
    [int]$ImportWorkers = 8,
    [int]$RefreshWorkers = 8,
    [int]$ScoreWorkers = 3
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repoRoot "artifacts\automation"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$postgresScript = Join-Path $repoRoot "scripts\start-portable-postgres.ps1"

if (-not (Test-Path $python)) {
    throw "Virtual environment missing. Run 'uv sync --extra dev' in $repoRoot first."
}

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$postgresReachable = Test-NetConnection -ComputerName 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue
if (-not $postgresReachable.TcpTestSucceeded) {
    Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @("-ExecutionPolicy", "Bypass", "-File", $postgresScript) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden | Out-Null
    $deadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Milliseconds 750
        $postgresReachable = Test-NetConnection -ComputerName 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue
    } while (-not $postgresReachable.TcpTestSucceeded -and (Get-Date) -lt $deadline)
    if (-not $postgresReachable.TcpTestSucceeded) {
        throw "Postgres is not reachable on 127.0.0.1:5432 after bootstrap."
    }
}

$argsList = @(
    "scripts\run_accountant_automation.py",
    "--import-workers", "$ImportWorkers",
    "--refresh-workers", "$RefreshWorkers",
    "--score-workers", "$ScoreWorkers"
)

if ($RefreshAllScores) {
    $argsList += "--refresh-all-scores"
}
if ($SkipImport) {
    $argsList += "--skip-import"
}
if ($SkipStaleRefresh) {
    $argsList += "--skip-stale-refresh"
}
if ($FromDate) {
    $argsList += @("--from-date", $FromDate)
}
if ($ToDate) {
    $argsList += @("--to-date", $ToDate)
}

Push-Location $repoRoot
try {
    & $python @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
