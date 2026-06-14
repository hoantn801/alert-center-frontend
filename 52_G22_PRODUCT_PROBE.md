# 52 — G2.2 probe-only: Omisell product/catalogue endpoints

Date: 2026-06-12 · Status: PROBE BUILT (chưa deploy, chưa chạy). Probe-only — KHÔNG sync, KHÔNG ghi SKU Catalog, KHÔNG đụng scheduler/ingest/hooks.

## Mục tiêu

Xác nhận field shape thật của các endpoint product/catalogue (đọc) để G2.2 fill SKU Catalog cho SKU chưa có đơn. Docs chỉ cho API IDs (Get Product List `api-6492412`, Get Product Detail by SKU `api-10762720`, Get Catalogue List `api-5741887` — schema `Response Product`/`Response Catalogue`), **URL path chính xác chưa confirm** (docs site là SPA, không fetch được) → probe thử candidate paths + nhận custom path.

## Đã build

1. **`alerts/api_probe_products.py`** (MỚI, additive, code-only):
   - `probe_product_endpoints(brand, extra_paths?)` — thử 5 candidate paths (`/api/v2/public/product/list`, `/products`, `/catalogue/list`, `/catalogues`, `/product/sku/list`) với `page_size=2`, 1 page.
   - `probe_product_api(brand, path, params?)` — probe 1 path tuỳ ý.
   - Cả hai SM-only POST; GET-only qua `OmisellClient._request` (chokepoint `ALLOWED_METHODS={GET}` — write verb là bất khả thi); output **shape-only**: key→{type, sample sanitized ≤120 chars}, pagination keys (count/next/...), rate-limit header, error per path. Không dump bulk, không ghi DocType nào.
   - Cố ý gọi `_request` private: public surface của client bị contract-freeze bởi `test_phase_d1.test_read_only_surface_unchanged` — probe không pre-empt quyết định thêm method; G2.2 thật sẽ thêm `get_product_list`/`get_catalogue_list` + update test đó.
2. **`deploy/probe_g22_products.ps1`** — chạy cho FES-VN + LOF-VN, in shape table + lưu JSON `probe_g22_<brand>_<stamp>.json`. `-ExtraPaths` để bổ sung path đúng từ docs nếu candidates đều 404.

Verify: py_compile OK, ASCII clean cả 2, không có `.insert/.save/set_value/delete`, braces cân.

## Owner runbook

```powershell
# 1. deploy probe (branch from CLEAN main, additive 1 file, no migrate)
git -C C:\dev\ecentric_workspace checkout main && git pull
git -C C:\dev\ecentric_workspace checkout -b feat/g2-2-product-probe
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_probe_products.py
git -C C:\dev\ecentric_workspace commit -m "feat(alerts): G2.2 probe-only product/catalogue endpoint probe"
# push -> PR -> merge -> FC deploy

# 2. run probe (FES-VN + LOF-VN)
cd C:\dev\ALERT_CENTER\deploy
.\probe_g22_products.ps1
# neu tat ca candidate 404: mo developers.omisell.com lay path that, roi:
.\probe_g22_products.ps1 -ExtraPaths "/api/v2/public/<path-that>"
```

## Recommended mapping (hypothesis — chốt sau khi có JSON probe)

Đích là `EC Marketplace SKU Catalog` (đã có từ G2.1, `source_level = omisell_product`):

| Catalog field | Nguồn kỳ vọng (Response Product/Catalogue) | Ghi chú |
|---|---|---|
| `seller_sku` | `catalogue_sku` / `sku` | cùng identity với order line (golden: `catalogue_sku`) |
| `product_name` | `name` / `product_name` | |
| `rsp_price` | `original_price` / `list_price` / `price` | PHẢI đối chiếu với order `original_price` (đơn vị per-unit, VND) trên cùng SKU (P02056 = 247000/282000 tuỳ thời điểm) trước khi tin |
| `image_url` | `image` / `images[0]` / `thumbnail` | field mới, blank cho order_derived |
| `external_product_id` | `id` / `product_id` | order line KHÔNG có — đây là giá trị gia tăng chính của Level B |
| `omisell_shop_id` + `platform`/`shop` | per-shop field hoặc param `shop_id` | NẾU product list là per-account (không per-shop) → map qua `EC Marketplace Shop` không khả thi trực tiếp → catalog_key thiếu shop → cần quyết định key mới (`source|account|seller_sku`?) — RỦI RO LỚN NHẤT |
| `is_active`/`status` | `status` / `is_active` | mapping enum cần bảng giá trị thật |

## Risks (đánh giá trước khi implement)

1. **Per-shop vs per-account scope** (cao): nếu product list không filter theo shop, `catalog_key = source|omisell_shop_id|seller_sku` không áp được → hoặc fan-out theo shop param, hoặc key cấp account — quyết định trước khi viết sync.
2. **Price semantics** (cao): product "price" có thể là sale price hiện tại, không phải RSP. Sai field → policy autofill sai RSP → alert sai hàng loạt. Bắt buộc đối chiếu golden SKU (P02056) giữa product API và order `original_price`.
3. **Volume + rate limit** (vừa): catalogue list có thể hàng nghìn SKU/brand; bucket 100/min + pacing 1s → full sync phải chunked + capped như Phase D; chỉ chạy on-demand (không scheduler) ở G2.2 đầu.
4. **Path/pagination unknown** (vừa): candidate paths có thể sai hết — probe có `-ExtraPaths`; pagination có thể không phải `count/next` chuẩn.
5. **Catalogue vs Product là 2 khái niệm** (vừa): Omisell phân biệt catalogue (master) vs product (per-channel listing). Mapping nhầm tầng → SKU trùng/sai shop. Probe cả hai schema rồi mới chọn.
6. **Timeout** (thấp): đã có GET retry (2s/5s) từ doc 50.

## Gate sang implementation

Chỉ sau khi: (1) probe JSON cho cả 2 brand, (2) bảng mapping trên được điền bằng field THẬT + ví dụ giá đối chiếu golden OK, (3) quyết định scope key (shop vs account), (4) user duyệt. Khi đó mới: thêm public client methods + update contract test, `sku_normalizer`, upsert `source_level=omisell_product` (hash-gated), on-demand sync endpoint — vẫn không scheduler.
