# Alert Center — Phase G2 Pre-Code Proposal
## SKU Catalog Sync / Policy Autofill

Date: 2026-06-08 · Status: **PRE-CODE — awaiting approval. No code written.** Read-only to Omisell; no stock write; DS1 locked; schedulers/hooks/tasks/PM untouched. Backend `C:\dev\ecentric_workspace`, frontend `C:\dev\ALERT_CENTER`.

Goal: make Price Policy creation fast + error-free for KAM by searching/autofilling SKU, product name, listed/RSP price, platform, shop from a synced SKU catalog.

---

## 1. Current available data sources (inspected from code + official docs)

**A. Order-derived (already in Frappe, zero new Omisell calls).** `EC Marketplace Order Item` lines carry `seller_sku`, `product_name`, `list_price` (= Omisell `original_price` = **RSP/listed**, confirmed reliable by the G1.1 golden), plus G1.1 component amounts. Via the parent `EC Marketplace Order Log`: `brand`, `platform`, `shop`, `omisell_shop_id`, `order_datetime`. The normalizer does **not** populate `external_product_id` or any image. `EC Marketplace Shop` provides `shop_code`/`shop_name`/`platform`/`brand`/`omisell_shop_id`/`status`. So order-derived catalog = brand + platform + shop + omisell_shop_id + seller_sku + product_name + listed/RSP + first/last seen. **No image, no ERPNext item_code** (Order Item `.item` is usually empty).

**B. Omisell product/catalogue endpoints (read-only GET, NOT yet in our client).** The official docs (developers.omisell.com) expose, under `Authorization: Omi <token>` (same auth we already use):
- **Get Product List** (`api-6492412`), **Get Product Detail** (`api-6492414`), **Get Product Detail by SKU** (`api-10762720`) — schema `Response Product` (`schema-1742819`).
- **Get Catalogue List** (`api-5741887`), **Get Catalogue Detail** (`api-5741888`) — schema `Response Catalogue` (`schema-1469226`).
- **Get Order Catalogues Detail** (`api-6690236`).
Our `OmisellClient` currently has only `get_shops` / `get_orders` / `get_order_detail` (`ALLOWED_METHODS = {GET}`, frozen). Adding Level B = 1–2 new GET methods. These are **read-only** (Add/Update Product are writes — explicitly NOT used). Exact field shape (image_url, price field name, ERPNext-mappable id, pagination) is **unconfirmed** — needs a probe + golden capture per brand/shop, exactly like Phase D.

**Recommendation: implement Level A first (G2.1).** It covers precisely the SKUs that already generate orders/alerts — the highest-value SKUs for policy authoring — with zero Omisell risk. Level B (G2.2) adds completeness (SKUs without orders) but requires a gated probe; do it second.

---

## 2. Proposed DocType — `EC Marketplace SKU Catalog`

New, app-owned (custom=0), SM-only DocPerm, service-layer access. Upserted (never blindly appended).

| Field | Type | Notes |
|---|---|---|
| `catalog_key` | Data, UNIQUE, read-only | upsert identity = `source|omisell_shop_id|seller_sku` (fit-to-140) |
| `brand` | Link Brand Approver | search_index |
| `platform` | Select | Shopee/Lazada/TikTok/Other |
| `shop` | Link EC Marketplace Shop | |
| `omisell_shop_id` | Data | search_index |
| `seller_sku` | Data | search_index |
| `external_product_id` | Data | from Level B / order line if present |
| `erpnext_item_code` | Link Item | only if a confident match exists (else blank) |
| `product_name` | Data | |
| `listed_price` / `rsp_price` | Currency | = order `list_price` (A) or product price (B) |
| `image_url` | Data | Level B only (blank for A) |
| `source_system` | Select | default `Omisell` |
| `source_level` | Select | `order_derived` / `omisell_product` |
| `raw_payload_hash` | Data | change detection for upsert |
| `first_seen_at` / `last_seen_at` | Datetime | |
| `is_active` | Check | seen within N days / present in latest sync |
| `status` | Select | Active / Stale / Retired |
| `note` | Small Text | import/source note |

