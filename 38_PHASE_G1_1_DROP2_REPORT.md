# Alert Center — Phase G1.1 Drop 2 (Frontend) Local Report

Date: 2026-06-08 · Status: **FRONTEND BUILT in `C:\dev\ALERT_CENTER` — ready to deploy. Frontend-only; no backend/scheduler/hooks/tasks/PM change; DS1 locked; ASCII-clean.** Backend G1.1 Drop 1 already deployed + verified (Case EC-AL-000662 / Occurrence EC-AOCC-000675).

---

## 1. Features implemented (`frontend/build_alert_pages.py`)

**/alerts (alert_center.html):**
- **occurrence_count column** (`Đơn`) in the list — shows how many violating order lines each Case aggregates (pill `.al-occ-n`).
- **Checkbox column** + **select-all on page** (`al-chk-all`) + a **bulk bar** (`al-bulkbar`) that appears when ≥1 row is checked, with **Resolve / Ignore / In Review selected** → `api_alerts.bulk_set_status` (per-row scoped; note prompted for Resolve/Ignore). Clicking a checkbox does not open the drawer.
- The list "Actual" column now shows `effective_check_price` (falls back to actual_price).
- **Alert drawer = wide**, with a **price breakdown** box and an **Occurrences evidence table** (`api_alerts.alert_occurrences`):
  - Breakdown (from the latest occurrence): `RSP − Seller discount − Seller voucher − Platform discount − Platform voucher = Effective check price`, plus `price_components_used`, min, baseline.
  - Evidence table (one row per order line): Omisell order number, order time, order status, SKU/product name, RSP, the four component amounts, effective_check_price, min, gap, price_components_used, rule_code + severity.
  - Drawer KV adds: effective check price, price_components_used, occurrence_count.

**/alerts/policies (alert_policies.html):**
- **`high_alert_percent` and `severe_drop_percent` inputs removed** from the Policy drawer (and dropped from the save FIELDS list) — Policy now holds price master data only.
- Neutral helper note: thresholds now live in Rules.

**/alerts/rules (alert_rules.html):**
- New section "Ngưỡng theo rule" with **`severe_drop_percent`** and **`high_alert_percent`** inputs (2-col grid + helper text explaining fallback to Policy then system default). Added to the rule save fields. Generic `threshold_percent` kept (labelled "chung").

Same `.al-*` Alert Center style throughout; new CSS is tokens-only (`.al-bulkbar`, `.al-chk-col`, `.al-occ-n`, `.al-breakdown`, `.al-occ-tbl`).

---

## 2. No backend / no-write confirmation

No change to any `ecentric_workspace` file — Drop 2 is purely `build_alert_pages.py` (+ rebuilt HTML). The new UI consumes **existing** Drop 1 endpoints (`bulk_set_status`, `alert_occurrences`, `occurrence_count`/`effective_check_price`/`price_components_used` already in `list_alerts`). No Omisell write, no stock/buffer write, DS1 locked, scheduler/hooks/tasks/PM untouched.

---

## 3. Build verification

Built all 5 pages — **every assert passes**, including the new Drop 2 asserts:
- M2c: policy drawer must **not** contain `e-high_alert_percent`/`e-severe_drop_percent`; thresholds-moved helper present.
- M2/M2b: page1 contains `al-bulkbar`, `al-chk-all`, `al-row-chk`, `al-occ-n`, `al-d-occ`, `api_alerts.bulk_set_status`, `api_alerts.alert_occurrences`, `renderOcc`.
- M3: rules page contains `r-severe_drop_percent`, `r-high_alert_percent`.

All 5 HTML are **ASCII-clean** (entities/`\uXXXX`), no unresolved `%()` placeholders, sidebar/module-shell intact. The rebuilt HTML are in `frontend/`.

> Sandbox note: the bash mount of `C:\dev\ALERT_CENTER` truncates reads of the freshly-edited 1465-line builder, so the build was validated by reassembling the file from the mount head + host-truth tail in `/tmp` (all asserts pass, ASCII clean). The **host `build_alert_pages.py` is correct** (edits verified present on host); the owner's Windows build reproduces the same output.

---

## 4. Deploy (owner, Windows)

```powershell
cd C:\dev\ALERT_CENTER\deploy
# (optional) rebuild from the host builder - or just deploy the HTML already in frontend\
python ..\frontend\build_alert_pages.py <home_snapshot_html> ..\frontend
.\deploy_alert_pages.ps1            # all 5 pages (sidebar/subnav consistency)
```
(The deploy script reads the `frappe_api_keys -newww.csv` at `C:\dev\` — already copied there.) Then Ctrl+Shift+R on `/alerts`, `/alerts/policies`, `/alerts/rules`.

---

## 5. Post-deploy verification (P02056 / EC-AL-000662)

1. `/alerts`: the P02056 Case row shows `Đơn = 1` (occurrence_count). Tick its checkbox → bulk bar appears → (optionally) In Review selected works.
2. Open the Case drawer → breakdown shows `RSP 282,000 − Seller 46,000 − Seller vch 0 − Plat disc 0 − Plat vch 44,600 = 191,400`; Occurrences table lists order `ODVN26060894414148` with the full evidence; `price_components_used = seller_discount+seller_voucher+platform_discount+platform_voucher`.
3. `/alerts/policies`: open a policy → High alert % / Severe drop % inputs are gone; helper points to Rules.
4. `/alerts/rules`: open a rule → Severe drop % + High alert % inputs present.

---

## 6. What's next

This completes G1.1 (backend Drop 1 + frontend Drop 2). Remaining Alert Center backlog (separate, gated): G2 Omisell Shop + SKU Catalog Sync, G3 Policy Coverage + Mass Update, G4 Onboarding Wizard, G5 Stock Read-only, G6 Real Lock Execution. The bash-mount read-lag on `C:\dev\ALERT_CENTER` is cosmetic (host correct); future large builder edits can use the same /tmp-reassembly fallback or build on Windows.
