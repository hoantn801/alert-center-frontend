# 47 — TZ-FIX: site-tz-aware epoch conversion for Omisell order/list

Date: 2026-06-10 · Status: BUILT + 14/14 tests pass, awaiting deploy · Root cause from doc 46 (drift_seconds = −25200 confirmed by owner-run diagnostic).

## Root cause

`int(naive_dt.timestamp())` interprets naive datetimes in the **server's** tz. Frappe Cloud server = UTC; site = Asia/Ho_Chi_Minh. Every `updated_from/to` epoch sent to Omisell order/list was **+7h in the future** → scheduled windows queried time that hadn't happened → `listed_total = 0` while `get_order_detail` (no timestamps) worked fine.

## Changes (backend only, code-only, no migrate)

| File | Change |
|---|---|
| `services/time_windows.py` | NEW, PURE (frappe-free): `epoch_in_tz(dt, tz_name=Asia/Ho_Chi_Minh)` — naive dt localized to site tz then → true UTC epoch; aware passthrough; TypeError on non-datetime. `utc_str(epoch)` for summaries. |
| `api_omisell.py` | `_site_timezone()` (System Settings, fail-safe VN) + `_to_epoch(dt)` wrapper. Both list call sites converted: `pull_orders` (`f_ts, t_ts = _to_epoch(f), _to_epoch(t)`) and `pull_preview`. Diagnostics added: `pull_orders` summary += `epoch_window`/`utc_window`; `pull_recent_job` run += `epoch_from/epoch_to/utc_from/utc_to/site_time_zone` (alongside existing `requested_from`/`effective_from_after_overlap`/`overlap_minutes`); per-chunk rollup += `epoch_window`/`utc_window`; `pull_status` += `site_time_zone`. |
| `tests/test_tz_epoch.py` | NEW. 14 tests: pure conversion (VN 2026-06-09 21:37:39 → epoch of UTC 14:37:39; server-tz independence; aware passthrough; TypeError), failing scheduler window now covers target epoch + old conversion provably missed it, monotonic-guard no-rollback model, plus source-text wiring asserts (no live `int(x.timestamp())`, pull_one_order untouched, overlap/chunk/guard strings intact, diagnostic fields present, no new write surface). |

NOT touched: `pull_one_order`, overlap logic, monotonic checkpoint, chunking, client (GET-only), alert engine, hooks/tasks/PM, stock.

## Verification done locally

py_compile OK ×3, ASCII clean ×3, 14/14 unittest pass (run in sandbox via /tmp reassembly — mount truncated `api_omisell.py`, host files verified correct via Read/Grep).

## Deploy (owner, Windows)

These edits live in the SAME `api_omisell.py` as the pending scheduler-overlap hotfix → ship together on `fix/scheduler-overlap`:

```powershell
git -C C:\dev\ecentric_workspace rev-parse --abbrev-ref HEAD   # verify FIRST
git -C C:\dev\ecentric_workspace checkout -b fix/scheduler-overlap
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_omisell.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/time_windows.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_tz_epoch.py
git -C C:\dev\ecentric_workspace commit -m "fix(alerts): site-tz-aware epoch for order/list + scheduled-pull overlap + monotonic checkpoint"
# push -> PR -> merge -> FC deploy (code-only, no migrate)
```

## Post-deploy verify (FES-VN)

1. `pull_recent(FES-VN)` → poll `pull_status`.
2. `last_run.utc_from/utc_to` = site `from/to` **minus 7h** (e.g. site 19:16 → UTC 12:16); `site_time_zone = Asia/Ho_Chi_Minh`.
3. `listed_order_numbers` now non-empty for active windows — should include `ODVN260609D6414F3F` while it's inside `last_sync_at − 360min` overlap, or other recent orders.
4. No duplicate Order Log / Occurrence (upsert + dedupe — re-pull of already-ingested orders shows `unchanged`).
5. `last_sync_at` only moves forward (`checkpoint_held` on overlap chunks).
6. Optional bench: `bench --site <site> run-tests --module ecentric_workspace.alerts.tests.test_tz_epoch`.

NOTE: first post-fix run re-scans a correct (older) window — expect a burst of listed orders that the broken windows missed; idempotent ingest makes this safe.
