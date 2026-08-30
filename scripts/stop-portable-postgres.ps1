$ErrorActionPreference = "SilentlyContinue"

$repoRoot = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $repoRoot ".run\postgres-portable\data-v2"
$pgCtl = Join-Path $repoRoot ".run\postgres-portable\pgsql-v2\pgsql\bin\pg_ctl.exe"

if ((Test-Path $pgCtl) -and (Test-Path $dataDir)) {
    & $pgCtl -D $dataDir stop -m fast | Out-Null
}
