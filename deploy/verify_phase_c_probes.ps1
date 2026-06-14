# verify_phase_c_probes.ps1 - Alert Center Phase C post-deploy verification
# Read-mostly; only writes: 1 EC Marketplace Order Log + 1 Warning EC Alert
# (SMOKE-C-001, missing_brand_mapping path - cannot create lock actions).
# Idempotent: safe to re-run (second ingest must return unchanged/deduped).
# Token is read at runtime from the local CSV - never hardcoded, never printed.
# Run:  powershell -ExecutionPolicy Bypass -File .\verify_phase_c_probes.ps1

$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$csvPath = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "frappe_api_keys -newww.csv"

function OK($m)   { Write-Host "[OK]  $m" -ForegroundColor Green }
function WARN($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function ERR($m)  { Write-Host "[ERR] $m" -ForegroundColor Red }

# --- auth ---------------------------------------------------------------
if (-not (Test-Path $csvPath)) { ERR "Key file not found: $csvPath"; exit 1 }
$cred = Import-Csv $csvPath | Select-Object -First 1
if (-not $cred.api_key -or -not $cred.api_secret) { ERR "api_key/api_secret missing in CSV"; exit 1 }
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }
OK "Token loaded from CSV (not displayed)"

$fail = 0

# --- Probe 1: empty action queue ----------------------------------------
try {
    $r1 = Invoke-RestMethod -Method Post -Headers $h -Uri "$base/api/method/ecentric_workspace.alerts.api.process_action_queue"
    $m = $r1.message
    OK ("Probe 1 process_action_queue: processed={0} errors={1}" -f $m.processed, $m.errors)
    if ($m.errors -gt 0) { WARN "Probe 1: errors > 0 - check Error Log on site"; $fail++ }
} catch { ERR "Probe 1 failed: $($_.Exception.Message)"; $fail++ }

# --- Probe 2: safe mock ingestion smoke (run 1 = create, run 2 = dedupe) -
$payload = '{"payload": [{"external_order_id": "SMOKE-C-001", "platform": "Shopee", "omisell_shop_id": "smoke-unmapped-shop", "order_status": "TEST", "items": [{"external_line_id": "L1", "seller_sku": "SMOKE-SKU-1", "quantity": 1, "customer_paid_price": 10000, "product_name": "deploy smoke test"}]}]}'
$ingestUri = "$base/api/method/ecentric_workspace.alerts.api.ingest_mock_orders"
try {
    $a = (Invoke-RestMethod -Method Post -Headers $h -Uri $ingestUri -ContentType "application/json" -Body $payload).message
    $st1 = $a.orders[0].status
    OK ("Probe 2 run 1: status={0} alerts_created={1} alerts_deduped={2} queue_processed={3}" -f `
        $st1, $a.orders[0].summary.alerts_created, $a.orders[0].summary.alerts_deduped, $a.action_queue.processed)
    $b = (Invoke-RestMethod -Method Post -Headers $h -Uri $ingestUri -ContentType "application/json" -Body $payload).message
    $st2 = $b.orders[0].status
    if ($st2 -eq "unchanged" -and $b.orders[0].summary.alerts_created -eq 0) {
        OK ("Probe 2 run 2 (idempotency): status={0} alerts_created=0 alerts_deduped={1}" -f $st2, $b.orders[0].summary.alerts_deduped)
    } else { ERR "Probe 2 run 2: expected unchanged/0 new alerts, got status=$st2"; $fail++ }
    # inspect the smoke alert
    $alertUri = "$base/api/resource/EC Alert?filters=[[%22rule_code%22,%22=%22,%22missing_brand_mapping%22],[%22dedupe_key%22,%22like%22,%22%25smoke-unmapped-shop%25%22]]&fields=[%22name%22,%22severity%22,%22status%22,%22dedupe_key%22]"
    $al = (Invoke-RestMethod -Headers $h -Uri $alertUri).data
    if ($al.Count -eq 1 -and $al[0].severity -eq "Warning") {
        OK ("Probe 2 alert: {0} severity=Warning dedupe_key={1}" -f $al[0].name, $al[0].dedupe_key)
    } else { ERR ("Probe 2 alert check: expected exactly 1 Warning alert, got {0}" -f $al.Count); $fail++ }
} catch { ERR "Probe 2 failed: $($_.Exception.Message)"; $fail++ }

# --- Probe 3: no real API / stock update active --------------------------
try {
    $acts = (Invoke-RestMethod -Headers $h -Uri "$base/api/resource/EC Alert Action?fields=[%22name%22,%22status%22]&limit_page_length=0").data
    $bad = @($acts | Where-Object { $_.status -notin @("Skipped", "Dry Run", "Pending", "Cancelled") })
    if ($acts.Count -eq 0) { OK "Probe 3b: zero EC Alert Action records (nothing executed, as expected)" }
    elseif ($bad.Count -eq 0) { OK ("Probe 3b: {0} actions, all Skipped/Dry Run/Pending/Cancelled - none executed" -f $acts.Count) }
    else { ERR ("Probe 3b: found {0} actions in unexpected states" -f $bad.Count); $fail++ }
    $bis = (Invoke-RestMethod -Headers $h -Uri "$base/api/resource/EC Brand Integration Settings?fields=[%22name%22,%22brand%22,%22enabled%22,%22credential_status%22,%22dry_run_stock_lock%22]").data
    if ($bis.Count -eq 0) { OK "Probe 3c: zero EC Brand Integration Settings - no credential exists, real call impossible" }
    else {
        $live = @($bis | Where-Object { $_.dry_run_stock_lock -eq 0 })
        if ($live.Count -eq 0) { OK ("Probe 3c: {0} credential record(s), ALL dry_run_stock_lock=1" -f $bis.Count) }
        else { ERR ("Probe 3c: {0} credential record(s) with dry_run_stock_lock=0!" -f $live.Count); $fail++ }
    }
    OK "Probe 3a (code layer) was verified pre-merge: zero HTTP imports in alerts/ at commit 08cfdaa"
} catch { ERR "Probe 3 failed: $($_.Exception.Message)"; $fail++ }

# --- verdict --------------------------------------------------------------
Write-Host ""
if ($fail -eq 0) { OK "PHASE C PRODUCTION VERIFICATION: ALL PROBES PASSED" }
else { ERR ("PHASE C VERIFICATION: {0} check(s) failed - send output to Claude" -f $fail) }
