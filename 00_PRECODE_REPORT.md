# Alert Center MVP — Pre-code Inspection Report (Phase A)

Date: 2026-06-06 · Author: Claude session · Status: **APPROVED 2026-06-06 with corrections — see §17 (binding decisions). §3 role proposal is SUPERSEDED by §17/D2.** Phase B plan: `01_PHASE_B_PLAN.md`.

Ground truth: live snapshot `MSOSOPOREC/phase8/snapshots/20260605_230007/live_state/` (generated 2026-06-05 23:00, i.e. last night — current). Brand/Global Role schemas from `20260527_120657_approval_check/`. App code from local git repo `ecentric_workspace/`.

---

## 1. Current app / module structure

[FACT, snapshot 20260605_230007] Live site `team.ecentric.vn`: 40 Web Pages, 248 Server Scripts, 31 custom DocTypes, 164 Custom Fields. ERPNext is installed (native Customer, Item, Contract in use).

Two code layers exist:

1. **Server Scripts (248)** — legacy + approval/GBS logic, RestrictedPython sandbox (no import, no `.append`, no dunder — see `_memory/`).
2. **`ecentric_workspace` app** (git repo in this folder, installed on site — `hooks.py` scheduler entries reference `ecentric_workspace.pm.api.*`). The **PM v2 module is the modern reference pattern**:
   - `ecentric_workspace/pm/api/*.py` — whitelisted service endpoints
   - `ecentric_workspace/pm/permissions.py` — **service-layer permission** (role layer = capability, department layer = data scope; no global `permission_query_conditions`)
   - `ecentric_workspace/pm/frontend/pm_app.html` + `deploy_pm_app.ps1` / `rollback_pm_app.ps1` — single-file Web Page frontend deployed by idempotent PS5 script
   - `fixtures/role.json`, `fixtures/custom_field.json` — filtered fixtures
   - `hooks.py` `scheduler_events` for daily jobs

**Recommendation: the Alert Center should be a new app module `ecentric_workspace/alerts/` cloned from the PM v2 pattern** (app code, not Server Scripts) — this satisfies the north-star (maintainability, service-layer permissions, background jobs need real Python: `frappe.enqueue`, requests, password decryption — none of which work in the Server Script sandbox).

## 2. Existing DocTypes — Brand / Shop / SKU / KAM / Lead

| Concept | Existing source of truth | Verdict |
|---|---|---|
| **Brand** | ✅ **`Brand Approver`** (custom DocType, module Ecentric Workspace, `autoname: field:brand_code`, `track_changes: 1`). Fields: `brand_code` (PK), `brand_name`, `parent_client_code` → Link Customer, `status` (Active/Inactive), `manager_email` → Link User, `leader_email` → Link User, `finance_email` → Link User, `approval_recipe`, `gbs_recipe`. Live records: AND-VN (Andros), BBT-VN (Bong Bach Tuyet), FCV-VN (Dutch Lady – Friso), … (7 records as of 2026-05-27). | **REUSE. All new DocTypes Link to `Brand Approver`.** Do NOT create a new Brand master. (ERPNext-native `Brand` DocType also exists but is unused by this project — do not introduce a second source of truth.) |
| **Brand Manager / KAM owner** | ✅ `Brand Approver.manager_email` (Link User) — per-brand manager. `leader_email` = lead. | **REUSE as owner resolution.** ⚠️ OPEN QUESTION Q1: confirm `manager_email` semantics = "KAM owner" for alert purposes. If KAM ≠ approval-manager, add one custom field `kam_owner` (Link User) on Brand Approver instead of a new mapping table. |
| **Lead / Manager** | ✅ `Brand Approver.leader_email`; plus `Global Role` DocType (role_key: ceo/hof/finance_lead/procurement_lead/manager/leader → user_email) for global escalation. | REUSE for escalation fallback. |
| **Shop / store** | ❌ None. No Shop DocType, no shop→brand mapping anywhere. `GBS Sales Order.store_name` is a plain Data field. | **Gap → create `EC Marketplace Shop`** (minimal mapping master, see §7). This is the keystone for brand resolution of Omisell orders. |
| **SKU / Item** | ⚠️ ERPNext `Item` exists but is used for **procurement/GBS** (custom fields `allowed_procurement_types`, `default_procurement_type`); GBS item data is even enriched from `team.boxme.asia` via `web_lookup`. **No evidence marketplace seller SKUs exist in Item.** No Item→Brand link in the 164 custom fields. | MVP: `seller_sku` = Data (Omisell identifier); optional nullable `item` Link → Item for future reconciliation. **Do not block on Item master.** NEEDS VERIFICATION V2: whether Item holds marketplace SKUs (one read-only query). |
| **SKU→Brand mapping** | ❌ None. | Brand resolution comes from shop mapping (§9), not SKU. |

