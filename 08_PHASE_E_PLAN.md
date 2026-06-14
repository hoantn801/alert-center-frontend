# Alert Center — Phase E Implementation Plan

Date: 2026-06-07 · Status: **PLAN — no code until you approve.** Implements decisions D1-E…D5-E. Hard constraints honored: no PM files touched, no DocPerm/Role changes, no new roles, no real Omisell/stock path, service-layer brand scope everywhere, `/alerts` exposes only scoped API data.

## 1. Backend — exact files (app repo, branch `alerts-phase-e`)

| File | A/C | Content |
|---|---|---|
| `alerts/api.py` | **unchanged** | existing 2 SM-only endpoints keep their live dotted paths |
| `alerts/api_alerts.py` | Add | `list_alerts`, `get_cards`, `set_status` |
| `alerts/api_pauses.py` | Add | `create_pause`, `cancel_pause`, `list_pauses` |
| `alerts/api_actions.py` | Add | `list_for_alert` (read-only) |
| `alerts/tasks.py` | Add | `expire_automation_pauses`, `process_action_queue_job` (see §3) |
| `ecentric_workspace/hooks.py` | Change (additive) | scheduler_events: hourly + cron */10 (see §3) |
| `alerts/doctype/ec_marketplace_order_item/ec_marketplace_order_item.json` | Change | + `external_product_id` (Data) after seller_sku (D3-E) |
| `alerts/doctype/ec_marketplace_order_log/ec_marketplace_order_log.json` | Change | + `omisell_shop_id` (Data) after shop (D3-E) |
| `alerts/services/ingestion.py` | Change | persist the 2 new fields from payload |
| `alerts/services/alert_engine.py` | Change | C1 keys read stored `external_product_id` + `log.omisell_shop_id` (transient `raw_shop_id` param kept as fallback) |
| `alerts/tests/test_phase_e.py` | Add | §6 cases |

Decision note (pre-code §2.1): keeping flat `api_*.py` modules instead of converting `api.py` into a package — zero refactor risk to the two live endpoint paths. New dotted paths: `ecentric_workspace.alerts.api_alerts.list_alerts` etc.

## 2. Endpoints (every one: first line `permissions.require_alert_center_access()`; writes POST-only; brand filter server-side)

| Endpoint | Method | Gate after access check | Notes |
|---|---|---|---|
| `api_alerts.list_alerts(filters?, start?, page_len?)` | GET/POST | results filtered to `get_allowed_brands` (supervisor `*` = all) | filters: status/severity/alert_type/rule_code/brand(∩scope)/platform/owner/date range; returns rows + per-alert latest action status (one joined query) |
| `api_alerts.get_cards()` | GET | same scope | Open / Critical(Open) / Warning(Open) / Missing Policy(Open) / Stock Safety Lock Pending(action status Pending or Dry Run today) / Resolved Today |
| `api_alerts.set_status(alert, new_status, note?)` | POST | `can_handle_alert(user, alert.brand)` | new_status ∈ In Review/Resolved/Ignored; **note required** for Resolved+Ignored (server-enforced); controller stamps resolved_by/at |
| `api_pauses.create_pause(brand, platform, shop?, item?, seller_sku?, pause_from, pause_until, reason)` | POST | `can_create_pause(user, brand)` | automation_type fixed = Stock Safety Lock; window sanity in controller |
| `api_pauses.cancel_pause(name)` | POST | `can_cancel_pause(user, pause.brand)` | status → Cancelled (no delete) |
| `api_pauses.list_pauses(active_only?)` | GET | scope-filtered | for UI list + "create pause" prefill |
| `api_actions.list_for_alert(alert)` | GET | `require_brand_access(user, alert.brand)` | read-only; **no retry/cancel/release endpoints in E** |

Out by design: any BIS/credential read, any action execution, any unscoped list. Unscoped user calling anything → 403 (clean "no access" state in UI).

## 3. Schedulers (D2-E — dry-run-safe by construction)

```python
# hooks.py (additive)
scheduler_events = { ...existing pm entries...,
  "hourly": ["ecentric_workspace.alerts.tasks.expire_automation_pauses"],
  "cron": {"*/10 * * * *": ["ecentric_workspace.alerts.tasks.process_action_queue_job"]},
}
```
- **Kill switch (fail-safe):** both jobs exit immediately if `frappe.conf.get("ec_alerts_scheduler_disabled")` is truthy — site_config flag on FC, no schema needed. Config read wrapped in try/except: **any config error → job no-ops** (fail safe = do nothing).
- `expire_automation_pauses`: Active pauses with `pause_until < now` → status=Expired. Per-row try/except + `frappe.log_error`; idempotent (already-Expired untouched).
- `process_action_queue_job`: thin wrapper over `action_queue.process_pending_actions()` — which structurally can only end Pending→Dry Run/Skipped (no HTTP client exists; verified Phase C). Per-action try/except already inside; batch never crashes; idempotent (processed actions leave Pending state).

## 4. Frontend — exact files

