# 67 — Hotfix B: durable failed-order retry — persistence audit + file-level plan

Date: 2026-06-13 · AUDIT for B (A already coded). No B code until this is reviewed.

## Can an existing DocType represent the retry queue? (audit)

Required fields: brand, external order ID, last error, attempt_count, next_retry_at, status (Pending/Processing/Completed/Dead), timestamps.

**`EC Marketplace Order Log`** — has `sync_status`, `sync_error`, `order_key`(UNIQUE = source|external_order_id), brand/platform/shop. **But unsuitable as the retry queue:**
1. A **detail-phase failure never creates an Order Log row** — `get_order_detail` fails *before* `ingest_orders`, which is the only place an Order Log row is upserted (ingestion.py L82). So the failed orders we must queue have **no Order Log row** to mark.
2. To use Order Log we'd have to **insert stub rows** from the list header (only `omisell_order_number` is reliably present; `order_datetime`/`order_status`/`items` come from the detail we failed to fetch). Stub rows with missing data **pollute the canonical order table** and risk being read by the rules engine / dashboards / occurrence rollups as if they were real orders.
3. Order Log lacks `attempt_count`, `next_retry_at`, and a `Dead` terminal — adding them is **a migration anyway**, on top of the pollution risk.

**Other existing doctypes** (`EC Alert`/`EC Alert Action`/`EC Catalogue Sync Run`/`EC Automation Pause`) are semantically different (alerts/cases, stock-lock actions, sync runs, pauses) and would be abused as a queue.

**Verdict:** no existing DocType safely supports the semantics. Reusing Order Log requires new fields **and** stub-row pollution → not safe. Since B inherently needs durable per-order retry state (attempt/Dead/next_retry), a **small new app-owned DocType is the correct, lowest-risk model.** It is a clean additive migration (empty table, no backfill) — comparable to `EC Catalogue Sync Run` we just added.

## Proposed DocType `EC Order Retry` (app-owned, custom=0, SM-only DocPerm)

| field | type | notes |
|---|---|---|
| `brand` | Link Brand Approver | idx |
| `source_system` | Select Omisell/ERP/Manual | default Omisell |
| `order_number` | Data | Omisell external order number; idx |
| `retry_key` | Data **UNIQUE** | `source_system\|brand\|order_number` (idempotent upsert identity) |
| `status` | Select `Pending/Processing/Completed/Dead` | default Pending; idx |
| `attempt_count` | Int | incremented per attempt |
| `max_attempts` | Int | default from site_config (e.g. 5) |
| `last_error` | Small Text | sanitized (no token/credential) |
| `next_retry_at` | Datetime | backoff schedule; idx |
| `first_failed_at` / `last_attempt_at` / `completed_at` | Datetime | timestamps |

autoname `EC-ORT-{######}`. search_index on brand, status, next_retry_at. No remote/Omisell field, no stock.

## Behavior (B spec mapping)

1. **Per transient detail/ingest failure** (inside `pull_orders` order loop): `retry_queue.upsert(brand, order_number, error)` — idempotent by `retry_key`: insert Pending if absent, else bump `attempt_count` + refresh `last_error`/`next_retry_at`/`last_attempt_at`. **Continue** the loop (no `break`). The order is **not** counted as a chunk-fatal failure once it is durably queued.
2. **Checkpoint may advance** only when: all batched orders ingested **and** every failed order was **durably persisted** to the retry queue (the upsert returned success). The current `failed==0` gate is replaced by `unqueued_failures==0` (a failure that was queued no longer blocks).
3. **If retry persistence itself fails** (DB/infra): that order is an *unqueued* failure → chunk stays incomplete → checkpoint holds → **brand breaker increments** (system-level failure).
4. **Retry worker** (new scheduled job, low frequency, gated like the pull): picks `status=Pending AND next_retry_at<=now` (bounded batch), sets `Processing`, calls the EXISTING `pull_one_order(brand, order_number)` (same Order Log upsert dedupe → replay-safe), on success → `Completed` (+completed_at), on failure → bump attempt, set next_retry_at (exponential backoff), and at `attempt_count>=max_attempts` → `Dead` + an `ingestion_api_failed`-style diagnostic alert. Never retries forever.
5. **Successful targeted retry** → `Completed`.
6. **Max attempts** → `Dead` + alert/diagnostic.

