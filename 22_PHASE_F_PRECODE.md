# Phase F — Alert Center Ops UI Full Build · Pre-code Proposal

Date: 2026-06-10 · Status: **PRE-CODE — one integrated phase, internal milestones M1–M4. No code until approved.**
Standing constraints honored throughout: FES-VN scheduler keeps running (monitored separately, untouched by F); no PM files; no Omisell write path; no stock/buffer/inventory write; **DS1 locked**; ERP-grade architecture (north-star rules), no UI hacks.

---

## 0. UI structure summary (requirement #9 — inspected before design)

Inspected: home shell snapshot (2026-06-05), deployed `/alerts` source (we build it from `frontend/build_alert_center_page.py`), `pm_app.html` (214KB reference app-page). Established inventory Phase F will reuse:

- **Shell (copied per page, never modified):** `ec-csrf-fetch-patch` script → navbar-hide style → master CSS (tokens `--navy/--navy-50/--gray-50..900/--green/--yellow/--yellow-50/--pink/--pink-50/--bg`) → svg icon defs → `.ecentric-app` → `.ec-sidebar` (verbatim, de-Jinja'd, user-card filled by JS) → `.ec-main` → `.topbar` (breadcrumb + icon-btns) → `.content`.
- **Established components:** homepage `stats-strip`/`stat-card s-navy|s-pink|s-yellow|s-green` (KPI cards), `panel`/`panel-header`/`panel-title`, and our 17 proven `al-*` widgets: `al-btn(.primary)`, `al-filters`, `al-tbl(-wrap)`, `al-badge` family (severity/status/action colors mapped to tokens), `al-drawer(+head/body/actions)`, `al-modal(+foot)`, `al-overlay`, `al-toast`, `al-pager`, `al-kv`, `al-empty`, `al-noaccess`, `al-actrows`.
- **Behavior patterns:** POST `/api/method/...` via patched fetch (CSRF/credentials handled), `_server_messages` error extraction, Guest→login redirect, 403→`al-noaccess` screen, vi-VN number formatting, loading rows in-table, toast feedback. All Vietnamese as entities/`\uXXXX` (PS5-safe), zero external libraries, zero Jinja.
- **Page skeleton (text mock) used by every Phase F screen:**
```
[ec-sidebar] | [topbar: Workspace / Alert Center / <Tab>]
             | [al-subnav: Dashboard · Alerts · Policies · Rules · Locks]   <- NEW, local to our pages
             | [stats-strip: stat-cards]
             | [panel: panel-header + al-filters + al-tbl + al-pager]
             | [al-drawer/al-modal for detail & edit]
```
Only NEW visual element: `al-subnav` (tab bar under topbar, styled from `nav-item` tokens) + `al-bar` (pure-CSS horizontal bars for by-dimension/trend charts — divs with token backgrounds, **no chart library**). Both minimal, token-based. Shared sidebar untouched (nav between Alert Center screens = our own subnav).

## 1. Proposed DocTypes & fields (additive-first; reuse > new)

| Concept | Decision | Detail |
|---|---|---|
| **A. Price Policy** | **EXTEND `EC Price Policy`** (no new master — avoids dual source of truth; engine already consumes it) | +`product_name` (Data), +`target_price` (Currency, RSP — display/reporting only in F), +`owner_user` (Link User, KAM), +`import_batch` (Data, read-only, CSV traceability). **status options extended:** `Draft\nActive\nPaused\nExpired` (engine filters `status=Active` already ⇒ Draft/Paused/Expired are naturally inert — zero engine change, migration-safe: existing Active/Inactive rows keep meaning; `Inactive` kept in options for back-compat). All track_changes already on. |
| **C. Rule config** | **NEW `EC Alert Rule`** (module Alerts, custom=0, track_changes=1, DocPerm SM-only like siblings) | `rule_code` (Select: below_min/above_high/severe_price_drop/possible_missing_zero), scope: `brand` (Link Brand Approver, reqd) / `platform` (Select incl. All) / `shop` (Link EC Marketplace Shop, opt) / `seller_sku` (Data, opt) / `item` (Link Item, opt); config: `enabled` (Check), `severity_override` (Select: ''/Critical/Warning/Info), `threshold_percent` (Percent — meaning per rule_code: below-min-by-X% escalation, drop %, high %), `recommend_stock_lock` (Check — only honored for the two severe rules; **hard matrix stays code-enforced: above_high/below_min can NEVER lock**), `effective_from/to` (Date), `status` (Select: `Draft\nActive\nPaused`), `approved_by`/`approved_at` (read-only). Scoping priority mirrors policy lookup (SKU > shop > platform > brand). |
| **D. Lock review** | **EXTEND `EC Alert Action`** | +`review_status` (Select: `\nPending Review\nApproved\nRejected`), +`reviewed_by` (Link User, RO), +`reviewed_at` (Datetime, RO), +`review_note` (Small Text). DS1 audit fields already exist (buffer/actual/available/locked_quantity/release_strategy) — F **displays** them; they stay empty until the DS1 read gate (shown as "awaiting DS1 gate"). |
| B. Dashboard | no schema — aggregation endpoints over existing tables (D.1 indexes serve them) | — |

No DocType permissions change anywhere (all SM-only Desk; service layer = the access path). No new roles.

## 2. Page/UI architecture

4 Web Page records sharing one builder (extend `frontend/build_alert_center_page.py` → multi-page: shared shell + per-page content blocks; one source of truth for shell/subnav/widgets):

| Route | Page | Content |
|---|---|---|
| `/alerts` | **Dashboard v2 + alert list** (upgrade in place) | KPI strip (Open, Critical, Warning, Missing policy, Lock pending review, Resolved today) · `al-bar` sections: by brand / by platform / by rule · Top violating SKUs (table, count+latest) · SLA aging buckets (<4h / 4–24h / 1–3d / >3d unresolved) · 14-day Resolved-vs-Ignored trend (CSS bars) · existing filterable alert table + drawer (kept; +SKU + date-range filters already exist; add shop filter) |
| `/alerts/policies` | Policy Master | filter bar (brand/platform/shop/SKU/status/owner) · table · drawer-form create/edit (single) · **CSV upload modal**: file → server-side parse → per-row validation preview table (errors highlighted) → confirm commit → batch report. Status transitions per permission (§4) |
| `/alerts/rules` | Rule Config | scoped rule table grouped by brand · drawer-form (rule_code, scope, thresholds, severity, recommend-lock checkbox with hard-matrix note) · Draft→Active button visible only to approvers · effective dates · audit column (approved by/at) |
| `/alerts/locks` | Stock Lock Control (DRY-RUN) | KPI mini-strip (Pending review / Approved / Rejected / Skipped-by-pause) · action table (alert link, SKU, qty proposed*, lock_until, release strategy, DS1 audit fields [placeholder until gate], status+review badges) · drawer: Approve (note opt) / Reject (note req) · Pause manager section: list + create/cancel pauses (reuses existing endpoints) · banner: "DRY-RUN ONLY — real buffer write locked by DS1" |

*proposed qty: until the DS1 read gate, stock numbers are unknown; the column shows order-line qty context + "—(DS1)" for buffer/actual — explicitly honest, no fake data.

## 3. API endpoints (all: `require_alert_center_access()` first line, server-side brand scope, writes POST-only, no DocPerm reliance)

New flat modules (same convention as api_alerts/api_pauses): **`api_policies.py`** — `list_policies`, `get_policy`, `save_policy` (create/edit, scope+field validation, status guard per §4), `set_policy_status`, `preview_policy_csv` (parse+validate only, NOTHING written), `import_policy_csv` (commits previewed batch, per-row scope check, `import_batch` tag) · **`api_rules.py`** — `list_rules`, `save_rule` (Draft only for KAM), `activate_rule`/`pause_rule` (approvers only, stamps approved_by/at) · **`api_dashboard.py`** — `kpis`, `by_dimension(dim ∈ brand|platform|shop|rule_code)`, `top_skus(limit)`, `aging`, `trend(days=14)` (GROUP BY + COUNT, scope-filtered, served by D.1 indexes) · **`api_actions.py` extension** — `list_actions(filters)` (beyond per-alert), `review_action(name, decision, note)` (Approve/Reject dry-run rows only; rejecting sets status=Cancelled + review fields; approving stamps review fields, status unchanged Dry Run). Existing endpoints untouched.

## 4. Permission model (no new roles — D2 unchanged; service-layer only)

Existing capability table extended in `permissions.py` (pure additions): `can_manage_policy(user, brand)` = kam/manager/supervisor (create/edit/Draft↔Active↔Paused within own brand; Expired auto by dates at read time + nightly later) · `can_activate_rule(user, brand)` = manager/leader/supervisor (**KAM creates/edits Draft rules only — activation is the approval step**) · `can_review_lock(user, brand)` = kam/manager/leader/supervisor (dry-run era; flipping any brand to real execution remains SM + DS1 gate, far away) · dashboard/list = any scoped user. CSV import = `can_manage_policy` per-row (a row for an out-of-scope brand fails validation, shown in preview). Desk stays SM-only.

## 5. Audit model

track_changes (Version) on all four DocTypes (already on; EC Alert Rule ships with it) · review/approval stamped fields (who/when/note) · CSV: every created/updated row carries `import_batch` (timestamp+user hash) + one summary Comment on each touched doc is skipped (noise) — instead a per-batch report returned to UI AND a Comment on the brand's BIS record (established audit spot) · policy/rule status changes go through `doc.save()` (never db_set) so Versions capture them · no hard delete anywhere (status fields only).

## 6. Engine ↔ policy/rule integration (zero-regression design)

- Policy: engine already reads `EC Price Policy` with `status=Active` — new Draft/Paused/Expired rows are invisible to it by construction. `target_price` NOT consumed by engine in F (display only; future decision could make it a baseline source).
- Rules: `services/rules.py` stays the pure default. New thin overlay in `alert_engine`: after policy lookup, fetch matching `EC Alert Rule` rows (Active, in-window, best-scope-wins like policy priority) → may override severity, thresholds (maps to the same parameters rules.evaluate already takes: high_alert_percent/severe_drop_percent + new below-min escalation percent), and `recommend_stock_lock` for the two severe rules only. **No matching rule rows ⇒ behavior byte-identical to today** (regression suite asserts this). C2 single-winner priority and the hard action matrix (high/below_min never lock) remain code-enforced and rule-config CANNOT widen them.

## 7. Dry-run lock recommendation flow (unchanged core + review layer)

Engine path stays: policy(+rule overlay) → eligible → EC Alert Action Pending → worker → **Dry Run** (or Skipped by pause/credential). Phase F adds: new actions get `review_status="Pending Review"`; KAM/Lead approve (audit stamp, stays Dry Run) or reject (→ Cancelled + note). This builds the human workflow that the future real executor will REQUIRE approval from (when DS1 opens, the executor will only act on `review_status=Approved` — designed now, enforced later). No stock numbers are fetched in F (stock READ is itself behind the DS1 gate, items 10–12d).

## 8. CSV/Excel upload approach

CSV-first (Excel→CSV is a KAM-side save-as; native xlsx parsing needs no new lib server-side via openpyxl IF frappe ships it — verified at M1, else CSV only, stated in UI). Flow: file → POST raw text → **server-side `csv` module parse** → per-row validation (required fields, brand scope, Link existence, dates, numbers via locale-safe parse — NEVER `parseFloat` on vi-VN strings per known footgun; server parses) → preview response (ok/error per row) → user confirms → `import_policy_csv` commits only valid rows in one batch (per-row insert with `import_batch`, transaction per batch) → report {created, updated (matched by brand+platform+shop+sku key), failed[]}. Template CSV downloadable from the page (static header row). Cap: 500 rows/batch (timebox-safe).

## 9. Test plan

M1 backend: schema additive checks; policy status inertness (Draft/Paused/Expired never matched by `find_policy`); rule overlay matrix (override severity/threshold; absent rules ⇒ **golden regression: existing 39-test suite + Phase C/E suites unchanged**); hard-matrix guard (rule row with recommend_stock_lock on below_min is ignored + flagged); review_action permission matrix + state machine (reject ⇒ Cancelled, approve keeps Dry Run; non-scoped user 403); CSV preview/commit (valid, out-of-scope row, bad number "5.000.000" vi-VN case, duplicate key update-vs-create, 501-row cap). Dashboard endpoints vs SQL spot checks + scope. UI/UAT: KAM end-to-end journey (input policy → see violation alert next pull → review dry-run lock → pause SKU), Lead approval journey, no-access states, mobile sanity — **UAT precondition: FES-VN policies entered by the KAM via the new UI** (real usage as the test).

## 10. Deploy/rollback plan

Two drops inside one phase (per-turn confirmed as always): **Drop 1** = app PR (schema + endpoints + engine overlay + tests; FC migrate) → backend probes (403 matrix, regression suites, policy-inertness probe on prod data) → **Drop 2** = 4 Web Pages via extended deploy script (deploy_alert_pages.ps1, per-page markers, backups, rollback script unpublishes all/each). Rollback: pages unpublish (seconds, per page); endpoints/overlay revert via PR; schema additions stay harmlessly (new DocType invisible to non-SM); **no engine behavior change survives a revert because default-path is byte-identical**. FES-VN scheduler unaffected by both drops (no api_omisell/tasks/hooks changes in F).

## 11. Internal milestones (one phase, gates internal — single integrated build)

**M1** backend foundation: schema (3 extends + 1 new DocType) + permissions additions + api_policies/api_rules/api_dashboard/review_action + engine rule-overlay + full test suite → local report (gate: your OK on the M1 diff = the only schema gate). **M2** `/alerts` dashboard v2 rebuild + `/alerts/policies` page incl. CSV flow. **M3** `/alerts/rules` page + activation workflow. **M4** `/alerts/locks` page + pause manager + integrated UAT script + deploy drops 1&2. M2–M4 are frontend-only iterations on the shared builder (no further schema), reported together or per-milestone as you prefer — **one branch, one PR for code, one page-deploy batch.** Estimated shape: M1 ≈ the largest; M2–M4 each ≈ a page build like Phase E's.

## 12. Explicitly out of scope

Real Omisell buffer/stock write AND stock READ (both behind DS1 items 10–12d) · executor acting on Approved reviews (designed-for, not built) · notifications (Teams/Lark/email) · shared-sidebar nav item (still deferred — subnav lives inside our pages) · multi-brand scheduler expansion (separate gate after 24h review) · nightly reconciliation (D.2) · archive execution · ERPNext Sales Order/Pricing Rule integration · target_price as engine input (future decision) · Excel native parsing if openpyxl unavailable.

---
**Decisions needed with your approval:** F-1 confirm `EC Price Policy` extension over a new master (recommended) · F-2 confirm rule approval split (KAM=Draft, Lead/SM=Activate) · F-3 confirm `/alerts` becomes Dashboard v2 in place (vs keeping old list page separate) · F-4 milestone reporting cadence (per-milestone reports vs single final report before deploy).
