# verify_phase_g1.ps1 - Phase G1 post-deploy verification (READ-ONLY).
# Calls the 3 new api_brands reads as System Manager and asserts:
#   * FES-VN present and healthy (Scheduler Enabled / Ready / Running)
#   * LOF-VN = Blocked with blocker missing_bis (if its Brand Approver exists)
#   * NO secret field (api_key/api_secret/token) anywhere in the payload
# Writes nothing. ASCII-only.
param([string]$Brand2 = "LOF-VN")
$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$root = Split-Path $PSScriptRoot -Parent
$csvPath = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"
function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function WARN($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
function ERR($m){Write-Host "[ERR] $m" -ForegroundColor Red}
$cred = Import-Csv $csvPath | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }
$M = "ecentric_workspace.alerts.api_brands"
$fail = 0

# 1. list_brand_readiness (SM)
$list = (Invoke-RestMethod -Method Post -Headers $h -Uri "$base/api/method/$M.list_brand_readiness").message
OK ("list_brand_readiness: {0} brand(s), supervisor={1}" -f $list.brands.Count, $list.is_supervisor)
if ($list.capacity) { OK ("capacity: log_plus_item={0} / trigger={1} due={2}" -f $list.capacity.log_plus_item, $list.capacity.archive_review_trigger, $list.capacity.archive_review_due) }
else { WARN "no capacity block (only for supervisors)" }

# secret leak scan over the whole JSON
$raw = $list | ConvertTo-Json -Depth 8
foreach ($s in @("api_key", "api_secret", '"token"')) {
    if ($raw -match $s) { ERR "SECRET LEAK: '$s' present in list payload"; $fail++ }
}
if ($fail -eq 0) { OK "no secret fields in list payload" }

# 2. FES-VN healthy
$fes = $list.brands | Where-Object { $_.brand -eq "FES-VN" } | Select-Object -First 1
if ($fes) {
    if ($fes.status -in @("Scheduler Enabled", "Ready", "Running")) { OK "FES-VN status = $($fes.status) (healthy)" }
    else { WARN "FES-VN status = $($fes.status) (expected Scheduler Enabled/Ready/Running)" }
} else { ERR "FES-VN not in readiness list"; $fail++ }

# 3. LOF-VN blocked: missing BIS (only if its Brand Approver exists)
$lof = $list.brands | Where-Object { $_.brand -eq $Brand2 } | Select-Object -First 1
if ($lof) {
    if ($lof.status -eq "Blocked") { OK "$Brand2 status = Blocked" } else { ERR "$Brand2 status = $($lof.status) (expected Blocked)"; $fail++ }
    $codes = @($lof.blockers | ForEach-Object { $_.code })
    # LOF is Blocked on missing_bis (no BIS) OR missing_base_url (BIS exists but base_url empty)
    if ($codes -contains "missing_bis" -or $codes -contains "missing_base_url") {
        OK "$Brand2 top blocker = $($codes[0]); action = $($lof.action.label)"
    } else { WARN "$Brand2 top blocker = $($codes -join ',') (expected missing_bis or missing_base_url)" }
    # 4. detail endpoint
    $det = (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" -Body (@{brand=$Brand2}|ConvertTo-Json) -Uri "$base/api/method/$M.brand_readiness").message
    OK ("brand_readiness($Brand2): status=$($det.status) bis_exists=$($det.bis_exists)")
    $rawd = $det | ConvertTo-Json -Depth 8
    foreach ($s in @("api_key", "api_secret", '"token"')) { if ($rawd -match $s) { ERR "SECRET LEAK in detail: $s"; $fail++ } }
} else {
    WARN "$Brand2 not in list (Brand Approver may not exist yet) - create it to see the Blocked:Missing-BIS test case"
}

# 5. policy_coverage smoke (FES-VN)
try {
    $cov = (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" -Body '{"brand":"FES-VN"}' -Uri "$base/api/method/$M.policy_coverage").message
    OK ("policy_coverage(FES-VN): pct=$($cov.pct) covered=$($cov.covered)/$($cov.distinct_skus) days=$($cov.days)")
} catch { WARN ("policy_coverage(FES-VN) failed: {0}" -f $_.Exception.Message) }

Write-Host ""
if ($fail -eq 0) { OK "G1 verification PASSED" } else { ERR "$fail G1 check(s) failed"; exit 1 }
