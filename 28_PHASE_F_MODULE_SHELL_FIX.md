# Phase F — Module Shell / Sidebar Fix (pre-Drop-2 correction)

Date: 2026-06-10 · Status: **FIXED LOCALLY. Drop 2 was HELD for this; now ready for review.** Workspace-side only (app repo untouched at `1a13fe9`).

## The problem you flagged

The Alert Center pages reused the **generic homepage nav-section** (Trang chủ / Tổng quan / Phê duyệt / Chấm công / Nghỉ phép …) in the left sidebar. That made the pages feel like the homepage, not a dedicated module — even though shell/tokens/components were correct.

## How the Approval module does it (inspected)

The Approval page keeps the **same `.ec-sidebar` shell** (brand header, search, footer/user card) but **swaps the `<nav class="nav-section">` content** for an Approval-specific menu (Dashboard · All Tickets · MSO/SO/PO/REC Request · GBS · Docs …) with grouped `nav-label`s. Same visual language, module-specific navigation. That is exactly the principle you asked for.

## The fix

Builder now extracts the home shell, **replaces the nav-section with an Alert Center module menu** (per-page active item), and keeps brand/search/footer/topbar/tokens identical. No new CSS, same `.nav-item`/`.nav-label` classes and existing svg icons.

**Alert Center menu (all 4 pages):**
```
ALERT CENTER
  Dashboard            (i-grid)   -> /alerts          [active on dashboard]
  Alerts               (i-bell)   -> /alerts          (the list lives on the dashboard page)
  Price Policies       (i-wallet) -> /alerts/policies [active on policies]
  Rules                (i-settings)-> /alerts/rules   [active on rules]
  Locks                (i-target) -> /alerts/locks    [active on locks]
OPERATIONS
  Automation Pauses    (i-clock)  -> /alerts/locks    (pause manager section)
  Integration Health   (i-sparkles)-> /alerts         (placeholder route until its own page in a later phase)
WORKSPACE
  Back to Workspace    (i-home)   -> /                (escape hatch)
```
Active item is set per route at build time and re-confirmed by the existing nav-active script on load. **Generic homepage links fully removed** (build assert greps for `coming-soon?tool=` and HR items → must be absent).

## Breadcrumb (your spec — verified)

`Workspace / Alert Center / Dashboard` · `… / Policies` · `… / Rules` · `… / Locks` (topbar per page).

## Dashboard content (confirmed Alert-Center, not homepage)

`/alerts` shows ONLY Alert Center data: 6 KPI cards (Open · Critical · Warning · Missing policy · **Lock pending review** · Resolved) → by-brand / by-platform / by-rule bars → Top violating SKUs → SLA aging buckets → 14-day trend → the full filterable alert list + drawer. No homepage widgets (no greeting stats, news, policies, attendance).

## Files changed (workspace only)

`frontend/build_alert_pages.py` (+`ASIDE_TEMPLATE` placeholder swap + `ac_aside(route)` + module-shell asserts) → rebuilt `alert_center.html` (55.4 KB) / `alert_policies.html` (50.8 KB) / `alert_rules.html` (49.5 KB) / `alert_locks.html` (52.6 KB). Deploy/rollback scripts unchanged (same files/markers). App repo: 0 changes; backend suite still 51/51.

## Build/verify results (just run)

All milestone asserts green + **new M2b module-shell asserts**: every page has `ec-sidebar` shell + the AC menu (Price Policies/Rules/Locks present) + "Back to Workspace" + **zero `coming-soon?tool=` / HR nav leakage**. Per-page sidebar dump confirms correct active item; breadcrumbs confirmed.

## Same constraints held

No new external library · no new visual language (same tokens/spacing/badges/cards/typography) · sidebar **structure** is now module-specific but **style** is identical to ERP · app repo / hooks / scheduler / Omisell client untouched · DS1 locked.

---
**Gate:** review this fix → resume Drop 2 staged rollout (deploy `alert-center` first → verify dashboard + module sidebar + alert list → then policies/rules/locks one by one → recheck FES-VN `pull_status`).
