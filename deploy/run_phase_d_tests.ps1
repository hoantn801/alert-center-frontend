# run_phase_d_tests.ps1 - Phase D manual T0-T3 driver (read-only Omisell ingestion)
# Token read at runtime from local CSV - never hardcoded, never printed.
# Usage:
#   .\run_phase_d_tests.ps1 -Step T0 -Brand BBT-VN
#   .\run_phase_d_tests.ps1 -Step T1 -Brand BBT-VN
#   .\run_phase_d_tests.ps1 -Step T2 -Brand BBT-VN -OrderNumber OMI-XXXX [-CaptureGolden]
#   .\run_phase_d_tests.ps1 -Step T3 -Brand BBT-VN -From "2026-06-09 10:00:00" -To "2026-06-09 11:00:00"
param(
    [Parameter(Mandatory=$true)][ValidateSet("T0","T1","T2","T3")][string]$Step,
    [Parameter(Mandatory=$true)][string]$Brand,
    [string]$OrderNumber = "",
    [string]$From = "",
    [string]$To = "",
    [switch]$CaptureGolden
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
function CallApi($method, $body) {
    $uri = "$base/api/method/ecentric_workspace.alerts.api_omisell.$method"
    return (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" `
        -Uri $uri -Body ($body | ConvertTo-Json -Depth 4)).message
}

switch ($Step) {
    "T0" {
        $r = CallApi "omisell_probe" @{ brand = $Brand }
        OK ("T0 probe: ok={0} shop_count={1} rate={2} scheme={3}" -f $r.ok, $r.shop_count, $r.rate_limit_header, $r.auth_scheme)
        OK "VERIFY: ok=true; rate header present; BIS credential_status flipped to Active in Desk."
        WARN "If auth path/body differs (T0 fails): adjust site_config ec_alerts_omisell_auth_path / _auth_field / _auth_scheme - no redeploy needed."
    }
    "T1" {
        $r = CallApi "sync_shop_directory" @{ brand = $Brand }
        OK ("T1 directory: total={0} mapped={1} unmapped={2}" -f $r.total, $r.mapped.Count, $r.unmapped.Count)
        if ($r.unmapped.Count -gt 0) {
            WARN "Unmapped shops - create EC Marketplace Shop rows manually (Desk), then re-run T1:"
            $r.unmapped | ForEach-Object { Write-Host ("   shop_id={0}  name={1}  platform={2}" -f $_.shop_id, $_.shop_name, $_.platform) }
        } else { OK "All Omisell shops mapped - ready for T2." }
    }
    "T2" {
        if (-not $OrderNumber) { ERR "T2 requires -OrderNumber"; exit 1 }
        $body = @{ brand = $Brand; omisell_order_number = $OrderNumber }
        if ($CaptureGolden) { $body["capture_golden"] = 1 }
        $r = CallApi "pull_one_order" $body
        OK ("T2 order {0}: status='{1}' real_sale={2} ({3}) lines={4} platform={5}" -f $r.order, $r.status, $r.real_sale, $r.status_reason, $r.lines, $r.platform)
        if ($r.ingest) { OK ("ingest: {0} | queue: {1}" -f ($r.ingest | ConvertTo-Json -Compress -Depth 4), ($r.action_queue | ConvertTo-Json -Compress)) }
        if ($r.golden_payload) {
            $gf = Join-Path $PSScriptRoot ("golden_T2_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
            $r.golden_payload | ConvertTo-Json -Depth 10 | Out-File $gf -Encoding ascii
            OK "Sanitized golden payload saved: $gf"
            WARN "Q-D5 4-point check NOW: (1) discounted_price unit or line total? (2) before/after seller voucher? (3) platform subsidy included? (4) matches KAM expectation? Send file + answers to Claude."
        }
        OK "VERIFY in Desk: EC Marketplace Order Log created; line snapshots; expected alerts; record actual status_id/status_name for Q-D2."
    }
    "T3" {
        if (-not $From -or -not $To) { ERR "T3 requires -From and -To (max 1 hour)"; exit 1 }
        $r = CallApi "pull_orders" @{ brand = $Brand; updated_from = $From; updated_to = $To }
        OK ("T3 window {0} -> {1}" -f $r.window[0], $r.window[1])
        OK ("listed={0} ingested={1} skipped_status={2} failed={3} last_sync_advanced={4}" -f $r.listed, $r.ingested, $r.skipped_status, $r.failed, $r.last_sync_at_advanced)
        if ($r.skipped_status_detail) { Write-Host "skipped statuses (Q-D2 evidence):"; $r.skipped_status_detail.PSObject.Properties | ForEach-Object { Write-Host ("   {0} x{1}" -f $_.Name, $_.Value) } }
        OK "VERIFY: counts vs Omisell UI for the same window; re-run SAME command -> ingested orders report 'unchanged', 0 new alerts (idempotency proof)."
    }
}
