# 63 — Combined Phase 3–4 audit + plan (promote SKU fields + backfill + background catalogue sync)

Date: 2026-06-13 · Status: AUDIT ONLY. No code/commit/deploy. One migration/deploy cycle proposed for Steps 3+4.

## A. Current SKU Catalog schema (`EC Marketplace SKU Catalog`, app-owned custom=0, autoname `EC-SKU-{######}`)

18 fields: `brand`(Link Brand Approver, **idx**), `platform`(Select Shopee/Lazada/TikTok/Other), `shop`(Link EC Marketplace Shop), `omisell_shop_id`(Data, **idx**), `seller_sku`(Data, **idx**), `product_name`(Data), `external_product_id`(Data), `erpnext_item_code`(Link Item), `rsp_price`(Currency), `is_active`(Check), `status`(Select Active/Stale/Retired), `source_system`(Select Omisell/ERP/Manual), `source_level`(Select order_derived/omisell_product), `first_seen_at`(Datetime), `last_seen_at`(Datetime, **idx**), `raw_payload_hash`(Data), `catalog_key`(Data **UNIQUE**), `note`(Small Text).

**Constraints:** `catalog_key` UNIQUE (= `source|omisell_shop_id|seller_sku`). search_index on brand, omisell_shop_id, seller_sku, last_seen_at.
**Used by G2.2 search** (`api_sku_catalog`): seller_sku, product_name, rsp_price, platform, shop, omisell_shop_id, source_level, is_active, status, first/last_seen_at, external_product_id, erpnext_item_code.
**Used by order-derived RSP logic** (`services/sku_catalog.upsert`): rsp_price (latest order list_price wins), source_level=`order_derived`, catalog_key.
**Stored in `note` JSON today** (`catalogue_sync.build_note`): `src, price_confidence, sale_price, catalogue_price, image_url, catalogue_id, shop_name, platform_raw, status_raw, status_name, external_stock, is_variant, parent_sku, parent_catalogue_id`.

### Proposed promoted-field table (only fields with a verified source)

| fieldname | label | fieldtype | source (note JSON key ← catalogue) | overwrite rule | search/index |
|---|---|---|---|---|---|
| `image_url` | Image URL | Data (300) | image_url ← `images[0]` | latest catalogue (hash-gated) | no |
| `catalogue_price` | Catalogue Price | Currency | catalogue_price ← `price` | latest catalogue | no |
| `sale_price` | Sale Price | Currency | sale_price ← `price_sale` | latest catalogue | no |
| `external_stock` | External Stock | Int | external_stock ← `external_stock` | latest catalogue | no |
| `product_status` | Product Status | Data | status_name (fallback status_raw) ← `status` | latest catalogue | optional idx (Brand Setup filter) |
| `catalogue_id` | Catalogue ID | Data | catalogue_id ← `catalogue_id`/`id` | latest catalogue | no |
| `parent_sku` | Parent SKU | Data | parent_sku (variant lineage) | latest catalogue | no |
| `is_variant` | Is Variant | Check | is_variant | latest catalogue | optional idx |
| `price_confidence` | Price Confidence | Select `high/low/unverified` | computed in upsert (catalogue vs order RSP) | recompute each sync | no |
| `last_catalogue_sync_at` | Last Catalogue Sync | Datetime | set = now on each catalogue upsert | always (catalogue path only) | optional idx |

**NOT promoted (already real fields):** `product_name`, `platform`, `shop`, `external_product_id`. **NOT promoted (low value, keep in note):** `shop_name`, `platform_raw`, `status_raw`, `parent_catalogue_id`, `src`. **`rsp_price` UNCHANGED** — order-derived priority, catalogue never overwrites (binding rule 1).

