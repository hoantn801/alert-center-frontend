# Omisell API — Requirement Checklist (to request from Omisell)

Date: 2026-06-06 · Purpose: information we need from Omisell before enabling real order sync + Stock Safety Lock execution in the ERP Alert Center. Until ALL of §1–§2 and the relevant parts of §3 are confirmed, the system runs **mock ingestion + Dry Run only** (no real API calls).

## 1. Orders (read-only) — needed for Phase D real ingestion

| # | Item | What we need exactly | Why we need it |
|---|---|---|---|
| 1 | Order list API | Endpoint, method, pagination, filter by updated/created time range, filter by shop | Periodic incremental pull of recent orders |
| 2 | Order detail API | Endpoint + whether line items are included in list response or require detail call | Per-line price checking |
| 3 | Auth format | API key header? Bearer token? Token refresh/expiry? Per-account or per-shop credentials? | Per-brand credential storage design (`EC Brand Integration Settings`: api_key vs api_secret vs token) |
| 4 | Shop/store ID field | Field name + stability (does it ever change?) + where to see the list of shop IDs per account | Shop → Brand mapping (`EC Marketplace Shop.omisell_shop_id`) — keystone of brand resolution |
| 5 | Brand/shop identifier | Any brand/owner grouping field in payload, if exists | Secondary brand resolution check |
| 6 | Seller SKU field | Field name at line level; is it always present; uniqueness scope (per shop? per account?) | Primary SKU identity for policy lookup |
| 7 | Product/listing ID | Marketplace product ID + Omisell internal product/variant ID at line level | Needed later to target the right listing for stock update |
| 8 | Quantity + final paid amount | Field names for: quantity, list price, seller discount, platform discount, **customer-paid line amount** | `unit_check_price` computation (customer_paid / qty) |
| 9 | Discount/voucher breakdown | Whether seller-funded vs platform-funded discounts are separable | Avoid false alarms when platform subsidizes price |

## 2. Stock (write) — needed before any real Stock Safety Lock

[UPDATED 2026-06-08, decision DS1 — see `11_STOCK_LOCK_BUFFER_DESIGN.md`. Lock mechanism = **buffer stock only**: never off listing, never set actual/physical stock to 0, never overwrite real stock. Available = actual − buffer; locking = set/increase buffer to the sellable quantity.]

| # | Item | What we need exactly | Why |
|---|---|---|---|
| 10 | Stock read | Read **actual stock, available stock, and buffer stock** by SKU / warehouse / pickup_id | Audit fields before locking (actual/available/buffer_before) |
| 11 | Buffer stock update | Endpoint to update **buffer stock specifically** (not general stock overwrite); request/response format; sync or async | The actual Safety Lock: buffer → sellable qty ⇒ available 0, physical unchanged |
| 12 | Update semantics | Is the buffer update an **absolute set or a delta adjustment**? | Fixes the release strategy (restore previous buffer vs reduce by locked_quantity) |
| 12b | Update granularity | Per warehouse / pickup_id? per shop? per SKU? Does one update propagate to all linked listings? | Lock blast-radius + release logic |
| 12c | Sample payloads | Real request/response for buffer stock update incl. error cases | Implementation + retry design |
| 12d | Safe testing | Sandbox env or a designated safe test SKU | Verify lock/release end-to-end before any real brand |

## 3. Operational

| # | Item | What we need |
|---|---|---|
| 13 | Rate limits | Requests/min per endpoint + burst rules + throttling response code |
| 14 | Sandbox | Test environment / test account availability |
| 15 | Sample payloads | Real sample JSON for: order list, order detail, stock query, stock update (request + response + error cases) |

## Extra (nice to have)

- Webhook support for new/updated orders (would replace polling).
- Error code catalogue + idempotency behavior of stock update (safe to retry?).
- Order status lifecycle values (which statuses mean "real sale" vs cancelled/test).

## Gate

Real stock-lock execution is enabled per brand only after: items 3, 10, 11, 12, 12b, 12c, 12d, 15 confirmed → verified in sandbox / on the safe test SKU → user flips `dry_run_stock_lock = 0` on that brand's `EC Brand Integration Settings` (explicit per-brand decision, never global default). Real **order ingestion** (§1) may be enabled separately and earlier — it does not unlock stock writes.
