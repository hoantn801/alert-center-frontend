# onboard_lof_pull.ps1 - Brand #2 (LOF) MANUAL PULL + VERIFY.
# Order: A omisell_probe -> B pull_preview (READ-ONLY) -> [stop unless -Confirm]
#        -> C pull_recent (background job) -> D poll pull_status -> E verify.
# Omisell side is READ-ONLY (auth + list + detail GETs). Ingestion writes go to
# Frappe (Order Log / Item / EC Alert) only - NO Omisell write, NO stock/buffer
# write, DS1 stays locked (dry_run_stock_lock honored). ASCII-only source.
#
# SAFE (no ingestion write): .\onboard_lof_pull.ps1 -Brand LOF-VN
#   -> runs probe + preview, then STOPS and asks you to re-run with -Confirm.
# DO THE PULL:               .\onboard_lof_pull.ps1 -Brand LOF-VN -Confirm
param(
    [Parameter(Mandatory=$true)][string]$Brand,
    [switch]$Confirm,
    [int]$MaxPollSeconds = 600
)
$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$root = Split-Path $PSScriptRoot -Parent
$csvPath = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"
function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function WARN($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
function ERR($m){Write-Host "[ERR] $m" -ForegroundColor Red}
function INFO($m){Write-Host "[..]  $m" -ForegroundColor Cyan}
$cred = Import-Csv $csvPath | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }
$M = "ecentric_workspace.alerts.api_omisell"
function Call($method, $bodyObj) {
    $uri = "$base/api/method/$M.$method"
    if ($bodyObj) { return (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" -Body ($bodyObj | ConvertTo-Json -Compress) -Uri $uri).message }
    return (Invoke-RestMethod -Method Post -Headers $h -Uri $uri).message
}

# --- A: credential probe (auth + 1 shop) ---
INFO "A - omisell_probe (auth + shop list head) ..."
try {
    $p = Call "omisell_probe" @{ brand = $Brand }
    OK ("probe ok: shop_count={0} auth_scheme={1} rate_hdr={2}" -f $p.shop_count, $p.auth_scheme, $p.rate_limit_header)
    OK "credential_status set to Active by probe."
} catch { ERR ("probe FAILED: {0}" -f $_.Exception.Message); ERR "Fix credentials in BIS, then retry. ABORT."; exit 1 }

# --- B: pull_preview (READ-ONLY count, no DB write) ---
INFO "B - pull_preview (dry-run count of next window) ..."
$pv = Call "pull_preview" @{ brand = $Brand; hours = 1 }
OK ("preview: window {0} -> {1} | would_list = {2}" -f $pv.window[0], $pv.window[1], $pv.would_list)

if (-not $Confirm) {
    Write-Host ""
    WARN "STOP: probe + preview done (no orders ingested)."
    WARN ("Review would_list above. To run the actual pull, re-run with -Confirm:")
    WARN ("    .\onboard_lof_pull.ps1 -Brand {0} -Confirm" -f $Brand)
    exit 0
}

# --- C: pull_recent (enqueues background job) ---
INFO "C - pull_recent (background catch-up job) ..."
$pr = Call "pull_recent" @{ brand = $Brand }
OK ("queued: job_id={0}" -f $pr.job_id)

# --- D: poll pull_status until the run finishes (or timeout) ---
INFO "D - polling pull_status ..."
$deadline = (Get-Date).AddSeconds($MaxPollSeconds)
$st = $null
do {
    Start-Sleep -Seconds 10
    $st = Call "pull_status" @{ brand = $Brand }
    $state = if ($st.last_run) { $st.last_run.state } else { "(no run yet)" }
    INFO ("   running_since={0} last_state={1} last_sync_at={2} breaker={3}" -f $st.running_since, $state, $st.last_sync_at, $st.consecutive_failures)
} while ($st.running_since -and (Get-Date) -lt $deadline)

# --- E: verification gates ---
Write-Host ""
INFO "E - verification ..."
$fail = 0
$lr = $st.last_run
if (-not $lr) { ERR "no last_run summary found"; $fail++ }
else {
    if ($lr.state -eq "done") { OK "state = done" } else { ERR ("state = {0} (expected done). error={1}" -f $lr.state, $lr.error); $fail++ }
    if ($lr.caught_up) { OK "caught_up = true" } else { WARN ("caught_up = false (chunks_done={0}/{1}; checkpoint holds - safe to re-run)" -f $lr.chunks_done, $lr.chunks_planned) }
    $failedTotal = 0
    foreach ($s in @($lr.summaries)) { $failedTotal += [int]($s.failed) }
    if ($failedTotal -eq 0) { OK "failed = 0 across all chunks" } else { ERR ("failed = {0} (see failed_order_numbers in summaries)" -f $failedTotal); $fail++ }
}
if ([int]$st.consecutive_failures -eq 0) { OK "breaker = 0 (closed)" } else { ERR ("consecutive_failures = {0}" -f $st.consecutive_failures); $fail++ }
if (-not $st.running_since) { OK "no stuck running lock" } else { ERR ("running lock still set since {0} (poll timed out at {1}s - re-run pull_status)" -f $st.running_since, $MaxPollSeconds); $fail++ }

# alerts appear under LOF?
$enc = [uri]::EscapeDataString('[["brand","=","' + $Brand + '"]]')
$alerts = (Invoke-RestMethod -Headers $h -Uri ("$base/api/resource/EC Alert?filters=$enc&fields=[`"name`",`"rule_code`",`"status`"]&limit_page_length=5")).data
$cntAll = (Invoke-RestMethod -Headers $h -Uri ("$base/api/resource/EC Alert?filters=$enc&limit_page_length=1&fields=[`"name`"]")).data
if ($alerts -and $alerts.Count -ge 1) { OK ("alerts under {0}: showing {1} (e.g. {2})" -f $Brand, $alerts.Count, ($alerts[0].rule_code)) }
else { WARN ("no EC Alert rows for {0} yet - OK if this window had no priced violations / no orders; widen window or wait for activity." -f $Brand) }

Write-Host ""
if ($fail -eq 0) {
    OK ("MANUAL PULL VERIFIED for {0}." -f $Brand)
    OK ("NEXT (runbook step 8): add '{0}' to site_config ec_alerts_scheduled_pull_brands alongside FES-VN, on the Frappe Cloud dashboard. Then 24h monitoring (step 9)." -f $Brand)
} else { ERR ("{0} verification blocker(s). Do NOT add {1} to the scheduled allowlist yet." -f $fail, $Brand); exit 1 }
