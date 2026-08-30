$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$envPath = Join-Path $repoRoot ".env"
$envExamplePath = Join-Path $repoRoot ".env.example"
$pidPath = Join-Path $repoRoot ".accountant.pid"
$logDir = Join-Path $repoRoot ".run"
$stdoutLog = Join-Path $logDir "accountant.out.log"
$stderrLog = Join-Path $logDir "accountant.err.log"
$port = 8010
$defaultDatabaseUrl = "postgresql+psycopg://accountant:accountant@127.0.0.1:5432/accountant"

function Test-Url {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Get-LatestWriteTime {
    param([string]$Path, [string]$Filter = "*")
    if (-not (Test-Path $Path)) {
        return [datetime]::MinValue
    }
    $items = Get-ChildItem -Path $Path -Recurse -File -Filter $Filter -ErrorAction SilentlyContinue
    if (-not $items) {
        return [datetime]::MinValue
    }
    return ($items | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).LastWriteTimeUtc
}

function Set-DotEnvValueIfMissing {
    param(
        [string]$Name,
        [string]$DotEnvPath
    )
    $existing = [Environment]::GetEnvironmentVariable($Name)
    if ($existing) {
        return
    }
    if (-not (Test-Path $DotEnvPath)) {
        return
    }
    $prefix = "$Name="
    $line = Get-Content -Path $DotEnvPath | Where-Object { $_.StartsWith($prefix) } | Select-Object -First 1
    if (-not $line) {
        return
    }
    $value = $line.Substring($prefix.Length).Trim()
    if ($value) {
        Set-Item -Path "Env:$Name" -Value $value
    }
}

function Get-DotEnvValue {
    param(
        [string]$Name,
        [string]$DotEnvPath
    )
    if (-not (Test-Path $DotEnvPath)) {
        return $null
    }
    $prefix = "$Name="
    $line = Get-Content -Path $DotEnvPath | Where-Object { $_.StartsWith($prefix) } | Select-Object -First 1
    if (-not $line) {
        return $null
    }
    return $line.Substring($prefix.Length).Trim()
}

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment missing. Run 'uv sync --extra dev' in $repoRoot first."
}

if (-not (Test-Path $envPath) -and (Test-Path $envExamplePath)) {
    Copy-Item -LiteralPath $envExamplePath -Destination $envPath
}

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    Push-Location $frontendDir
    try {
        npm install | Out-Host
    }
    finally {
        Pop-Location
    }
}

$distIndex = Join-Path $frontendDir "dist\index.html"
$srcLatest = Get-LatestWriteTime -Path (Join-Path $frontendDir "src")
$distLatest = Get-LatestWriteTime -Path (Join-Path $frontendDir "dist")
$packageLatest = Get-LatestWriteTime -Path $frontendDir -Filter "package.json"

if (-not (Test-Path $distIndex) -or $srcLatest -gt $distLatest -or $packageLatest -gt $distLatest) {
    Write-Host "Building frontend bundle..."
    Push-Location $frontendDir
    try {
        npm run build | Out-Host
    }
    finally {
        Pop-Location
    }
}

$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $process.Id -Force
        Start-Sleep -Milliseconds 500
    }
}

$staleProcesses = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*$repoRoot*" -and
        $_.CommandLine -like "*scripts\\serve_local.py*"
    }
