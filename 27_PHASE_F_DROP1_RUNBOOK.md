# Phase F — Drop 1 Runbook (App PR + Migrate)

Date: 2026-06-10 · Status: **PRE-PUSH CHECKS ALL PASS (verified read-only after fresh fetch). Nothing pushed. Drop 2 HELD until Drop-1 probes pass.**

## Pre-push output (just verified)

| # | Check | Result |
|---|---|---|
| 1 | Branch `alerts-phase-f`, tip `1a13fe9` (single M1 commit) | ✅ |
| 2 | Diff vs fresh origin/main (`2f2f593`) = **exactly 15 M1 files** (8 A + 7 M, list matches report §1) | ✅ |
| 3 | 0 `pm/**`, 0 hooks.py | ✅ |
| 4 | 0 diff on api_omisell.py / tasks.py / omisell_client.py / omisell_normalizer.py (scheduler + client untouched) | ✅ |
| 5 | Full backend suite re-run: **51/51 PASS** | ✅ |

## Deploy steps (owner machine, per-turn confirm)

1. Housekeeping (`.git/*stale*`, `config.corrupt.*`) → `git fetch` → re-run checks 1–4 → push `alerts-phase-f`.
2. PR #13 → Files-changed gate (15 files) → merge commit → FC Deploy. **Migrate applies:** EC Alert Rule DocType + EC Price Policy 4 fields & status options + EC Alert Action review section. Watch log: 1 new table + field syncs, no tracebacks (no patch entry this time).
3. Run probes: `.\verify_phase_f_drop1.ps1` (optionally `-NonSmCsv` for the 403 matrix). The script covers, in order:
   - **1 Policy inertness** — creates a Draft probe policy (min 999,999 / DROP1-PROBE-SKU) → asserts it is NOT visible as Active → parks it Inactive (audit kept, no deletion).
   - **2 Rule overlay golden** — asserts zero Active EC Alert Rules ⇒ overlay identity; dashboard kpis serve. (Stronger optional check: re-pull a small FES-VN window via `pull_orders` and confirm alert output unchanged — manual, your call.)
   - **3 403 matrix** — 4 new modules probed with the non-SM token (scoped user → 200 with own data; unscoped → denied).
   - **4 review_action behavior** — queue total served; actual Approve/Reject exercised during UAT (script deliberately does NOT auto-review real records).
   - **5 `/alerts` v1 still functional** — page 200 + marker, v1 `get_cards` serves (Drop 2 not yet deployed).
   - **6 FES-VN scheduler health** — last_sync_at fresh (≤45 min), breaker 0, no running lock; any drift ⇒ HOLD Drop 2.
4. Send me the probe output → I cross-check → **only then Drop 2** (`deploy_alert_pages.ps1`, suggest `-Only alert-center` first if you want a staged page rollout).

## Rollback (Drop 1 only)

Revert PR #13 → FC deploy: overlay/APIs gone, engine returns to literal current production code; schema stays harmlessly (nothing writes Draft/Paused/review fields until pages exist). Config off-switch without deploy: keep zero Active EC Alert Rules (overlay = identity by construction).
