# probe_g22_products.ps1 - G2.2 PROBE-ONLY: Omisell product/catalogue endpoints.
# Runs api_probe_products.probe_product_endpoints for FES-VN + LOF-VN, prints
# per-path: ok/error, pagination keys, item field shape (key/type/sample),
# rate-limit header. Saves full JSON per brand for the mapping report.
# NO writes: shape-only probe via the GET-only client chokepoint.
# Usage: .\probe_g22_products.ps1
#        .\probe_g22_products.ps1 -Brands FES-VN -ExtraPaths "/api/v2/public/xyz"
param(
    [string[]]$Brands = @("FES-VN", "LOF-VN"),
    [string[]]$ExtraPaths = @()
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
$M = "ecentric_workspace.alerts.api_probe_products.probe_product_endpoints"

foreach ($b in $Brands) {
    Write-Host ""
    Write-Host ("=== G2.2 product probe: {0} @ {1} ===" -f $b, (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    $body = @{ brand = $b }
    if ($ExtraPaths.Count -gt 0) { $body.extra_paths = ($ExtraPaths | ConvertTo-Json -Compress) }
    try {
        $r = (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" `
              -Body ($body | ConvertTo-Json -Compress) -TimeoutSec 180 `
              -Uri "$base/api/method/$M").message
    } catch {
        ERR ("{0}: probe FAILED - {1}" -f $b, $_.Exception.Message)
        ERR "Is api_probe_products.py deployed? (additive, code-only, no migrate)"
        continue
    }
    foreach ($p in $r.results) {
        if ($p.ok) {
            OK ("{0}  rate={1}" -f $p.path, $p.rate_limit_header)
            if ($p.pagination) { Write-Host ("      pagination: " + ($p.pagination | ConvertTo-Json -Compress)) }
            if ($p.results_len -ne $null) { Write-Host ("      results_len: " + $p.results_len) }
            if ($p.item_shape) {
                Write-Host "      item fields:"
                foreach ($prop in $p.item_shape.PSObject.Properties) {
                    $v = $prop.Value
                    $line = "        {0,-28} {1}" -f $prop.Name, $v.type
                    if ($v.sample) { $line += ("  e.g. " + $v.sample) }
                    Write-Host $line
                }
            }
        } else {
            WARN ("{0}  -> {1}" -f $p.path, $p.error)
        }
    }
    if (@($r.live_paths).Count -eq 0) {
        WARN ("{0}: NO live candidate path - get exact paths from developers.omisell.com (api-6492412 / api-5741887 / api-10762720) and re-run with -ExtraPaths" -f $b)
    } else {
        OK ("{0}: live paths: {1}" -f $b, ($r.live_paths -join ", "))
    }
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $outFile = Join-Path $PSScriptRoot ("probe_g22_{0}_{1}.json" -f $b, $stamp)
    $r | ConvertTo-Json -Depth 14 | Set-Content -Path $outFile -Encoding UTF8
    OK ("full JSON saved: " + $outFile)
}
