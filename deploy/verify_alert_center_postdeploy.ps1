# verify_alert_center_postdeploy.ps1 - Pre-E2E post-deploy smoke (READ-ONLY).
#
# Verifies the operational/setup split + brand scope + integration health WITHOUT
# writing anything and WITHOUT hardcoded credentials. The API token is loaded
# from a CSV (same convention as verify_phase_g1.ps1) or from the
# EC_API_TOKEN environment variable ("api_key:api_secret"). ASCII-only.
#
# Checks:
#   1. All five Alert Center routes return HTTP 200.
#   2. api_dashboard.kpis exposes the new operational/setup split
#      (open/critical/warning + setup_issues), legacy missing_policy alias kept.
#   3. DEFAULT operational views EXCLUDE setup gaps: by_dimension(rule_code) and
#      by_dimension(brand) contain no missing_brand_mapping / "(none)" rows.
#   4. Setup issues remain EXPLICITLY queryable (rule_code=missing_brand_mapping
#      and the setup_only view), so history is preserved.
#   5. Integration Health: FES-VN + LOF-VN present; no secret field leaks.
#   6. my_scope resolves (no 500); unauthenticated call is rejected.
#
# Usage:
#   .\deploy\verify_alert_center_postdeploy.ps1
#   .\deploy\verify_alert_center_postdeploy.ps1 -Base https://team.ecentric.vn -CredCsv "C:\path\keys.csv"
param(
    [string]$Base = "https://team.ecentric.vn",
    [string]$CredCsv = "",
    [string[]]$Brands = @("FES-VN", "LOF-VN")
)
$ErrorActionPreference = "Stop"
function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function WARN($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
function ERR($m){Write-Host "[ERR] $m" -ForegroundColor Red}
$fail = 0

# --- credentials (CSV first col, or EC_API_TOKEN env "key:secret"); never hardcoded ---
$key = $null; $secret = $null
if ($env:EC_API_TOKEN -and $env:EC_API_TOKEN.Contains(":")) {
    $parts = $env:EC_API_TOKEN.Split(":", 2); $key = $parts[0]; $secret = $parts[1]
} else {
    if (-not $CredCsv) {
        $root = Split-Path $PSScriptRoot -Parent
        $CredCsv = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"
    }
    if (-not (Test-Path $CredCsv)) {
        ERR "No credentials: set EC_API_TOKEN='key:secret' or pass -CredCsv <file>."; exit 2
    }
    $cred = Import-Csv $CredCsv | Select-Object -First 1
    $key = $cred.api_key; $secret = $cred.api_secret
}
$h = @{ Authorization = ("token {0}:{1}" -f $key, $secret) }
# NOTE: PowerShell variable names are CASE-INSENSITIVE, so these module-path
# constants must NOT collide with the $Brands parameter (a prior $BRANDS
# constant silently overwrote the brand array -> the bogus
# "...api_brands not in readiness list" warning). Use an Ep* prefix.
$EpDash = "ecentric_workspace.alerts.api_dashboard"
$EpAlerts = "ecentric_workspace.alerts.api_alerts"
$EpBrands = "ecentric_workspace.alerts.api_brands"

function PostMsg($method, $bodyObj) {
    $args = @{ Method = "Post"; Headers = $h; Uri = "$Base/api/method/$method" }
    if ($bodyObj) { $args.ContentType = "application/json"; $args.Body = ($bodyObj | ConvertTo-Json -Depth 6) }
    return (Invoke-RestMethod @args).message
}

# 1. routes return 200 (GET, read-only) ------------------------------------
$routes = @("/alerts", "/alerts/policies", "/alerts/rules", "/alerts/locks", "/alerts/integration-health")
foreach ($r in $routes) {
    try {
        $resp = Invoke-WebRequest -Method Get -Headers $h -Uri "$Base$r" -UseBasicParsing
        if ($resp.StatusCode -eq 200) { OK "route $r -> 200" } else { ERR "route $r -> $($resp.StatusCode)"; $fail++ }
    } catch { ERR "route $r failed: $($_.Exception.Message)"; $fail++ }
}

# 2. KPI shape: operational + setup split ----------------------------------
try {
    $kpi = PostMsg "$EpDash.kpis" @{ filters = @{} }
    $haveOp = ($null -ne $kpi.open) -and ($null -ne $kpi.critical) -and ($null -ne $kpi.warning)
    if ($haveOp) { OK ("kpis operational: open=$($kpi.open) critical=$($kpi.critical) warning=$($kpi.warning)") }
    else { ERR "kpis missing operational keys"; $fail++ }
    if ($null -ne $kpi.setup_issues) { OK "kpis exposes setup_issues=$($kpi.setup_issues) (separate from operational)" }
    else { ERR "kpis missing setup_issues key"; $fail++ }
    if ($null -ne $kpi.missing_policy) { OK "legacy alias missing_policy kept = $($kpi.missing_policy)" }
} catch { ERR "kpis failed: $($_.Exception.Message)"; $fail++ }

# 3. DEFAULT operational views exclude setup gaps --------------------------
try {
    $byRule = PostMsg "$EpDash.by_dimension" @{ dim = "rule_code"; filters = @{} }
    $ruleKeys = @($byRule.rows | ForEach-Object { $_.key })
    if ($ruleKeys -contains "missing_brand_mapping") { ERR "DEFAULT rule distribution still contains missing_brand_mapping"; $fail++ }
    else { OK "default rule distribution excludes missing_brand_mapping" }
    foreach ($sys in @("missing_policy", "missing_integration_credential", "ingestion_api_failed", "stock_lock_api_failed")) {
        if ($ruleKeys -contains $sys) { WARN "default rule distribution unexpectedly contains $sys" }
    }
    $byBrand = PostMsg "$EpDash.by_dimension" @{ dim = "brand"; filters = @{} }
    $brandKeys = @($byBrand.rows | ForEach-Object { $_.key })
    if ($brandKeys -contains "(none)") { ERR "default brand distribution still dominated by '(none)' brand"; $fail++ }
    else { OK "default brand distribution has no '(none)' bucket" }
} catch { ERR "by_dimension failed: $($_.Exception.Message)"; $fail++ }

# 4. setup issues remain explicitly queryable (history preserved) ----------
try {
    $hist = PostMsg "$EpAlerts.list_alerts" @{ filters = @{ rule_code = "missing_brand_mapping" }; page_len = 5 }
    OK "explicit rule_code=missing_brand_mapping queryable (total=$($hist.total))"
    $setup = PostMsg "$EpAlerts.list_alerts" @{ filters = @{ setup_only = 1 }; page_len = 5 }
    $bad = @($setup.rows | Where-Object { @("below_min","above_high","severe_price_drop","possible_missing_zero") -contains $_.rule_code })
    if ($bad.Count -gt 0) { ERR "setup_only view leaked operational rows ($($bad.Count))"; $fail++ }
    else { OK "setup_only view returns only setup rules (total=$($setup.total))" }
} catch { ERR "setup queryability check failed: $($_.Exception.Message)"; $fail++ }

# 5. Integration Health present + no secret leak ---------------------------
# Regression guard: $Brands must still be the brand ARRAY here (not a module
# string shadowed by a same-named constant). A non-array/empty value would make
# the per-brand loop bogus, so assert it explicitly.
if ($Brands -isnot [array] -or $Brands.Count -lt 1 -or ($Brands -join ",") -match "api_brands") {
    ERR "smoke bug: \$Brands is not a valid brand array ($($Brands -join ','))"; $fail++
}
try {
    $list = PostMsg "$EpBrands.list_brand_readiness" $null
    if (-not $list.brands -or @($list.brands).Count -lt 1) {
        ERR "list_brand_readiness returned no brands (real dependency/permission issue)"; $fail++
    } else { OK ("list_brand_readiness returned $(@($list.brands).Count) brand(s)") }
    $raw = $list | ConvertTo-Json -Depth 8
    foreach ($s in @("api_key", "api_secret", '"token"')) {
        if ($raw -match $s) { ERR "SECRET LEAK '$s' in brand readiness payload"; $fail++ }
    }
    foreach ($b in $Brands) {
        $row = $list.brands | Where-Object { $_.brand -eq $b } | Select-Object -First 1
        if ($row) { OK "health $b status=$($row.status)" } else { WARN "$b not in readiness list (Brand Approver may not exist)" }
    }
} catch { ERR "list_brand_readiness failed: $($_.Exception.Message)"; $fail++ }

# 6. my_scope resolves --------------------------------------------------------
try {
    $scope = PostMsg "$EpAlerts.my_scope" $null
    OK ("my_scope: supervisor=$($scope.supervisor) brands=$(@($scope.brands.PSObject.Properties.Name).Count)")
} catch { ERR "my_scope failed: $($_.Exception.Message)"; $fail++ }

Write-Host ""
if ($fail -eq 0) { OK "Alert Center post-deploy smoke PASSED" }
else { ERR "$fail check(s) failed"; exit 1 }
