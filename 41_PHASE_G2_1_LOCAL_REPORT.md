# Alert Center — Phase G2.1 Local Implementation Report
## Order-derived SKU Catalog + Policy Autofill

Date: 2026-06-08 · Status: **IMPLEMENTED — backend in `C:\dev\ecentric_workspace`, frontend built in `C:\dev\ALERT_CENTER`. Ready to deploy.** Order-derived only (no Omisell call). No stock write; DS1 locked; scheduler/hooks/tasks/PM untouched; G1.1 Case/Occurrence unchanged.

---

## 1. Files changed

**Backend (`ecentric_workspace/alerts/`):**
- NEW DocType `doctype/ec_marketplace_sku_catalog/` (`.json` + `.py` + `__init__.py`).
- NEW `services/sku_catalog.py` — key builder + upsert + backfill (PURE-ish).
- NEW `api_sku_catalog.py` — 5 whitelisted reads/backfill.
- NEW `tests/test_phase_g2.py`.
- EDIT `services/alert_engine.py` — `+import sku_catalog` and one **fail-open** inline upsert per line in `check_order_log` (the only ingest-path touch).

**Frontend (`ALERT_CENTER/frontend/build_alert_pages.py`):** `/alerts/policies` — enabled the SKU search button + SKU search modal + autofill, a "Thiếu policy" coverage modal (+ export CSV template), CSS reuse, build asserts. Rebuilt 5 HTML in `frontend/`.

---

## 2. Schema impact / migrate

**Migrate REQUIRED** (one new DocType). `EC Marketplace SKU Catalog` fields: brand, platform, shop, omisell_shop_id, seller_sku, product_name, external_product_id, erpnext_item_code, rsp_price, is_active, status, source_system, source_level(order_derived/omisell_product), first_seen_at, last_seen_at, raw_payload_hash, **catalog_key (UNIQUE)**, note. Search indexes on brand/seller_sku/omisell_shop_id/last_seen_at. Additive only — no change to existing tables. No DocPerm/role change (SM-only DocPerm; service-layer access).

---

## 3. Upsert logic (`services/sku_catalog.py`)

Identity `catalog_key = source_system | omisell_shop_id | seller_sku` (fit ≤140). `upsert(...)`:
- look up by `catalog_key`. If found and `raw_payload_hash` unchanged → touch `last_seen_at` + `is_active=1` (cheap, no modified bump) → `unchanged`.
- if found and hash changed → update product_name + **latest** rsp_price + last_seen + hash → `updated`.
- if absent → insert with first_seen=last_seen=now → `created`.
- empty SKU → `skipped`.

`raw_payload_hash` = hash(product_name, rsp, platform, shop) — so a new RSP triggers an update (latest wins, per G2.1 decision). `upsert_from_order_line(log, line)` is the inline hook (wrapped in try/except in the engine — **fail-open**, never blocks ingestion/pull). `backfill(brand, days, limit)` rebuilds from existing Order Items joined to Order Log, **oldest→newest** so the latest order's RSP wins; bounded by `limit`; per-row try/except. Re-running never duplicates (unique key); idempotent.

---

## 4. API contracts (all brand-scoped, no secret leak, Omisell never called)

- `list_sku_catalog(filters, start, page_len)` → `{rows, total}` (CAT_FIELDS; brand/platform/shop/seller_sku-like/is_active).
- `search_skus(brand, platform?, shop?, keyword="", limit=20)` → `{rows:[{seller_sku, product_name, rsp_price, platform, shop, omisell_shop_id, source_level}]}` — powers autofill; matches seller_sku OR product_name; `require_brand_access`.
- `sync_sku_catalog_preview(brand, days=90)` → `{distinct_order_skus, existing_catalog}` (read-only count).
- `sync_sku_catalog_confirm(brand, days=90, limit=5000)` [POST] → backfill counts; `can_manage_policy` gated; writes catalog only (no Omisell).
- `policy_missing_skus(brand, platform?, days=30, limit=200)` → `{missing:[{seller_sku, product_name, rsp_price, order_lines, last_order}], missing_count, checked, coverage_pct}`.

