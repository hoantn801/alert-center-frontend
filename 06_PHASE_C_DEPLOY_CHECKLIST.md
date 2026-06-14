# Alert Center Phase C — Deploy Checklist

Date: 2026-06-07 · Status: **CHECKLIST ONLY — nothing pushed/merged/deployed.** Execution waits for your explicit confirm after reviewing this document.

Phase B production verification: **COMPLETE** (R1 + R2 passed, user-confirmed 2026-06-07).

## 0. Pre-deploy confirmations (items 1–8, verified read-only against git just now)

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Branch = `alerts-phase-c` | ✅ | exists, currently checked out, tip below |
| 2 | Commit = `08cfdaa` | ✅ | `git log -1 alerts-phase-c` |
| 3 | Diff vs main = Phase C additions only | ✅ | `git diff main alerts-phase-c --stat` → **13 files, +1253, 0 deletions**; 0 files outside `ecentric_workspace/alerts/`; 0 existing files modified |
| 4 | No schema/DocType/fixture change | ✅ | name-only diff has no `.json` (non-test), no `fixtures/`, no `hooks.py`, no `modules.txt`, no `patches.txt` |
| 5 | No frontend change | ✅ | no `frontend/`, `www/`, `.html` in diff |
| 6 | No HTTP/Omisell client | ✅ | `git grep` on the branch blobs for `requests/urllib/http` imports under `alerts/` → NONE |
| 7 | No real stock update path | ✅ | `action_queue._process_one` terminal states = Skipped / Dry Run only; no executor exists (report §9) |
| 8 | No scheduler | ✅ | `git diff main alerts-phase-c -- ecentric_workspace/hooks.py` → empty |

File list (13): `alerts/api.py`, `alerts/services/{__init__, pricing, rules, dedupe_keys, brand_resolver, policy_lookup, baseline, alert_engine, action_queue, ingestion}.py`, `alerts/tests/{test_phase_c, test_rules_pure}.py`.

## 1. Pre-push housekeeping (your Windows machine — sandbox cannot unlink)

```powershell
cd "C:\Users\admin\NextCommerce\Data - Documents\General\ERP Website\ecentric_workspace"
Get-ChildItem .git -Recurse -Force -File | Where-Object { $_.Name -like "*stale*" -or $_.Name -like "index.corrupt.*" -or $_.Name -like "stale_trash*" } | Remove-Item -Force
git fsck --connectivity-only 2>&1 | Select-String -NotMatch "dangling"   # expect no broken/corrupt
git log --oneline -1 alerts-phase-c    # expect 08cfdaa
git diff main alerts-phase-c --stat | Select-Object -Last 2   # expect 13 files, +1253
```
Dangling objects (`def79e0`, old Phase B shas) are normal; safe to `git gc` AFTER push if desired.

## 2. Push → PR → merge (your Windows machine; OneDrive sync paused or editors closed during git ops)

```powershell
git push origin alerts-phase-c
```
GitHub: PR `alerts-phase-c → main`, single commit `08cfdaa`, review = this checklist §0 table, **merge commit** (not squash — keeps the audited sha). Per standing rules: tell me before you start, and don't commit other work to the repo mid-process.

## 3. Frappe Cloud deploy

1. FC dashboard → bench/site `team.ecentric.vn` → Apps → `ecentric_workspace` shows the merge commit on `main`.
2. **Deploy/Update**. Code-only change: the migrate step in FC's pipeline is a harmless no-op for this diff (no DocType/fixture/patch).
3. Watch deploy log: build OK, no import errors at restart (an import-time failure in any `alerts.services` module would surface on first call, not boot — see §4 probe 1).

## 4. Post-deploy production verification

As **Administrator** (probes 1–3 are read-only; probe 4 writes ALERTC test records — optional, see note):
1. **Import probe:** `POST /api/method/ecentric_workspace.alerts.api.process_action_queue` (empty queue) → expect `200` with `{"processed": 0, ...}`. Proves the module tree imports and the endpoint is alive.
2. **Permission probe (non-SM user):** same endpoint → expect **403**; `POST .../ingest_mock_orders` → **403**. (R2 already proved Desk/API lockdown of the DocTypes.)
3. **GET-write guard:** `GET /api/method/ecentric_workspace.alerts.api.ingest_mock_orders` → expect 405/not allowed (POST-only).
4. **Functional smoke (optional now, required before Phase E):** run the 13-case suite if a bench console is available on FC (`bench --site team.ecentric.vn run-tests --module ecentric_workspace.alerts.tests.test_phase_c` — test data is ALERTC-prefixed and self-cleaning), **or** one manual mock ingestion with a 2-line payload (sample schema in `services/ingestion.py` docstring) against a test brand/shop you nominate → check: 1 EC Alert created, lock action Dry Run, re-POST same payload → no duplicates. Test records can stay for audit or be deleted with your approval.
5. Fresh handover-log entry + (optional) snapshot. Reminder: the 8 DocTypes won't appear in `custom_doctypes_list` (custom=0) — not a drift signal.