## 3. Existing roles — ⚠️ SUPERSEDED by §17/D2: NO new roles for MVP. Kept for history only.

[FACT] App fixtures define `PM Manager` (desk) and `PM Member` (portal). No KAM/compliance/integration roles exist in app fixtures or docs. ⚠️ NEEDS VERIFICATION V1: full live Role list isn't captured by the snapshot script (read-only GET `/api/resource/Role` — propose adding a `roles_list` section to `snapshot_live_state.ps1`).

**Proposed minimal new roles (fixtures, following PM pattern):**

| Role | desk_access | Purpose |
|---|---|---|
| `Price Compliance Manager` | 1 | Full on all EC alert DocTypes |
| `EC KAM` | 0 | Portal user, brand-scoped alerts/pauses |
| `EC KAM Lead` | 0 | Team/brand scope, cancel pauses, resolve |
| `EC Integration Manager` | 1 | Manage per-brand credentials only |
| (reuse) `System Manager` | — | Full |

Data/Ops read-only and Management dashboard view can ride on read DocPerms for existing roles — defer until Q2 answered (which existing role names map to Ops/Management users).

## 4. Existing User Permission model

No Frappe **User Permission** usage found in docs/snapshots. The project's established pattern is **service-layer scope** (PM v2 `permissions.py` — explicitly chosen over global hooks, decision PM1-T03) plus the `EC Viewer Permission` DocType for the ticket-viewing subsystem (scripts `ec_sync_viewer_permissions`, `get_user_perm`).

**Recommendation:** enforce brand scope in `ecentric_workspace/alerts/permissions.py` exactly like PM v2:
- Capability layer: role check (`require_alerts_access()`).
- Scope layer: user's brand set = brands where `Brand Approver.manager_email == user` (KAM) ∪ `leader_email == user` (Lead) [∪ `kam_owner == user` if Q1 adds it]. Managers/System Manager/Price Compliance Manager → all brands.
- Every read/write service filters/validates by this brand set. Frontend hiding is cosmetic only.
- Native Frappe User Permission on Brand Approver can be layered later for Desk users; not required for MVP because all portal access goes through the service layer.

## 5. Frontend route/page pattern

[FACT] All UI = Frappe **Web Page** records (40 routes), single-file HTML+JS in `main_section_html`, deployed by idempotent PS5 scripts (marker pattern `<script id="ec-FEATURE">`, PUT both `main_section` and `main_section_html`). PM v2 is the cleanest instance: one source file `pm/frontend/pm_app.html` + `deploy_pm_app.ps1` + `rollback_pm_app.ps1`. Sub-routes like `pm/tasks` are separate Web Page records.

**`/alerts` will follow the PM pattern**: one Web Page record `alert-center` (route `alerts`, title "Alert Center"), source file `ALERT_CENTER/frontend/alert_center.html`, deploy/rollback PS scripts. Cards + filters + table + row actions all call whitelisted `ecentric_workspace.alerts.api.*` methods. If Phase E runs out of time inside the 1-day MVP, fallback = Desk List View on EC Alert for desk roles only, and the custom page slips to Phase 2 — data model and services are unaffected.

## 6. Omisell integration — existing?

❌ **Nothing exists.** Zero hits for "omisell" across all docs, scripts, server-script names, custom fields, and DocTypes. No generic integration-settings DocType either (`GBS Settings` is GBS-specific). Greenfield → we design per-brand credentials from scratch (§7, `EC Brand Integration Settings`), which cleanly satisfies the multi-brand requirement (no single global API key to refactor later).

⚠️ OPEN QUESTION Q3: Omisell API contract (auth scheme: api_key vs token? order-list endpoint? stock-update endpoint? shop identifiers in payload?). Until confirmed → mock ingestion endpoint + `dry_run_stock_lock = 1` (Dry Run actions only), per your spec.

