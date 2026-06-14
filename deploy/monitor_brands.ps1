# monitor_brands.ps1 - 24h health snapshot for the scheduled brands (READ-ONLY).
# Prints one status line per brand: running flag, last_sync_at freshness, breaker,
# last-run state, failed total. Run ad hoc during the 24h window (step 9).
# Usage: .\monitor_brands.ps1                       (defaults FES-VN + LOF-VN)
#        .\monitor_brands.ps1 -Brands FES-VN,LOF-VN
param([string[]]$Brands = @("FES-VN","LOF-VN"))
$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$root = Split-Path $PSScriptRoot -Parent
$csvPath = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"
function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function WARN($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
function ERR($m){Write-Host "[ERR] $m" -ForegroundColor Red}
$cred = Import-Csv $csvPath | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }
$M = "ecentric_workspace.alerts.api_omisell"
Write-Host ("=== brand health @ {0} ===" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
foreach ($b in $Brands) {
    try {
        $st = (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" -Body (@{brand=$b}|ConvertTo-Json -Compress) -Uri "$base/api/method/$M.pull_status").message
        $state = if ($st.last_run) { $st.last_run.state } else { "none" }
        $failedTotal = 0; if ($st.last_run) { foreach ($s in @($st.last_run.summaries)) { $failedTotal += [int]($s.failed) } }
        $age = "n/a"
        if ($st.last_sync_at) { $age = [int]((New-TimeSpan -Start ([datetime]$st.last_sync_at) -End (Get-Date)).TotalMinutes) }
        $runFlag = "idle"; if ($st.running_since) { $runFlag = "yes" }
        $line = ("{0,-8} run={1,-5} sync_age_min={2,-6} breaker={3} last_state={4} failed={5} pull_disabled={6}" -f `
            $b, $runFlag, $age, $st.consecutive_failures, $state, $failedTotal, $st.pull_disabled)
        if ([int]$st.consecutive_failures -ge 1 -or $state -eq "error" -or $failedTotal -gt 0) { ERR $line }
        elseif ($age -ne "n/a" -and [int]$age -gt 45) { WARN ($line + "  (sync stale > 45 min)") }
        else { OK $line }
    } catch { ERR ("{0}: pull_status FAILED - {1}" -f $b, $_.Exception.Message) }
}