## 5. Rollback

Revert the PR merge commit on GitHub → FC Deploy again. Endpoints disappear with the code; no scheduler to unhook, no schema to unwind; any test alert/action/log records stay for audit unless you approve cleanup. Phase B remains untouched either way.

## 6. Exact production verification commands (added 2026-06-07 post-deploy)

PowerShell (PS5-safe: all payloads pure ASCII). Token = `api_key:api_secret` of a **System Manager** user — load from your secrets file as usual, never paste into chat/Git.

```powershell
$base = "https://team.ecentric.vn"
$h = @{ Authorization = "token <api_key>:<api_secret>" }   # SM user, from secrets
```

**Probe 1 — empty action queue (no writes):**
```powershell
Invoke-RestMethod -Method Post -Uri "$base/api/method/ecentric_workspace.alerts.api.process_action_queue" -Headers $h
# EXPECT: message = {processed:0, dry_run:0, skipped_pause:0, skipped_credential:0, skipped_not_implemented:0, errors:0}
# Proves: module tree imports cleanly on FC + endpoint alive + SM auth path works.
```

**Probe 2 — safe mock ingestion smoke (writes 1 Order Log + 1 Warning alert, audit-safe):**
Uses a deliberately UNMAPPED shop id → exercises ingestion + engine + C1 daily dedupe via the `missing_brand_mapping` path, which by design runs no policy check and can never create a lock action. No seed data needed.
```powershell
$payload = '{"payload": [{"external_order_id": "SMOKE-C-001", "platform": "Shopee", "omisell_shop_id": "smoke-unmapped-shop", "order_status": "TEST", "items": [{"external_line_id": "L1", "seller_sku": "SMOKE-SKU-1", "quantity": 1, "customer_paid_price": 10000, "product_name": "deploy smoke test"}]}]}'
Invoke-RestMethod -Method Post -Uri "$base/api/method/ecentric_workspace.alerts.api.ingest_mock_orders" -Headers $h -ContentType "application/json" -Body $payload
# EXPECT: orders[0].status="created", summary: lines=1, alerts_created=1; action_queue.processed=0
# Run the SAME command a second time:
# EXPECT: orders[0].status="unchanged", alerts_created=0, alerts_deduped=1  (idempotency proof)
# Inspect the alert (SM):
Invoke-RestMethod -Headers $h -Uri "$base/api/resource/EC Alert?filters=[[`"rule_code`",`"=`",`"missing_brand_mapping`"]]&fields=[`"name`",`"title`",`"severity`",`"status`",`"dedupe_key`"]"
# EXPECT: exactly 1 record, severity=Warning, dedupe_key=omisell|Shopee|smoke-unmapped-shop|SMOKE-SKU-1|missing_brand_mapping|<today YYYYMMDD>
```
Cleanup: keep both records for audit (recommended — mark the alert Ignored with note "deploy smoke") or approve deletion explicitly.

**Probe 3 — no real Omisell API / stock update path active (3 layers of evidence):**
```powershell
# (a) Code layer - run against the merged commit (local or GitHub):
git grep -nE "import requests|import urllib|from requests|from urllib|import http" <merge-sha> -- ecentric_workspace/alerts
# EXPECT: no output (no HTTP client exists in the deployed code)

# (b) Data layer - smoke above created ZERO actions; total actions on site:
Invoke-RestMethod -Headers $h -Uri "$base/api/resource/EC Alert Action?fields=[`"name`",`"status`"]"
# EXPECT: [] (nothing can execute anyway: the only terminal states in code are Skipped / Dry Run)

# (c) Config layer - per-brand credentials all absent or dry-run:
Invoke-RestMethod -Headers $h -Uri "$base/api/resource/EC Brand Integration Settings?fields=[`"name`",`"brand`",`"enabled`",`"credential_status`",`"dry_run_stock_lock`"]"
# EXPECT: [] (no credentials configured yet) - any future lock action would end Skipped +
# missing_integration_credential alert; even with a credential, dry_run_stock_lock=1 by default.
```

**Bonus (R2-style for the new endpoints):** repeat Probe 1 with a NON-SM user's token → EXPECT 403 PermissionError.

## 7. Explicitly NOT in this deploy

`/alerts` page (Phase E), scheduler jobs, real Omisell pull (Phase D, gated on OMISELL_API_CHECKLIST), real stock lock execution (gated per-brand on `dry_run_stock_lock` + your approval), KAM-facing read APIs (Phase E), `kam_owner` data fill (separate data step — still pending on the 7 brand records).
