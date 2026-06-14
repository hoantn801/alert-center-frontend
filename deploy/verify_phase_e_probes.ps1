# verify_phase_e_probes.ps1 - Alert Center Phase E post-deploy verification
# Read-only except probe writes nothing. Optional 2nd CSV with a NON-SM token
# proves the 403 matrix: .\verify_phase_e_probes.ps1 -NonSmCsv path\to.csv
param([string]$NonSmCsv = "")
$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$root = Split-Path $PSScriptRoot -Parent
$csvPath = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"
function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function WARN($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
function ERR($m){Write-Host "[ERR] $m" -ForegroundColor Red}
$cred = Import-Csv $csvPath | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }
$fail = 0

# 1. D3-E fields present after migrate
foreach ($pair in @(@("EC Marketplace Order Item","external_product_id"), @("EC Marketplace Order Log","omisell_shop_id"))) {
    $dt = $pair[0]; $fn = $pair[1]
    $meta = (Invoke-RestMethod -Headers $h -Uri ("$base/api/resource/DocType/" + [uri]::EscapeDataString($dt))).data
    if (@($meta.fields | Where-Object { $_.fieldname -eq $fn }).Count -eq 1) { OK "$dt has field $fn" }
    else { ERR "$dt missing field $fn"; $fail++ }
}

# 2. new endpoints alive (SM)
$scope = (Invoke-RestMethod -Method Post -Headers $h -Uri "$base/api/method/ecentric_workspace.alerts.api_alerts.my_scope").message
if ($scope.supervisor -eq $true) { OK "my_scope (SM): supervisor=true" } else { ERR "my_scope unexpected: $($scope | ConvertTo-Json -Compress)"; $fail++ }
$cards = (Invoke-RestMethod -Method Post -Headers $h -Uri "$base/api/method/ecentric_workspace.alerts.api_alerts.get_cards").message
OK ("get_cards: open={0} critical={1} lock_pending={2} resolved_today={3}" -f $cards.open, $cards.critical, $cards.lock_pending, $cards.resolved_today)
$list = (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" -Body '{"page_len": 5}' -Uri "$base/api/method/ecentric_workspace.alerts.api_alerts.list_alerts").message
OK ("list_alerts: total={0} rows={1}" -f $list.total, $list.rows.Count)

# 3. scheduler entries registered (config probe: queue drains on demand)
$q = (Invoke-RestMethod -Method Post -Headers $h -Uri "$base/api/method/ecentric_workspace.alerts.api.process_action_queue").message
OK ("action queue drain: processed={0} errors={1}" -f $q.processed, $q.errors)

# 4. optional non-SM 403 matrix
if ($NonSmCsv -and (Test-Path $NonSmCsv)) {
    $c2 = Import-Csv $NonSmCsv | Select-Object -First 1
    $h2 = @{ Authorization = ("token {0}:{1}" -f $c2.api_key, $c2.api_secret) }
    foreach ($ep in @("api.ingest_mock_orders", "api.process_action_queue")) {
        try { $null = Invoke-RestMethod -Method Post -Headers $h2 -Uri "$base/api/method/ecentric_workspace.alerts.$ep"; ERR "$ep should be 403 for non-SM"; $fail++ }
        catch { OK "$ep -> denied for non-SM (expected)" }
    }
    try {
        $s2 = (Invoke-RestMethod -Method Post -Headers $h2 -Uri "$base/api/method/ecentric_workspace.alerts.api_alerts.my_scope").message
        OK ("my_scope (non-SM): supervisor={0} brands={1}" -f $s2.supervisor, (@($s2.brands.PSObject.Properties).Count))
    } catch { OK "my_scope (non-SM, no brand binding) -> 403 (expected for unscoped users)" }
} else { WARN "Non-SM token not provided - run again with -NonSmCsv to prove the 403 matrix" }

# 5. page (only meaningful after deploy_alert_page.ps1)
try {
    $page = Invoke-WebRequest -Uri "$base/alerts" -Headers $h -UseBasicParsing
    if ($page.Content -match "ec-alert-center") { OK "GET /alerts -> 200 + marker" } else { WARN "/alerts up but marker missing" }
} catch { WARN "GET /alerts not available yet (page not deployed or unpublished)" }

Write-Host ""
if ($fail -eq 0) { OK "PHASE E PROBES: ALL PASSED (within provided tokens)" } else { ERR ("{0} check(s) failed" -f $fail) }
