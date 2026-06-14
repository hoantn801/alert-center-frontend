# rollback_alert_pages.ps1 - unpublish Alert Center pages (content preserved).
# Usage: .\rollback_alert_pages.ps1            (all)
#        .\rollback_alert_pages.ps1 -Only alert-policies
param([string]$Only = "")
$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$root = Split-Path $PSScriptRoot -Parent
$csvPath = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"
function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function WARN($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
$cred = Import-Csv $csvPath | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }
# Resolve by route (same autoname caveat as deploy) then unpublish.
$routes = @(
    @{ key = "alert-center";   route = "alerts" },
    @{ key = "alert-policies"; route = "alerts/policies" },
    @{ key = "alert-rules";    route = "alerts/rules" },
    @{ key = "alert-locks";    route = "alerts/locks" },
    @{ key = "alert-health";   route = "alerts/integration-health" }
)
foreach ($r in $routes) {
    if ($Only -and $r.key -ne $Only) { continue }
    $realName = $null
    try {
        $enc = [uri]::EscapeDataString('[["route","=","' + $r.route + '"]]')
        $found = (Invoke-RestMethod -Headers $h -Uri "$base/api/resource/Web Page?filters=$enc&fields=[`"name`"]").data
        if ($found -and $found.Count -ge 1) { $realName = $found[0].name }
    } catch { $realName = $null }
    if (-not $realName) { WARN ("no Web Page for route /{0} - skip" -f $r.route); continue }
    $null = Invoke-RestMethod -Method Put -Headers $h -ContentType "application/json" `
        -Uri "$base/api/resource/Web Page/$([uri]::EscapeDataString($realName))" -Body '{"published": 0}'
    OK "$realName (/$($r.route)) unpublished (content preserved)"
}