→ **10 new additive fields.** All have a verified source in the existing normalizer/upsert. Decision needed: promote all 10, or core-6 only (image_url, catalogue_price, sale_price, external_stock, product_status, last_catalogue_sync_at) + keep lineage (catalogue_id/parent_sku/is_variant/price_confidence) in note? (Recommend all 10 — D2 already locked them; lineage is needed for variant grouping in Brand Setup.)

## B. Existing catalogue sync audit

- **Endpoint/shape:** `OmisellClient.get_catalogues(page, page_size)` → GET `/api/v2/public/catalogue/list` params `{page, page_size}`. Read-only via the frozen `ALLOWED_METHODS={GET}` chokepoint.
- **Pagination:** page-by-page; stops on `not data.next or not results`. Caps (confirm hotfix doc 55): pages ≤40, rows ≤5000, page_size ≤100, time budget.
- **Per-brand/shop:** per **brand** (one BIS/client). catalogue/list is shop-scoped in payload (shop_id/shop_name per item) — no per-shop iteration needed.
- **Platform normalization:** `catalogue_sync.norm_platform` prefix-based on lowercased `-`→`_`: `shopee_v2/shopee-v2 → Shopee`, lazada*/tiktok* similarly, else Other (binding rule 2 — already correct).
- **Upsert key:** `sku_catalog.catalog_key("Omisell", omisell_shop_id, seller_sku)` (= `Omisell|shop_id|sku`), UNIQUE.
- **RSP precedence:** in `catalogue_sync.upsert_catalogue_row` — if existing row is `source_level=order_derived` with `rsp_price`, catalogue NEVER overwrites `rsp_price`; mismatch → `price_confidence=low` in note. Order-derived wins (binding rule 1).
- **Failure/retry:** per-row try/except (counts errors, continues); fetch errors → OmisellError → `frappe.throw`. Client has GET timeout retry (2s/5s) + 60s read timeout (doc 53, pending deploy).
- **Scheduler/manual:** **MANUAL only** — `api_catalogue_sync.confirm_catalogue_sku_sync` (SM-only POST). NOT in hooks/tasks/scheduler. (Order pull stays priority.)
- **Lock/cooldown:** **NONE today.** Confirm runs **synchronously** (page-stream + 50s budget); no enqueue, no per-brand lock, no cooldown. ← Step 4 adds these.
- **note/JSON write:** `build_note(row, confidence)` → `json.dumps` of the 14 keys; `upsert_catalogue_row` sets `doc.note = note`.

## C. Backfill impact — queries to MEASURE on bench (sandbox has no DB/live data)

I cannot read live counts here; run these read-only on the site before migrate:
```sql
SELECT COUNT(*) FROM `tabEC Marketplace SKU Catalog`;                                  -- total rows
SELECT source_level, COUNT(*) FROM `tabEC Marketplace SKU Catalog` GROUP BY source_level;
SELECT COUNT(*) FROM `tabEC Marketplace SKU Catalog`
  WHERE note IS NOT NULL AND note LIKE '%"src": "catalogue/list"%';                     -- rows with catalogue note JSON
SELECT COUNT(*) FROM `tabEC Marketplace SKU Catalog`
  WHERE source_level='order_derived' AND rsp_price IS NOT NULL AND rsp_price>0;          -- order-derived RSP (never overwrite)
```
Inferred from code: order-derived rows have NO catalogue note (note set only by catalogue_sync); rows created by catalogue sync carry the 14-key JSON. Malformed note → must skip + log.