## 7. Proposed DocType design (adjusted to this repo)

All custom DocTypes, module **Ecentric Workspace**, `track_changes: 1`, no hard delete (no delete DocPerm except System Manager; cancellation via status). `brand` is **Link → Brand Approver, reqd** everywhere. Adjustments vs your draft are marked **Δ**.

1. **`EC Marketplace Shop`** **Δ NEW (not in your draft — required for brand resolution)**
   `shop_code` (autoname field), `shop_name`, `platform` (Shopee/Lazada/TikTok/Other), `brand` (Link Brand Approver, reqd), `omisell_shop_id` (Data, unique — join key for ingestion), `kam_override` (Link User, optional — shop-level owner override), `status` (Active/Inactive). Minimal master: 8 fields, no duplication of any existing data (nothing exists).

2. **`EC Brand Integration Settings`** — per your spec: `brand` (Link Brand Approver, reqd, unique per integration_type), `integration_type` (Omisell), `enabled`, `base_url`, `api_key`/`api_secret`/`token` (**Password fields** — encrypted at rest, never returned by resource API, read server-side via `get_password()` only), `credential_status`, `last_sync_at`, `dry_run_stock_lock` (default 1), `default_platform_scope`, `notes`. DocPerm: System Manager + EC Integration Manager only (read/write); **no role else can even read**. Never logged, never sent to frontend.

3. **`EC Alert`** — as specced, with: `brand` Link Brand Approver reqd; `shop` Link EC Marketplace Shop; `sku` **Δ renamed `item`** (Link Item, optional/nullable) + `seller_sku` Data (primary identifier); `rule_code` Select **Δ adds** `missing_brand_mapping`, `missing_integration_credential`, `stock_lock_api_failed`; `dedupe_key` Data **unique=1** (feasible — Data ≤140 chars, format fits; service-level check kept as belt-and-braces); `reference_name` Dynamic Link on `reference_doctype`. `owner_user` Link User.

4. **`EC Price Policy`** — as specced; `brand` reqd (brand-scoped, lookup always brand-first); `shop` Link EC Marketplace Shop; `item` Link Item optional + `seller_sku` Data; defaults `severe_drop_percent=70`, `stock_lock_duration_minutes=120`. Importable via standard **Frappe Data Import** (no custom importer). Not ERPNext Pricing Rule: confirmed unsuitable — Pricing Rule has no platform/shop/anomaly/stock-action semantics and is coupled to selling transactions we're explicitly not creating.

5. **`EC Marketplace Order Log`** (+ child **`EC Marketplace Order Item`**) — as specced; parent unique key `source_system + external_order_id` (service-enforced + unique Data `order_key`); `brand`/`shop` Links resolved at ingestion; child stores all price-snapshot fields (`unit_check_price`, `min_price_at_check`, `baseline_price_at_check`, `check_result`). `raw_payload_hash` for idempotent re-sync. No accounting/inventory impact (plain custom DocTypes).

6. **`EC Alert Action`** — as specced + `brand` Link reqd (credential lookup key); statuses include Skipped + Dry Run; `dedupe_key` unique=1; `previous_available_stock`, `lock_until`, `release_status`. No Off-Listing action type exists at all (not just disabled).

7. **`EC Automation Pause`** — as specced, brand-scoped, scheduler flips Active→Expired.

**Link vs Data summary:** brand → Link Brand Approver (everywhere, reqd). shop → Link EC Marketplace Shop (new minimal master, justified: no existing source). SKU → `seller_sku` Data primary + optional `item` Link Item (pending V2). owner/users → Link User. platform/source_system/statuses → Select. Nothing structured goes into JSON/text blobs.

## 8. Business logic placement (backend impact)

New module `ecentric_workspace/alerts/`:

