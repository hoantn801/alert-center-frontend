# 68 — Hotfix B REVISED plan + schema (Frappe-native architecture correction)

Date: 2026-06-13 · Updates doc 67 per the 7 binding corrections. **Schema updated now; dispatcher/worker/Dead-notify/manual-service to be coded after this plan is reviewed.** Prior bindings (durable-queue-before-checkpoint, queued≠breaker, auth/list/system=breaker, reuse pull_one_order, dedupe intact, cap/timebox untouched) all hold.

## What is ALREADY coded and STILL valid (keep)
- `EC Order Retry` DocType (now `track_changes=1`, +`processing_started_at`, +`trigger_source`).
- `services/order_retry.upsert()` — idempotent, no same-cycle attempt double-count, sanitized bounded error, terminal→restart. ✓
- `services/order_retry._claim()` atomic conditional UPDATE + token, `recover_stale()`. ✓ (needs +processing_started_at + Redis brand lock).
- `api_omisell.pull_orders` — durable-queue + `unqueued_failures` checkpoint/breaker gate. ✓ (binding unchanged).
- token Hotfix A. ✓ 9/9.

## To REVISE / ADD per correction

### 1. Lightweight scheduler → dispatcher → per-brand worker
- `hooks.py` cron `*/10` calls `tasks.dispatch_order_retries` which ONLY `frappe.enqueue("…retry_dispatcher_job")` and returns fast. (Replace the current inline `process_order_retries` in the cron.)
- `retry_dispatcher_job()` (background): `claim/peek` due items (oldest `next_retry_at` first), **group by brand**, and for each brand with due items + no active brand-worker, `frappe.enqueue("…retry_brand_worker_job", brand=…, batch=small)`. Honors a total time budget; leftover brands wait for the next cycle. **Does not process orders itself.**
- `retry_brand_worker_job(brand)`: **max ONE active worker per brand** (Redis brand lock, §2). Claims a small batch (default 20) for that brand, processes each via `pull_one_order`, releases lock in finally. Per-item time budget so a brand can't monopolize.

### 2. Concurrency + ownership (Redis + DB)
- DocType fields added: `processing_token`, `processing_started_at`, `trigger_source`. DB status = audit source of truth.
- **Per-claim ownership:** `_claim(name, token)` sets `status=Processing, processing_token=token, processing_started_at=now` atomically (conditional UPDATE WHERE status='Pending'); re-read token confirms ownership. A worker only `mark_completed/mark_retry/release` if `processing_token` still equals its token (token-checked transitions).
- **Per-brand Redis lock:** `retry_brand_worker_job` acquires `frappe.cache().set(make_key("ec_order_retry_brand_<brand>"), token, nx=True, ex=TTL)` (atomic SET NX EX, same primitive as catalogue sync); skips the brand if held → "max one worker per brand". Release via Lua compare-del in finally.
- **Stale recovery (30 min default):** `recover_stale()` reverts `Processing → Pending` only where `processing_started_at < now − threshold` (use the new field, not last_attempt_at); never steals a genuinely-running item (its processing_started_at is recent + the brand lock is held).

### 3. State machine (controller-enforced)
`ec_order_retry.py` controller `validate()` allows ONLY: `Pending→Processing`, `Processing→Completed`, `Processing→Pending`, `Processing→Dead`, and `*→Pending` via stale recovery. **Forbids** `Completed→Processing`, `Dead→Processing` automatically (a generic form/API edit attempting these throws). The pull-failure `upsert` terminal→Pending restart is an explicit re-failure event (new cycle), allowed via the service (not a worker transition).

