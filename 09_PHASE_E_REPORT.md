# Alert Center — Phase E Implementation Report

Date: 2026-06-08 (night session) · Status: **IMPLEMENTED LOCALLY — commit `c176ec3` on `alerts-phase-e` (off `dcb6741` = origin/main with Phase C merge). NOT pushed/merged/deployed.** Awaiting review/approval.

## 1. Files added / changed

**App commit `c176ec3` — 11 files, +547/−5, zero PM files (verified: 0 pm/ paths staged):**
- Add: `alerts/api_alerts.py` (153 ln), `alerts/api_pauses.py`, `alerts/api_actions.py`, `alerts/tasks.py`, `alerts/tests/test_phase_e.py` (222 ln).
- Change: `hooks.py` (+10: scheduler entries only), `ec_marketplace_order_item.json` (+7: external_product_id), `ec_marketplace_order_log.json` (+7: omisell_shop_id), `services/ingestion.py` (+4/−1: persist both fields), `services/alert_engine.py` (+6/−4: C1 keys use stored values), `services/action_queue.py` (+1: external_product_id onto actions). `api.py` (live Phase C endpoints) **untouched**.

**Workspace (`ALERT_CENTER/`, not in app repo):** `frontend/build_alert_center_page.py` (page builder), `frontend/alert_center.html` (49.9 KB output), `deploy/deploy_alert_page.ps1`, `deploy/rollback_alert_page.ps1`, `deploy/verify_phase_e_probes.ps1` (all ASCII-only).

## 2. Endpoints added (all: `require_alert_center_access()` first line; brand scope server-side)

`api_alerts.list_alerts` (scoped list + per-alert latest action status; out-of-scope brand filter → 0 rows), `api_alerts.get_cards` (6 KPIs scoped), `api_alerts.set_status` (POST; In Review/Resolved/Ignored; **note required server-side** for Resolve+Ignore; `can_handle_alert` per brand; brand-less alerts = supervisors only), `api_alerts.my_scope` (UI bootstrap), `api_pauses.create_pause` (POST; `can_create_pause`), `api_pauses.cancel_pause` (POST; `can_cancel_pause`; status→Cancelled, never deleted), `api_pauses.list_pauses` (scoped), `api_actions.list_for_alert` (read-only, scoped). No retry/cancel/release endpoints exist.

## 3. Scheduler entries added (hooks.py)

`hourly: alerts.tasks.expire_automation_pauses` · `cron */10: alerts.tasks.process_action_queue_job`. Both: kill switch `ec_alerts_scheduler_disabled` in site_config (config-read error → fail-safe no-op), per-row try/except + `frappe.log_error`, idempotent, **no HTTP path** (worker terminal states: Dry Run / Skipped only — wraps the Phase C queue unchanged). They activate at FC deploy of this branch (approved D2-E).

## 4. Fields changed (D3-E, additive, app-owned JSON → idempotent migrate)

`EC Marketplace Order Item.external_product_id` (Data, after seller_sku) · `EC Marketplace Order Log.omisell_shop_id` (Data, after shop). Ingestion persists both; C1 dedupe keys now use the **stored** external_product_id / raw shop id — re-checks from saved docs produce identical keys (closes Phase C limitation §6.2/6.3).

## 5. UI files added

