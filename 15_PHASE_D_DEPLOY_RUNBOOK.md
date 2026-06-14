# Alert Center Phase D — Pre-push Output + Deploy Runbook

Date: 2026-06-08 · Status: **PRE-PUSH CHECKS ALL PASS (verified read-only against git). Nothing pushed/merged/deployed. Zero real Omisell calls made.** Execute after your review.

## Checks 1–7 — results (sandbox-verified just now)

| # | Check | Result |
|---|---|---|
| 1 | Branch `alerts-phase-d`, tip `04d4c68` | ✅ |
| 2 | Diff vs origin/main (`d5aae18`) = 10 files, +812/−3 | ✅ |
| 3 | Exactly the 10 approved Phase D files (5 A + 5 M, listed in 14 report §1) | ✅ |
| 4 | Zero `pm/**` in diff | ✅ (count = 0) |
| 5 | Zero hooks.py diff | ✅ (0 lines) |
| 6 | HTTP import grep: line-anchored `^import requests` exists **only in `omisell_client.py:29`** (the raw grep also flags `test_phase_d.py` — that match is the enforcement test's own regex string, not an import; verified) | ✅ |
| 7 | No-write summary: `ALLOWED_METHODS = frozenset({"GET"})` at client line 33; public surface = `get_shops/get_orders/get_order_detail` + `_request` chokepoint only; **0 mutation-named functions**; no write-verb URL strings outside the tests' forbidden-pattern list; 10/10 unit proofs incl. stubbed-network assertion | ✅ |

## 8. Deploy / migrate expectations

Owner machine: housekeeping (`.git/*stale*` cleanup) → `git fetch` → re-run checks 1–6 vs fresh origin/main → push `alerts-phase-d` → PR (Files-changed gate = the 10 files) → merge commit → FC Deploy. Migrate applies exactly: BIS `token_expired_at`, EC Alert rule_code option `ingestion_api_failed`, EC Alert Action DS1 audit block (9 rows incl. breaks). **No scheduler registers** (hooks untouched); dormant Phase E schedulers and kill switch unaffected. Site behavior unchanged for all users — the 4 new endpoints are SM-only and idle until called.

## 9. Post-deploy probes (before any T-step)

1. Fields/option present: Desk → EC Brand Integration Settings (Token Expired At), EC Alert rule_code list, EC Alert Action Stock Audit section.
2. Non-SM token POST to each `ecentric_workspace.alerts.api_omisell.*` endpoint → **403** ×4.
3. SM POST `omisell_probe` with a brand that has **no** BIS record → clean "No EC Brand Integration Settings" error (proves guard before any HTTP).
4. Phase C/E regression: `verify_phase_c_probes.ps1` + `verify_phase_e_probes.ps1` still green.
Then the manual flow — **I need from you: pilot brand (Q-D1), its Omisell API key entered into that brand's BIS via Desk (enabled=1), and a specific order number for T2.** Run: `run_phase_d_tests.ps1 -Step T0 → T1 (map shops manually, repeat until unmapped=0) → T2 -OrderNumber ... -CaptureGolden → T3 -From/-To (≤1h, run twice)`. If T0 fails on auth: adjust `ec_alerts_omisell_auth_path` / `_auth_field` / `_auth_scheme` in FC site config — no redeploy.

## 10. Rollback plan

Revert PR → FC deploy (4 endpoints vanish; client module gone). Instant per-brand stop without deploy: BIS `enabled=0` (or clear token). Read-only integration → **nothing on Omisell's side to undo**. Additive schema stays harmlessly; ingested orders/alerts kept for audit; `last_sync_at`/`token_expired_at` reset by clearing fields if ever needed.
