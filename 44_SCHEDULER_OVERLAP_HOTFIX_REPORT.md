# Alert Center — Scheduled-Pull Overlap Hotfix (Local Report)

Date: 2026-06-10 · Status: **IMPLEMENTED in `C:\dev\ecentric_workspace` (backend-only). Ready to deploy.** No Omisell write, no stock write, no PM/hooks/tasks change, alert-engine logic unchanged, manual `pull_one_order` unchanged.

## Problem
The scheduled order-list pull missed a real order: window `00:00:23 → 00:16:01` returned `listed=0`, yet `pull_one_order(ODVN260609D6414F3F)` read + evaluated it correctly (EC-MOL-000707 / EC-AL-000708, `below_min`, effective 209985 < min 250500). The order's update fell outside / was not yet visible in the narrow scheduled window (list-API eventual consistency / clock skew). Detail API + engine are fine; only the list window was too tight.

## Fix (file: `alerts/api_omisell.py`)
1. **Configurable overlap** — `_overlap_minutes()` reads site_config `ec_alerts_pull_overlap_minutes`, **default 360**, fail-safe to default.
2. **Re-scan window** — in `pull_recent_job` (the body the scheduler enqueues), `effective_from = last_sync_at − overlap_minutes` (clamped ≤ now). The order-list is re-scanned over the recent past so late/out-of-order updates are caught.
3. **No checkpoint regression** — two guards so the overlap never moves `last_sync_at` backward:
   - `pull_orders` now sets `last_sync_at = max(prev_last_sync_at, window_end)` (MONOTONIC; was `= window_end`). An overlap chunk ending in already-checkpointed time can't regress the checkpoint. (`checkpoint_held` flag added.)
   - `pull_recent_job` uses **enough ≤1h chunks to span `[effective_from, now]`** (`span_chunks`, capped at `MAX_OVERLAP_CHUNKS=12`) so the run REACHES now and advances the checkpoint forward, instead of stopping mid-window. Empty windows are ~1 cheap list call each.
4. **Checkpoint advancement unchanged in spirit** — still advances only on a fully-successful chunk; the overlap only widens the *start* of the scan.
5. **No duplicate business records** — Order Log is upserted by `order_key`; EC Alert Occurrence is deduped by `order|line|rule`. Re-scanning the same orders is a no-op (verified by G1.1 dedupe).
6. **pull_status / run summary fields added:** `requested_from`, `effective_from_after_overlap`, `overlap_minutes`, `to` (`from`), `listed_order_numbers` (run-level rollup), `listed_total`; plus top-level `overlap_minutes` on `pull_status`.

## Verification
- **Reconstructed `py_compile` OK** (sandbox mount truncates the freshly-edited file — false positive; the file was reassembled from mount head + host-truth tail and compiles cleanly; all edited regions Read-verified well-formed).
- **Progression simulation 7/7 PASS** over 3 scheduled cycles with overlap 360:
  - every cycle: `new_last_sync_at ≥ old` (no regression),
  - every cycle: window reaches `now` (forward progress, 7 chunks for ~6.25h),
  - cycle 1 catches the missed order (update at 00:05 inside the re-scan `18:16 → 00:31`).

## Constraints
No Omisell write (still GET list/detail only). No stock/buffer/inventory write. No PM/hooks/tasks change. Alert-engine logic untouched (the fix is purely the pull window + checkpoint guard). `pull_one_order` unchanged. FES-VN/LOF-VN scheduler stays healthy — the overlap applies to their scheduled `pull_recent_job` and only widens the list window; the monotonic guard + full-span chunks keep the checkpoint advancing.

## Deploy / rollback
- Backend (Windows, `C:\dev\ecentric_workspace`): branch, stage `ecentric_workspace/alerts/api_omisell.py`, PR → merge → **FC deploy (no migrate, code-only)**.
- Optional: set `ec_alerts_pull_overlap_minutes` in site_config (default 360 if unset; e.g. 180 to narrow, 720 to widen).
- Rollback: revert PR → FC deploy. No data change; checkpoint monotonic so nothing to unwind.

## Verify after deploy
1. Wait for one scheduled cycle (or `pull_recent("FES-VN")`), then `pull_status("FES-VN")` → `overlap_minutes=360`, `last_run.requested_from`, `last_run.effective_from_after_overlap` (≈ requested − 6h), `last_run.to` ≈ now, `last_run.listed_order_numbers` non-empty when orders updated.
2. `last_sync_at` keeps advancing forward each cycle (never regresses).
3. Re-confirm no duplicate EC-MOL / EC Alert Occurrence for a re-scanned order (counts stable).
