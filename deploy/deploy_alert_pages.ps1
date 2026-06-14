# deploy_alert_pages.ps1 - Phase F: create/update ALL Alert Center Web Pages.
# Idempotent; backs up existing records; ASCII-only page sources required.
# Usage: .\deploy_alert_pages.ps1            (all pages)
#        .\deploy_alert_pages.ps1 -Only alert-policies
param([string]$Only = "")
$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$root = Split-Path $PSScriptRoot -Parent
$csvPath = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"
function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function WARN($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
function ERR($m){Write-Host "[ERR] $m" -ForegroundColor Red}
$cred = Import-Csv $csvPath | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }

$pages = @(
    @{ name = "alert-center";   route = "alerts";          title = "Alert Center";          file = "alert_center.html";   marker = "ec-alert-center" },
    @{ name = "alert-policies"; route = "alerts/policies"; title = "Alert Center Policies"; file = "alert_policies.html"; marker = "ec-alert-policies" },
    @{ name = "alert-rules";    route = "alerts/rules";    title = "Alert Center Rules";    file = "alert_rules.html";    marker = "ec-alert-rules" },
    @{ name = "alert-locks";    route = "alerts/locks";    title = "Alert Center Locks";    file = "alert_locks.html";    marker = "ec-alert-locks" },
    @{ name = "alert-health";   route = "alerts/integration-health"; title = "Alert Center Integration Health"; file = "alert_health.html"; marker = "ec-alert-health" }
)

foreach ($p in $pages) {
    if ($Only -and $p.name -ne $Only) { continue }
    $htmlPath = Join-Path $root ("frontend\" + $p.file)
    if (-not (Test-Path $htmlPath)) { ERR "Missing $htmlPath"; exit 1 }
    $html = [System.IO.File]::ReadAllText($htmlPath)
    if ($html -notmatch $p.marker) { ERR "Marker $($p.marker) missing"; exit 1 }
    if ($html -match "[^\x00-\x7F]") { ERR "Non-ASCII in $($p.file) - rebuild"; exit 1 }
    OK ("{0}: {1} chars, ASCII, marker ok" -f $p.file, $html.Length)

    # Resolve the existing record by ROUTE (stable identity). Frappe autonames
    # Web Page from the title (e.g. "Alert Center Policies" -> alert-center-
    # policies), so the configured name may NOT match the real record name -
    # that was the DuplicateEntryError bug (GET by name 404 -> POST -> collide).
    $realName = $null
    try {
        $enc = [uri]::EscapeDataString('[["route","=","' + $p.route + '"]]')
        $found = (Invoke-RestMethod -Headers $h -Uri "$base/api/resource/Web Page?filters=$enc&fields=[`"name`"]").data
        if ($found -and $found.Count -ge 1) { $realName = $found[0].name }
    } catch { $realName = $null }
    # fallback: try the configured name directly
    if (-not $realName) {
        try { $null = (Invoke-RestMethod -Headers $h -Uri "$base/api/resource/Web Page/$($p.name)").data; $realName = $p.name }
        catch { $realName = $null }
    }

    $body = @{ title = $p.title; route = $p.route; published = 1; content_type = "HTML";
               dynamic_template = 0; full_width = 1; main_section = $html; main_section_html = $html }

    if ($realName) {
        $cur = (Invoke-RestMethod -Headers $h -Uri "$base/api/resource/Web Page/$([uri]::EscapeDataString($realName))").data
        $bdir = Join-Path $PSScriptRoot ("backups\" + ($realName -replace '[^\w\-]', '_') + "_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
        New-Item -ItemType Directory -Force -Path $bdir | Out-Null
        $cur | ConvertTo-Json -Depth 6 | Out-File (Join-Path $bdir "web_page.json") -Encoding ascii
        OK "Backup -> $bdir (record: $realName)"
        $null = Invoke-RestMethod -Method Put -Headers $h -ContentType "application/json" `
            -Uri "$base/api/resource/Web Page/$([uri]::EscapeDataString($realName))" -Body ($body | ConvertTo-Json -Depth 4)
        OK ("{0} updated (route /{1})" -f $realName, $p.route)
    } else {
        # genuinely new: let Frappe autoname from title; do NOT force a name
        $body["doctype"] = "Web Page"
        $created = (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" `
            -Uri "$base/api/resource/Web Page" -Body ($body | ConvertTo-Json -Depth 4)).data
        OK ("created (route /{0}, record {1})" -f $p.route, $created.name)
    }
    try {
        $live = Invoke-WebRequest -Uri ("$base/" + $p.route) -Headers $h -UseBasicParsing
        if ($live.StatusCode -eq 200 -and $live.Content -match $p.marker) { OK ("VERIFIED live: /{0}" -f $p.route) }
        else { WARN ("/{0} live check inconclusive - try cache clear + hard reload" -f $p.route) }
    } catch { WARN ("GET /{0} failed: {1}" -f $p.route, $_.Exception.Message) }
}
OK "DONE. Browser test with Ctrl+Shift+R."
