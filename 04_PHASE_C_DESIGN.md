# Alert Center — Phase C Pre-code Design Note

Date: 2026-06-07 · Status: **DESIGN ONLY — no app code touched, nothing committed.** Phase C implementation starts only after Phase B production verification passes AND separate Phase C approval.

## 0. Approved Phase C decisions (user, 2026-06-07) — BINDING

**C1 — Master-data alert dedupe = daily SKU-level** (missing_policy / missing_brand_mapping are master-data issues; one actionable alert per brand/shop/SKU/day, no order-line flood):
- `missing_policy`: `omisell|{brand}|{platform}|{shop}|{seller_sku}|missing_policy|{YYYYMMDD}` — if `external_product_id` exists, prefer `omisell|{brand}|{platform}|{shop}|{external_product_id}|{seller_sku}|missing_policy|{YYYYMMDD}`
- `missing_brand_mapping`: `omisell|{platform}|{shop}|{seller_sku}|missing_brand_mapping|{YYYYMMDD}` — if `external_product_id` exists, prefer `omisell|{platform}|{shop}|{external_product_id}|{seller_sku}|missing_brand_mapping|{YYYYMMDD}`
- Transaction-level price incidents (`below_min`, `severe_price_drop`, `possible_missing_zero`) keep order-line dedupe: `omisell|{external_order_id}|{external_line_id}|price|{rule_code}`

**C3 — missing_integration_credential dedupe (approved 2026-06-07):** `omisell|{brand}|missing_integration_credential|{YYYYMMDD}` — credential is brand-scoped in MVP, so one alert per brand per day; extend key with platform later if credentials become platform-scoped. (Implemented as `dedupe_keys.missing_credential_key`.)

**C2 — Priority-based single alert per line.** Rule priority: 1 `possible_missing_zero` → 2 `severe_price_drop` → 3 `below_min` → 4 `above_high` → 5 OK. Highest-priority matching rule wins; lower matches create NO second alert; `recommended_action` follows the winning rule only. Action matrix unchanged: missing_zero / severe_drop → Critical + optional lock (enabled + High/Medium confidence + no pause); below_min → Critical only; above_high → Warning only; missing_policy / missing_brand_mapping → Warning only, C1 dedupe.

---

## 1. Scope

Phase C = the brains: price-check services, rules engine, dedupe, alert/action creation, dry-run action worker. Out: ingestion endpoint (D), frontend (E), real Omisell calls (post-checklist gate). All writes by these services target the 8 Phase B DocTypes only.

## 2. Proposed service modules (to be created in Phase C, under `ecentric_workspace/alerts/`)

| File | Responsibility | Key functions (pure where possible) |
|---|---|---|
| `services/pricing.py` | Rule A — isolated price extraction | `compute_unit_check_price(line) -> (price, source_tag)`: customer_paid_price/qty → fallback payload selling price fields. One function, swappable later. |
| `services/policy_lookup.py` | Rule B — brand-mandatory policy resolution | `find_policy(brand, platform, shop, item, seller_sku, on_date) -> (policy, priority_level)`. 6-level priority, brand always required, status=Active + effective window, `is_brand_fallback` honored only at level 6. Returns None → missing_policy path. |
| `services/baseline.py` | Rule C — baseline + confidence | `get_baseline(brand, item, seller_sku) -> (price, confidence, source)`: 30-day median of `unit_check_price` from EC Marketplace Order Item (same brand!) with n≥5 → High; else policy.reference_price → Medium; else policy.min_price → Low. |
| `services/rules.py` | Rule D — pure rule functions, no DB | `evaluate(unit_price, policy, baseline) -> RuleHit | None` — **single winning hit per line (decision C2)**: checks in priority order possible_missing_zero (×10 within ±10–15% of baseline) → severe_price_drop → below_min → above_high → OK; first match wins, lower matches suppressed; recommended_action follows winner. Action matrix hard-coded here: **only severe_price_drop + possible_missing_zero may recommend Stock Safety Lock; above_high/below_min/missing_* never.** |
| `services/owner.py` | Owner resolution | `resolve_owner(shop, brand) -> user`: shop.kam_owner → brand.kam_owner → brand.manager_email → brand.leader_email → None (alert still created, unowned, visible to supervisors). |
| `services/alert_engine.py` | Orchestrator + dedupe + persistence | `check_order_log(order_log_name)`: per line → pricing → brand guard → policy → baseline → rules → upsert EC Alert + EC Alert Action, set line snapshot fields + check_result. Single DB transaction; **no HTTP here ever** (hard rule 11/12). |
| `services/stock_lock.py` | Action queue worker (dry-run era) | `process_pending_actions()`: final guards in order → pause re-check → BIS credential load → dry-run flag → mark **Dry Run** with simulated response. Real executor body stays `NotImplemented` until Omisell gate passes. Per-action try/except + `frappe.log_error`; one failure never kills the batch. |
| `tasks.py` | Scheduler entries (registered only at Phase C deploy, with approval) | `process_action_queue` (*/10 min), `expire_automation_pauses` (hourly: Active → Expired where pause_until < now). |

