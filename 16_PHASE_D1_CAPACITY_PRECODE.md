# Alert Center — Phase D.1 Capacity Hardening Pre-code Report

Date: 2026-06-09 · Status: **PRE-CODE — nothing implemented.** Gate before enabling any scheduler or multi-brand sync. **Still 100% read-only: no Omisell write path, stock/buffer write stays locked by DS1, scheduler kill switch stays ON, no PM files, no unrelated UI.**

Volume assumption (yours): ~100K orders/month → EC Marketplace Order Item 200–300K rows/month, **several million rows/year**; EC Alert grows much slower (only violations + daily-deduped missing_* alerts).

## 1. Index review — current state vs required

Current DB indexes (from Phase B JSONs + Frappe defaults): unique `order_key` (Log), unique `dedupe_key` (Alert/Action), unique `omisell_shop_id`/`shop_code` (Shop), child-table `parent`, standard `modified`/`creation`. **No index today on brand, platform, order_datetime, seller_sku, sync_status** — fine at pilot size, not at millions of rows.

Required (your list, mapped to mechanism — all additive):

| Table | Index | How |
|---|---|---|
| EC Marketplace Order Log | `brand`, `order_datetime`, `sync_status`, `omisell_shop_id`, `external_order_id`, `platform` | `search_index: 1` in DocType JSON (single-column, applied by migrate) |
| EC Marketplace Order Log | **composite `(brand, order_datetime)`** — the baseline-median scan key | idempotent patch via `frappe.db.add_index` (patches.txt entry) |
| EC Marketplace Order Item | `seller_sku`, `item`, `external_line_id` | `search_index: 1` |
| EC Marketplace Order Item | composite `(seller_sku, parent)` optional — evaluate EXPLAIN after single-column lands | patch (deferred unless needed) |
| EC Alert (related, /alerts perf) | `detected_at`, `owner_user` single + composite `(brand, status, detected_at)` | search_index + patch |

The hot query is baseline §C: `JOIN Item ON parent WHERE Log.brand=? AND order_datetime>=30d AND Item.seller_sku=?` → `(brand, order_datetime)` + `seller_sku` turns a table scan into a tight range read.

## 2. Batch size & pagination

Keep API `page_size=50` (raise to 100 only if T-tests confirm the API honors it). New per-cycle caps: `MAX_DETAILS_PER_RUN` ≈ 300 (config-tunable) — a run that hits the cap stops cleanly and the next cycle continues from the overlap window. Insert path stays per-doc (audit/track_changes) — at 100K/month (~2.3/min average) this is comfortably within Frappe write capacity; bulk-insert only if measured otherwise.

## 3. Scheduler cadence recommendation

100K/month ≈ 140 orders/hour average, assume 10× peak ≈ 1,400/hour. **Recommend `*/15 min` per pilot brand**, each run pulling successive ≤1h chunks from `last_sync_at` until caught up or caps hit. Per-run math: 35 orders avg (peak 350) → ≈40 (peak ~360) API calls → 1–6 min at ≤1 req/s — fits the cycle with margin. Backfill/catch-up after downtime happens naturally in bounded chunks (no thundering herd).

## 4. Per-brand sync isolation

One scheduler job iterates Active+enabled BIS records **serially** (MVP), each brand in its own try/except with its own `last_sync_at` and chunk budget — one brand failing or rate-limited never blocks others. When >3 brands sync, move to `frappe.enqueue` one job per brand (queue=long) with stagger offsets — design ready, not built until needed.

## 5. Rate-limit budget (official: bucket 100, leak 100/min, per shop)

Client already paces ≤1 req/s + watches `X-Omisell-Api-Call-Limit` + backs off on 429. Budget at scale: 15-min cycle per brand needs ≤360 calls peak ≈ 0.4 req/s sustained — ¼ of the leak rate. Docs say the bucket is tracked "for a particular shop" ⚠️TC — if per-shop, multi-brand parallelism is even safer; we keep the global ≤1 req/s pacing regardless.

## 6. Overlap window strategy

Keep 10-minute overlap on every chunk (re-fetched orders are no-ops via order_key + payload hash). Add a **nightly reconciliation sweep** (optional, same read-only code path): re-pull the previous 24h once per night to catch updates that arrived later than the overlap — this is the cheap insurance against missed `updated_time` edge cases. Both windows are chunked and capped like normal runs.

