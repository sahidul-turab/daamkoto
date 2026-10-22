# Nightly scrape for retailers that block GitHub Actions' datacenter IPs but
# serve a home connection (scheduler.py LOCAL_ONLY_RETAILERS, e.g. EZGadgets).
#
# Runs from this PC on a Windows scheduled task and loads straight into
# production Neon, exactly like the GitHub job does for the other retailers.
# Background removal is skipped here: the next GitHub "report" job cuts out
# every current image that has no cutout yet, and only it holds R2 settings.
#
# Register (once):
#   powershell -ExecutionPolicy Bypass -File scripts\run_local_scrape.ps1 -Register
# Remove:
#   Unregister-ScheduledTask -TaskName "DaamKoto local scrape" -Confirm:$false
# Run now:
#   powershell -ExecutionPolicy Bypass -File scripts\run_local_scrape.ps1

param(
    [switch]$Register,
    [string]$At = "21:00"   # local time; well before GitHub's 20:00 UTC sweep
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$TaskName = "DaamKoto local scrape"

if ($Register) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" `
        -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -Daily -At $At
    # StartWhenAvailable: if the PC was off at $At, run as soon as it is back on.
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 3) -DontStopIfGoingOnBatteries `
        -AllowStartIfOnBatteries
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Description "DaamKoto: scrape LOCAL_ONLY_RETAILERS into Neon" -Force | Out-Null
    Write-Output "Registered '$TaskName' daily at $At (runs late if the PC was off)."
    exit 0
}

Set-Location $Root
New-Item -ItemType Directory -Force "logs" | Out-Null
$log = Join-Path $Root "logs\local_scrape.log"

# Production database: NEON_URL from .env.neon, passed as DATABASE_URL, which
# the pipeline and loader prefer over the local .env settings.
$neon = (Get-Content ".env.neon" | Where-Object { $_ -match '^\s*NEON_URL\s*=' } |
         Select-Object -First 1) -replace '^\s*NEON_URL\s*=\s*', '' -replace '^["'']|["'']$', ''
if (-not $neon) { throw "NEON_URL not found in .env.neon" }
$env:DATABASE_URL = $neon
$env:PYTHONIOENCODING = "utf-8"

$python = Join-Path $Root "venv\Scripts\python.exe"
$retailers = & $python -c "import scheduler; print(' '.join(scheduler.LOCAL_ONLY_RETAILERS))" 2>$null |
             Select-Object -Last 1
if (-not $retailers) { throw "Could not read LOCAL_ONLY_RETAILERS from scheduler.py" }

"`n===== $(Get-Date -Format s) local scrape: $retailers =====" | Add-Content $log -Encoding utf8
& $python scheduler.py --once --no-cutouts --retailers $retailers.Split(" ") *>&1 |
    Add-Content $log -Encoding utf8
"===== exit $LASTEXITCODE =====" | Add-Content $log -Encoding utf8
exit $LASTEXITCODE