## 3. Rules engine flow (per order line)

```
EC Marketplace Order Log (synced/mock)
  └─ for each item line:
     1. unit_check_price = pricing.compute_unit_check_price(line)
     2. brand = order.brand  ──(empty?)──► ALERT missing_brand_mapping (Warning,
        Notify Only, daily SKU-level dedupe key per C1) ·
        check_result=Missing Brand Mapping · STOP (no policy check, no lock)
     3. policy = policy_lookup.find_policy(...)  ──(none?)──► ALERT missing_policy
        (Warning, Notify Only, daily SKU-level dedupe key per C1) ·
        check_result=Missing Rule · STOP
     4. baseline, confidence = baseline.get_baseline(...)
     5. hit = rules.evaluate(unit_price, policy, baseline)   # ONE winning hit
        per priority C2 (missing_zero > severe_drop > below_min > above_high > OK)
     6. if hit: alert_engine persists
        a. dedupe: order-line key for price rules (C1); skip if EC Alert with
           same dedupe_key in (Open, In Review) [unique index = backstop for races]
        b. create EC Alert (owner_user = owner.resolve_owner, detected_at=now,
           snapshot prices, gap_percent)
        c. lock decision — ALL must hold, else action = Notify Only record or none:
           rule ∈ {severe_price_drop, possible_missing_zero}
           AND policy.enable_stock_safety_lock = 1
           AND confidence ∈ {High, Medium}          (Low → alert only)
           AND no active EC Automation Pause match  (brand-scoped, priority
               brand+platform+shop+sku → … → brand only; Brand A pause never hits Brand B)
           → create EC Alert Action (Stock Safety Lock, status=Pending,
             dedupe: skip if same dedupe_key in (Pending, Processing, Success, Dry Run);
             if skipped because of pause → create with status=Skipped + reason)
     7. write line snapshots: unit_check_price, min_price_at_check,
        baseline_price_at_check, check_result
  └─ order.sync_status = Success / Failed(+sync_error)
```

Worker (separate transaction, `frappe.enqueue` / scheduler — never inline with step 6):
```
process_pending_actions():
  for action in EC Alert Action(status=Pending, action_type=Stock Safety Lock):
    re-check pause (final guard)          → status=Skipped, note
    bis = EC Brand Integration Settings(action.brand, Omisell)
      missing OR enabled=0 OR credential_status≠Active
        → status=Skipped + upsert ALERT missing_integration_credential (Warning)
        → never attempt API, never borrow another brand's credential
    bis.dry_run_stock_lock=1 (current era) → status=Dry Run,
        api_response="DRY RUN: would set available stock to 0 until {lock_until}",
        executed_at=now, lock_until=now+policy.stock_lock_duration_minutes
    (future, gated) real call: Processing → fetch current stock →
        previous_available_stock → set 0 → Success/Failed(+stock_lock_api_failed alert);
        retry ≤3 with backoff; secrets via bis.get_password() only, never logged
```

