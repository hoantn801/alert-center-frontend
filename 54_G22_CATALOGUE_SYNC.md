# 54 — G2.2: catalogue/list → SKU Catalog sync (preview + confirm)

Date: 2026-06-12 · Status: BUILT, 101/101 tests pass (full suite, 1 bench-only skip), awaiting deploy.
Probe verdict (doc 52, owner-run): primary source = `/api/v2/public/catalogue/list` (per-shop scope đầy đủ); `product/list` KHÔNG dùng làm primary (không có shop scope).

## Changes (4 files sửa/mới + 2 tests, code-only, NO migration)

| File | Change |
|---|---|
| `services/omisell_client.py` | +`get_catalogues(page, page_size)` — GET `/api/v2/public/catalogue/list` qua chokepoint (read-only). |
| `tests/test_phase_d1.py` | Contract test surface cập nhật CÓ CHỦ ĐÍCH: `["get_catalogues", "get_order_detail", "get_orders", "get_shops"]`. |
| `services/catalogue_sync.py` | MỚI. PURE: `normalize_catalogue()` (mapping đúng spec: sku/name/price/price_sale/images[0]/platform→normalize Select + platform_raw/shop_id/shop_name/external_id/catalogue_id/status/status_name/external_stock), **flatten variants** thành rows riêng (variant.sku = seller_sku, kế thừa field parent khi variant thiếu, giữ parent_sku + parent_catalogue_id + is_variant; parent có sku sellable cũng sync; parent không sku → chỉ variants). `compare_price()` tolerance 0.5%. Frappe-side: `upsert_catalogue_row()` — ghi DUY NHẤT `EC Marketplace SKU Catalog`, key giữ nguyên `Omisell\|omisell_shop_id\|seller_sku` (sku_catalog.catalog_key), hash-gated idempotent. |
| `api_catalogue_sync.py` | MỚI. SM-only POST: `preview_catalogue_sku_sync(brand, pages?, page_size?)` — **zero write**, trả counts (rows/parents/variants/would_create/would_enrich) + **price report** (catalogue price/price_sale vs order-derived RSP per SKU+shop, verdict match/mismatch, cap 200 dòng) + sample 10 rows + pagination/rate header. `confirm_catalogue_sku_sync(brand, pages?, page_size?, max_rows?)` — upsert với caps (pages ≤40, rows ≤5000, default 1000, time budget 200s, capped/timeboxed → chạy lại để tiếp, idempotent). |
| `tests/test_catalogue_sync.py` | MỚI, 15 tests: parent row, variant flatten (own-price wins, inherit, empty-sku dropped, parent-no-sku case), platform normalize, shop-scoped key distinct (21611 vs 21612 cùng SKU), price guard (match/tolerance/mismatch/no_reference), note JSON confidence, hash sensitivity, preview-no-write (cấm insert/save/set_value trong api module), confirm-writes-only-SKU-Catalog, order-derived-RSP-wins, SM-only + caps, client path read-only. |

## Price guard (đúng yêu cầu)

- `catalogue.price` CHƯA được tin là RSP.
- Row đã tồn tại `source_level=order_derived` có `rsp_price` → catalogue **không bao giờ** ghi đè rsp_price; verdict mismatch → `price_confidence=low` trong note JSON. Match (≤0.5%) → `high`. Không có reference → `unverified`.
- Preview cho bảng so sánh trước khi confirm; muốn catalogue price thắng phải có quyết định riêng của anh (chưa code đường đó).

## Quyết định không-migration (2 điểm cần anh biết)

1. `source_level` dùng option có sẵn **`omisell_product`** (Select hiện chỉ có order_derived/omisell_product; thêm option `omisell_catalogue` = sửa DocType + migrate). Phân biệt nguồn nằm trong note JSON `"src": "catalogue/list"`. Muốn đúng chữ `omisell_catalogue` → follow-up nhỏ có migrate.
2. Các field mới (sale_price, image_url, catalogue_id, parent_sku/is_variant, status_raw, external_stock, shop_name, price_confidence) đóng gói vào field `note` (Small Text, JSON ≤1200 chars) — không schema change. Cần query/filter theo các field này sau → promote lên field thật (migrate) ở G2.3.

## Deploy (owner)

```powershell
git -C C:\dev\ecentric_workspace rev-parse --abbrev-ref HEAD   # verify FIRST
git -C C:\dev\ecentric_workspace checkout -b feat/g2-2-catalogue-sync
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/omisell_client.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/catalogue_sync.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_catalogue_sync.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_catalogue_sync.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_phase_d1.py
git -C C:\dev\ecentric_workspace commit -m "feat(alerts): G2.2 catalogue/list SKU sync - preview/confirm, variant flatten, price guard"
# push -> PR -> merge -> FC deploy (code-only, no migrate)
```

LƯU Ý: nếu hotfix doc 53 (`fix/omisell-timeout-minimal`) chưa merge — 2 branch cùng sửa `omisell_client.py`, merge hotfix TRƯỚC rồi rebase branch này.

## Run sau deploy (PowerShell, thứ tự bắt buộc)

```powershell
$cred = Import-Csv "C:\dev\frappe_api_keys -newww.csv" | Select-Object -First 1
$h = @{ Authorization = ("token {0}:{1}" -f $cred.api_key, $cred.api_secret) }
$base = "https://team.ecentric.vn/api/method/ecentric_workspace.alerts.api_catalogue_sync"

# 1. PREVIEW (zero write) - xem price report truoc
$p = (Invoke-RestMethod -Method Post -Headers $h -ContentType "application/json" `
  -Body '{"brand":"FES-VN","pages":2}' -Uri "$base.preview_catalogue_sku_sync").message
$p | ConvertTo-Json -Depth 8 | Set-Content preview_fes.json
$p.price_compare   # mismatches phai duoc review truoc khi confirm

# 2. CONFIRM (chi ghi SKU Catalog; can xac nhan truoc khi chay)
# (Invoke... "$base.confirm_catalogue_sku_sync" -Body '{"brand":"FES-VN"}')
# 3. Lap lai cho LOF-VN. 4. Re-run confirm -> counts.unchanged tang, khong dup.
```

## Verify checklist

1. Preview FES-VN: parents+variants đếm hợp lý, price_compare.mismatches — soi từng dòng mismatch (kỳ vọng P02056 RSP 247000 khớp).
2. Confirm: `created` ≈ SKU chưa có đơn; `enriched` = rows order-derived nhận thêm external_id/image/note, **rsp_price không đổi** (spot-check P02056).
3. Re-run confirm → toàn `unchanged`, count catalog không tăng (idempotent).
4. `/alerts/policies` SKU search thấy SKU mới (source_level=omisell_product).
5. Bench tuỳ chọn: `run-tests --module ...test_catalogue_sync` + `...test_phase_d1`.
