# Alert Center Phase D.1 — Pre-push Output + Deploy Runbook

Date: 2026-06-09 · Status: **ALL 10 PRE-PUSH CHECKS PASS (verified read-only against git, after fresh `git fetch`). Nothing pushed/merged/deployed.**

## Checks 1–10 — results

| # | Check | Result |
|---|---|---|
| 1 | Branch `alerts-phase-d1`, tip `794b1ce` | ✅ |
| 2 | Diff vs fresh origin/main (`1fecf86`, fetched just now) | ✅ 10 files, +285/−39 |
| 3 | Exactly the 10 D.1 files (3 A + 7 M, list verified) | ✅ |
| 4 | Zero `pm/**` | ✅ (count = 0) |
| 5 | Zero hooks.py diff | ✅ (0 lines) |
| 6 | Migrate impact = exactly: search_index Log×6 / Item×3 / Alert×2 (field lists verified from blobs), BIS `consecutive_failures` (Int, default 0), `patches.txt` tail = `...alerts.patches.p001_capacity_indexes` | ✅ |
| 7 | Patch idempotent + safe: `SHOW INDEX` pre-check → "already present - skip"; any error → `frappe.log_error` + continue (never blocks migrate) | ✅ (guards at patch lines 22/24/30) |
| 8 | No scheduler registered: hooks.py unchanged (check 5) + zero `scheduler_events` references in `alerts/` | ✅ |
| 9 | No archive/delete code: grep across api/patches finds only the *measurement* strings in `capacity_stats` (docstring + 2M trigger constants) — no delete_doc/truncate/drop anywhere | ✅ |
| 10 | No Omisell write path: `ALLOWED_METHODS = frozenset({"GET"})` present in client blob; **client diff vs origin/main = 0 lines** (D.1 didn't touch it); read-only-surface regression test in suite | ✅ |

## 11. Deploy + post-deploy probes (owner machine, per-turn confirmed)

1. Housekeeping (`.git/*stale*`) → re-run checks 1–5 → push `alerts-phase-d1` → PR #6 (Files-changed gate = 10 files) → merge → FC Deploy.
2. **Watch migrate log:** search_index column changes + `p001_capacity_indexes: created brand_order_datetime_index...` + `created brand_status_detected_at_index...` (or "already present" on re-deploys) + BIS field added. A p001 error would appear in Error Log but never abort migrate.
3. Probes:
   - `POST .../api_omisell.capacity_stats` (SM) → 200 + counts + `archive_review_due: false`. **Save this baseline reading** (first datapoint of the measurement program).
   - `/alerts` → cards values identical to pre-deploy (COUNT refactor equivalence in production).
   - Non-SM token → **403** on `capacity_stats` AND `pull_recent`.
   - Optional live exercise: `POST .../api_omisell.pull_recent {"brand": "FES-VN"}` (manual, read-only) → expect chunked summaries, `caught_up: true`, `last_sync_at` advanced per chunk; re-run → small/empty window, idempotent.
   - Optional bench console: `run-tests --module ecentric_workspace.alerts.tests.test_phase_d1` (TestSchemaD1: meta search_index + SHOW INDEX + cards equivalence).
4. Fresh handover entry after probes.

## 12. Rollback plan

Revert PR → FC deploy: endpoints/COUNT-refactor revert; **indexes remain (harmless, beneficial — removal only via explicit drop-index patch if ever desired)**; `consecutive_failures` field stays harmlessly. Instant stops without deploy: `ec_alerts_pull_disabled: 1` (all pulls), BIS `enabled=0` (per brand), circuit breaker self-opens on repeated failures. No data to unwind; nothing on Omisell's side (read-only).

## Still true after this deploy

Scheduler kill switch ON, no scheduler entries exist, no archive/delete execution, no nightly reconciliation (D.2), no Omisell write path, DS1 locked, PM untouched. Next gate after verification: **narrow scheduler enablement decision** (single pilot brand, */15, hooks.py change + its own approval).