```
alerts/
  __init__.py
  permissions.py            # brand-scope service-layer guard (PM v2 pattern)
  services/
    pricing.py              # unit_check_price extraction (isolated fn, per rule A)
    policy_lookup.py        # brand-mandatory priority chain (your 6 levels)
    baseline.py             # 30d median → reference_price → min_price + confidence
    rules.py                # above_high / below_min / severe_price_drop /
                            # possible_missing_zero / missing_policy /
                            # missing_brand_mapping — pure functions, unit-testable
    alert_engine.py         # dedupe + EC Alert / EC Alert Action creation (one tx)
    omisell_client.py       # per-brand credential loader + HTTP wrapper + dry-run
    stock_lock.py           # background worker: pause re-check (final guard),
                            # credential check → missing_integration_credential,
                            # execute / Dry Run, retry, frappe.log_error
  api/
    ingestion.py            # whitelisted mock-ingest endpoint (+ Omisell pull when Q3 confirmed)
    alerts.py               # list/cards/mark-in-review/resolve/ignore (note required)
    actions.py              # list/retry/cancel/manual release (role-gated)
    pauses.py               # create (brand-scope enforced)/cancel/list
  tasks.py                  # scheduler: action queue worker, pause expiry, (later) order pull
```

Hard rules honored: price-check transaction only writes EC Alert + EC Alert Action (Pending/Dry Run); the Omisell HTTP call happens only in `frappe.enqueue`'d worker, separate transaction, with EC Automation Pause re-checked as final guard. High-price never locks. Only severe_price_drop / possible_missing_zero with policy `enable_stock_safety_lock=1` + High/Medium confidence + active per-brand credential + no active pause produce an executable lock; everything else is Notify Only. No listing off, no price write, no ERPNext Sales Order.

`hooks.py` additions: `scheduler_events` (cron ~*/10 action worker; hourly pause expiry) + fixtures (roles).

## 9. Brand resolution & owner assignment (multi-brand answers)

Direct answers to your six questions:

1. **Existing Brand source of truth?** `Brand Approver` (brand_code PK, Active records live). All new DocTypes Link to it.
2. **Where is Brand Manager/KAM stored?** `Brand Approver.manager_email` (manager) + `leader_email` (lead) + `finance_email`. Pending Q1 on whether manager_email = KAM; if not, add `kam_owner` custom field there — never a new mapping table.
3. **Existing shop-to-brand mapping?** **None.** → new `EC Marketplace Shop` with `omisell_shop_id` → `brand`. This is the only new master data proposed.
4. **Existing SKU-to-brand mapping?** **None** (Item has no brand custom field; marketplace SKUs likely not in Item at all). SKU is not used for brand resolution in MVP.
5. **Where should per-brand Omisell credentials live?** `EC Brand Integration Settings` (one record per brand × integration_type), Password fieldtypes, DocPerm restricted to System Manager + EC Integration Manager, decrypted only inside `omisell_client.py` via `get_password()`. No global key anywhere.
6. **How are brand-scoped permissions enforced?** Service layer (`alerts/permissions.py`), PM v2 pattern: user → allowed brand set from Brand Approver fields; every API filters and validates against it; pauses/resolves outside scope throw `PermissionError`. Frontend default view derives from the same call.

**Order brand resolution chain:** (1) `omisell_shop_id` → EC Marketplace Shop → brand; (2) payload brand field if Q3 shows it's reliable; (3) — SKU-based: skipped, no source; (4) fail → `missing_brand_mapping` Warning alert, no policy check, no lock. **Owner:** shop.kam_override → brand.manager_email (KAM) → brand.leader_email → Global Role manager/leader → Price Compliance Manager fallback.

## 10. Schema / backend / frontend impact

- **Schema:** 7 new custom DocTypes (+1 child) listed in §7, all net-new — zero changes to existing DocTypes (except possibly +1 custom field `kam_owner` on Brand Approver pending Q1). 4–5 new Roles + DocPerms. No Frappe-native DocType touched. No destructive migration.
- **Backend:** new isolated app module `ecentric_workspace/alerts/` + hooks.py scheduler/fixture entries. No change to existing approval/GBS/PM code paths. No Server Scripts needed.
- **Frontend:** 1 new Web Page `/alerts` (PM single-file pattern). No shared sidebar changes, no Website Settings changes.

## 11. Files to add / change