Indexes: `(brand, seller_sku)`, `(brand, platform, shop)`. Growth is bounded by distinct SKUs per brand (small vs orders).

---

## 3. Sync / upsert strategy

Pure key builder `catalog_key(source, omisell_shop_id, seller_sku)` (mirrors `dedupe_keys`). Upsert = look up by `catalog_key`; if found, update `product_name`/`listed_price`/`last_seen_at`/`raw_payload_hash` (only when hash changed) and set `is_active=1`; else insert with `first_seen_at`. Never delete on sync — mark `Stale`/`is_active=0` when not seen for > threshold (a separate, optional maintenance pass; NOT a scheduler change in G2.1).

- **Level A backfill** (`services/sku_catalog.py`): a bounded function that scans recent `EC Marketplace Order Item` (joined to Order Log for brand/platform/shop, last N days, capped) and upserts catalog rows. Run on demand via the confirm endpoint; optionally also called inline at the end of `alert_engine.check_order_log` per line (tiny, idempotent) so the catalog grows automatically as orders ingest — **this is the only backend touch to the ingest path; it adds no Omisell call and no scheduler change.** (If you prefer zero ingest-path change, keep it backfill-only.)
- **Level B sync** (G2.2): read-only `get_product_list`/`get_catalogue_list` paged calls (rate-paced, same circuit-breaker discipline as Phase D), normalize via a new `sku_normalizer`, upsert. Gated by a probe + golden capture confirming the schema first.

Idempotency: re-running a backfill/sync never duplicates rows (unique `catalog_key`); `raw_payload_hash` skips no-op writes.

---

## 4. API endpoints (new `api_sku_catalog.py`, all `@frappe.whitelist`, brand-scoped, no secret leak)

- `list_sku_catalog(filters, start, page_len)` → `{rows, total}`. Filters: brand/platform/shop/seller_sku(like)/is_active. Scoped via `get_allowed_brands`.
- `search_skus(brand, platform=None, shop=None, keyword="", limit=20)` → `[{seller_sku, product_name, listed_price, platform, shop, omisell_shop_id, source_level}]`. Powers the policy autofill search; `require_brand_access(brand)`. Keyword matches seller_sku OR product_name (bounded LIMIT).
- `sync_sku_catalog_preview(brand, platform=None, shop=None, days=30)` → counts that **would** be upserted from orders (Level A) — read-only, no write. (G2.2: also previews Omisell product count.)
- `sync_sku_catalog_confirm(brand, platform=None, shop=None, days=30)` → runs the Level A backfill (writes Frappe catalog rows only; **no Omisell call**). SM or manager gated. (G2.2: a separate `sync_from_omisell_*` that does the read-only Omisell pull, gated by probe.)
- `policy_missing_skus(brand, platform=None, days=30, limit=200)` → SKUs seen in recent orders (or catalog) with **no Active EC Price Policy** — reuses the G1 `_coverage` join. Feeds the coverage UX.

No endpoint returns api_key/secret/token. Writes are Frappe-only; Omisell stays read-only (and absent entirely from G2.1).

---

## 5. UI flow (`/alerts/policies`)

Replace the current disabled **"Tìm SKU từ Omisell"** placeholder with a working **SKU search**:
1. User picks Brand (+ optional Platform / Shop) in the policy drawer.
2. Clicks "Tìm SKU" → a search modal/dropdown (`search_skus`) lists matches: `seller_sku · product_name · listed/RSP · platform · shop`.
3. Selecting a row autofills the policy form: `seller_sku`, `product_name`, `reference_price`/`target_price` from `listed_price` (RSP) where appropriate, and `platform`/`shop` when the catalog row is shop-specific.
4. **Manual entry stays possible** (autofill only pre-fills; KAM can edit).

Same `.al-*` style (reuse the modal + `.al-occ-tbl`/`.al-fgrid` patterns). ASCII-clean build.

---

## 6. Coverage UX

