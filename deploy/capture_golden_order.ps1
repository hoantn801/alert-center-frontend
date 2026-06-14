# capture_golden_order.ps1 - capture ONE real Omisell order detail (sanitized)
# for the G1.1 price-component mapping confirmation. READ-ONLY to Omisell
# (pull_one_order does a GET + idempotent Frappe ingest; capture_golden=1 also
# returns the SANITIZED raw payload). No Omisell write, no stock write.
#
# 1) Find a real Omisell order number that contains SKU P02056 (Omisell
#    dashboard, or the /alerts list reference). pull_one_order needs the ORDER
#    NUMBER, not the SKU.
# 2) Run:  .\capture_golden_order.ps1 -OrderNumber "<omisell_order_number>"
#          (optional -Brand FES-VN ; -OutFile path)
# It saves the sanitized payload and auto-checks the price arithmetic + lists
# EVERY field on a line item (so extra layers - coins/shipping/subsidy/payment
# - are revealed). Share the saved JSON back for mapping confirmation.
param(
    [Parameter(Mandatory=$true)][string]$OrderNumber,
    [string]$Brand = "FES-VN",
    [string]$OutFile = ""
)
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
$M = "ecentric_workspace.alerts.api_omisell.pull_one_order"
if (-not $OutFile) { $OutFile = Join-Path $PSScriptRoot ("golden_capture_" + ($OrderNumber -replace '[^\w\-]','_') + ".json") }

INFO "Capturing $OrderNumber (brand $Brand) ..."
$body = @{ brand = $Brand; omisell_order_number = $OrderNumber; capture_golden = 1 } | ConvertTo-Json
$resp = Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" -Body $body -Uri "$base/api/method/$M"
$payload = $resp.message.golden_payload
if (-not $payload) { ERR "No golden_payload returned. Check the order number / brand / SM token."; exit 1 }

# save pretty JSON
$payload | ConvertTo-Json -Depth 12 | Out-File $OutFile -Encoding utf8
OK "Saved sanitized golden payload -> $OutFile"

# --- auto-inspection -------------------------------------------------------
INFO "Order: status_id=$($payload.status_id) status_name=$($payload.status_name)"
$parcels = @($payload.parcels)
INFO ("parcels: {0}" -f $parcels.Count)
$lineNo = 0
foreach ($p in $parcels) {
    foreach ($it in @($p.catalogue_items)) {
        $lineNo++
        Write-Host ""
        INFO ("LINE {0}: sku={1} qty={2}" -f $lineNo, $it.catalogue_sku, $it.quantity)
        # dump EVERY property name+value so unexpected discount layers show up
        Write-Host "      all fields on this line item:" -ForegroundColor DarkGray
        $it.PSObject.Properties | ForEach-Object {
            Write-Host ("        {0} = {1}" -f $_.Name, $_.Value)
        }
        # arithmetic check: original - (discount_seller+voucher_seller+discount_platform+voucher_platform) ?= discounted_price
        $orig = [double]($it.original_price); $disc = [double]($it.discounted_price)
        $ds = [double]($it.discount_seller); $vs = [double]($it.voucher_seller)
        $dp = [double]($it.discount_platform); $vp = [double]($it.voucher_platform)
        $calc = $orig - $ds - $vs - $dp - $vp
        $delta = $disc - $calc
        if ([math]::Abs($delta) -lt 0.5) {
            OK ("  arithmetic OK: {0} - ({1}+{2}+{3}+{4}) = {5} = discounted_price (per-unit)" -f $orig,$ds,$vs,$dp,$vp,$calc)
        } else {
            WARN ("  arithmetic MISMATCH: original-4components = {0} but discounted_price = {1} (delta {2}). EXTRA discount layer likely exists - inspect the field dump above." -f $calc,$disc,$delta)
        }
        # per-unit vs line-total hint
        $tx = $null
        if ($payload.payment_information) { $tx = [double]($payload.payment_information[0].transaction_amount) }
        if ($tx) { INFO ("  hint: discounted_price*qty = {0} ; order transaction_amount = {1} (sum across lines = per-unit confirmation)" -f ($disc*[double]$it.quantity), $tx) }
    }
}
Write-Host ""
OK "Done. Share $OutFile back for mapping confirmation (it is already sanitized - no tokens/PII)."
WARN "Confirm from the dump: (1) field names discount_seller/voucher_seller/discount_platform/voucher_platform, (2) arithmetic OK lines, (3) any EXTRA field (coin/point/shipping/subsidy/payment), (4) per-unit (transaction_amount = sum of discounted_price*qty)."