---

## 5. UI changes (`/alerts/policies`)

- The previously-disabled **"Tìm SKU từ Omisell"** button is now **enabled**. Clicking it (after a Brand is chosen in the drawer) opens a **SKU search modal**: keyword box (sku/name) + results table (`seller_sku · product_name · RSP · platform · shop`) via `search_skus` scoped to the drawer's Brand/Platform/Shop. Selecting a row **autofills** `seller_sku`, `product_name`, `target_price` (Listed/RSP), and `platform`/`shop` when empty. **Manual entry still works** (autofill only pre-fills).
- New header button **"Thiếu policy"** opens a **coverage modal**: pick brand → shows **coverage %** + the table of SKUs with recent orders but **no Active policy** (`policy_missing_skus`), and an **Export CSV template** button (`missing_policy_<brand>.csv`, columns matching the policy importer, RSP prefilled) for bulk creation.

Same `.al-*` style; built pages ASCII-clean, no unresolved placeholders.

---

## 6. Tests

- Sandbox **9/9 PASS** (`test_phase_g2`): `catalog_key` (format, distinct by shop/sku/source, trim-stable, None parts, fit≤140 with hash); `_row_hash` (changes on rsp/name, stable when same); secret-redaction (`CAT_FIELDS` has no key/secret/token/password).
- All 5 backend Python files `py_compile` clean; DocType JSON parses (22 fields, unique catalog_key). Upsert/backfill DB behavior is bench-pending (`bench run-tests --module ...test_phase_g2`).
- Frontend: all 5 pages build, **every assert passes** incl. G2.1 (SKU search ENABLED; `pl-sku-modal`, `api_sku_catalog.search_skus`, `openSkuSearch`, `pl-coverage`, `policy_missing_skus`, `exportCovTemplate`). ASCII-clean.

---

## 7. No-write confirmation

No Omisell call anywhere in G2.1 (catalog is built from already-ingested Frappe order data). No stock/buffer/inventory write. DS1 locked. The only ingest-path change is a **fail-open** catalog upsert (try/except) that cannot break ingestion/pull. No scheduler/hooks/tasks/PM change. No DocPerm/role change. G1.1 Case/Occurrence engine path unchanged (the hook runs before it and never raises).

---

## 8. Deploy / rollback

**Drop 1 (backend, owner commits from Windows in `C:\dev\ecentric_workspace`):** new branch, stage the 5 new files + `services/alert_engine.py`, PR → merge → **FC deploy WITH migrate**. Then optionally `sync_sku_catalog_confirm(brand=FES-VN)` (and LOF-VN) to backfill the catalog from existing orders (or let it grow on the next pull via the inline hook).

**Drop 2 (frontend):** `cd C:\dev\ALERT_CENTER\deploy; .\deploy_alert_pages.ps1` (all 5 pages). Ctrl+Shift+R `/alerts/policies`.

**Rollback:** backend revert PR → FC deploy (new DocType harmless if left; engine reverts to no-catalog). Frontend `rollback_alert_pages.ps1` / redeploy prior HTML. Additive; no data unwind.

---

## 9. Verify after deploy

1. Backfill FES-VN: `sync_sku_catalog_confirm(brand="FES-VN")` → counts created/updated. `list_sku_catalog({brand:"FES-VN"})` returns rows incl. P02056 with RSP.
2. `/alerts/policies` → +Policy → choose FES-VN → "Tìm SKU" → search "P02056" → select → seller_sku/product_name/RSP autofill.
3. "Thiếu policy" → FES-VN → coverage % + missing-SKU table; Export CSV downloads `missing_policy_FES-VN.csv`.
4. Confirm a normal pull still ingests + raises Case/Occurrence (G1.1) with no error (catalog hook fail-open).