## Breaker semantics (revised, per B)

- An **isolated order failure that was successfully queued** must NOT increment `consecutive_failures`. → In `pull_orders`, only count toward the breaker when there are **unqueued** failures.
- **Brand breaker increments** only for system-level failure: list/auth failure after retries (existing), chunk/job exception (existing), **inability to persist a retry item** (new), DB/infra failure.
- Net effect: the LOF death-spiral ends — a transient detail/auth failure on one order is queued, the chunk completes, the checkpoint advances, and the failed order is retried out-of-band; the breaker no longer opens on isolated order hiccups (only on real system faults).

## File-level plan (B — code only after approval)

1. `doctype/ec_order_retry/` — NEW DocType (json + .py + __init__).
2. `services/order_retry.py` — NEW: `upsert(brand, order_number, error, source="Omisell")` (idempotent, returns bool persisted-ok), `claim_due(limit)`, `mark(name, status, error=None)`, `_next_retry_at(attempt)` (backoff), `_max_attempts()` (site_config `ec_alerts_order_retry_max_attempts` default 5). Sanitizes errors.
3. `api_omisell.py` — in `pull_orders`: on detail/ingest failure, call `order_retry.upsert(...)`; track `unqueued_failures`; checkpoint-advance gate uses `unqueued_failures==0 AND not capped AND not timeboxed`; breaker records failure only when `unqueued_failures>0` or list/auth/exception. (cap/timebox unchanged — still hold; that is Hotfix C territory, out of B scope.)
4. `tasks.py` + `hooks.py` — NEW low-frequency scheduled `process_order_retries` job, brand-gated like the pull (and pull-priority: skip a brand whose pull is running). Bounded batch + time budget. (Adds one scheduler entry — flagged as a scheduler change; if you want zero scheduler change, the retry worker can instead be enqueued at the end of each pull run.)
5. `services/order_retry.py` Dead-path → reuse `_ingestion_failure_alert`-style alert.
6. Tests `tests/test_order_retry.py`.

**Migration:** one additive DocType (`EC Order Retry`), empty table, no backfill. Same-turn confirm for `bench migrate`.

**Open decision for you (B-1):** retry worker as a **scheduled job** (needs 1 hooks scheduler entry) vs **enqueued at the end of each pull run** (zero scheduler change). The spec says "retry worker/process" — recommend **enqueue-at-end-of-pull** first (zero scheduler change, simplest, runs exactly when there's likely new work), with a scheduled sweep as a later option.

## Tests required (B, mapped)

8 one failed order durably queued + remaining continue; 9 queued failure does NOT increment breaker; 10 checkpoint advances when all failures queued; 11 retry-persist failure holds checkpoint + increments breaker; 12 duplicate failed order upserts ONE retry item; 13 targeted retry success → Completed; 14 max attempts → Dead + alert; 15 order dedupe intact (pull_one_order replay safe). Regression: FES pull path, LOF capped/timeboxed (unchanged in B), overlap behavior, catalogue/Alert Center unchanged.

## Constraints honored
Reuses `pull_one_order` + Order Log dedupe; no catalogue/case/ToDo/PM/stock/remote-write touch. Await review of the persistence model (new DocType) + B-1 before coding B.

---

## Hotfix A — DONE (coded, this turn)

`services/omisell_client.py`: `AUTH_MAX_ATTEMPTS=3`, `AUTH_BACKOFFS=(1,3)`, `token_ttl_minutes()` (site_config `ec_alerts_omisell_token_ttl_minutes`, default 30); `_authenticate(reason)` retries the auth POST transiently (timeout/conn/429/5xx) via `_request(auth_retry=True)`, NEVER on 400/401/403; sets a fallback expiry when Omisell omits `expired_time`; `_ensure_token` reuses the cached token (2-min margin) and emits token-source diagnostics (`reused_cached`/`refreshed_missing_token`/`refreshed_missing_expiry`/`refreshed_expired`/`fallback_ttl_applied`) — **no token/credential ever logged**. `tests/test_omisell_token.py` **9/9** (cached avoids POST, fallback TTL, reuse, timeout-retry-succeeds, 5xx-retry, 401 no-retry, 400 no-retry, exhaust at 3, no secrets in logs). Not committed/deployed.