| Area | File | Add/Change |
|---|---|---|
| DocTypes | `ALERT_CENTER/deploy/01_create_doctypes.ps1` (idempotent POST/PUT DocType JSON — matches existing convention: all 31 live custom DocTypes were created this way) | Add |
| Roles/Perms | `ALERT_CENTER/deploy/02_roles_docperms.ps1` (or app fixtures + migrate — Q4) | Add |
| Backend | `ecentric_workspace/ecentric_workspace/alerts/**` (per §8 tree) | Add |
| Hooks | `ecentric_workspace/ecentric_workspace/hooks.py` (scheduler + fixtures) | Change (additive) |
| Frontend | `ALERT_CENTER/frontend/alert_center.html`, `deploy/03_deploy_alert_page.ps1`, `deploy/03_rollback_alert_page.ps1` | Add |
| Test data | `ALERT_CENTER/test/mock_orders.json`, `04_run_mvp_tests.ps1` | Add |
| Docs | `ALERT_CENTER/README.md` (created), `04_HANDOVER_LOG.md` entry, `02_CURRENT_STRUCTURE.md` (+folder), `01_DECISION_LOG.md` (new decisions: Brand Approver as brand SoT for alerts; per-brand credentials) | Change (append) |

## 12. Phases for the 1-day MVP

- **A. DONE** — this report. Gate: your approval + answers Q1–Q4.
- **B (~1.5h)** — DocTypes + roles + DocPerms + 2–3 EC Marketplace Shop & EC Price Policy seed records + EC Brand Integration Settings (dry-run, fake key) for 2 test brands. Verify via GET.
- **C (~2h)** — services: pricing, policy_lookup, baseline+confidence, rules, alert_engine with dedupe. Pure-function tests offline first.
- **D (~1h)** — mock ingestion endpoint (whitelisted, role-gated) normalizing sample payload → Order Log → run checks. Real Omisell pull deferred unless Q3 lands today.
- **E (~2h)** — `/alerts` Web Page: 6 cards, filters (Brand first-class), table, actions (In Review / Resolve+note / Ignore+note / Open source / Create pause). Release button only as manual, role-gated, and only if time allows; else Phase 2.
- **F (~1h)** — run test matrix (§13) via mock orders on the 2 seed brands; verify; handover log entry. `dry_run_stock_lock` stays 1.

If the day runs short, E degrades to Desk List View + the page ships next session — B/C/D are the ERP-grade core and are not negotiable.

## 13. Test plan (acceptance matrix)

Schema: all DocTypes exist post-deploy; track_changes=1 on EC Alert / EC Price Policy / EC Alert Action / EC Automation Pause / EC Brand Integration Settings; dedupe_key unique constraint active; brand Links resolve to Brand Approver.

Rules (mock orders, seed policy baseline 99,000, severe_drop 70%, high_alert e.g. 30%):
1. actual 9,900 → `possible_missing_zero`, Critical, lock action iff enabled + High/Medium confidence.
2. actual 25,000 → `severe_price_drop`, Critical, lock action iff enabled + confidence ok.
3. below min but not severe → `below_min`, Critical, **no lock**.
4. above high → `above_high`, Warning, **never lock**.
5. no policy → `missing_policy`, Warning, no lock.
6. active pause → alert created, action Skipped.
7. same order re-synced → zero new alerts/actions (dedupe).
8. Low confidence (min_price-only baseline) → alert only, no lock.
9. unknown omisell_shop_id → `missing_brand_mapping`, Warning, no policy check, no lock.
10. Brand B credential missing/inactive → action Skipped/Failed + `missing_integration_credential` alert; Brand A (active cred) → Dry Run proceeds.

Multi-brand: same seller_sku on Brand A (min 50k) and Brand B (min 80k) → each order uses its own brand's policy only. Pause on Brand A → Brand B unaffected.

Permissions: KAM A cannot list/resolve Brand B alerts nor create Brand B pause (service-layer throw, tested via API not UI); Lead sees team brands; Price Compliance Manager sees all; KAM cannot read EC Brand Integration Settings at all.

Secrets: GET EC Brand Integration Settings as non-integration role → 403/forbidden; API responses and `frappe.log_error` payloads contain no key material; `/alerts` page source and network payloads contain no credentials.

## 14. Risk level

**Overall: LOW–MEDIUM.**
- LOW: purely additive schema; no existing DocType/script/page modified; no inventory/accounting documents; stock lock is dry-run by default; production writes are all new records.
- MEDIUM: (a) new Web Page + new module on a production site — mitigated by PM-pattern deploy/rollback scripts and per-turn write confirmation (A33); (b) Omisell contract unknown — mitigated by mock + dry-run; (c) `manager_email`=KAM assumption — gated by Q1; (d) future real stock-lock execution is the genuinely risky part and is **out of MVP** (stays Dry Run until you confirm the API and flip the flag per brand).

