# 64 — Combined Phase 3–4 implementation report

Date: 2026-06-13 · Status: BUILT + sandbox-verified. **NOT committed/deployed. One migration cycle.** Production unchanged.

## 1. Final file list

| File | Change |
|---|---|
| `doctype/ec_marketplace_sku_catalog/ec_marketplace_sku_catalog.json` | **+10 additive fields** (sec_catalogue section) |
| `doctype/ec_catalogue_sync_run/ec_catalogue_sync_run.json` + `.py` + `__init__.py` | **NEW DocType** (run history) |
| `services/catalogue_sync.py` | `promoted_values()` + `PROMOTED_FIELDS`; `upsert_catalogue_row` writes the 10 fields (both branches), keeps note, rsp_price untouched |
| `services/catalogue_backfill.py` | **NEW** idempotent note→fields backfill + deterministic summary |
| `patches/p003_backfill_sku_catalogue_fields.py` + `patches.txt` | **NEW** post-model-sync patch |
| `api_catalogue_sync.py` | preview kept (read-only); **confirm retired**; **NEW** `trigger_catalogue_sync` / `catalogue_sync_job` / `catalogue_sync_status` |
| `permissions.py` | **NEW** `can_run_catalogue_sync` |
| `tests/test_catalogue_backfill.py`, `tests/test_catalogue_promote.py`, `tests/test_catalogue_sync_run.py` | **NEW**; `tests/test_catalogue_sync.py` updated for retired confirm |

## 2. Schema & patch summary

**SKU Catalog +10 (all additive, nullable):** `image_url`(Data 300), `catalogue_price`(Currency), `sale_price`(Currency), `external_stock`(Int), `product_status`(Data, idx), `catalogue_id`(Data), `parent_sku`(Data), `is_variant`(Check), `price_confidence`(Select), `last_catalogue_sync_at`(Datetime, idx). `rsp_price` unchanged (order-derived priority); `note` kept.

