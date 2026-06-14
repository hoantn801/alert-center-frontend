# Alert Center — Phase B Implementation Plan

Date: 2026-06-06 · Status: **PLAN — awaiting "go" before any code/commit.** Implements decisions D1–D6 (`00_PRECODE_REPORT.md` §17). Scope: schema + permission utilities only. No Omisell calls, no stock lock execution, no scheduler jobs, no frontend yet. Dry-run only.

---

## 1. DocType delivery mechanism (decision needed inside this plan — D4 driven)

**Proposal: app-owned DocTypes** in a new Frappe module **`Alerts`** inside the existing `ecentric_workspace` app (JSON files in git, installed by `migrate` during Frappe Cloud deploy).

Why not the existing convention (custom=1 DocTypes created via API scripts, like the 31 live ones): D4 requires version-controlled schema + Frappe Cloud deploy flow + no ad-hoc production writes. App-owned JSON gives: git history, deterministic migrate, FC-native, clean rollback (revert commit). This is also the north-star direction (CLAUDE.md maintainability).

Consequence to note explicitly (per D2 "report any native DocPerm requirement"): each new DocType JSON ships its **own** permission block — **System Manager only** (read/write/create; delete System Manager only, and business rule = never hard delete, status fields instead). This is NOT a change to any existing role/DocPerm and is not a manual Role Permission Manager edit — it ships as reviewed code. **No existing DocType's permissions are touched.** Desk access to all new DocTypes is therefore System Manager only; everyone else goes through `/alerts` + scoped APIs (D2 compliant).

