$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$outputDir = Join-Path $repoRoot "output"
$statusPath = Join-Path $outputDir "full-pass-status.txt"
$summaryPath = Join-Path $outputDir "full-pass-summary.txt"
$auditPath = Join-Path $outputDir "report-card-audit.json"

if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

function Write-Status {
    param([string]$Message)
    $line = "[{0}] {1}" -f ([datetime]::UtcNow.ToString("o")), $Message
    $line | Tee-Object -FilePath $statusPath -Append
}

function Invoke-Step {
    param(
        [string]$Name,
        [string]$Command
    )
    $stdout = Join-Path $outputDir "$Name.out.log"
    $stderr = Join-Path $outputDir "$Name.err.log"
    Write-Status "starting $Name"
    & powershell -NoProfile -Command $Command 1>> $stdout 2>> $stderr
    if ($LASTEXITCODE -ne 0) {
        Write-Status "failed $Name exit_code=$LASTEXITCODE"
        throw "$Name failed with exit code $LASTEXITCODE"
    }
    Write-Status "completed $Name"
}

function Write-Summary {
    $code = @'
import sqlite3
con = sqlite3.connect("data/accountant.db")
cur = con.cursor()
queries = {
    "companies": "select count(*) from companies",
    "company_reports": "select count(*) from company_reports",
    "report_cards": "select count(*) from report_cards",
    "missing_company_reports": "select count(*) from companies c where not exists (select 1 from company_reports r where r.company_id=c.id)",
    "missing_report_cards": "select count(*) from company_reports r where not exists (select 1 from report_cards rc where rc.company_id=r.company_id)",
}
for key, query in queries.items():
    print(f"{key}={cur.execute(query).fetchone()[0]}")
con.close()
'@
    $summary = & powershell -NoProfile -Command "@'`n$code`n'@ | python -"
    $summary | Set-Content -Path $summaryPath
    $summary | ForEach-Object { Write-Status $_ }
}

function Run-Audit {
    Write-Status "starting report-card-audit"
    $audit = & powershell -NoProfile -Command "uv run python scripts/audit_report_cards.py"
    $audit | Set-Content -Path $auditPath
    Write-Status "completed report-card-audit"
}

Set-Content -Path $statusPath -Value ""
Write-Status "full pass runner started"

Push-Location $repoRoot
try {
    Invoke-Step -Name "catch-up-missing-reports" -Command "uv run python scripts/catch_up_missing_reports_parallel.py --workers 6 --report-workers 3"
    Invoke-Step -Name "second-sweep" -Command "uv run python scripts/run_second_sweep.py --workers 4"
    Invoke-Step -Name "refresh-all-reports" -Command "uv run python scripts/refresh_all_report_scores.py --workers 3"
    Invoke-Step -Name "backfill-report-cards" -Command "uv run python scripts/backfill_report_cards.py --workers 3"
    Run-Audit
    Write-Summary
    Write-Status "full pass runner completed"
}
finally {
    Pop-Location
}