### Backfill patch design (idempotent)
- For each SKU Catalog row WHERE note LIKE catalogue-marker: `json.loads(note)` (try/except → on malformed: `frappe.log_error` + skip, count `malformed`).
- For each promoted field that is currently empty/NULL: set from the parsed JSON key (image_url, catalogue_price, sale_price, external_stock, product_status from status_name, catalogue_id, parent_sku, is_variant, price_confidence). `last_catalogue_sync_at` = `last_seen_at` as a one-time seed.
- **Never overwrite `rsp_price`** (untouched by backfill). **Never overwrite a promoted field that already has a value** (idempotent rerun: second pass finds them set → no-op).
- **Do NOT delete `note`** this phase (binding rule 8 — kept for compatibility).
- Raw SQL UPDATE per row OR `frappe.db.set_value(..., update_modified=False)`; bounded batch + `frappe.db.commit()` periodically. Report `{total, updated, skipped_already_set, malformed}`.
- **Rollback honesty:** backfill only POPULATES new empty fields from data still present in `note` → re-running the backfill reconstructs them; a code/field rollback (drop columns) loses the promoted copies but `note` still holds the source → no data loss. True rollback = restore from pre-migrate backup if needed; dropping the new fields is safe (note intact).

## D. `EC Catalogue Sync Run` DocType — does NOT exist → propose (app-owned, custom=0)

| field | type | notes |
|---|---|---|
| `brand` | Link Brand Approver | idx |
| `requested_by` | Link User | who triggered |
| `trigger_type` | Select `Manual/Scheduled/Backfill` | |
| `status` | Select `Queued/Running/Done/Done Partial/Error/Skipped` | idx |
| `started_at` / `finished_at` | Datetime | |
| `total_items` / `processed_items` | Int | progress |
| `inserted` / `updated` / `skipped` / `failed` | Int | counts |
| `error_message` | Small Text | sanitized |
| `lock_key` | Data | per-brand lock id held during the run |
| `cooldown_until` | Datetime | next allowed trigger |
| `job_id` | Data | rq job id |
| `summary_json` | Long Text | full run summary (pages, caps, timebox) |

autoname `EC-CSR-{######}`. DocPerm = System Manager only (read via service layer, like other alert doctypes). search_index on brand, status, started_at.

## E. Concurrency model (reuse the proven `api_omisell.pull_recent` pattern)

- **Per-brand lock key:** `frappe.cache().set_value("ec_catalogue_sync_running_<brand>", run_name, expires_in_sec=TTL)`. Mirrors `_running_key` for pulls.
- **Lock TTL:** e.g. 3900s (> max run budget), auto-expires → **stale-lock recovery** is automatic (cache TTL); plus on run finish the `finally` deletes the key.
- **Cooldown:** default **30 min** (`ec_alerts_catalogue_cooldown_minutes`, site_config). Store `cooldown_until` on the last Sync Run; new trigger checks `now < last.cooldown_until` → reject with the existing run id / next-allowed time. KAM-friendly message.
- **Duplicate trigger:** if lock present → return the in-flight run id (HTTP-quick, no new job). If within cooldown → return last run id + cooldown_until.
- **Background enqueue:** `frappe.enqueue("...catalogue_sync_job", queue="long", timeout=..., brand=..., run=run_name)` — UI POST returns `{run_id, status:"Queued"}` immediately (binding rule 5). **Order pull priority:** catalogue job on `queue="long"`; skip/defer if a pull for the brand is running (check `ec_alerts_pull_running_<brand>`).
- **Progress persistence:** the job updates the `EC Catalogue Sync Run` row (processed_items/counts/status) periodically + final; `summary_json` at end. Poll via a read endpoint.
- **Failure state:** exception → status `Error` + `error_message`; partial (cap/timebox) → `Done Partial` + next_page in summary. Lock always cleared in `finally`.
- **Safe resume/retry:** upserts are hash-gated idempotent (catalog_key UNIQUE) → re-running a brand never duplicates; `Done Partial` can be re-triggered (after cooldown or by Admin override) to continue.
- **Permissions (binding 3/4):** `can_run_catalogue_sync(user, brand)` = supervisor | manager(brand) | **kam(brand)** (own brand only). Reuse `permissions` role model.

## Gap analysis