`Brand Approver` itself is custom=1 (lives in DB only) → `kam_owner` goes in as **Custom Field fixture** (exact same pattern as PM v2's `Project-ec_department`), synced automatically on migrate.

## 2. Exact files to add / change

**App repo `ecentric_workspace` (github.com/hoantn801/ecentric_workspace, branch `main`, FC-deployed). Work on feature branch `alerts-phase-b`, merge after local tests.**

| File | A/C | Content |
|---|---|---|
| `ecentric_workspace/modules.txt` | Change | + line `Alerts` |
| `ecentric_workspace/hooks.py` | Change | fixtures filter list += `"Brand Approver-kam_owner"`. Nothing else (no scheduler in Phase B). |
| `ecentric_workspace/fixtures/custom_field.json` | Change | + 1 record: `Brand Approver-kam_owner` (see §3) |
| `ecentric_workspace/alerts/__init__.py` | Add | empty |
| `ecentric_workspace/alerts/permissions.py` | Add | brand-scope utilities (see §5) |
| `ecentric_workspace/alerts/doctype/__init__.py` | Add | empty |
| `ecentric_workspace/alerts/doctype/ec_marketplace_shop/{__init__.py, ec_marketplace_shop.json, ec_marketplace_shop.py}` | Add | §4.1 |
| `ecentric_workspace/alerts/doctype/ec_brand_integration_settings/{...}` | Add | §4.2 |
| `ecentric_workspace/alerts/doctype/ec_price_policy/{...}` | Add | §4.3 |
| `ecentric_workspace/alerts/doctype/ec_marketplace_order_log/{...}` | Add | §4.4 |
| `ecentric_workspace/alerts/doctype/ec_marketplace_order_item/{...}` | Add | §4.5 (istable) |
| `ecentric_workspace/alerts/doctype/ec_alert/{...}` | Add | §4.6 |
| `ecentric_workspace/alerts/doctype/ec_alert_action/{...}` | Add | §4.7 |
| `ecentric_workspace/alerts/doctype/ec_automation_pause/{...}` | Add | §4.8 |
| `ecentric_workspace/alerts/tests/{__init__.py, test_phase_b.py}` | Add | §7 tests (run locally) |

**Workspace folder `ALERT_CENTER/` (docs/ops only, not deployed):**

| File | A/C | Content |
|---|---|---|
| `deploy/verify_phase_b.ps1` | Add | **READ-ONLY** production verification: GET each DocType meta, check track_changes/unique/kam_owner field. `[OK]/[WARN]/[ERR]`, ASCII-only, idempotent. No writes. |
| `01_PHASE_B_PLAN.md` | This file | — |

**NOT in Phase B:** `patches.txt` unchanged (no patch needed — fixtures + new DocTypes cover everything). No Web Page. No Server Scripts. No api/ services (Phase C). No changes to any existing module.

## 3. Custom Field (the only touch on an existing DocType)

```
name: Brand Approver-kam_owner · dt: Brand Approver · module: Ecentric Workspace
fieldname: kam_owner · label: KAM Owner · fieldtype: Link · options: User
insert_after: manager_email · reqd: 0 · in_list_view: 1 · in_standard_filter: 1
description: "Daily KAM responsible for marketplace alerts (Alert Center owner resolution). Not the approval manager."
```

Filling `kam_owner` on the 7 existing Brand Approver records = production data entry, done by you in Desk after deploy (or give me the list and I seed it with per-turn confirmation). Field stays optional; resolution falls back per D1 chain when empty.

## 4. DocTypes to add (all: module `Alerts`, `custom: 0`, `track_changes: 1`, perms = System Manager only, no workflow)

Field lists per approved spec (report §7 + your original spec). Schema-relevant specifics only:

1. **EC Marketplace Shop** — autoname `field:shop_code`. Fields: shop_code, shop_name, platform (Select Shopee/Lazada/TikTok/Other), brand (Link **Brand Approver**, reqd, in_standard_filter), `omisell_shop_id` (Data, **unique=1**), `kam_owner` (Link User, optional shop-level override — D1 priority 1), status (Select Active/Inactive, default Active). Controller: normalize/strip omisell_shop_id.
2. **EC Brand Integration Settings** — autoname `format:EC-BIS-{####}`. brand (Link Brand Approver, reqd), integration_type (Select: Omisell, default), enabled (Check 0), base_url (Data), api_key/api_secret/token (**Password**), credential_status (Select Active/Inactive/Expired, default Inactive), last_sync_at (Datetime, read-only), `dry_run_stock_lock` (Check, **default 1**), default_platform_scope (Select All/Shopee/Lazada/TikTok, default All), notes (Small Text). Controller `validate()`: enforce one record per (brand, integration_type). Secrets only ever read server-side via `get_password()` (Phase C+); never in list views, logs, or API responses.
3. **EC Price Policy** — autoname `format:EC-PP-{#####}`. brand (Link Brand Approver, **reqd**), platform (Select incl. All), shop (Link EC Marketplace Shop), item (Link Item, optional), seller_sku (Data), min_price/reference_price (Currency), high_alert_percent (Percent), severe_drop_percent (Percent, default 70), enable_stock_safety_lock (Check 0), stock_lock_duration_minutes (Int, default 120), effective_from/effective_to (Date), status (Select Active/Inactive, default Active). Controller: effective_to ≥ effective_from; at least one of item/seller_sku unless intentional brand-level fallback (flag field `is_brand_fallback` Check 0 — makes priority 6 explicit, per your rule B.6). Importable with standard Frappe Data Import.
4. **EC Marketplace Order Log** — autoname `format:EC-MOL-{######}`. source_system (Select Omisell/ERP/Manual, default Omisell), external_order_id (Data, reqd), `order_key` (Data, **unique=1**, = `{source_system}|{external_order_id}`, set in controller), platform, shop (Link EC Marketplace Shop), brand (Link Brand Approver — empty allowed = unresolved → missing_brand_mapping path), order_datetime, order_status (Data), raw_payload_hash (Data), sync_status (Select Pending/Success/Failed), sync_error (Small Text), items (Table → EC Marketplace Order Item). No submit/docstatus — plain records, zero accounting/inventory impact.
5. **EC Marketplace Order Item** (istable=1) — external_line_id, item (Link Item, optional), seller_sku, product_name, quantity (Float), list_price/seller_discount/platform_discount/customer_paid_price/unit_check_price/min_price_at_check/baseline_price_at_check (Currency), check_result (Select OK/Below Min/Above High/Severe Price Drop/Possible Missing Zero/Missing Rule/Missing Brand Mapping).
6. **EC Alert** — autoname `format:EC-AL-{######}`. Per spec; `rule_code` Select = below_min, above_high, severe_price_drop, possible_missing_zero, missing_policy, **missing_brand_mapping, missing_integration_credential, stock_lock_api_failed**; status Select Open/In Review/Resolved/Ignored (default Open); brand Link Brand Approver (in_standard_filter); shop Link EC Marketplace Shop; item Link Item + seller_sku Data; owner_user Link User; reference_doctype (Link DocType) + reference_name (**Dynamic Link**); `dedupe_key` (Data, **unique=1**); currencies/percent/datetimes per spec; resolution_note Small Text. Controller: status transitions append to comment trail (native), resolved_at/resolved_by auto-set.
7. **EC Alert Action** — autoname `format:EC-AA-{######}`. alert (Link EC Alert, reqd), action_type (Select Notify Only/Stock Safety Lock/Release Stock Safety Lock — **no Off Listing value exists**), status (Select Pending/Processing/Success/Failed/Cancelled/Skipped/**Dry Run**, default Pending), brand (Link Brand Approver, reqd), platform/shop/item/seller_sku/external_product_id, previous_available_stock (Float), lock_until (Datetime), lock_reason (Small Text), release_status (Select Not Required/Pending/Released/Failed, default Not Required), requested_at/executed_at, executed_by (Link User), api_response/error_message (Small Text), `dedupe_key` (Data, **unique=1**).
8. **EC Automation Pause** — autoname `format:EC-AP-{#####}`. automation_type (Select: Stock Safety Lock), brand (Link Brand Approver, reqd), platform (Select incl. All), shop (Link EC Marketplace Shop), item/seller_sku, paused_by (Link User), pause_from/pause_until (Datetime, reqd), reason (Small Text), status (Select Active/Expired/Cancelled, default Active). Controller: pause_until > pause_from. (Active→Expired scheduler = Phase C.)

## 5. Permission approach — no new roles (D2)

`ecentric_workspace/alerts/permissions.py` — pure service-layer, modeled on `pm/permissions.py`, **zero hardcoded users**, fail-safe:

- `get_allowed_brands(user)` → `"*"` for Administrator / System Manager role; else `{brand_code: role}` dict from active `Brand Approver` records where user ∈ {`kam_owner`, `manager_email`, `leader_email`} (role = kam / manager / leader; highest wins if multiple).
- `require_alert_center_access(user)` → throw `PermissionError` unless `"*"` or ≥1 brand.
- `require_brand_access(user, brand)` → throw unless allowed.
- Capability helpers (used by Phase C/E services): `can_handle_alert(user, brand)` (kam/manager/leader → In Review/Resolve/Ignore), `can_create_pause(user, brand)` (kam/manager), `can_cancel_pause(user, brand)` (manager/leader/SM), `can_manage_credentials(user)` (**System Manager only**), `can_execute_action(user)` (System Manager only for MVP).
- All future list APIs filter by `get_allowed_brands` server-side; KAM default view = own brands automatically.

Desk leakage is impossible because DocPerm grants nothing below System Manager (§1). If we ever need Desk access for non-SM users, that's a reported-and-approved change, not part of this phase.

## 6. Fixture / patch summary

- Fixture: 1 Custom Field (`Brand Approver-kam_owner`) — auto-synced on migrate, idempotent.
- Patches: **none** for Phase B.
- New module `Alerts` in modules.txt — additive.
- No roles, no DocPerm edits to existing DocTypes, no Property Setters, no Website Settings, no Web Pages, no Server Scripts.

## 7. Test cases (run on local dev site before any FC deploy)

`alerts/tests/test_phase_b.py` (+ manual local smoke):

1. Migrate clean (no errors); all 8 DocTypes exist; module = Alerts.
2. `track_changes == 1` on all 8 (assert via `frappe.get_meta`).
3. Unique constraints: duplicate `EC Alert.dedupe_key`, `EC Alert Action.dedupe_key`, `EC Marketplace Order Log.order_key`, `EC Marketplace Shop.omisell_shop_id` each raise on insert.
4. `Brand Approver.kam_owner` exists, fieldtype Link→User, after manager_email.
5. Link integrity: EC Alert.brand → Brand Approver; shop → EC Marketplace Shop; item → Item; invalid brand code rejected.
6. BIS: second record for same (brand, integration_type) rejected; api_key set then read back via resource API as user ≠ SM → not readable (perm denied); `dry_run_stock_lock` default 1.
7. Policy validation: effective_to < effective_from rejected; brand reqd enforced.
8. Permissions matrix (seed test users + 2 test Brand Approver records TB-A/TB-B): kam of TB-A → allowed_brands == {TB-A: kam}; manager/leader mapping correct; user with no binding → `require_alert_center_access` throws; System Manager → `"*"`; `can_create_pause` true for kam/manager, false for leader; `can_cancel_pause` true for manager/leader, false for kam; `can_manage_credentials` false for everyone except SM. KAM-A has no access to TB-B (test 9 of master plan).
9. Non-SM user `frappe.get_list("EC Alert")` (with permissions) → PermissionError/empty — Desk lockdown verified.
10. No hard delete path: non-SM delete attempt on EC Alert fails.

## 8. UI reference report (for Phase E — answers the 5 UI questions; no frontend code in Phase B)

[FACT, snapshot 20260605_230003 + `pm/frontend/pm_app.html`]

1. **Reference pages:** homepage (`home` Web Page) = layout shell + dashboard cards reference; **PM v2 `pm_app.html`** = app-page reference (filter bar, data table, buttons, badges, toasts — the most recent, cleanest implementation); `all-ticket` = list/filter precedent.
2. **Reused conventions:** shared CSS custom properties used by both home and PM (`--navy`, `--navy-50`, `--navy-700`, `--gray-50…900`, `--green`, `--yellow`, `--yellow-50`, `--pink`, `--pink-50`, `--bg`); shell = `.ec-sidebar` (copied verbatim, **never modified** — hard "no") + `.topbar`; cards = `.stats-strip` / `.stat-value` / `.stat-label` / `.stat-meta` (homepage) for the 6 KPI cards; panels = `.panel` / `.panel-header` / `.panel-title` / `.panel-action`; widgets = PM patterns `pm-btn`, `pm-input`, `pm-sel`, `pm-tbl`, `pm-badge`, `pm-tag` re-namespaced `al-*` inside the page (pages are self-contained by convention — each Web Page embeds its own CSS copy).
3. **Files (Phase E):** `ALERT_CENTER/frontend/alert_center.html` (single file, marker `<script id="ec-alert-center">`) + `deploy/deploy_alert_page.ps1` + `deploy/rollback_alert_page.ps1`. One new Web Page record `alert-center`, route `alerts`.
4. **Same shell as homepage/PM?** Yes — copy the current home shell markup+tokens into the page (self-contained, consistent with all 40 existing pages). It will render as the same ERP, same sidebar, same typography.
5. **UI gaps needing minimal new CSS:** severity badge colors mapped to existing tokens (Critical → `--pink`/`--pink-50`, Warning → `--yellow`/`--yellow-50`, Info → `--gray-*`, Resolved → `--green`); a date-range filter input (styled as `pm-input`); nothing else. **No new framework, no external libraries, no new visual system** (D6).

## 9. Deploy plan (Frappe Cloud — D4)

1. **Local implementation:** branch `alerts-phase-b` in app repo; `python -m py_compile` all new files.
2. **Local migrate/test:** `bench --site <local dev site> migrate` → run §7 tests → manual smoke in local Desk (create shop/policy/alert as Administrator; confirm non-SM blocked).
3. **Frappe Cloud deploy:** merge → push `main` → FC dashboard → Deploy (FC builds bench image and pulls app). **Per-turn confirmation before push/deploy, per A33.**
4. **Production migrate:** runs inside FC deploy step (FC executes migrate during update); confirm in FC deploy log: fixture synced + 8 DocTypes created.
5. **Production verification (read-only):** run `ALERT_CENTER/deploy/verify_phase_b.ps1` (GET metas, check track_changes/unique/kam_owner); fresh `snapshot_live_state.ps1`; append handover log entry. Then you fill `kam_owner` on the 7 Brand Approver records (or approve me seeding them).

No data is written to production by the deploy itself beyond schema + 1 custom field. No scheduler activates (none registered). Nothing user-visible changes (`/alerts` doesn't exist yet).

## 10. Rollback plan

Everything additive → rollback = revert commit on `main` + FC re-deploy. New DocTypes: can be left in place harmlessly (no perms below SM, no UI, no jobs) — preferred for audit; physical removal only with your explicit approval. `kam_owner` field: leave (harmless) or remove fixture + delete Custom Field record with approval. No destructive step exists in this phase; created test records (local only) never reach production.

## 11. Risk

**LOW.** Surface area on production = 1 Custom Field on Brand Approver (additive, optional) + 8 net-new DocTypes invisible to all non-SM users. Zero existing code paths touched. Main residual risks: (a) FC deploy pipeline quirks (first time this session — mitigated by deploy-log check + read-only verify script); (b) fixture sync overwrites manual edits to that one Custom Field in future (fixture is now its owner — documented here).

## 12. Out of scope for Phase B (comes next)

Phase C: services (pricing/policy_lookup/baseline/rules/alert_engine + dedupe), pause-expiry + action-queue scheduler (dry-run worker). Phase D: mock ingestion endpoint. Phase E: `/alerts` page per §8. Phase F: full test matrix + verification + handover.