| File | Content |
|---|---|
| `ALERT_CENTER/frontend/alert_center.html` | single self-contained page, marker `<script id="ec-alert-center">`. Shell copied from current `home` snapshot (`.ec-sidebar` verbatim — never modified), tokens `--navy/--gray-*/--green/--yellow/--pink`. 6 KPI cards (`stat-*` pattern), filter bar + table + row detail (PM `pm-*` widget styles re-namespaced `al-*`), modals: Resolve/Ignore (note required client-side too), Create Pause. Badges: Critical `--pink`, Warning `--yellow`, Info `--gray`, Resolved `--green`. Fetch pattern copied from `pm_app.html` (same session/CSRF handling — proven in production). Empty/no-access states. No external libs, no framework (D6). |
| `ALERT_CENTER/deploy/deploy_alert_page.ps1` | idempotent: create-or-update Web Page `alert-center`, route `alerts`, title "Alert Center", published=1, PUT `main_section` + `main_section_html` (cache-bust), ASCII-only source w/ `\uXXXX` escapes for any Vietnamese UI strings, verify section |
| `ALERT_CENTER/deploy/rollback_alert_page.ps1` | unpublish (published=0) — content preserved |
| `ALERT_CENTER/deploy/verify_phase_e_probes.ps1` | post-deploy probes (§7) |

UI shows only what scoped APIs return; Desk remains SM-only; no direct `/api/resource` calls from the page (method endpoints only).

## 5. D3-E fields — implementation + verification

Added inside the two app-owned DocType JSONs (current convention) → applied by FC migrate (idempotent, additive, non-destructive; no patch needed — `migrate` syncs DocType JSON). Post-migrate verification (in `verify_phase_e_probes.ps1`): GET both DocTypes' meta → fields present; ingest a mock order carrying `external_product_id` + unmapped `omisell_shop_id` → values persisted + missing_brand_mapping key uses stored raw id.

## 6. Test cases (`test_phase_e.py`, bench)

1. Unscoped user: every §2 endpoint → PermissionError.
2. KAM A: `list_alerts` returns only Brand A alerts; brand filter for Brand B silently yields nothing (∩ scope); supervisor sees all.
3. `get_cards` counts match direct SQL for a seeded fixture set.
4. `set_status` Resolved without note → throws; with note → resolved_by/at set; KAM A on Brand B alert → PermissionError; In Review needs no note.
5. `create_pause`: KAM A on Brand A OK; on Brand B → throw; leader → throw (can_create_pause=kam/manager); window inverted → throw.
6. `cancel_pause`: manager/leader OK, kam → throw; status=Cancelled not deleted.
7. Scheduler: expired Active pause → Expired after `expire_automation_pauses`; non-expired untouched; kill-switch on → nothing changes.
8. `process_action_queue_job`: seeded Pending action → Dry Run (with Active+dry_run BIS) / Skipped (no BIS); kill-switch on → stays Pending.
9. D3-E: ingested `external_product_id`/`omisell_shop_id` persisted; missing_* dedupe keys use preferred forms; re-check from saved doc keeps same key (no transient loss).
10. Re-run whole suite → idempotent, no duplicates.

**UAT (manual, after deploy) — PRECONDITION: all 7 Brand Approver records have `kam_owner` filled (D4-E, you fill manually).** KAM login → `/alerts` shows only own brand; resolve+note flow; ignore flow; create pause → verify lock skipped on next mock ingest; Lead sees team brands; non-KAM user sees clean no-access page; mobile width sanity.

## 7. Deploy / rollback

Deploy order (each production step per-turn confirmed): (1) local build + tests + blob-verified commit on `alerts-phase-e`; (2) implementation report → your review; (3) push from Windows → PR → merge → FC deploy (migrate applies 2 fields + scheduler hooks — **schedulers go live at this step**, safe: dry-run-only outcomes + kill switch); (4) `verify_phase_e_probes.ps1` (403 matrix, fields present, scheduler heartbeat via a seeded expired pause, smoke alert state); (5) Web Page deploy via PS script; (6) UAT (precondition D4-E). Rollback: page → rollback script (unpublish); scheduler → set `ec_alerts_scheduler_disabled=1` in site config (instant) or revert PR; API → revert PR; fields → additive, stay; no destructive step.

## 8. D5-E execution (ready now, separate from Phase E code)

`ALERT_CENTER/deploy/ignore_smoke_alert.ps1` (written, ASCII-only, reads token from `frappe_api_keys -newww.csv`): sets EC-AL-000568 → status Ignored + resolution_note "Deploy smoke test for Phase C verification. Safe mock record, no real stock/API action." Idempotent (skips if already Ignored). **Run when ready — this is the one production write already approved by D5-E.**

## 9. Risk

LOW-MEDIUM: new page + first schedulers on production. Mitigations: kill switch, dry-run-only worker, PM-proven page deploy pattern, 403-first API design, page is additive and unpublishable in seconds. PM files, DocPerms, roles: untouched (verified in pre-push checks like Phase C §0).