## 7. Error / retry strategy at volume

Existing: per-order isolation, bounded HTTP retries, `last_sync_at` only on full success, daily-deduped `ingestion_api_failed` / `missing_integration_credential` alerts. Add for volume: (a) **chunk-level checkpointing** — advance `last_sync_at` per fully-successful chunk, not per whole run, so one bad order doesn't force re-pulling hours of backlog; (b) **circuit breaker** — N consecutive failed cycles for a brand (default 3) → stop attempting that brand until the daily alert is handled (state on BIS, e.g. `consecutive_failures` Int — small additive field); (c) `frappe.log_error` throttling (one detailed log per brand per cycle, counters in the summary) to keep Error Log usable.

## 8. Retention / archive plan (Order Log + Item only — alerts/actions are audit, never deleted)

Hot window needed by the engine = **30 days** (baseline median). Proposal: keep 6 months hot; after that, monthly archive job exports rows >6 months to compressed JSON files (private Files/object storage) then deletes them **only with your explicit approval per run** (consistent with the no-hard-delete rule — this is the one documented exception, log-type data, export-first). Defer activation until the table passes ~2M rows; D.1 only ships the *measurement* (row-count in a weekly digest/log) so the decision is data-driven. Native partitioning isn't available in Frappe — archive-and-delete is the practical path.

## 9. Alert-first operational model (confirmed as the design)

KAM never works raw orders: `/alerts` reads EC Alert only (small, indexed); EC Marketplace Order Log/Item stay SM-only audit storage. OK lines create zero alert rows, so KAM-facing data volume ≈ violations only. The "Open Source Order" drawer link opens a single doc by name (PK lookup — O(1) regardless of table size).

## 10. Query performance risks — Desk List View & /alerts

- Desk Order Log list (SM only): default `modified desc` sort is indexed — fine; risk = ad-hoc `%LIKE%` searches on unindexed Data fields at millions of rows → §1 indexes cover the realistic filters (brand/status/date/order id).
- `/alerts` `get_cards`: currently counts via `len(get_all(..., limit_page_length=0))` — pulls names into memory. **D.1 change: switch to `frappe.db.count` / COUNT(*) queries** (same results, constant memory). `list_alerts` already paginates (≤100/page) and gains the EC Alert composite index.
- Baseline median: indexed by §1; if EXPLAIN still shows pain past ~3M item rows → §11.

## 11. Summary / materialized tables — later, criteria defined now

Not in D.1. Trigger criteria: baseline query p95 > 500 ms or item table > 5M rows. Then: nightly-refreshed `EC SKU Price Baseline` summary table (brand+platform+shop+sku → 30d median, n, confidence), engine reads it with live-query fallback. Designed, deferred.

## 12. Rollback / kill switch

Unchanged layers: global `ec_alerts_scheduler_disabled` (covers the future pull job too — it will check the same switch), per-brand BIS `enabled=0`, revert-PR. New in D.1: pull job gets its own additional conf flag `ec_alerts_pull_disabled` so you can stop ingestion without touching the (separately gated) pause-expiry/queue jobs. Index rollback: `frappe.db` drop-index patch (data untouched). Archive job (if ever enabled) is approval-gated per run.

## 13. Read-only confirmation

Phase D.1 contains: indexes, counters/caps, checkpointing, circuit breaker, COUNT-based cards, measurement hooks, and (separately approved at the end) one narrow scheduler entry for ONE pilot brand. It contains **no Omisell write path, no stock/buffer code, no change to ALLOWED_METHODS={GET}**, and the DS1 gate stays locked.

## Implementation candidates for the D.1 build (when approved)

1. JSON `search_index` edits (≈10 fields) + 1 idempotent index patch (first `patches.txt` entry for the alerts module) — needs migrate.
2. `get_cards` COUNT refactor (small, no behavior change).
3. Pull-job hardening in `api_omisell`/new `tasks` function: chunking + checkpoint + circuit breaker + caps (manual-callable first; scheduler entry LAST, separately confirmed, single pilot brand, behind both kill switches).
4. Row-count measurement log (weekly).
Decisions for you at approval: hot/archive thresholds (§8), cadence (§3, propose */15), whether nightly reconciliation ships in D.1 or D.2.
