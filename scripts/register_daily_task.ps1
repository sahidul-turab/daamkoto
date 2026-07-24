# Register the local daily scrape as a Windows Scheduled Task.
#
# This is the fallback path. The cloud workflow (.github/workflows/daily-scrape.yml)
# is the primary, because it does not care whether this PC is on.
#
# Settings chosen to survive the failure mode seen in scheduler.log, where a
# sweep starting at 22:49 was killed at 00:36 when the machine slept:
#   -WakeToRun          wake the PC if it is asleep at start time
#   -StartWhenAvailable run late if the PC was off at start time
#   -DontStopIfGoingOnBatteries / -AllowStartIfOnBatteries
#   ExecutionTimeLimit  6h, so a wedged run cannot block the next day's
#
# Usage (must be an elevated PowerShell for -WakeToRun to apply):
#   powershell -ExecutionPolicy Bypass -File scripts\register_daily_task.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\register_daily_task.ps1 -At 03:30
#   powershell -ExecutionPolicy Bypass -File scripts\register_daily_task.ps1 -Unregister

param(
    [string] $At = "02:00",
    [string] $TaskName = "DaamKoto Daily Scrape",
    [switch] $Unregister
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $ProjectRoot "scripts\run_daily_scrape.ps1"

if ($Unregister) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Output "Removed scheduled task '$TaskName'."
    } else {
        Write-Output "No scheduled task named '$TaskName' - nothing to remove."
    }
    return
}

if (-not (Test-Path $Runner)) { throw "Runner not found: $Runner" }

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`"" `
    -WorkingDirectory $ProjectRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $At

$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
    -MultipleInstances IgnoreNew

# Run whether or not the user is logged on would need a stored password; running
# as the logged-on user keeps this password-free, and -StartWhenAvailable covers
# the case where the PC was off at the trigger time.
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Runs the DaamKoto scrape pipeline once daily and reports data freshness." `
    -Force | Out-Null

Write-Output "Registered '$TaskName' - daily at $At."
Write-Output ""
Write-Output "Verify : Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Output "Run now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Output "Remove : powershell -File scripts\register_daily_task.ps1 -Unregister"