## 15. Deploy / rollback plan

Deploy (every write gated by your per-turn confirmation, per A33): snapshot first (`snapshot_live_state.ps1`) → 01 DocTypes → verify GET → 02 roles/perms → verify → app code commit + pull + `bench migrate` + restart (or PS-script-only path if bench access is not available today — Q4) → 03 Web Page → seed test data → run §13 matrix → fresh snapshot + handover-log entry. `dry_run_stock_lock=1` everywhere; scheduler worker initially disabled or no-op until C/D verified.

Rollback: page → `03_rollback_alert_page.ps1` (delete/unpublish Web Page); logic → remove scheduler entries + disable whitelisted endpoints (revert commit, restart); credentials → `enabled=0` per brand; schema → DocTypes are additive, leave in place (set roles' perms off) — **no destructive deletion; all created alert/action records stay for audit** unless you explicitly approve test-data cleanup.

## 16. Open questions (blocking, please answer with approval)

- **Q1.** Is `Brand Approver.manager_email` the KAM owner for alert purposes, or should I add a dedicated `kam_owner` field on Brand Approver?
- **Q2.** Which existing users/roles map to "Data/Ops" and "Management" viewers for MVP read perms? (Can defer — default: only the 4 new roles + System Manager.)
- **Q3.** Omisell API: do you have docs/sample payload (order list + stock update + shop id field)? Without it, Phase D = mock endpoint only and all lock actions = Dry Run.
- **Q4.** Deploy channel for app code: do we have bench/SSH access to run `bench migrate` on team.ecentric.vn (PM v2 build sheet implies yes)? If not, DocTypes/roles go via PS scripts and module code deploy needs the same channel PM v2 used.
- **Q5.** Folder/page naming OK? Folder `ALERT_CENTER/`, route `/alerts`, page title "Alert Center", roles named as §3.

---

## 17. Approved decisions (user, 2026-06-06) — BINDING

- **D1 (Q1):** Add Custom Field **`Brand Approver.kam_owner`** (Link User, label "KAM Owner", insert after `manager_email`, in list view + standard filter, not reqd). `manager_email` is NOT the KAM owner by default. Owner resolution: shop-level override (later) → `kam_owner` → `manager_email` → `leader_email` → System Manager/configured fallback. No separate KAM mapping table.
- **D2 (Q2):** **NO new System Roles** (no Price Compliance Manager / Integration Manager / KAM roles). **No manual edits to Role Permission Manager / global DocPerm in production.** Access = service-layer brand scope from `Brand Approver` (`kam_owner` → `manager_email` → `leader_email`; System Manager = global override). New DocTypes get minimal DocPerm: **System Manager only** (Desk locked down; `/alerts` page + scoped backend APIs are the access channel). Management/Ops read-only views deferred. Any unavoidable native DocPerm/Role change must be reported and approved first. Credentials: System Manager only; never visible to KAM/frontend.
- **D3 (Q3):** No confirmed Omisell API. Phase B/C/D = schema + services + **mock ingestion only**; all Stock Safety Lock actions **Dry Run / Pending**; no real Omisell call; no irreversible stock logic. API requirement checklist for Omisell: `OMISELL_API_CHECKLIST.md`.
- **D4 (Q4):** **Frappe Cloud** deploy: commit to app repo → Frappe Cloud deploy flow → migrate via FC mechanism. No SSH/bench assumptions. One-time patches must be idempotent app patches; fixtures/schema version-controlled. Deploy plan must separate: local implementation → local migrate/test → FC deploy → production migrate → production verification. Rollback (additive changes): disable scheduler/jobs, disable route/page, `dry_run_stock_lock=1`, keep records for audit, revert commit only if needed.
- **D5 (Q5):** Approved: folder `ALERT_CENTER/`, route `/alerts`, title "Alert Center", python package **`ecentric_workspace/alerts/`**, DocType prefix `EC`.
- **D6 (UI, 2026-06-06):** `/alerts` must reuse the existing ERP visual system (homepage shell, shared tokens, panel/card/table/badge patterns). No new visual system, no external UI framework/library. UI reference report in `01_PHASE_B_PLAN.md` §8.