`alert_center.html` — built by `build_alert_center_page.py` from the **production home shell snapshot** (csrf-fetch patch, navbar-hide style, master CSS tokens, svg icon defs, `.ec-sidebar` markup copied — with home's Jinja stripped: approvals badge removed, user card filled client-side). Content: 6 `stat-card` KPIs, filter bar (Status/Severity/Type/Rule/Brand/Platform/Owner/date range), 15-column table, detail drawer, Resolve/Ignore note modal, Create Pause modal, toast — all `al-*` namespaced CSS on existing tokens (Critical `--pink`, Warning `--yellow`, Resolved `--green`). Guest → redirect `/login?redirect-to=/alerts`; unscoped user → clean no-access screen. **No framework/library; no Jinja; 100% ASCII (VN labels as entities/\uXXXX); no backticks/${} in JS.** Build asserts: ASCII-only, no `{{`/`{%`, balanced style/script tags, VN labels decode correctly.

## 6. Tests run / results

- Executed in this workspace: `py_compile` all (incl. from committed blobs); pure suite `test_rules_pure` **16/16 PASS** (regression); import-smoke of all 7 new/changed runtime modules with stub frappe PASS; page build assertions PASS; `grep` zero HTTP imports under `alerts/`; PS scripts ASCII-check PASS.
- Written, pending bench site: `test_phase_e.py` — 9 cases: unscoped 403 on every endpoint; KAM sees own brand only (+ out-of-scope filter → 0); cards vs SQL; set_status note/permission matrix; pause create/cancel role matrix; pause-expiry job (incl. kill-switch respected + idempotent re-run); queue job dry-run-only outcomes; D3 fields persisted end-to-end; actions read scoped. Run with: `bench --site <site> run-tests --module ecentric_workspace.alerts.tests.test_phase_e`.
- UAT script in `08_PHASE_E_PLAN.md` §6 — **PRECONDITION: all 7 Brand Approver records have `kam_owner` filled (D4-E, you fill manually before KAM scoped testing).**

## 7. Confirmations

- **No PM files changed**: commit `c176ec3` contains zero `pm/` paths (working tree does show pm diffs — they are NOT mine and were left untouched; see §10 note).
- **No real Omisell/stock path**: zero HTTP imports in `alerts/` (blob-level grep); worker outcomes remain Dry Run/Skipped only; no new execution code.
- No new roles, no DocPerm/Role Permission Manager change, no credentials touchable from frontend (no BIS endpoint exists), `/alerts` consumes only scoped method endpoints — Desk stays SM-only.

## 8. Deploy checklist (when approved — each step per-turn confirmed)

1. Pre-push (Windows): housekeeping `.git/*stale*`; `git diff main alerts-phase-e --stat` → 11 files +547/−5; no pm/ paths; push `alerts-phase-e`.
2. PR → merge `main` (merge commit) → FC Deploy. Migrate applies the 2 fields; **schedulers go live here** (kill switch available: add `ec_alerts_scheduler_disabled: 1` to site config first if you want them dormant initially).
3. Run `verify_phase_e_probes.ps1` (fields present, my_scope/get_cards/list_alerts alive, queue drain, optional non-SM 403 matrix via `-NonSmCsv`).
4. Fill `kam_owner` × 7 (D4-E) — before page deploy or right after.
5. Deploy page: `deploy_alert_page.ps1` (backs up existing record if any; creates/updates Web Page `alert-center`, route `/alerts`; verifies record + live GET).
6. UAT per plan §6; fresh snapshot + handover entry.

## 9. Rollback plan

Page: `rollback_alert_page.ps1` (unpublish, seconds, content kept). Schedulers: site_config kill switch (instant) or revert PR. APIs: revert PR → FC deploy. Fields: additive, stay harmlessly. No destructive step; all records kept for audit.

## 10. Notes for you

- Working tree on the shared checkout currently shows **uncommitted pm/ diffs** (checklist.py, recurrence.py, pm_app.html — content drift vs origin/main, possibly your WIP or OneDrive lag). I did not touch or stage them. Before pushing Phase E from Windows, double-check those are your intended local state.
- Sidebar has no "Alert Center" nav item (adding one would touch every page's embedded sidebar copy — out of scope per "do not modify shared sidebar"). Proposal for later: add item to the shared sidebar in a separate approved change; until then `/alerts` is reached by direct URL.
- The `/alerts` Web Page record is published (page shell is public like other Web Pages; all DATA requires an authenticated, brand-scoped session; Guest is redirected to login by the page itself).
