# ignore_smoke_alert.ps1 - D5-E: mark Phase C smoke alert EC-AL-000568 as Ignored
# (audit record kept, removed from active queue). Idempotent - skips if already
# Ignored. One production write, approved by user decision D5-E (2026-06-07).
# Token read at runtime from local CSV - never hardcoded, never printed.
# Run:  powershell -ExecutionPolicy Bypass -File .\ignore_smoke_alert.ps1

$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$alertName = "EC-AL-000568"
$note = "Deploy smoke test for Phase C verification. Safe mock record, no real stock/API action."
$csvPath = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "frappe_api_keys -newww.csv"

function OK($m)   { Write-Host "[OK]  $m" -ForegroundColor Green }
function WARN($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function ERR($m)  { Write-Host "[ERR] $m" -ForegroundColor Red }

if (-not (Test-Path $csvPath)) { ERR "Key file not found: $csvPath"; exit 1 }
$cred = Import-Csv $csvPath | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }
OK "Token loaded from CSV (not displayed)"

# current state
$uri = "$base/api/resource/EC Alert/$alertName"
try { $cur = (Invoke-RestMethod -Headers $h -Uri $uri).data }
catch { ERR "Cannot read ${alertName}: $($_.Exception.Message)"; exit 1 }
OK ("Current: {0} rule={1} status={2}" -f $cur.name, $cur.rule_code, $cur.status)

if ($cur.rule_code -ne "missing_brand_mapping") { ERR "Safety stop: unexpected rule_code on $alertName"; exit 1 }
if ($cur.status -eq "Ignored") { OK "Already Ignored - nothing to do (idempotent exit)"; exit 0 }

# update (ASCII body -> Invoke-RestMethod is safe here)
$body = (@{ status = "Ignored"; resolution_note = $note } | ConvertTo-Json)
try {
    $res = (Invoke-RestMethod -Method Put -Headers $h -Uri $uri -ContentType "application/json" -Body $body).data
} catch { ERR "Update failed: $($_.Exception.Message)"; exit 1 }

# verify
if ($res.status -eq "Ignored" -and $res.resolution_note -eq $note -and $res.resolved_by) {
    OK ("VERIFIED: {0} status=Ignored, resolved_by={1}, resolved_at={2}" -f $res.name, $res.resolved_by, $res.resolved_at)
    OK "Note set. Audit trail preserved (no deletion)."
} else {
    ERR "Verify mismatch - re-check the record in Desk"; exit 1
}
