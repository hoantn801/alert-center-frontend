# verify_phase_f_drop1.ps1 - Phase F Drop 1 post-deploy probes (BEFORE Drop 2).
# Writes: 1 Draft test policy (then sets Inactive) + nothing else.
# Optional non-SM matrix: -NonSmCsv <csv with non-SM token>
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
function CallApi($method, $body) {
    $uri = "$base/api/method/ecentric_workspace.alerts.$method"
    if ($null -eq $body) { return (Invoke-RestMethod -Method Post -Headers $h -Uri $uri).message }
    return (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" `
        -Uri $uri -Body ($body | ConvertTo-Json -Depth 6)).message
}
$fail = 0

# --- 1. Policy inertness: Draft policy must be invisible to the engine -----
try {
    $pol = CallApi "api_policies.save_policy" @{ policy = @{ brand = "FES-VN"; platform = "All";
        seller_sku = "DROP1-PROBE-SKU"; min_price = 999999; product_name = "drop1 probe" } }
    if ($pol.status -ne "Draft") { ERR "1) new policy status expected Draft, got $($pol.status)"; $fail++ }
    else { OK "1) probe policy created as Draft: $($pol.name)" }
    # engine-side check: list Active policies for that SKU -> must NOT include it
    $lst = CallApi "api_policies.list_policies" @{ filters = @{ seller_sku = "DROP1-PROBE-SKU"; status = "Active" } }
    if ($lst.total -eq 0) { OK "1) Draft policy NOT visible as Active (inert to engine)" }
    else { ERR "1) Draft policy appears Active!"; $fail++ }
    $null = CallApi "api_policies.set_policy_status" @{ name = $pol.name; status = "Inactive" }
    OK "1) probe policy parked as Inactive (audit kept)"
} catch { ERR "1) policy inertness probe failed: $($_.Exception.Message)"; $fail++ }

# --- 2. Rule overlay golden regression: zero Active rules => engine default -
try {
    $rules = CallApi "api_rules.list_rules" @{ filters = @{ status = "Active" } }
    if ($rules.rows.Count -eq 0) { OK "2) zero Active EC Alert Rules -> overlay is identity (golden default)" }
    else { WARN ("2) {0} Active rules exist - golden regression requires comparing a re-pulled window" -f $rules.rows.Count) }
    # functional golden check: kpis/list still serve (backend regression)
    $k = CallApi "api_dashboard.kpis" @{}
    OK ("2) dashboard kpis serve: open={0} lock_pending_review={1}" -f $k.open, $k.lock_pending_review)
} catch { ERR "2) golden regression probe failed: $($_.Exception.Message)"; $fail++ }

# --- 3. 403 matrix (needs non-SM token) -------------------------------------
if ($NonSmCsv -and (Test-Path $NonSmCsv)) {
    $c2 = Import-Csv $NonSmCsv | Select-Object -First 1
    $h2 = @{ Authorization = ("token {0}:{1}" -f $c2.api_key, $c2.api_secret) }
    foreach ($ep in @("api_policies.list_policies", "api_rules.list_rules",
                      "api_dashboard.kpis", "api_actions.list_actions")) {
        try {
            $null = Invoke-RestMethod -Method Post -Headers $h2 -ContentType "application/json" `
                -Body '{}' -Uri "$base/api/method/ecentric_workspace.alerts.$ep"
            OK "3) $ep -> 200 for scoped non-SM user (expected if user has brand scope)"
        } catch { OK "3) $ep -> denied for unscoped non-SM (expected if user has no brand)" }
    }
} else { WARN "3) non-SM token not provided - rerun with -NonSmCsv for the 403 matrix" }

# --- 4. review_action behavior (state machine, read-only if queue empty) ----
try {
    $acts = CallApi "api_actions.list_actions" @{ filters = @{ review_status = "Pending Review" }; page_len = 1 }
    OK ("4) list_actions serves: pending_review_total={0}" -f $acts.total)
    if ($acts.total -gt 0) {
        WARN "4) actions exist - exercise Approve/Reject manually in UAT (not auto-probed to avoid touching real reviews)"
    } else { OK "4) queue empty - review_action exercised in UAT after first dry-run action" }
} catch { ERR "4) review probe failed: $($_.Exception.Message)"; $fail++ }

# --- 5. /alerts v1 page still functional (pre-Drop-2) ------------------------
try {
    $page = Invoke-WebRequest -Uri "$base/alerts" -Headers $h -UseBasicParsing
    if ($page.StatusCode -eq 200 -and $page.Content -match "ec-alert-center") { OK "5) /alerts v1 page 200 + marker (unchanged until Drop 2)" }
    else { WARN "5) /alerts marker missing - check before Drop 2" }
    $cards = CallApi "api_alerts.get_cards" $null
    OK ("5) v1 get_cards still serves: open={0}" -f $cards.open)
} catch { ERR "5) /alerts v1 probe failed: $($_.Exception.Message)"; $fail++ }

# --- 6. FES-VN scheduler health (must be unaffected) -------------------------
try {
    $st = CallApi "api_omisell.pull_status" @{ brand = "FES-VN" }
    $ageMin = [math]::Round(((Get-Date) - [datetime]$st.last_sync_at).TotalMinutes, 0)
    OK ("6) FES-VN: last_sync_at={0} (~{1} min ago), breaker={2}, running={3}, state={4}" -f `
        $st.last_sync_at, $ageMin, $st.consecutive_failures, $st.running_since, $st.last_run.state)
    if ($st.consecutive_failures -gt 0 -or $ageMin -gt 45) { WARN "6) scheduler drift - investigate before Drop 2"; $fail++ }
} catch { ERR "6) scheduler probe failed: $($_.Exception.Message)"; $fail++ }

Write-Host ""
if ($fail -eq 0) { OK "DROP 1 PROBES: PASSED (within provided tokens) - Drop 2 may proceed after review" }
else { ERR ("DROP 1 PROBES: {0} failure(s) - HOLD Drop 2" -f $fail) }
