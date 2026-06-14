# diagnose_omisell_list.ps1 - READ-ONLY Omisell order/list window diagnostic.
# Runs ecentric_workspace.alerts.api_diag.diagnose_order_list (must be deployed
# first - additive file, no migrate) for the 5 section-6 probe windows and
# prints per-window: raw params sent, reported count, listed numbers, target
# appearance. Also prints tz_evidence (drift_seconds = server-vs-site tz gap).
# NO production writes. Saves full JSON next to this script for handover.
# Usage: .\diagnose_omisell_list.ps1
#        .\diagnose_omisell_list.ps1 -Brand FES-VN -Target ODVN260609D6414F3F
param(
    [string]$Brand = "FES-VN",
    [string]$Target = "ODVN260609D6414F3F"
)
$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$root = Split-Path $PSScriptRoot -Parent
$csvPath = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"
function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function WARN($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
function ERR($m){Write-Host "[ERR] $m" -ForegroundColor Red}
$cred = Import-Csv $csvPath | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }
$M = "ecentric_workspace.alerts.api_diag.diagnose_order_list"

Write-Host ("=== omisell list diagnostic @ {0} (brand={1} target={2}) ===" -f `
    (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Brand, $Target)

$body = @{ brand = $Brand; target_order = $Target } | ConvertTo-Json -Compress
try {
    $r = (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" `
          -Body $body -TimeoutSec 180 -Uri "$base/api/method/$M").message
} catch {
    ERR ("diagnose_order_list FAILED - {0}" -f $_.Exception.Message)
    ERR "Is api_diag.py deployed? (additive file, code-only, no migrate)"
    exit 1
}

# --- tz evidence -------------------------------------------------------------
$tz = $r.tz_evidence
Write-Host ""
Write-Host "--- tz evidence ---"
Write-Host ("site_time_zone           : {0}" -f $tz.site_time_zone)
Write-Host ("now_datetime (site)      : {0}" -f $tz.now_datetime_site)
Write-Host ("datetime.now (server)    : {0}" -f $tz.datetime_now_server)
Write-Host ("datetime.utcnow          : {0}" -f $tz.datetime_utcnow)
Write-Host ("target epoch (prod conv) : {0} -> UTC {1}" -f `
    $tz.target_dt_epoch_production_style, $tz.target_dt_epoch_read_back_utc)
$drift = [int]$tz.drift_seconds
if ($drift -eq 0) { OK ("drift_seconds = 0 (naive epoch conversion CORRECT on server)") }
elseif ([Math]::Abs($drift + 25200) -le 60) { ERR ("drift_seconds = {0} -> SERVER IS UTC, SITE IS UTC+7. Scheduled windows are ~7h in the future. ROOT CAUSE." -f $drift) }
else { WARN ("drift_seconds = {0} (unexpected value - inspect manually)" -f $drift) }

# --- per-window results ------------------------------------------------------
Write-Host ""
Write-Host "--- probe windows ---"
foreach ($p in $r.probes) {
    if ($p.error) { ERR ("{0}: ERROR {1}" -f $p.label, $p.error); continue }
    $line = ("{0,-28} count={1,-5} fetched={2,-4} pages={3} target={4}" -f `
        $p.label, $p.listed_count_reported, $p.fetched_headers, `
        $p.pages_fetched, $p.target_found)
    if ($p.target_found) { OK $line } elseif ([int]$p.fetched_headers -gt 0) { WARN $line } else { Write-Host ("[--]  " + $line) }
    Write-Host ("      params: updated_from={0} updated_to={1} (UTC {2} -> {3})" -f `
        $p.raw_params_first_page.updated_from, $p.raw_params_first_page.updated_to, `
        $p.epoch_window_read_back_utc[0], $p.epoch_window_read_back_utc[1])
    if ($p.listed_order_numbers_total -gt 0) {
        $shown = ($p.listed_order_numbers | Select-Object -First 10) -join ", "
        Write-Host ("      orders ({0}): {1}" -f $p.listed_order_numbers_total, $shown)
    }
    if ($p.target_found -and $p.target_header) {
        Write-Host "      target header time fields:"
        foreach ($prop in $p.target_header.PSObject.Properties) {
            if ($prop.Name -match "time|date|status|shop") {
                Write-Host ("        {0} = {1}" -f $prop.Name, $prop.Value)
            }
        }
    }
}

# --- summary + artifact --------------------------------------------------------
Write-Host ""
Write-Host "--- summary ---"
$foundIn = @($r.summary.target_found_in)
if ($foundIn.Count -gt 0) { OK ("target found in: " + ($foundIn -join ", ")) }
else { WARN "target NOT found in ANY window -> tz alone does not explain; check status filter / list-vs-detail inconsistency with Omisell support" }
Write-Host ("checkpoint last_sync_at (untouched): {0}" -f $r.checkpoint_last_sync_at_untouched)

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $PSScriptRoot ("diag_omisell_list_{0}_{1}.json" -f $Brand, $stamp)
$r | ConvertTo-Json -Depth 12 | Set-Content -Path $outFile -Encoding UTF8
OK ("full JSON saved: " + $outFile)