| Need | State |
|---|---|
| Promoted fields | ❌ in note JSON → promote 10 (migration) |
| Backfill | ❌ → new patch |
| Catalogue sync writes promoted fields | ⚠️ writes note only → update upsert to set fields + keep note |
| Background + lock + cooldown + run history | ❌ confirm is sync, no lock/cooldown/run record → Step 4 |
| EC Catalogue Sync Run | ❌ → new DocType (migration) |
| Platform norm / RSP precedence / upsert key | ✅ correct, reuse |
| Permissions role model | ✅ extend with can_run_catalogue_sync |

## File-level plan (ONE migration/deploy cycle)

1. `doctype/ec_marketplace_sku_catalog/ec_marketplace_sku_catalog.json` — +10 fields (additive).
2. `doctype/ec_catalogue_sync_run/` — NEW DocType (json + .py minimal).
3. `services/catalogue_sync.py` — `upsert_catalogue_row` writes promoted fields (+ keep note); `last_catalogue_sync_at=now`; RSP precedence unchanged.
4. `services/catalogue_backfill.py` — NEW idempotent backfill (note→fields).
5. `patches/p003_backfill_sku_catalogue_fields.py` + `patches.txt` — run backfill post model-sync.
6. `api_catalogue_sync.py` — `trigger_catalogue_sync(brand)` (perm + lock + cooldown + enqueue + create Run, returns run_id) ; `catalogue_sync_job(brand, run)` (background body, updates Run) ; `catalogue_sync_status(run/brand)` (read). Keep existing preview/confirm or fold confirm into the job.
7. `permissions.py` — `can_run_catalogue_sync`.
8. Tests: `tests/test_catalogue_backfill.py`, `tests/test_catalogue_sync_run.py` (lock/cooldown/dup/resume), extend `test_catalogue_sync.py` (upsert writes fields + RSP guard + platform norm).
9. (no hooks/scheduler change — manual/background trigger only.)

## Migration / deploy / rollback risk

- **Migration:** additive only (10 columns on SKU Catalog + 1 new DocType). `bench migrate` syncs schema then p003 backfills. **Same-turn confirm required** (production migrate). No column drops, no type changes, no PM touch.
- **Risk:** backfill on a large SKU Catalog (measure §C first) — bound batch + commit periodically; fail-open per row. New DocType is empty (no data risk).
- **Rollback:** drop the 10 fields + the DocType = safe (note still holds all data; rsp_price untouched). Backfill is re-runnable. True rollback = pre-migrate backup. Document that dropping fields loses promoted copies but not source (note).

## Tests required

Backfill: populates empty fields from note; **idempotent rerun** (2nd pass no-op); malformed JSON skipped + logged; **never overwrites rsp_price**; never overwrites already-set field; note retained. Upsert: writes promoted fields + keeps note; order-derived RSP never overwritten by catalogue mismatch; platform `shopee_v2→Shopee`; hash-gate idempotent. Run/concurrency: per-brand lock blocks 2nd trigger (returns in-flight run); cooldown blocks within 30 min (returns last run + cooldown_until); KAM own-brand only / Manager+Admin broader; background returns run_id fast; Done Partial resumable; failure → Error + message + lock released. Plus full-suite regression.

## Estimated implementation time

~7–9h: fields+DocType+JSON (1.5h), upsert update (1h), backfill+patch (1.5h), background+lock+cooldown+run+status (2.5h), tests (2h), report+verify (1h). One migration/deploy cycle.

## Decisions needed before coding
- **Q34-1:** promote all 10 fields, or core-6 + keep lineage (catalogue_id/parent_sku/is_variant/price_confidence) in note? (recommend all 10)
- **Q34-2:** keep `confirm_catalogue_sku_sync` (sync) as-is alongside the new background trigger, or replace it with the background path? (recommend: keep preview; replace confirm with background trigger)
- **Q34-3:** cooldown default 30 min OK + Admin override flag to bypass cooldown? (recommend yes)

Wait for approval (Q34-1/2/3 + the §C measured counts) before coding.