foreach ($staleProcess in $staleProcesses) {
    Stop-Process -Id $staleProcess.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 500

Remove-Item -LiteralPath $stdoutLog, $stderrLog -ErrorAction SilentlyContinue

$databaseUrl = [Environment]::GetEnvironmentVariable("DATABASE_URL")
if (-not $databaseUrl) {
    $databaseUrl = Get-DotEnvValue -Name "DATABASE_URL" -DotEnvPath $envPath
}
if (-not $databaseUrl) {
    $databaseUrl = $defaultDatabaseUrl
}
$env:DATABASE_URL = $databaseUrl
$env:ACCOUNTANT_ENV = "development"
$env:DATA_DIR = (Join-Path $repoRoot "data")
$env:PYTHONPATH = (Join-Path $repoRoot "src")
$configuredWorkers = Get-DotEnvValue -Name "MACHINE_WORKERS" -DotEnvPath $envPath
if (-not $configuredWorkers) {
    $configuredWorkers = "4"
}
if ($databaseUrl -like 'postgresql*') {
    try {
        $workerValue = [int]$configuredWorkers
        if ($workerValue -gt 4) {
            $configuredWorkers = "4"
        }
    } catch {
        $configuredWorkers = "4"
    }
}
$env:MACHINE_WORKERS = $configuredWorkers
$stockIntelEnv = "C:\Case Capital\stock-intel\backend\.env"
foreach ($name in @(
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "ALPACA_DATA_BASE_URL",
    "ALPACA_STOCK_FEED",
    "OPTIONS_APCA_API_KEY_ID",
    "OPTIONS_APCA_API_SECRET_KEY",
    "OPTIONS_APCA_DATA_BASE_URL",
    "OPTIONS_APCA_STOCK_FEED"
)) {
    Set-DotEnvValueIfMissing -Name $name -DotEnvPath $envPath
}
$stockIntelEnv = "C:\Case Capital\stock-intel\backend\.env"
foreach ($name in @(
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "ALPACA_DATA_BASE_URL",
    "ALPACA_STOCK_FEED",
    "OPTIONS_APCA_API_KEY_ID",
    "OPTIONS_APCA_API_SECRET_KEY",
    "OPTIONS_APCA_DATA_BASE_URL",
    "OPTIONS_APCA_STOCK_FEED"
)) {
    Set-DotEnvValueIfMissing -Name $name -DotEnvPath $stockIntelEnv
}
$serveScript = Join-Path $repoRoot "scripts\serve_local.py"
$pythonLauncher = $venvPython

if ($databaseUrl -like 'postgresql*') {
    $postgresReachable = Test-NetConnection -ComputerName 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue
    if (-not $postgresReachable.TcpTestSucceeded) {
        $postgresScript = Join-Path $repoRoot "scripts\start-portable-postgres.ps1"
        $postgresBootstrap = Start-Process `
            -FilePath "powershell.exe" `
            -ArgumentList @("-ExecutionPolicy", "Bypass", "-File", $postgresScript) `
            -WorkingDirectory $repoRoot `
            -WindowStyle Hidden `
            -PassThru
        $pgDeadline = (Get-Date).AddSeconds(45)
        while ((Get-Date) -lt $pgDeadline) {
            $postgresReachable = Test-NetConnection -ComputerName 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue
            if ($postgresReachable.TcpTestSucceeded) {
                break
            }
            if ($postgresBootstrap.HasExited) {
                break
            }
            Start-Sleep -Milliseconds 500
        }
        $postgresReachable = Test-NetConnection -ComputerName 127.0.0.1 -Port 5432 -WarningAction SilentlyContinue
        if (-not $postgresReachable.TcpTestSucceeded) {
            throw "Postgres is not reachable on 127.0.0.1:5432 after bootstrap."
        }
    }
}

$process = Start-Process `
    -FilePath $pythonLauncher `
    -ArgumentList @("-u", $serveScript) `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) {
        break
    }
    if (Test-Url -Url "http://127.0.0.1:$port/health") {
        $activeListener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($activeListener) {
            $activeListener.OwningProcess | Set-Content -Path $pidPath
        } else {
            $process.Id | Set-Content -Path $pidPath
        }
        Write-Host "Accountant running at http://127.0.0.1:$port/"
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

if ($process.HasExited) {
    $stderr = if (Test-Path $stderrLog) { Get-Content $stderrLog -Raw } else { "" }
    throw "Accountant failed to start.`n$stderr"
}

throw "Accountant did not become healthy within 90 seconds."
