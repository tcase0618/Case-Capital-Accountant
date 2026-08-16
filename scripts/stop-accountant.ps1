$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $repoRoot ".accountant.pid"
$port = 8010

if (Test-Path $pidPath) {
    $pidValue = Get-Content $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pidValue) {
        $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $process.Id -Force
        }
    }
    Remove-Item -LiteralPath $pidPath -ErrorAction SilentlyContinue
}

$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
}

Write-Host "Accountant stopped."