## 4. API boundaries (declared now, implemented Phase C/D — none exist today)

All `@frappe.whitelist()` methods gate through `permissions.require_alert_center_access()` first, then brand-scope per record. POST-only for writes.

| Endpoint (`ecentric_workspace.alerts.api.*`) | Who | Notes |
|---|---|---|
| `alerts.list_alerts(filters, page)` | any scoped user | server-side brand filter via `filter_brands`; supervisors see all |
| `alerts.get_cards()` | any scoped user | 6 KPI counts, same scope |
| `alerts.set_status(alert, action, note)` | `can_handle_alert` | In Review / Resolved / Ignored; note required for Resolve/Ignore |
| `pauses.create_pause(...)` | `can_create_pause` (brand) | KAM only own brands; window sanity in controller |
| `pauses.cancel_pause(name)` | `can_cancel_pause` (brand) | |
| `actions.list_actions(alert)` | scoped | read-only |
| `actions.retry/cancel(name)` | `can_execute_action` (SM only) | dry-run era: cancel only |
| `ingestion.ingest_mock_orders(payload)` | System Manager only (Phase D) | normalization + check trigger |

Never exposed: any BIS read/write API; credentials have no client path at all.

## 5. Dry-run strategy

Layered so a real call is impossible by accident: (1) no HTTP client code in Phase C at all — executor raises/skips; (2) `dry_run_stock_lock` default 1 per brand record; (3) credential gate (no Active credential = Skipped); (4) per-brand flip only after OMISELL_API_CHECKLIST gate, with your explicit approval, one brand at a time. Dry Run actions populate every field a real run would (lock_until, executed_at, api_response) so Phase E UI and reports are testable end-to-end.

## 6. Test cases (pure-function tests run without site; integration tests on bench)

Pure (rules.py/pricing.py — no frappe): baseline 99k/actual 9.9k → possible_missing_zero Critical+lock-eligible; 99k/25k @70% → severe_price_drop; below min not severe → below_min Critical no-lock; above high → above_high Warning never-lock; boundary cases (exactly at threshold, ±10 vs ±15% missing-zero band, qty=0 guard, price=0 guard); **C2 priority tests:** line matching both below_min + severe_drop → ONE alert (severe_price_drop); line matching missing_zero + severe_drop + below_min → ONE alert (possible_missing_zero); recommended_action always from winner.
Integration: policy priority 1>3>5 with competing records; effective-date edge (today=effective_to inclusive?  decision: inclusive); inactive policy ignored; brand isolation (same seller_sku two brands, §13 master plan); dedupe re-sync idempotency (run check twice → 0 new docs); **C1 dedupe tests:** 10 order lines same SKU same day with no policy → exactly 1 missing_policy alert; same SKU next day → new alert; with external_product_id present → preferred key form used; price-rule alerts on those same lines still dedupe per order-line; pause active → Skipped action; pause expired → lock proceeds; credential missing on Brand B → Skipped + missing_integration_credential; Low confidence → no action row at all; median window 31-day-old orders excluded; n=4 vs n=5 confidence boundary.

## 7. Open items before Phase C build

1. Phase B must be live + verified (gate).
2. `kam_owner` values filled (else owner falls back to manager_email — acceptable but noisy).
3. ~~Dedupe granularity~~ — **RESOLVED → Decision C1** (§0): daily SKU-level for missing_*, order-line for price rules.
4. ~~Multi-rule collision~~ — **RESOLVED → Decision C2** (§0): priority-based single alert, missing_zero > severe_drop > below_min > above_high.
5. Omisell checklist — needed only for Phase D real pull + future real lock; mock path unblocked.

Implementation note for C1: the new dedupe key forms exceed nothing structurally — `dedupe_key` stays Data(140), unique. Action dedupe keys are unaffected (lock actions only arise from price rules, which keep order-line keys). The `detected_at`-day component uses site timezone (Asia/Ho_Chi_Minh) for the `{YYYYMMDD}` segment.
