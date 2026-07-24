# Local daily scrape wrapper - the fallback for when the cloud run is blocked.
#
# Two things this does that running scheduler.py by hand does not:
#
#  1. Keeps the machine awake for the duration. Every failure in the existing
#     scheduler.log is exit code 3221226091 (STATUS_DLL_INIT_FAILED_LOGOFF) -
#     Windows killing the pipeline mid-sweep when the PC slept. A ~2.7h sweep
#     will always outlast the default sleep timer, so we hold a power request
#     until the run finishes.
#
#  2. Writes its own transcript, so a run that dies still leaves evidence.
#
# Run directly to test:
#   powershell -ExecutionPolicy Bypass -File scripts\run_daily_scrape.ps1
#
# To point this at Neon instead of the local database, set DATABASE_* in .env
# (see DEPLOY.md) - this script does not manage credentials.

param(
    [string[]] $Categories = @(),
    [string[]] $Retailers  = @()
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$Transcript = Join-Path $LogDir "daily_scrape_task.log"

# --- keep the machine awake -------------------------------------------------
# ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001)
# Deliberately omits ES_DISPLAY_REQUIRED so the screen may still switch off.
$SleepBlocker = @"
using System;
using System.Runtime.InteropServices;
public static class SleepBlocker {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
    public static void Prevent() { SetThreadExecutionState(0x80000000 | 0x00000001); }
    public static void Restore() { SetThreadExecutionState(0x80000000); }
}
"@

$python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment not found at $python - create it before scheduling this task."
}

Add-Type -TypeDefinition $SleepBlocker -ErrorAction SilentlyContinue
[SleepBlocker]::Prevent()

$started = Get-Date
Add-Content -Path $Transcript -Encoding utf8 -Value "`n===== run started $($started.ToString('u')) ====="

try {
    $pipelineArgs = @("scheduler.py", "--once")
    if ($Categories.Count -gt 0) { $pipelineArgs += "--categories"; $pipelineArgs += $Categories }
    if ($Retailers.Count  -gt 0) { $pipelineArgs += "--retailers";  $pipelineArgs += $Retailers }

    Add-Content -Path $Transcript -Encoding utf8 -Value "CMD: $python $($pipelineArgs -join ' ')"
    & $python @pipelineArgs 2>&1 | Tee-Object -FilePath $Transcript -Append
    $code = $LASTEXITCODE

    # Surface silent empty scrapes the same way the cloud run does.
    & $python "scripts\freshness_report.py" 2>&1 | Tee-Object -FilePath $Transcript -Append

    $elapsed = (Get-Date) - $started
    Add-Content -Path $Transcript -Encoding utf8 -Value `
        "===== run finished exit=$code after $([int]$elapsed.TotalMinutes) min ====="
    exit $code
}
finally {
    [SleepBlocker]::Restore()
}
