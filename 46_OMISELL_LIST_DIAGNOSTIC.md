# 46 — Omisell order/list window diagnostic (READ-ONLY probe)

Date: 2026-06-10 · Status: BUILT, awaiting deploy + run · Prereq for any further scheduler change.

## Problem

Scheduled pull window `2026-06-09 19:16 → 2026-06-10 01:18` returned `listed_total = 0`, but target order `ODVN260609D6414F3F` (FES-VN, shop 21611, `order_datetime = 2026-06-09 21:37:39`) is readable via `get_order_detail`. Overlap hotfix widens the window but does not explain the miss.

## Leading hypothesis (found by code read, to be PROVEN by probe)

`api_omisell.pull_orders` line ~303: `f_ts = int(f.timestamp())` on a **naive** datetime. Python interprets naive datetimes in the **server's** local tz. Frappe Cloud servers typically run UTC while `now_datetime()` returns site-tz (Asia/Ho_Chi_Minh) naive wall time. If so, every epoch sent to Omisell is **+7h ahead of real time** → the scheduled window `[last_sync − overlap, now]` actually queries a mostly-future window → empty list. Detail API is unaffected (no timestamps).

The probe outputs `tz_evidence.drift_seconds = int(time.time()) − int(now_datetime().timestamp())`:

* `0` → conversion correct, hypothesis dead, look at status filter / list-vs-detail inconsistency.
* `≈ −25200` → server UTC vs site UTC+7 confirmed = ROOT CAUSE.

Cross-check: target should then appear in the `utc_shifted` windows (w2/w4) and NOT in the VN-local ones.

## What was built

* `C:\dev\ecentric_workspace\ecentric_workspace\alerts\api_diag.py` — NEW additive file. SM-only POST `diagnose_order_list(brand, target_order?, windows?, page_size?, max_pages?)`. Runs the 5 section-6 windows with the **identical** epoch conversion as production, logs per window: raw params (`updated_from/to` epochs + UTC read-back), reported `count`, fetched headers, listed order numbers (≤120), target appearance + raw target header (sanitized), first-header time-field sample, rate header. Plus `tz_evidence` block. Caps: 4 pages × 50/window, 100 s budget. **No writes** (checkpoint untouched; only inherent client token refresh). Verified: py_compile OK, ASCII clean, no `.insert/.save/set_value` in file.
* `C:\dev\ALERT_CENTER\deploy\diagnose_omisell_list.ps1` — PS5 driver (same auth pattern as `monitor_brands.ps1`). Prints colored verdicts incl. drift interpretation, saves full JSON `diag_omisell_list_<brand>_<stamp>.json` beside the script. ASCII clean, braces balanced.

`api_diag.py` only imports `_get_bis` (Phase D, on main) + the client → **deployable independently** of the 4 pending built items; no migrate.

## Owner runbook

```powershell
# 1. deploy (separate tiny branch, explicit path)
git -C C:\dev\ecentric_workspace rev-parse --abbrev-ref HEAD      # verify first
git -C C:\dev\ecentric_workspace checkout -b diag/omisell-list-windows
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_diag.py
git -C C:\dev\ecentric_workspace commit -m "diag(alerts): read-only omisell order/list window probe"
# push -> PR -> merge -> FC deploy (code-only, no migrate)

# 2. run probe
cd C:\dev\ALERT_CENTER\deploy
.\diagnose_omisell_list.ps1                  # defaults FES-VN / ODVN260609D6414F3F
```

## Decision table after run

| drift_seconds | target in w2/w4 only | Conclusion | Fix |
|---|---|---|---|
| ≈ −25200 | yes | tz bug confirmed | tz-aware epoch conversion in `api_omisell` (one helper `_to_epoch(dt)` using site tz; apply at the 3 `.timestamp()` call sites) |
| 0 | found in w1/w3/w5 | window math fine, scheduled-run-specific issue | compare scheduled params vs probe params |
| 0 | not found anywhere | list endpoint excludes the order (status/shop/list-lag) | escalate to Omisell with probe JSON |

Fix goes on top of (or into) the pending `fix/scheduler-overlap` branch — coordinate so the two `api_omisell.py` edits don't collide.
