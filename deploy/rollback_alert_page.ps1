# rollback_alert_page.ps1 - Alert Center Phase E: unpublish /alerts (content kept)
$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$root = Split-Path $PSScriptRoot -Parent
$csvPath = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"
function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function ERR($m){Write-Host "[ERR] $m" -ForegroundColor Red}
$cred = Import-Csv $csvPath | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }
$null = Invoke-RestMethod -Method Put -Headers $h -ContentType "application/json" `
    -Uri "$base/api/resource/Web Page/alert-center" -Body '{"published": 0}'
$chk = (Invoke-RestMethod -Headers $h -Uri "$base/api/resource/Web Page/alert-center").data
if ($chk.published -eq 0) { OK "VERIFIED: /alerts unpublished (content preserved for re-publish)" }
else { ERR "Rollback verify failed"; exit 1 }
