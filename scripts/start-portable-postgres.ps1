$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $repoRoot ".run"
$portableRoot = Join-Path $runDir "postgres-portable"
$zipPath = Join-Path $runDir "postgresql-16.15-1-windows-x64-binaries.zip"
$extractContainer = Join-Path $portableRoot "pgsql-v2"
$extractRoot = Join-Path $extractContainer "pgsql"
$dataDir = Join-Path $portableRoot "data-v2"
$logPath = Join-Path $runDir "postgres-portable.log"
$pwFile = Join-Path $runDir "postgres-password.txt"
$downloadUrl = "https://get.enterprisedb.com/postgresql/postgresql-16.15-1-windows-x64-binaries.zip"
$port = 5432
$databaseName = "accountant"
$dbUser = "accountant"
$dbPassword = "accountant"

function Test-PostgresPort {
    $probe = Test-NetConnection -ComputerName 127.0.0.1 -Port $port -WarningAction SilentlyContinue
    return [bool]$probe.TcpTestSucceeded
}

if (Test-PostgresPort) {
    Write-Host "Portable Postgres already reachable on 127.0.0.1:$port"
    exit 0
}

New-Item -ItemType Directory -Force -Path $runDir, $portableRoot | Out-Null

if (-not (Test-Path $extractRoot)) {
    if (-not (Test-Path $zipPath)) {
        Write-Host "Downloading portable PostgreSQL..."
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath
    }
    Write-Host "Extracting portable PostgreSQL..."
    if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
        New-Item -ItemType Directory -Force -Path $extractContainer | Out-Null
        & tar.exe -xf $zipPath -C $extractContainer
    } else {
        Expand-Archive -Path $zipPath -DestinationPath $extractContainer -Force
    }
}

$binDir = Join-Path $extractRoot "bin"
$shareDir = Join-Path $extractRoot "share"
$initdb = Join-Path $binDir "initdb.exe"
$pgCtl = Join-Path $binDir "pg_ctl.exe"
$createdb = Join-Path $binDir "createdb.exe"
$psql = Join-Path $binDir "psql.exe"

if (-not (Test-Path $initdb)) {
    throw "Portable PostgreSQL binaries are missing: $initdb"
}

$pidFile = Join-Path $dataDir "postmaster.pid"
if ((Test-Path $pidFile) -and -not (Test-PostgresPort)) {
    $pidLines = Get-Content -Path $pidFile -ErrorAction SilentlyContinue
    $stalePid = if ($pidLines) { $pidLines[0] } else { $null }
    $staleProcess = if ($stalePid) { Get-Process -Id $stalePid -ErrorAction SilentlyContinue } else { $null }
    if (-not $staleProcess) {
        Remove-Item -LiteralPath $pidFile -Force
        Write-Host "Removed stale PostgreSQL postmaster.pid"
    }
}

$clusterAlreadyInitialized = Test-Path (Join-Path $dataDir "PG_VERSION")
if (-not $clusterAlreadyInitialized) {
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    Set-Content -Path $pwFile -Value $dbPassword -NoNewline
    & $initdb `
        --pgdata="$dataDir" `
        -L "$shareDir" `
        --username="$dbUser" `
        --pwfile="$pwFile" `
        --auth-host=scram-sha-256 `
        --auth-local=trust `
        --encoding=UTF8 `
        --no-instructions | Out-Host
    Remove-Item -LiteralPath $pwFile -ErrorAction SilentlyContinue
}

& $pgCtl -D $dataDir -l $logPath -o "-p $port" start | Out-Host

$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    if (Test-PostgresPort) {
        break
    }
    Start-Sleep -Milliseconds 500
}

if (-not (Test-PostgresPort)) {
    throw "Portable PostgreSQL did not start on 127.0.0.1:$port"
}

if ($clusterAlreadyInitialized) {
    Write-Host ("Portable PostgreSQL running at postgresql+psycopg://{0}:{1}@127.0.0.1:{2}/{3}" -f $dbUser, $dbPassword, $port, $databaseName)
    exit 0
}

$env:PGPASSWORD = $dbPassword
$dbExists = & $psql `
    -w `
    -h 127.0.0.1 `
    -p $port `
    -U $dbUser `
    -d postgres `
    -tAc "select 1 from pg_database where datname = '$databaseName';"
if ($dbExists.Trim() -ne "1") {
    & $createdb -w -h 127.0.0.1 -p $port -U $dbUser $databaseName | Out-Host
}

Write-Host ("Portable PostgreSQL running at postgresql+psycopg://{0}:{1}@127.0.0.1:{2}/{3}" -f $dbUser, $dbPassword, $port, $databaseName)