**EC Catalogue Sync Run** (app-owned, SM-only DocPerm, autoname EC-CSR-{######}): brand, requested_by, trigger_type(Manual/Scheduled/Backfill), status(Queued/Running/Completed/Partial/Failed/Cancelled), started_at, finished_at, cooldown_until, lock_key, job_id, total/processed_items, inserted/updated/skipped/failed, error_message, summary_json.

**Patch p003** (post_model_sync, after p002): delegates to `catalogue_backfill.run_backfill()`. Idempotent via the `last_catalogue_sync_at` marker — a row already backfilled/synced is counted `already_populated` and skipped. Per-row: parse note JSON (malformed → skip + `log_error`, never fails migrate); fill promoted fields from JSON; **never writes rsp_price**, **never overwrites a populated field**, **never rewrites note**. Deterministic summary `{total_scanned, eligible, backfilled, already_populated, malformed, skipped, failures}` printed + logged (replaces the bench-SQL count gate). `run_backfill(dry_run=1)` is the reusable read-only report helper (no temporary prod endpoint).

## 3. Lock / cooldown / background behavior

- **Per-brand cache lock** `ec_catalogue_sync_running_<brand>` = run name, **TTL 3900s** (> max run budget) → stale lock auto-recovers; also deleted in the worker `finally`.
- **Cooldown** default **30 min** (`ec_alerts_catalogue_cooldown_minutes`); `cooldown_until` stored on the run; new trigger within window → rejected with the last run id + cooldown_until.
- **force=1** = System Manager only; bypasses cooldown **only** — an **active lock always wins** (the lock check has no force exception, returns the in-flight run without enqueueing). Never two jobs per brand.
- **Order-pull priority:** if `ec_alerts_pull_running_<brand>` is set → `trigger` returns `Deferred/order_pull_running` (no run created).
- **Duplicate trigger during active run** → returns `{status: AlreadyRunning, run_id}` (no second enqueue).
- **Worker** `catalogue_sync_job` (queue `long`, not scheduled): Queued→Running, page-streams + upserts (hash-gated idempotent), updates progress live, ends Completed / Partial (cap/timebox) / Failed (exception + error_message); **persists result BEFORE releasing the lock** in `finally`.

## 4. Exact API changes

- `preview_catalogue_sku_sync` — UNCHANGED (read-only, SM-only).
- **RETIRED** `confirm_catalogue_sku_sync` (synchronous write path removed).
- **NEW** `trigger_catalogue_sync(brand, force=0, <cap aliases>)` — POST; gates: permission → force-SM → order-pull → **active lock** → cooldown; creates Run (Queued), takes lock, enqueues worker, returns `{run_id, status, cooldown_until}` immediately.
- **NEW** `catalogue_sync_job(brand, run, params)` — background worker (not whitelisted).
- **NEW** `catalogue_sync_status(run=None, brand=None)` — read; brand-scoped permission.
- `permissions.can_run_catalogue_sync(user, brand)` = kam/manager/leader/supervisor of brand (KAM = own brand; force is is_global_supervisor only).

## 5. Test results (sandbox; per-module — see note)

- **`test_catalogue_backfill` 10/10** — backfills all 10 fields, idempotent rerun, no overwrite of populated, malformed skipped+logged, **rsp_price never written**, note never modified, marker-skip, dry-run, deterministic summary.
- **`test_catalogue_promote` 9/9** — promoted_values maps all 10, rsp_price excluded, status fallback, stock coercion, **platform `shopee_v2→Shopee`**; upsert source-text (3 skip when /tmp truncated).
- **`test_catalogue_sync` OK** (resolve_confirm_params caps/aliases + preview-no-write + RSP-wins + single-doctype-write; 3 source-text skip).
- **`test_catalogue_sync_run` OK** — pure helpers (cooldown/truthy/lock_key) + permission; 12 source-text wiring tests (gate order, active-lock-wins, force, worker states, lock-released-in-finally, order-pull-priority) **skip in sandbox** (OneDrive mount truncates the large api file) and **run on bench**; gate order + invariants independently confirmed via host-truth grep.
- **Regression**: `test_case_lifecycle` 30/30, `test_case_todo` 29/29, `test_case_grouping` 15/15, `test_phase_g1_1` 19/19, `test_rules_pure` 16/16 — Step 1 lifecycle, Step 2 ToDo, order-derived RSP precedence, catalogue preview/search all intact.

Note: each test module installs its own `frappe` stub, so a single combined `run-tests` collides (one stub per process) — modules are verified **individually** in sandbox; the owner's `bench run-tests` uses real frappe (no stubs, no collision, no mount truncation).

## 6. Migration / deploy / rollback

**Migration (additive, non-destructive — requires same-turn confirm):**
```powershell
git -C C:\dev\ecentric_workspace checkout -b feat/phase34-catalogue-promote origin/main
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/doctype/ec_marketplace_sku_catalog/ec_marketplace_sku_catalog.json
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/doctype/ec_catalogue_sync_run/
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/catalogue_sync.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/catalogue_backfill.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_catalogue_sync.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/permissions.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/patches/p003_backfill_sku_catalogue_fields.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/patches.txt
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_catalogue_backfill.py ecentric_workspace/alerts/tests/test_catalogue_promote.py ecentric_workspace/alerts/tests/test_catalogue_sync_run.py ecentric_workspace/alerts/tests/test_catalogue_sync.py
git -C C:\dev\ecentric_workspace commit -m "feat(alerts): Phase 3-4 - promote SKU catalogue fields + backfill + background catalogue sync (run history, lock, cooldown)"
```
Then PR → merge → FC deploy WITH migrate. `bench migrate` syncs the 10 columns + EC Catalogue Sync Run, then p003 backfills (prints the summary). Depends on Step 1 (status enum) being merged; Step 2 independent.

**Verify post-deploy:** p003 summary in the migrate log; `trigger_catalogue_sync(FES-VN)` → run_id fast; poll `catalogue_sync_status`; second immediate trigger → Cooldown/AlreadyRunning; SKU Catalog rows show promoted fields; `bench run-tests --module ...test_catalogue_backfill/...test_catalogue_sync_run`.

**Rollback:** drop the 10 columns + EC Catalogue Sync Run = safe (note retains all source data; rsp_price untouched; backfill re-runnable). The retired confirm endpoint stays retired (no caller). True rollback = pre-migrate backup. Additive migration → reverting code without dropping columns is harmless.

## 8. Gate resolutions (2026-06-13)

### Gate 1 — confirm API contract preserved
`confirm_catalogue_sku_sync(...)` is **kept as a deprecated backward-compatible wrapper**: its body is `return trigger_catalogue_sync(...)` (all alias params forwarded) — it does NOT do any synchronous catalogue write (`upsert_catalogue_row`/`_fetch_page`/`enqueue`/`set_value` absent from its body) and returns the new run response (`run_id` + status). `trigger_catalogue_sync` is the canonical endpoint; the frontend may drop the alias in a later UI phase. **Updated behavior:** existing callers of `confirm` now enqueue exactly one background run, no sync write. (Test `test_confirm_is_deprecated_alias`.)

### Gate 2 — field-level backfill idempotency
The row-level `last_catalogue_sync_at` skip is removed. Each promoted field is inspected independently: an EMPTY (NULL/"") real field is filled from a usable note value; a POPULATED field is preserved (0 is a valid Currency/Int/Check value, never treated as empty → `is_variant=0` default is preserved). A partially populated row is repairable on rerun. `last_catalogue_sync_at` is itself populated from `last_seen_at` but **does not gate other fields**. Malformed note → skip+log; `rsp_price` never touched; `note` never rewritten. **Summary semantics:** `fully_already_populated`, `partially_backfilled`, `newly_backfilled`, `malformed`, `skipped`, `failures` (+ total_scanned, eligible). newly vs partially is keyed on whether the marker was empty before (deterministic; the is_variant-default-0 makes a field-count signal unreliable). **Gate-2 test** `test_04_gate2_marker_set_repairs_only_missing`: marker set + several fields empty → rerun fills only the missing, preserves set, classified partially_backfilled.

### Gate 3 — no Deferred + atomic lock
Gate order: **permission → atomic lock acquire → order-pull-active → cooldown → create Queued run → enqueue.** If the brand's order pull is active: lock released, **no run, no enqueue**, return `OrderPullActive` (a result, not a run status). Sync Run enum unchanged (Queued/Running/Completed/Partial/Failed/Cancelled) — **no `Deferred`** anywhere.
- **Atomic primitive:** `frappe.cache().set(cache.make_key(<lock_key>), token, nx=True, ex=LOCK_TTL)` — Redis `SET key token NX EX` (frappe.cache() is a redis.Redis subclass; make_key adds the site keyspace). Returns truthy iff THIS caller acquired it — no get-then-set TOCTOU.
- **Ownership token:** `frappe.generate_hash(length=24)` per trigger; stored as the lock VALUE (+ in the run's summary_json) and passed to the worker.
- **Release proves single-owner:** Lua compare-and-delete `if redis.call('get',KEYS[1])==ARGV[1] then del`. A worker with a non-matching token cannot delete another's lock (test: wrong token → lock stays held).
- **Stale-lock TTL:** `EX = LOCK_TTL (3900s)` > max run budget → if a worker dies without releasing, Redis auto-expires the key and the brand recovers automatically.
- **Two simultaneous triggers → exactly one enqueue:** the loser's `_acquire_lock` returns False → `AlreadyRunning` (with the active run id) **before** reaching enqueue. (Test `TestAtomicLockBehavior.test_two_acquires_one_wins` + source-text `test_loser_returns_without_enqueue`.)

### Updated test results
`test_catalogue_backfill` **11/11** (field-level, Gate-2 repair, marker-not-gating, rsp untouched, note kept, deterministic summary). `test_catalogue_sync_run` — atomic-acquire behavior + helpers pass; source-text gate-order/atomic/token/confirm-alias/no-Deferred tests **run on bench** (skip in sandbox: OneDrive mount truncates the ~410-line api file; all invariants confirmed via host-truth grep). `test_catalogue_promote` 9/9, `test_catalogue_sync` OK. Regression: lifecycle 30/30, todo 29/29, grouping 15/15, g1_1 19/19, rules 16/16.

### Final file diff (this gate round)
- `api_catalogue_sync.py`: NEW `_acquire_lock`/`_release_lock` (atomic SET NX + Lua compare-del) + `_active_run`; `trigger_catalogue_sync` reordered to perm→acquire→pull→cooldown→run→enqueue with token + lock-release on every early-return/error; `OrderPullActive` replaces `Deferred`; **NEW `confirm_catalogue_sku_sync` deprecated alias**; worker takes `lock_token`, captures token early, releases own lock in finally.
- `services/catalogue_backfill.py`: field-level `run_backfill` + new summary keys; removed row-marker skip.
- `tests/test_catalogue_backfill.py`: rewritten for field-level + Gate-2 test (11). `tests/test_catalogue_sync_run.py`: Gate-1 alias + Gate-3 atomic/order/token tests + `TestAtomicLockBehavior`.

## 7. Production unchanged
No deploy, no migrate, no PUT/POST to the site, no scheduler/hooks/tasks/order-pull/PM change, no Omisell/stock write. Local files pending owner branch+commit+PR+deploy.
