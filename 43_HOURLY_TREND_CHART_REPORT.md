# Alert Center — Hourly Trend Chart on /alerts (Local Report)

Date: 2026-06-08 · Status: **BUILT — backend `C:\dev\ecentric_workspace`, frontend `C:\dev\ALERT_CENTER`. Ready to deploy.** No data/Omisell/stock write; scheduler/hooks/tasks/PM untouched.

## Files changed
- `api_dashboard.py` — new read endpoint `hourly_trend(filters)`.
- `frontend/build_alert_pages.py` — /alerts top area restructured (KPI + chart row), new chart panel + `renderHourly` SVG + CSS. Rebuilt 5 HTML.

## Backend
`api_dashboard.hourly_trend(filters)` → `{rows:[{hour:0..23, total, critical}]}`. Reuses the dashboard `_flt` (same brand/platform/status/severity/rule/sku/owner/from/to filters + brand scope) and `_where` (parameterized SQL). One grouped query: `HOUR(detected_at)`, `COUNT(*)`, `SUM(severity='Critical')`; fills all 24 hours with 0. Read-only.

## Frontend
- **Layout fixed:** the KPI `stats-strip` and the new chart now sit in one `al-top-row` (KPI left, chart right) **above** the filter panel — removing the previous top-right blank space; the filter panel starts below this row. Wraps on narrow screens.
- **Chart panel** (title "Alert trend theo giờ", subtitle "Cột = tổng alert, đường = Critical"): a hand-drawn SVG (no external libs) — 24 navy columns = total alerts/hour, a pink line+dots = Critical/hour, x-axis labels 0/4/8/12/16/20/23, baseline axis, per-bar `<title>` tooltip "Nh: N alert, M critical".
- Uses the **same dashboard filters** — `loadDash()` now also calls `api_dashboard.hourly_trend` with the current filters, so the chart refreshes with Apply/Clear/Refresh and the date/brand/etc. selectors.

Same Alert Center style; tokens only (`--navy`/`--pink`/`--gray`). ASCII-clean build.

## Build / test
All 5 pages build, **every assert passes** incl. new markers (`dash-hourly`, `api_dashboard.hourly_trend`, `renderHourly`, `al-top-row`, `al-hour-panel`). `api_dashboard.py` `py_compile` clean. ASCII-clean, no unresolved placeholders. (Sandbox build via /tmp reassembly — host builder correct; owner's Windows build reproduces it.)

## Deploy / rollback
- Backend (Windows, `C:\dev\ecentric_workspace`): branch, stage `api_dashboard.py`, PR → merge → **FC deploy (no migrate, code-only)**.
- Frontend: `cd C:\dev\ALERT_CENTER\deploy; .\deploy_alert_pages.ps1`. Ctrl+Shift+R `/alerts`.
- Rollback: revert PR; redeploy prior HTML. No data change.

## Verify
`/alerts` → top-right shows the column+line chart; change the date range / brand filter → chart updates; hover a column for the tooltip; the filter panel sits below the KPI+chart row (no blank gap).
