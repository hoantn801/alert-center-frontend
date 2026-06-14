# Phase F — M2 Local Report (Dashboard v2 + Policies Page)

Date: 2026-06-10 · Status: **M2 BUILT LOCALLY (workspace-side only — zero app-repo changes in M2; pages deploy after M4 per plan). M3 not started.**

## 1. Files changed (all in `ALERT_CENTER/`, none in the app repo)

- `frontend/build_alert_pages.py` (new multi-page builder, ~650 ln — supersedes `build_alert_center_page.py`, which is kept for history): one shared shell extraction + shared CSS + shared `window.AL` JS namespace + per-page content/JS; emits both pages with build-time acceptance asserts.
- `frontend/alert_center.html` (56.7 KB) — Dashboard v2 in place.
- `frontend/alert_policies.html` (52.2 KB) — Policies page.
- `deploy/deploy_alert_pages.ps1` + `deploy/rollback_alert_pages.ps1` (multi-page, `-Only` selector, backups per page, ASCII-checked).

## 2. UI layout summary (text — same shell/tokens/components as ever)

```
[ec-sidebar verbatim] | [topbar: Workspace / Alert Center / <Tab>]
                      | [al-subnav: Dashboard & Alerts · Policies · Rules · Locks]
/alerts:              | [stats-strip x6: Đang mở · Critical · Warning · Thiếu policy ·
                      |                  Lock chờ duyệt · Resolved (trong khoảng lọc)]
                      | [panel: filter bar — Từ/Đến (DEFAULT = last 14 days) + brand/
                      |  platform/status/severity/rule/SKU/owner + Lọc + "Mặc định 14 ngày"]
                      | [al-dash-grid 6 panels: Theo brand (al-bars) · Theo platform ·
                      |  Theo rule · Top SKU vi phạm (table) · SLA aging (4 buckets) ·
                      |  Xu hướng 14 ngày (CSS columns Mới/Resolved/Ignored + legend)]
                      | [panel: Alerts — THE EXISTING 15-column list, drawer, Resolve/
                      |  Ignore note modal, pause modal — ALL KEPT, now range-filtered]
/alerts/policies:     | [panel: header buttons — Tải CSV Template · Upload CSV · +Policy]
                      | [filter bar: brand/platform/SKU/status/owner]
                      | [11-col table → row drawer-form (15 fields + status buttons
                      |  →Active/→Paused/→Draft per server permission)]
                      | [CSV modal (wide): file input → Kiểm tra (preview) → per-row
                      |  table (#, OK?, brand, SKU, min, Lỗi) + error textarea +
                      |  Copy lỗi button → Import dòng hợp lệ (disabled until valid>0)]
```
New CSS only: `al-subnav`, `al-dash-grid`, `al-bars`, `al-trend`, `al-banner` (for M4), policy status badges — all token-based; **no external library, no sidebar change, no new visual language**.

## 3. Endpoint usage (all M1 endpoints, all scoped server-side — the pages never aggregate client-side)

`/alerts`: `api_alerts.my_scope` (bootstrap + brand dropdown) · `api_dashboard.kpis / by_dimension×3 / top_skus / aging / trend` (all receive the SAME filter object incl. date range — scope enforced in `_flt`) · `api_alerts.list_alerts / set_status` · `api_actions.list_for_alert` · `api_pauses.create_pause`. `/alerts/policies`: `my_scope` · `api_policies.list_policies / save_policy / set_policy_status / csv_template / preview_policy_csv / import_policy_csv`. Nothing unscoped; no `/api/resource` calls from pages.

## 4. States (existing patterns reused)

Loading: in-table `al-empty` "Đang tải..." rows · Empty: "Không có dữ liệu khớp bộ lọc." per panel/table · No-access: 403 on `my_scope` → `al-noaccess` screen (both pages) · Guest → `/login?redirect-to=<route>` · Errors: `al-toast` with `_server_messages` extraction; per-section dashboard fetch failures degrade silently per panel (list errors show in-table). CSV errors: per-row reasons in preview table **+ aggregated into a read-only textarea + "Copy lỗi" button** (your requirement: easy to copy).

## 5. Test results

- Build-time acceptance asserts (run on every build, just executed): ASCII-only ×2 pages, no Jinja, balanced style/script tags, markers present, **`daysAgo(14)` default present**, all 6 dashboard section ids, **`list_alerts` still present on `/alerts` (existing list kept)**, template-button + preview + import + copy-errors ids on policies page, subnav on both.
- VN labels decode correctly (sidebar "Tìm kiếm" round-trip check) ×2 pages.
- Backend suite unaffected (M2 made zero app-repo changes — branch still at `1a13fe9`; suite remains 51/51 from M1).
- Functional click-through = deploy-time UAT (M4 gate), as planned.

## 6. No-write confirmation

M2 touched only `ALERT_CENTER/` workspace files. App repo: 0 new commits, 0 pm/, hooks/client/scheduler untouched (verified branch tip unchanged). Pages call only M1 scoped endpoints; no Omisell write, no stock/buffer anything; DS1 locked. Locks UI (with the DRY-RUN banner — CSS already shipped) is M4.

## 7. Existing alert list — explicitly kept

`/alerts` retains the full 15-column list + drawer + Resolve/Ignore + pause flows below the dashboard grid (M2 acceptance assert enforces `list_alerts` usage in the built page). One behavior change as approved: the list now respects the date-range filter, defaulting to last 14 days — the "Mặc định 14 ngày" button restores defaults; users can widen the range freely.

---
**Gate:** M2 review. Next = M3 (`/alerts/rules` page: scoped rule table, drawer-form with scope-priority display + `check_rule_overlap` integration, Draft→Active approval buttons per F-2).
