<#
.SYNOPSIS
    BEW ERP - Khulna Server Management Script

.DESIGN RULES
    1. Local machine NEVER creates commits independently.
       Every sync cycle starts with: git reset --hard origin/main
       This means local is ALWAYS an exact copy of remote before any change.

    2. Data is committed ON TOP of the reset point, then pushed.
       Because we reset first, local is never "behind" remote — no divergence.

    3. If Dhaka pushes while we are pushing → push fails → caught by try/catch
       → next cycle retries cleanly. No manual intervention ever needed.
#>

param(
    [switch]$Setup,
    [switch]$Run,
    [switch]$Status,
    [switch]$Stop,
    [switch]$Restart
)

$PYTHON  = "C:\Users\PC\AppData\Local\Programs\Python\Python311\python.exe"
$GIT     = "C:\Program Files\Git\bin\git.exe"
$DIR     = $PSScriptRoot
$APP     = "main.py"
$LOG     = "$DIR\automation.log"
$TASK    = "BEW_ERP_Automation"
$BACKUP  = "$env:TEMP\bew_data_backup"

function Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Write-Host $line
    try { $line | Out-File $LOG -Append -Encoding UTF8 } catch {}
}

function Git {
    $flatArgs = @()
    foreach ($a in $args) {
        if ($a -is [System.Array]) { $flatArgs += $a }
        else { $flatArgs += $a }
    }
    & $GIT -C $DIR @flatArgs 2>&1
}

function Get-App {
    $proc = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -like "*$APP*" }
    if (-not $proc) {
        $pids = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess
        if ($pids) {
            $proc = Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -in $pids }
        }
    }
    return $proc
}

function Start-App {
    Log "Starting app..."
    Start-Process -FilePath $PYTHON -ArgumentList $APP -WorkingDirectory $DIR -NoNewWindow
}

function Stop-App {
    $p = Get-App
    if ($p) {
        Log "Stopping app..."
        $p | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }
        Start-Sleep 2
    }
}


# ── STATUS ─────────────────────────────────────────────────────────────────
if ($Status) {
    Write-Host "`n=== BEW ERP Status ===" -ForegroundColor Cyan
    if (Get-App) { Write-Host "[OK]   App: RUNNING" -ForegroundColor Green }
    else          { Write-Host "[FAIL] App: NOT RUNNING" -ForegroundColor Red }

    $t = Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue
    if ($t) { 
        Write-Host "[OK]   Task: $($t.State)" -ForegroundColor Green 
    } else {
        $taskCheck = schtasks /query /tn $TASK 2>&1
        if ($taskCheck -match "Access is denied|ERROR: Access") {
            Write-Host "[OK]   Task: REGISTERED (SYSTEM / Running at Boot)" -ForegroundColor Green
        } else {
            Write-Host "[FAIL] Task: NOT REGISTERED" -ForegroundColor Red
        }
    }


    $ok = Test-NetConnection localhost -Port 5000 -InformationLevel Quiet
    if ($ok) { Write-Host "[OK]   Port 5000: OPEN" -ForegroundColor Green }
    else      { Write-Host "[FAIL] Port 5000: CLOSED" -ForegroundColor Red }

    if (Test-Path $LOG) { Get-Content $LOG -Tail 5 -Encoding UTF8 }
    return
}

# ── STOP ───────────────────────────────────────────────────────────────────
if ($Stop) { Stop-App; return }

# ── RESTART ────────────────────────────────────────────────────────────────
if ($Restart) {
    Log "Restarting app..."
    Stop-App
    Start-App
    return
}


# ── SETUP (Admin) ──────────────────────────────────────────────────────────
if ($Setup) {
    $me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Error "Run PowerShell as Administrator."; return
    }
    $action   = New-ScheduledTaskAction -Execute "powershell.exe" `
                    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""$DIR\erp.ps1"" -Run"

    # Two triggers: fires at boot AND at logon (whichever comes first)
    $triggerBoot   = New-ScheduledTaskTrigger -AtStartup
    $triggerLogon  = New-ScheduledTaskTrigger -AtLogOn

    $settings = New-ScheduledTaskSettingsSet `
                    -AllowStartIfOnBatteries `
                    -DontStopIfGoingOnBatteries `
                    -StartWhenAvailable `
                    -RestartCount 10 `
                    -RestartInterval (New-TimeSpan -Minutes 1) `
                    -ExecutionTimeLimit ([TimeSpan]::Zero)   # run forever

    if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TASK -Confirm:$false
    }
    Register-ScheduledTask -Action $action `
                           -Trigger $triggerBoot, $triggerLogon `
                           -Settings $settings `
                           -TaskName $TASK `
                           -User "SYSTEM" `
                           -RunLevel Highest

    Write-Host "Task registered. Triggers: AtStartup + AtLogon. User: SYSTEM" -ForegroundColor Green
    Start-ScheduledTask -TaskName $TASK
    return
}

# ── RUN (main loop — runs forever) ─────────────────────────────────────────
if ($Run) {
    Log "=== ERP Automation started ==="
    Set-Location $DIR

    while ($true) {
        try {
            # ── 1. Keep app alive ─────────────────────────────────────
            if (-not (Get-App)) { Start-App }

            # ── 2. Fetch latest remote state ──────────────────────────
            Git fetch, origin, main | Out-Null
            $localHash  = (Git rev-parse, HEAD)       -join "" -replace "\s",""
            $remoteHash = (Git rev-parse, origin/main) -join "" -replace "\s",""
            $codeChanged = ($localHash -ne $remoteHash)

            # ── 3. Save local data before any git operation ───────────
            if (Test-Path "$DIR\data") {
                if (Test-Path $BACKUP) { Remove-Item $BACKUP -Recurse -Force }
                Copy-Item "$DIR\data" $BACKUP -Recurse -Force
            }

            # ── 4. Reset to remote (code always wins) ─────────────────
            #    This is the KEY step: local is now IDENTICAL to remote.
            #    History cannot diverge from this point.
            Git reset, --hard, origin/main | Out-Null

            # ── 5. Restore local data on top of reset ─────────────────
            if (Test-Path $BACKUP) {
                Copy-Item "$BACKUP\*" "$DIR\data\" -Recurse -Force
            }

            # ── 6. If data changed, commit and push ───────────────────
            $dataDiff = (Git status, --short, data) -join ""
            if ($dataDiff -ne "") {
                Log "Data changed. Pushing to GitHub..."
                Git add, data | Out-Null
                Git commit, -m, "data: khulna sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')" | Out-Null
                $pushResult = (Git push, origin, main) -join " "
                if ($pushResult -match "error|rejected") {
                    Log "Push blocked (Dhaka may have pushed). Will retry next cycle."
                } else {
                    Log "Data pushed."
                }
            }

            # ── 7. Restart app only if code changed ───────────────────
            if ($codeChanged) {
                Log "Code updated from Dhaka. Restarting app..."
                Stop-App
                Start-App
            }

        } catch {
            Log "ERROR: $($_.Exception.Message)"
        }

        Start-Sleep -Seconds 600   # check every 10 minutes
    }
}
