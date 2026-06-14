# Alert Center — Phase D/E Pre-code Report

Date: 2026-06-07 · Status: **PRE-CODE — no implementation until approved.** Phases A–C are production-complete.

## 0. What exists in production today

Schema (8 DocTypes, SM-only) · rules engine with C1/C2/C3 · idempotent mock ingestion · dry-run action queue · 2 SM-only POST endpoints · brand-scope permission utilities (unused by any endpoint yet). Missing for a usable product: **a UI for KAMs** and **real order flow**.

## 1. Recommended sequencing: E before D

**Phase E (`/alerts` UI + KAM-facing scoped APIs) first**, because: (a) Phase D's real Omisell pull is **hard-blocked** on the API checklist answers (`OMISELL_API_CHECKLIST.md` — items 1–9 minimum); (b) E is fully unblocked and turns existing data (mock + manual) into business value; (c) E lets KAM/Lead validate the workflow (resolve/ignore/pause) before real volume arrives. Your earlier phrasing "proceed to Phase D `/alerts` UI" matches this — to avoid label confusion this doc uses: **Phase E = UI+APIs (next)**, **Phase D = real ingestion + schedulers (gated)**.

## 2. Phase E scope (next, pending your approval)

### 2.1 Backend additions (app code, `ecentric_workspace/alerts/api/` package — refactor `api.py` → `api/__init__.py` keeping existing two endpoints' import paths stable, or keep `api.py` and add siblings; final layout in the implementation plan)

All endpoints: `@frappe.whitelist`, POST for writes, **first line = `permissions.require_alert_center_access()`**, brand scope filtered server-side via `get_allowed_brands` — exactly the boundary table in `04_PHASE_C_DESIGN.md` §4:

- `alerts.list_alerts(filters, start, page_len)` — scoped list incl. lock-action status per alert (for the Action Status column).
- `alerts.get_cards()` — the 6 KPI counts (Open / Critical / Warning / Missing Policy / Lock Pending / Resolved Today), same scope.
- `alerts.set_status(alert, new_status, note)` — In Review / Resolved / Ignored; note **required** for Resolve+Ignore; `can_handle_alert` per alert.brand; sets resolved_by/at (controller already does).
- `pauses.create_pause(...)` / `pauses.cancel_pause(name)` / `pauses.list_pauses()` — `can_create_pause` / `can_cancel_pause`.
- `actions.list_for_alert(alert)` — read-only, scoped. Retry/cancel/release stay **SM-only and out of E's UI** (dry-run era; Release = post-real-execution feature).

### 2.2 Frontend — one Web Page, route `/alerts`, title "Alert Center"

Per approved D6 + UI reference report (`01_PHASE_B_PLAN.md` §8): single-file `ALERT_CENTER/frontend/alert_center.html`, marker `<script id="ec-alert-center">`; shell + tokens copied from homepage (`.ec-sidebar` copied verbatim, never modified); cards = `stat-*` pattern; filter bar/table/badges/buttons re-namespaced `al-*` from `pm-*` patterns; severity badge colors mapped to existing tokens (Critical `--pink`, Warning `--yellow`, Info `--gray-*`, Resolved `--green`). Default view: KAM sees own brands (server enforces; UI just renders). Filters: Status / Severity / Alert Type / Rule Code / Brand / Platform / Owner / date range. Row actions: Mark In Review · Resolve+note · Ignore+note · Open Source Order (link to reference) · View Action · Create Pause. Deploy = `deploy_alert_page.ps1` + `rollback_alert_page.ps1` (PM pattern, idempotent, ASCII-only).

Page access: Web Page published to logged-in users; the page itself calls `get_cards` first — users with no brand scope get a clean "no access" state (server returns 403; page renders message). No data leaks via the page because every byte comes from scoped APIs.

### 2.3 Files (E)

App: `alerts/api/` additions (~3 modules), no schema, no hooks change. Workspace: `frontend/alert_center.html`, 2 deploy PS scripts, bench tests `tests/test_phase_e.py` (scope filtering, status transitions w/ note enforcement, pause create/cancel permissions, 403 for unscoped users — extends master-plan tests 9/10/13).

### 2.4 Risks (E): LOW-MEDIUM

New Web Page on production (mitigated: PM-pattern deploy/rollback, page additive); scoped-API correctness is the real surface → test-first on the permission matrix (already proven at util level in Phase B test 8). Prereq data step: **fill `kam_owner` on 7 Brand Approver records** — otherwise every KAM's default view is empty and owner column falls back to manager_email.

## 3. Phase D scope (gated — do not schedule until checklist answered)

1. **Scheduler trio** in hooks.py (separate, small deploy; can ship with E if you want): `expire_automation_pauses` (hourly), `process_action_queue` (*/10min — still dry-run-only outcomes), optional `pull_omisell_orders` (disabled until D gate passes).
2. **Real ingestion** (`services/omisell_client.py` — first and only HTTP module): per-brand credential from EC Brand Integration Settings via `get_password()`, incremental order pull → same normalizer → same engine. Requires checklist items 1–9 + 13–15; stock-write items 10–12 remain a SEPARATE later gate (real Stock Safety Lock execution is **not** part of D).
3. Schema micro-additions (need approval, additive): `EC Marketplace Order Item.external_product_id` (persist for C1 keys on re-checks) + `EC Marketplace Order Log.omisell_shop_id` (raw id for unmapped orders). Both Data, optional.

## 4. Test/deploy/rollback (E summary)

Tests: bench suite (scope/actions/pauses/notes) + manual UAT script for KAM user. Deploy: app code via push→PR→FC (same as C), then Web Page via PS script with per-turn confirm. Verification: probes like Phase C (`verify_phase_e_probes.ps1`: 403 matrix for unscoped user, scoped list correctness for a real KAM, card counts vs SQL). Rollback: rollback PS unpublishes the page; revert PR removes APIs; zero schema involved (unless §3.3 approved — those are additive and stay harmlessly).

## 5. Decisions needed from you

- **D1-E:** Approve Phase E scope (§2) as the next implementation phase? (Phase D real-pull stays gated on Omisell answers regardless.)
- **D2-E:** Ship the pause-expiry + queue schedulers together with E, or keep zero schedulers until D? (Recommend: ship with E — pauses that never expire will confuse KAMs; both jobs are dry-run-safe.)
- **D3-E:** Approve the 2 additive fields in §3.3 now (one small migrate) or defer?
- **D4-E:** `kam_owner` fill: give me the brand→KAM list to seed (per-turn confirm) or you fill in Desk before E UAT.
- **D5-E:** Smoke records SMOKE-C-001 / EC-AL-000568: keep-and-Ignore (recommended) or delete?