### 4. Dispatcher behavior
batch default **20** (`ec_alerts_order_retry_batch_size`), configurable; group by brand; **≤1 worker/brand**; oldest `next_retry_at` first; total dispatcher time budget **5–8 min** (`ec_alerts_order_retry_dispatch_budget_seconds`, default 360); leftover → next cycle; never mass-enqueue many items of one brand (the per-brand worker drains a small bounded batch with ~1s Omisell pacing, so token/API isn't spammed).

### 5. Dead item → actionable (not just Error Log)
On `Dead`, `order_retry._on_dead(doc)`:
- create a **Frappe Notification Log** (`for_user` = brand KAM owner via `brand_resolver.resolve_owner`, else System Manager) AND/OR a **ToDo** (reference_type="EC Order Retry", reference_name=doc.name, allocated to the same user) — reuse the Step-2 `assign_to.add` contract.
- **dedupe:** at most one open Notification/ToDo per retry item (check existing open ToDo with reference_name=doc.name before creating).
- content: brand, order_number, attempt_count, sanitized last_error. **No token/credential.**
- keep the Error Log too (diagnostic).

### 6. Manual-action service boundary (no UI this phase)
`api_order_retry.py` service-layer endpoints (SM/Manager-perm, audited) designed now, thin:
- `retry_now(name)` — force `next_retry_at=now` on a Pending item (Manager/SM).
- `requeue(name)` — Completed/Dead → Pending (new cycle), reset attempt_count; **the ONLY sanctioned path out of a terminal state**, permissioned + audited (trigger_source="Manual").
- `mark_dead(name, reason)` — Pending/Processing → Dead (SM).
- `get_retry(name)` — view item + linked Order Log / last_error.
Generic form/API status edits are blocked by the §3 controller guard; these endpoints set `trigger_source="Manual"` and rely on track_changes for audit.

### 7. Frappe-native checklist
app-owned DocType JSON ✓; `track_changes=1` ✓; System-Manager-only DocPerm ✓; background jobs via `frappe.enqueue` ✓; scheduler hook = dispatch-only ✓; Dead → Notification Log/ToDo ✓; no custom scheduler loop (dispatcher enqueues, workers are rq jobs) ✓.

## Revised file list
- `doctype/ec_order_retry/` json (+2 fields, track_changes) + .py (state-machine `validate` guard) + __init__.
- `services/order_retry.py` — `_claim` sets processing_started_at; token-checked transitions; `recover_stale` uses processing_started_at; `_on_dead` Notification/ToDo (dedupe); restart-on-refailure (have).
- `services/retry_locks.py` (or inline) — per-brand Redis acquire/release (reuse catalogue-sync primitive).
- `api_order_retry.py` — NEW manual-action service endpoints (retry_now/requeue/mark_dead/get_retry) + perms.
- `tasks.py` — `dispatch_order_retries` (cron, enqueue-only), `retry_dispatcher_job` (group-by-brand, budget, enqueue per-brand), `retry_brand_worker_job` (brand lock, small batch, pull_one_order). (Replaces the inline worker.)
- `hooks.py` — cron `*/10` → `dispatch_order_retries` (dispatch-only).
- `api_omisell.pull_orders` — unchanged from current (sets trigger_source="Pull Failure" in upsert).
- `permissions.py` — `can_manage_order_retry` (SM/Manager) for manual actions.
- tests `test_order_retry.py` — extend: dispatcher groups+enqueues (not inline), per-brand single worker, token-checked transition, stale uses processing_started_at, state-machine forbids Completed/Dead→Processing, Dead creates deduped Notification/ToDo, manual endpoints permissioned.

## Migration / rollback
One additive DocType (now with 2 extra fields), empty table, no backfill. `track_changes=1` adds a Version trail (no migration cost beyond schema). Rollback = drop DocType (no other table affected); the pull/breaker changes revert with code. Same-turn confirm for `bench migrate`.

## Decision for you
Confirm this revised architecture (dispatcher → per-brand worker + Redis brand lock + state-machine guard + Dead→Notification/ToDo + manual-service boundary). On confirm I code the revised tasks/dispatcher/worker, `_on_dead`, `api_order_retry`, controller guard, and the added tests. **No commit/deploy.**
