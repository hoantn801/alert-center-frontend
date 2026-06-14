# Alert Center — Phase D Pre-code Report (Read-only Omisell Ingestion)

Date: 2026-06-08 · Status: **APPROVED 2026-06-08 with decisions Q-D1/2/3/5/6 resolved, Q-D4 deferred — see `13_PHASE_D_PLAN.md` §0 for the binding record.**

**Q-D2 FINAL (business decision 2026-06-10) — "PRICE-RISK / CUSTOMER-CHECKOUT statuses", not "real sales".** Rationale: Alert Center is price compliance — if a customer could place an order at a price, the exposure already happened, even if the order is later cancelled; brands check final customer-paid price after platform vouchers. Production allowlist (FC Site Config): `ec_alerts_omisell_allowed_status_ids = [250, 300, 400, 460, 500, 600, 702, 900]` (250 Chờ xác nhận · 300 Đã duyệt · 400 Đã tạo vận đơn · 460 Sẵn sàng giao · 500 Đã bàn giao · 600 Đang giao · **702 Huỷ bởi đối tác — included, exposure already happened** · 900 Giao thành công). Excluded: draft / unpaid / payment-failed / invalid / pre-creation failures. Function name `is_real_sale` kept for API stability; semantics documented in `omisell_normalizer.py` (commit `d841400`). Based on the **official Omisell developer portal** (developers.omisell.com, pages last modified 2026-01..2026-05 — current). Items marked ⚠️TC = to confirm against the real account during the §10 manual test.