On `/alerts/policies` (or a small sub-panel): **SKUs missing an active policy** — a table from `policy_missing_skus` (seller_sku, product_name, last order date, order count), the brand **policy coverage %** (reuse `api_brands.policy_coverage`), and a button to **export a missing-policy CSV template** (client-side, columns matching the existing policy CSV import) so KAM can bulk-create. Catalog SKUs without a policy can be folded into the same view (source_level shown).

---

## 7. Permission / scoping

Reuse the service layer: every endpoint starts with `require_alert_center_access` and scopes by `get_allowed_brands` / `require_brand_access(brand)`. Catalog management (sync confirm) = `can_manage_policy` (manager/KAM) for Level A; Level B Omisell sync = SM-only (it touches the integration). No new role, no DocPerm widening. Catalog holds no secrets.

---

## 8. Risks / unknowns

- **Level A incompleteness** — SKUs with no orders won't appear (acceptable: those SKUs aren't generating alerts yet; Level B fills the gap).
- **RSP per-order variance** — `list_price` is per order line; the same SKU could show different `original_price` across orders/time. Strategy: store the **latest** (by order_datetime) and keep `raw_payload_hash`; optionally surface "RSP last seen on <date>".
- **No image / ERPNext item_code from orders** — those fields stay blank until Level B (image) / an explicit mapping step (item_code).
- **Level B schema unconfirmed** — `Response Product`/`Response Catalogue` field names, price semantics, pagination, and whether a per-shop listing price exists must be confirmed via a real probe + golden capture before G2.2 coding (same gate as Phase D).
- **Ingest-path hook** (optional inline upsert) adds a tiny write per line — must stay idempotent and never block ingestion (wrap in try/except, fail-open). If risk-averse, keep backfill-only.
- Catalog table growth — bounded by distinct SKUs (small); add to `capacity_stats` for visibility.

---

## 9. Test plan

- Pure: `catalog_key` builder (stable, ≤140, distinct per shop+sku); upsert decision (hash-equal → no write).
- Bench: backfill from seeded orders → catalog rows upserted, re-run → no duplicates + last_seen advanced; `search_skus` scoping (KAM sees only own brands, keyword matches sku/name); `policy_missing_skus` correctness vs Active policies; secret-redaction (no key in any response).
- Live (read-only probe): `list_sku_catalog`/`search_skus` for FES-VN return expected rows; coverage % matches `policy_coverage`.
- Regression: G1.1 Case/Occurrence unchanged; FES-VN/LOF-VN schedulers healthy; no Omisell write.

---

## 10. Deploy / rollback

- **G2.1 (Level A):** Drop 1 backend — new DocType `EC Marketplace SKU Catalog` + `services/sku_catalog.py` + `api_sku_catalog.py` (+ optional 1-line ingest hook); PR → FC deploy **with migrate**. Drop 2 frontend — `/alerts/policies` SKU search + autofill + coverage panel; `deploy_alert_pages.ps1`. Additive; rollback = revert PR (catalog table harmless if left) + redeploy prior pages.
- **G2.2 (Level B):** separate gated phase — probe + golden capture → new read-only client GET methods + `sku_normalizer` + sync endpoints; PR + migrate (only if fields added). Rollback additive.

---

## Recommended implementation phases

1. **G2.1 — Order-derived catalog + search/autofill + coverage UX** (no new Omisell call, immediate KAM value). ← do first.
2. **G2.2 — Omisell product/catalogue sync** (read-only GET, probe-gated, fills SKUs without orders; adds image/richer RSP).
3. **G2.3 — Enrichment** (ERPNext item_code mapping, image display, stale-marking maintenance) — optional, gated.

---

## Open questions for approval

1. Confirm **G2.1 (order-derived) first**, G2.2 (Omisell product sync) as a gated follow-up?
2. Inline catalog upsert in the ingest path (auto-growing catalog) vs **backfill-only** (zero ingest-path change)? Recommend the tiny fail-open inline hook, but will do backfill-only if you prefer no ingest touch.
3. RSP when it varies across orders: store **latest** (recommended) vs most-frequent?
4. Coverage UX location: inside `/alerts/policies` (recommended) vs a new tab.
