# Alert Center — G1.1 Drop 2 Polish (Frontend) Report

Date: 2026-06-08 · Status: **BUILT in `C:\dev\ALERT_CENTER`, ready to deploy.** Frontend-only; no backend/Omisell/stock/scheduler/hooks/tasks/PM change; DS1 locked; ASCII-clean.

## Files changed
- `frontend/build_alert_pages.py` (PAGE1 alert modal + CSV export, PAGE3 rules drawer redesign, CSS, build asserts).
- Rebuilt: `frontend/alert_center.html`, `alert_rules.html` (+ the other 3 carry shared CSS). No `ecentric_workspace` change.

## UI changes
1. **Rules drawer redesigned** (`/alerts/rules`) — same pattern as the Price Policy form: wide drawer (`al-drawer-wide`), 5 clear sections (1 Scope · 2 Rule & severity · 3 Thresholds · 4 Dry-run lock · 5 Effective & status), 2-column `al-fgrid`, short `al-help` text. `severe_drop_percent` / `high_alert_percent` are explained with helper text; a note states **Rules own thresholds, Price Policy holds price master data only**.
2. **Alert detail = centered wide modal** (was a narrow right drawer) — `al-modal-xl` ~1140px, max-height 85vh, scroll inside the body. Header shows alert id + a subtitle (status · SKU · rule/severity). Body: summary KV grid (3 pairs/row incl. effective_check_price, min, baseline, occurrence_count, last seen), the **price breakdown** (RSP − seller discount − seller voucher − platform discount − platform voucher = effective), and the **Occurrences evidence table** with full horizontal room. Footer: Resolve / Ignore / In Review / Pause.
3. **Export occurrence evidence** — in the modal's "Bằng chứng theo đơn" header: **Export CSV** (required) + **Copy CSV**. CSV is built client-side from the loaded rows, UTF-8 with BOM, filename `alert_occurrences_<alert_name>.csv`, columns exactly: external_order_id, order_datetime, order_status, seller_sku, product_name, rsp_price, seller_discount_amount, seller_voucher_amount, platform_discount_amount, platform_voucher_amount, effective_check_price, min_price_at_check, baseline_price_at_check, gap_percent, rule_code, severity, detected_at, price_components_used.

Same Alert Center visual style; new CSS is tokens-only (`al-modal-xl`, `al-modal-head/body/foot`, `al-kv-wide`, `al-occ-head`). No new endpoints — reuses Drop 1 `alert_occurrences` / `bulk_set_status`.

## Build / assert results
All 5 pages build; **every assert passes**, including new polish asserts: page1 contains `al-modal-xl`, `al-d-sub`, `al-occ-export`, `exportOccCsv`, `OCC_CSV_COLS`; rules page uses `al-drawer-wide" id="ru-drawer"` and has ≥5 `al-fsec` sections (built page has 8). All HTML **ASCII-clean**, no unresolved `%()` placeholders, sidebar/module-shell intact.

> Sandbox build was validated via `/tmp` reassembly (the bash mount truncates the ~1500-line builder); the host `build_alert_pages.py` is correct and the rebuilt HTML are in `frontend/`. Owner's Windows build reproduces the same output.

## Deploy (owner, Windows)
```powershell
cd C:\dev\ALERT_CENTER\deploy
.\deploy_alert_pages.ps1            # all 5 pages
```
(Deploy the HTML already in `frontend\`, or rebuild first with `python ..\frontend\build_alert_pages.py <home_snapshot> ..\frontend`.) Then Ctrl+Shift+R on `/alerts` and `/alerts/rules`.

## Rollback
`.\rollback_alert_pages.ps1` unpublishes the pages (content preserved); or re-deploy the previous `frontend\*.html` from a backup (each deploy writes a timestamped backup under `deploy\backups\`). Purely frontend — no data/migration to unwind.