Scope per your directive: **GET/read-only only** (+ auth/token request). Forbidden and absent from this design: inventory/buffer/stock adjust, delist, product update, order update/cancel, webhook registration, anything that mutates Omisell data. (The portal's `Adjust Stock`/`Delisted Stock`/`Update/Cancel Order` endpoints exist — we will **never** call them in Phase D; see §12.)

## 1. Omisell API endpoints to be used (base: `https://api.omisell.com`)

| Purpose | Endpoint | Method |
|---|---|---|
| Token exchange / refresh | Authentication flow per docs (exact path ⚠️TC — the doc page shows flow + response but the request line renders only in the portal UI) | POST (allowed: auth only) |
| Shop list (mapping bootstrap) | `/api/v2/public/shop/list?page=&page_size=&is_active=1` | GET |
| Order list (incremental pull) | `/api/v2/public/order/list?page=&page_size=&updated_from=&updated_to=&shop_id=&status_group=all` (unix-timestamp filters; also `external_created_from/to`) | GET |
| Order detail (line items + prices) | `/api/v2/public/order/{omisell_order_number}` | GET |
| Product detail by SKU (only if needed for mapping) | `/api/v2/public/...product...by SKU` (docs: "Get Product Detail by SKU") — **deferred unless pilot shows we need it** | GET |

Order list returns only headers (order_number, omisell_order_number, status_id/name, created/updated_time) → **detail call per order** is required for line items. Cost: 1 list page + N detail calls per window (rate-limit math §7).

## 2. Auth mechanism (official)

Token-based. Seller creates an **API key** in app.omisell.com → API Integrated API Tool (per-seller = per our brand, fits `EC Brand Integration Settings`). The key is exchanged for `{token, expired_time, refresh_token, refresh_expired_time}`; requests carry `Authorization: Omi <token>` + `Content-Type: application/json` (Partner-key mode would add `Seller-ID`/`Country` headers — not our MVP mode ⚠️TC which mode your account uses; `Account <account_key>` exists for multi-business). **Token expires ~daily → client must refresh via refresh_token before expiry.** Storage mapping (existing BIS fields, no schema change): `api_key` = the Omisell API key; `token` = cached current access token (+ we may need a `token_expired_at` Datetime — small additive field, decision Q-D6); refresh handled inside `omisell_client.py` with re-auth fallback. HTTPS only (docs mandate).

## 3. Request/response field map (from official Get Order Detail schema)

Key response fields we consume: `shop_id`, `shop_name`, `platform`/`platform_name`, `order_number` (platform's), `omisell_order_number` (canonical), `status_id`/`status_name`, `created_time`/`updated_time` (unix), `parcels[].catalogue_items[]` = {catalogue_sku, product_name, quantity, original_price, discounted_price, discount_seller, discount_platform, voucher_seller, voucher_platform}, `parcels[].inventory_items[]` = {inventory_sku, sale_price, ...}, `payment_information[].transaction_amount` (order-level), `seller_discount_amount`. Envelope: `{data, error, error_code, messages}` — `error:true` handling in §8.

## 4. Normalization mapping → EC Marketplace Order Log / Item

| Ours | Omisell | Note |
|---|---|---|
| source_system | `"Omisell"` | |
| external_order_id | `omisell_order_number` | canonical + unique across platforms → order_key dedupe unchanged |
| platform | `platform`/`platform_name` mapped → Shopee/Lazada/TikTok/Other | mapping table in normalizer |
| omisell_shop_id | `shop_id` | feeds shop→brand resolution |
| order_datetime | `created_time` unix → site TZ datetime | |
| order_status | `status_name` (keep `status_id` inside it: "12 - Delivered" form ⚠️TC) | drives Q-D2 real-sale filter |
| items[] | flatten `parcels[].catalogue_items[]` | one row per (parcel, catalogue_sku) |
| └ external_line_id | `{parcel_index or package_number}:{catalogue_sku}` | Omisell has no explicit line id → deterministic synthetic id (stable across re-pulls ⚠️TC) |
| └ seller_sku | `catalogue_sku` | policy lookup key |
| └ external_product_id | — (not present in catalogue_items) | stays empty for Omisell pulls; C1 keys use the non-EPID form |
| └ quantity | `quantity` | |
| └ list_price | `original_price` | |
| └ unit_check_price | `discounted_price` (treated as the payload unit price → pricing rule A path 2) | ⚠️TC unit-vs-line semantics + whether it's net of platform subsidy → **Q-D5** |
| └ seller_discount | `discount_seller + voucher_seller` | |
| └ platform_discount | `discount_platform + voucher_platform` | intentionally NOT subtracted by pricing rule A |
| └ customer_paid_price | left empty for Omisell source (order-level `transaction_amount` is not per-line) | rule A falls to path 2 above |

Golden-file tests pin this mapping against real sample payloads captured in §10.

## 5. Shop → brand resolution

Unchanged from live code: `omisell_shop_id` → `EC Marketplace Shop` (Active) → brand; unresolved → `missing_brand_mapping` Warning (C1 daily key), no policy check, no action. **New helper:** SM-only endpoint `sync_shop_directory(brand)` calling Get Shop List → returns Omisell's shops vs our EC Marketplace Shop rows (report-only, NO auto-create) so you/KAM map shops before the pilot. Data precondition: EC Marketplace Shop rows filled for the pilot brand's real shop_ids.

## 6. Idempotency & dedupe

All existing layers apply unchanged: order_key unique (`Omisell|{omisell_order_number}`), payload-hash skip/update, alert keys (C1/C2/C3), action keys, unique DB indexes as race backstop. Incremental pull uses `updated_from/updated_to` with a **10-minute overlap window** against `BIS.last_sync_at` — overlap re-fetches are no-ops by design. Updated orders (status change) → hash differs → items rewritten + re-checked → same line/rule keys still dedupe alerts.

## 7. Rate limit / pagination (official: leaky bucket, size 100, leak 100/min, header `X-Omisell-Api-Call-Limit: n/100`, 429 on overflow)

Client budget: **≤1 req/sec sustained** (¼ of capacity), read `X-Omisell-Api-Call-Limit` and sleep when >70/100; on 429 → exponential backoff (30s, 60s, 120s; max 3) then defer to next cycle. Pagination: `page`/`page_size` (+ `next`/`previous` links, `count`) — follow `next` until null; cap pages per cycle (default 20 ⇒ ≤ ~400 orders/cycle headroom incl. detail calls); leftovers roll to next cycle via the overlap window. Detail-call fan-out is the real cost: a 100-order window ≈ 1 list + 100 details ≈ under 2 minutes at 1 req/s.

## 8. Error handling & retry

Envelope `error:true`/`error_code` → mapped per Common Errors doc: auth/401-class → one re-auth attempt (refresh, then full re-login) → still failing → BIS `credential_status=Expired` + daily `missing_integration_credential` alert (C3 key) → brand skipped; 429 → backoff (§7), never alert-spam; 5xx/timeouts → 3 bounded retries → mark window failed (`last_sync_at` NOT advanced ⇒ auto-retry next cycle) + `frappe.log_error`; per-order detail failure → that order logged + skipped, others continue; per-brand isolation (one brand's failure never blocks others). `last_sync_at` advances **only** after the window fully succeeds.

## 9. Per-brand credential security

Existing D2/BIS rules: Password fieldtypes (encrypted at rest), `get_password()` decryption only inside `omisell_client.py`, never logged (responses logged only after a `_sanitize()` strips Authorization/token fields), never serialized into alerts/actions/sync_error, no frontend path exists, SM-only DocPerm. Tokens cached per brand in BIS (server-side only). No cross-brand reuse — client takes a single BIS record per call.

## 10. Dry-run test plan (narrow + manual first — NO scheduler)

1. **T0 — auth probe:** SM-only endpoint `omisell_probe(brand)` → token exchange + `GET shop/list page_size=1` → returns sanitized status only. Proves credential + headers + envelope parsing. Zero data written.
2. **T1 — shop directory:** `sync_shop_directory(pilot_brand)` → map real shop_ids into EC Marketplace Shop (you approve the mapping; manual entry).
3. **T2 — single order:** `pull_one_order(brand, omisell_order_number)` with a specific known order you pick → normalize → ingest → verify Order Log/Items/alerts vs the Omisell UI numbers. Capture payload as golden file (sanitized) for unit tests.
4. **T3 — narrow window:** `pull_orders(brand, updated_from, updated_to)` limited to a **1-hour range** you choose → verify counts vs Omisell UI, idempotent re-run (0 new docs), rate-limit header observed.
5. Only after T0–T3 pass + your approval → discuss scheduler-based continuous pull (cadence Q-D1) as a separate enablement (and it still sits behind the existing kill switch).
All T-endpoints: `@frappe.whitelist(methods=["POST"])` + `frappe.only_for("System Manager")` — same pattern as mock ingestion.

## 11. Deploy / rollback

Deploy: branch `alerts-phase-d` → local validation (golden-file unit tests for normalizer/client with stubbed HTTP — no real calls in tests) → implementation report → your approval → push from Windows → PR (files-changed gate) → FC deploy. **No migrate needed unless Q-D6 token field approved (then 1 additive field).** No scheduler entry in the initial Phase D deploy (manual T0–T3 first). Batched into same deploy: DS1 audit fields + Dry Run terminology fix (already approved direction). Rollback: revert PR; BIS `enabled=0` kills a brand instantly; no Omisell-side state exists to undo (read-only); ingested orders/alerts stay for audit.

## 12. Explicit no-write confirmation

Phase D's `omisell_client.py` will contain **only**: the auth/token POST and GET methods for shop list / order list / order detail (+ product-by-SKU if later needed). Enforced four ways: (1) module-level `ALLOWED_METHODS = {"GET"}` + auth-endpoint allowlist checked in the single `_request()` chokepoint — any other verb/path raises immediately; (2) no function for stock/product/order mutation exists in the codebase; (3) unit test asserts the module exposes no write verbs and `_request` rejects POST-to-non-auth; (4) pre-merge grep gate in the deploy checklist (like Phase C/E §0). Stock buffer write remains locked by DS1 (checklist items 10–12d unanswered — note: the portal's `Adjust Stock` schema will be the input for that future gate discussion, but it is out of Phase D entirely).

## Decisions needed before implementation plan

- **Q-D1:** pilot brand + (post-T3) pull cadence. Proposal: 1 brand, manual only in Phase D; cadence decided at scheduler-enable gate.
- **Q-D2:** which `status_id`s count as "real sale" for checks/baseline (extract list from Status-overview doc + your business call at T2/T3 — propose: include from "Ready to ship"/paid onward, exclude cancelled/returned).
- **Q-D3:** failure rule_code: add `ingestion_api_failed` Select value (additive) vs reuse `stock_lock_api_failed` (misleading). Propose: add value.
- **Q-D5:** price to check for Omisell lines: `discounted_price` as-is (customer-facing, per original spec intent) — confirm unit semantics + platform-subsidy treatment with golden files at T2.
- **Q-D6:** add `token_expired_at` (Datetime, BIS) for token caching — additive, recommend yes.
- **Q-D4 (carried):** sidebar nav item in same deploy?

Sources: [Omisell Authentication](https://developers.omisell.com/doc-400887) · [Get Order List](https://developers.omisell.com/api-5173039) · [Get Order Detail](https://developers.omisell.com/api-5183983) · [Get Shop List](https://developers.omisell.com/api-5380269) · [API Rate Limits](https://developers.omisell.com/doc-968943) · [Introduction/portal index](https://developers.omisell.com/doc-394461)
