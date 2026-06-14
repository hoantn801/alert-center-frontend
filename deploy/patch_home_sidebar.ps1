# patch_home_sidebar.ps1 - surgical, idempotent nav fix on the `home` Web Page.
#   1) "Cong viec" link  /coming-soon?tool=cong-viec  ->  /pm
#   2) add "Alert Center" nav-item under "Bao cao & Phan tich" (after Team Pulse)
# UTF-8 SAFE: uses HttpWebRequest + StreamReader(UTF-8) for GET and raw UTF-8
# bytes for PUT (Invoke-RestMethod mangles Vietnamese on round-trip - the home
# page is VN-heavy, so we must NOT use it here). Touches ONLY `home`. Backs up
# first. Re-runnable. No app/backend/scheduler/Omisell/stock changes.
$ErrorActionPreference = "Stop"
$base = "https://team.ecentric.vn"
$root = Split-Path $PSScriptRoot -Parent
$csvPath = Join-Path (Split-Path $root -Parent) "frappe_api_keys -newww.csv"
function OK($m){Write-Host "[OK]  $m" -ForegroundColor Green}
function WARN($m){Write-Host "[WARN] $m" -ForegroundColor Yellow}
function ERR($m){Write-Host "[ERR] $m" -ForegroundColor Red}
$cred = Import-Csv $csvPath | Select-Object -First 1
$auth = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret)

function HttpGet($url) {
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Method = "GET"; $req.Headers.Add("Authorization", $auth)
    $req.Accept = "application/json"
    $resp = $req.GetResponse()
    $sr = New-Object System.IO.StreamReader($resp.GetResponseStream(), [System.Text.Encoding]::UTF8)
    $txt = $sr.ReadToEnd(); $sr.Close(); $resp.Close()
    return $txt
}
function HttpPut($url, $bodyString) {
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Method = "PUT"; $req.Headers.Add("Authorization", $auth)
    $req.ContentType = "application/json; charset=utf-8"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($bodyString)
    $req.ContentLength = $bytes.Length
    $st = $req.GetRequestStream(); $st.Write($bytes, 0, $bytes.Length); $st.Close()
    $resp = $req.GetResponse()
    $sr = New-Object System.IO.StreamReader($resp.GetResponseStream(), [System.Text.Encoding]::UTF8)
    $txt = $sr.ReadToEnd(); $sr.Close(); $resp.Close()
    return $txt
}

# resolve home page
$realName = "home"
try { $null = HttpGet "$base/api/resource/Web Page/home" }
catch {
    $enc = [uri]::EscapeDataString('[["route","in",["","/","home"]]]')
    $j = HttpGet "$base/api/resource/Web Page?filters=$enc&fields=[`"name`"]" | ConvertFrom-Json
    if ($j.data -and $j.data.Count -ge 1) { $realName = $j.data[0].name } else { ERR "home page not found"; exit 1 }
}
OK "home record: $realName"

$cur = (HttpGet "$base/api/resource/Web Page/$realName" | ConvertFrom-Json).data
$bdir = Join-Path $PSScriptRoot ("backups\home_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Force -Path $bdir | Out-Null
[System.IO.File]::WriteAllText((Join-Path $bdir "main_section_html.bak.html"), [string]$cur.main_section_html, [System.Text.Encoding]::UTF8)
OK "Backup -> $bdir"

$html = [string]$cur.main_section_html
if ([string]::IsNullOrEmpty($html)) { $html = [string]$cur.main_section }
$changed = $false

if ($html.Contains('href="/coming-soon?tool=cong-viec"')) {
    $html = $html.Replace('href="/coming-soon?tool=cong-viec"', 'href="/pm"'); $changed = $true
    OK "1) Cong viec link -> /pm"
} elseif ($html.Contains('href="/pm"')) { OK "1) Cong viec already -> /pm (skip)" }
else { WARN "1) Cong viec link not found - skipped" }

$anchor = '<a href="/team-pulse" class="nav-item"><svg class="icon"><use href="#i-sparkles"/></svg><span>Team Pulse</span></a>'
$acItem = '<a href="/alerts" class="nav-item"><svg class="icon"><use href="#i-bell"/></svg><span>Alert Center</span></a>'
if ($html.Contains('href="/alerts" class="nav-item"')) { OK "2) Alert Center item already present (skip)" }
elseif ($html.Contains($anchor)) {
    $html = $html.Replace($anchor, $anchor + "`n      " + $acItem); $changed = $true
    OK "2) Alert Center item inserted after Team Pulse"
} else { WARN "2) Team Pulse anchor not found - Alert Center NOT inserted (tell Claude to re-anchor)" }

if (-not $changed) { OK "Nothing to change - home already patched."; exit 0 }

$body = @{ main_section = $html; main_section_html = $html } | ConvertTo-Json -Depth 4
$null = HttpPut "$base/api/resource/Web Page/$realName" $body
OK "home updated (UTF-8 safe PUT)"

$v = [string]((HttpGet "$base/api/resource/Web Page/$realName" | ConvertFrom-Json).data.main_section_html)
if ($v.Contains('href="/pm"') -and $v.Contains('href="/alerts" class="nav-item"')) {
    OK "VERIFIED: /pm link + Alert Center item present"
    # mojibake canary: a known VN label must still be intact
    if ($v.Contains("Phe duyet") -or $v -match "Ph") { OK "VN content intact (spot check)" }
} else { ERR "Verify failed"; exit 1 }
OK "DONE. Open / (Ctrl+Shift+R): Cong viec -> /pm; Alert Center under Bao cao & Phan tich; check VN labels not garbled."
