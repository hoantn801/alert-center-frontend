# deploy_alert_page.ps1 - Alert Center Phase E: create/update Web Page /alerts
# Idempotent. Backs up existing record before PUT. ASCII-only page content
# (built by frontend/build_alert_center_page.py) -> ConvertTo-Json is safe.
# Run AFTER app code (api_* endpoints) is deployed via Frappe Cloud.

$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$pageName = "alert-center"
$root = Split-Path $PSScriptRoot -Parent
$htmlPath = Join-Path $root "frontend\alert_center.html"
$csvPath = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"

function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function WARN($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
function ERR($m){Write-Host "[ERR] $m" -ForegroundColor Red}

if (-not (Test-Path $htmlPath)) { ERR "Missing $htmlPath"; exit 1 }
$html = [System.IO.File]::ReadAllText($htmlPath)
if ($html -notmatch "ec-alert-center") { ERR "Marker ec-alert-center missing in HTML"; exit 1 }
if ($html -match "[^\x00-\x7F]") { ERR "Non-ASCII found in HTML - rebuild with builder"; exit 1 }
OK ("HTML loaded: {0} chars, ASCII-only, marker present" -f $html.Length)

$cred = Import-Csv $csvPath | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }

# existing?
$exists = $true
try { $cur = (Invoke-RestMethod -Headers $h -Uri "$base/api/resource/Web Page/$pageName").data }
catch { $exists = $false }

if ($exists) {
    $bdir = Join-Path $PSScriptRoot ("backups\alert_page_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
    New-Item -ItemType Directory -Force -Path $bdir | Out-Null
    $cur | ConvertTo-Json -Depth 6 | Out-File (Join-Path $bdir "web_page_alert-center.json") -Encoding ascii
    OK "Backup saved to $bdir"
}

$body = @{
    title             = "Alert Center"
    route             = "alerts"
    published         = 1
    content_type      = "HTML"
    dynamic_template  = 0
    full_width        = 1
    main_section      = $html
    main_section_html = $html
}
if ($exists) {
    $null = Invoke-RestMethod -Method Put -Headers $h -ContentType "application/json" `
        -Uri "$base/api/resource/Web Page/$pageName" -Body ($body | ConvertTo-Json -Depth 4)
    OK "Web Page updated"
} else {
    $body["doctype"] = "Web Page"; $body["name"] = $pageName
    $null = Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" `
        -Uri "$base/api/resource/Web Page" -Body ($body | ConvertTo-Json -Depth 4)
    OK "Web Page created"
}

# verify
$chk = (Invoke-RestMethod -Headers $h -Uri "$base/api/resource/Web Page/$pageName").data
if ($chk.route -eq "alerts" -and $chk.published -eq 1 -and $chk.main_section_html -match "ec-alert-center") {
    OK ("VERIFIED record: route=/alerts published=1 marker present ({0} chars)" -f $chk.main_section_html.Length)
} else { ERR "Record verify failed"; exit 1 }
try {
    $page = Invoke-WebRequest -Uri "$base/alerts" -Headers $h -UseBasicParsing
    if ($page.StatusCode -eq 200 -and $page.Content -match "ec-alert-center") { OK "VERIFIED live: GET /alerts -> 200 + marker" }
    else { WARN "GET /alerts returned 200 but marker not found - check render/cache (try force_clear_cache)" }
} catch { WARN "GET /alerts failed: $($_.Exception.Message) - may need cache clear" }
OK "DONE. Test in browser: $base/alerts (Ctrl+Shift+R)"
