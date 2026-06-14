# onboard_lof_preflight.ps1 - Brand #2 (LOF) onboarding PREFLIGHT (READ-ONLY).
# Resolves the exact brand code, checks Brand Approver KAM scope, and inspects
# EC Brand Integration Settings (Omisell). Writes NOTHING. No Omisell call here
# (that is the probe step in onboard_lof_pull.ps1). ASCII-only source.
#
# Usage: .\onboard_lof_preflight.ps1                 (auto-resolves LOF / LOF-VN)
#        .\onboard_lof_preflight.ps1 -Brand LOF-VN   (force a specific code)
param([string]$Brand = "")
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
$fail = 0

function GetByName($doctype, $name) {
    try { return (Invoke-RestMethod -Headers $h -Uri ("$base/api/resource/" + [uri]::EscapeDataString($doctype) + "/" + [uri]::EscapeDataString($name))).data }
    catch { return $null }
}

# --- STEP 1: resolve the exact brand code from Brand Approver (source of truth) ---
INFO "STEP 1 - resolving brand code from Brand Approver ..."
$candidates = if ($Brand) { @($Brand) } else { @("LOF-VN", "LOF") }
$ba = $null; $code = $null
foreach ($c in $candidates) {
    $rec = GetByName "Brand Approver" $c
    if ($rec) { $ba = $rec; $code = $c; break }
}
if (-not $ba) {
    ERR ("No Brand Approver found for: {0}. Confirm the exact record name in Desk (Brand Approver list)." -f ($candidates -join " / "))
    ERR "ABORT - do not proceed until the brand code is confirmed."
    exit 1
}
OK ("Brand code CONFIRMED = '{0}' (Brand Approver record exists)" -f $code)

# --- STEP 2: Brand Approver / KAM scope ---
INFO "STEP 2 - KAM / manager / leader scope ..."
if ($ba.status -eq "Active") { OK "Brand Approver status = Active" } else { ERR ("status = '{0}' (need Active)" -f $ba.status); $fail++ }
if ($ba.kam_owner)     { OK ("kam_owner      = {0}" -f $ba.kam_owner) }     else { WARN "kam_owner EMPTY - alerts will have no daily owner (resolve_owner falls back)" }
if ($ba.manager_email) { OK ("manager_email  = {0}" -f $ba.manager_email) } else { WARN "manager_email EMPTY" }
if ($ba.leader_email)  { OK ("leader_email   = {0}" -f $ba.leader_email) }  else { WARN "leader_email EMPTY" }
if (-not $ba.kam_owner -and -not $ba.manager_email -and -not $ba.leader_email) {
    ERR "NO scope users on LOF - non-SM users would have zero Alert Center access for this brand."; $fail++
}

# --- STEP 3: EC Brand Integration Settings (Omisell) ---
INFO "STEP 3 - EC Brand Integration Settings (Omisell) ..."
$enc = [uri]::EscapeDataString('[["brand","=","' + $code + '"],["integration_type","=","Omisell"]]')
$bisList = (Invoke-RestMethod -Headers $h -Uri ("$base/api/resource/EC Brand Integration Settings?filters=$enc&fields=[`"name`"]")).data
if (-not $bisList -or $bisList.Count -lt 1) {
    ERR "No EC Brand Integration Settings (Omisell) for $code. Create it in Desk (SM only) before any pull."; $fail++
} else {
    $bis = GetByName "EC Brand Integration Settings" $bisList[0].name
    OK ("BIS record = {0}" -f $bis.name)
    if ([int]$bis.enabled -eq 1) { OK "enabled = 1" } else { ERR ("enabled = {0} (need 1)" -f $bis.enabled); $fail++ }
    if ($bis.credential_status -eq "Active") { OK "credential_status = Active" }
    else { WARN ("credential_status = '{0}' - run omisell_probe (pull script step A) to validate + set Active" -f $bis.credential_status) }
    if ($bis.base_url) { OK ("base_url = {0}" -f $bis.base_url) } else { WARN "base_url empty - client falls back to default api.omisell.com" }
    # Password fields return masked '*' when set, null/empty when not.
    if ($bis.api_key)    { OK "api_key configured" }    else { ERR "api_key NOT configured"; $fail++ }
    if ($bis.api_secret) { OK "api_secret configured" } else { ERR "api_secret NOT configured"; $fail++ }
    if ($bis.last_sync_at) { OK ("last_sync_at = {0}" -f $bis.last_sync_at) }
    else { WARN "last_sync_at EMPTY - first pull will default the window to now-1h (expected for a brand-new brand)" }
    if ([int]$bis.consecutive_failures -gt 0) { WARN ("consecutive_failures = {0} (breaker opens at 3)" -f $bis.consecutive_failures) }
    else { OK "consecutive_failures = 0 (breaker closed)" }
    if ([int]$bis.dry_run_stock_lock -eq 1) { OK "dry_run_stock_lock = 1 (DS1 honored - safe)" }
    else { ERR "dry_run_stock_lock != 1 - DS1 requires dry-run; FIX before pull"; $fail++ }
}

# --- STEP 4: scheduled allowlist (must NOT contain LOF yet) ---
INFO "STEP 4 - current scheduled allowlist (LOF should be ABSENT until manual pull passes) ..."
WARN "site_config 'ec_alerts_scheduled_pull_brands' is not REST-readable; check it on the Frappe Cloud dashboard (Site Config)."
WARN "Expected NOW: [\"FES-VN\"].  Add \"$code\" only AFTER the manual pull verification passes (runbook step 8)."

Write-Host ""
if ($fail -eq 0) { OK ("PREFLIGHT PASSED for {0}. Next: .\onboard_lof_pull.ps1 -Brand {0}" -f $code) }
else { ERR ("PREFLIGHT has {0} blocker(s). Resolve them before pulling." -f $fail); exit 1 }
