# Alert Center Phase E — Deploy Runbook (owner machine)

Date: 2026-06-08 · Pre-push checks 1–6: **ALL PASS** (verified read-only against the repo — see table). Execute top-to-bottom; stop and report at any [ERR].

## 0. Pre-push verification results (sandbox-verified; re-confirm in step 1)

| # | Check | Result |
|---|---|---|
| 1 | branch = `alerts-phase-e` | ✅ |
| 2 | tip = `c176ec3` | ✅ |
| 3 | diff main..alerts-phase-e = 11 Phase E files only (5 A + 6 M, list in 09 report §1) | ✅ |
| 4 | zero `ecentric_workspace/pm/**` in branch diff | ✅ |
| 5 | zero `.ps1`/backup artifacts in branch diff | ✅ |
| 6 | single commit, author Claude (Alert Center), no PM WIP swept | ✅ |

## 1. Owner-machine re-verification (PowerShell — OneDrive sync paused, editors closed)

```powershell
cd "C:\Users\admin\NextCommerce\Data - Documents\General\ERP Website\ecentric_workspace"
Get-ChildItem .git -Recurse -Force -File | Where-Object { $_.Name -like "*stale*" -or $_.Name -like "index.corrupt.*" } | Remove-Item -Force
git fetch origin
git log --oneline -1 alerts-phase-e          # expect c176ec3
git diff --name-status origin/main..alerts-phase-e   # expect EXACTLY the 11 files
git diff --name-only origin/main..alerts-phase-e | Select-String "pm/"   # expect EMPTY
git status --short ecentric_workspace/pm     # your PM WIP - must stay UNSTAGED; stash/commit it separately FIRST if you want it safe
```

## 2. Scheduler dormant FIRST (your decision — do this BEFORE merge/deploy)

Frappe Cloud dashboard → site `team.ecentric.vn` → **Site Config** → add:
```json
"ec_alerts_scheduler_disabled": 1
```
Save. (FC applies site_config without redeploy.) Both jobs will register at deploy but no-op until you remove this key. Verification of dormancy after deploy: create nothing — `EC Automation Pause` records stay untouched and Error Log shows no alerts.tasks entries.

## 3. Push → PR → merge

```powershell
git push origin alerts-phase-e
```
GitHub → PR `alerts-phase-e → main` → **Files changed must show exactly the 11 files, zero pm/** → merge commit (not squash).

## 4. Frappe Cloud deploy + migrate

FC dashboard → Deploy/Update → watch log: build OK, migrate applies 2 new fields (`external_product_id`, `omisell_shop_id`), no tracebacks, site up, `/pm` + `/home` unchanged.

## 5. Backend probes (before page deploy)

```powershell
cd "...\ERP Website\ALERT_CENTER\deploy"
powershell -ExecutionPolicy Bypass -File .\verify_phase_e_probes.ps1
# optional full 403 matrix: -NonSmCsv <csv with a non-SM user token>
```
Expect: 2 field checks OK, my_scope supervisor=true, get_cards/list_alerts alive, queue drain processed≥0 errors=0. (GET /alerts WARN is expected — page not deployed yet.)

## 6. Data step (UAT precondition D4-E)

Fill `kam_owner` on all 7 Brand Approver records (Desk). Required before KAM-scoped UAT; the page works for supervisors without it.

## 7. Page deploy

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy_alert_page.ps1
```
Expect: [OK] HTML 49894 chars ASCII + marker → backup (if exists) → created/updated → record verified → live GET 200 + marker. Browser: `https://team.ecentric.vn/alerts` (Ctrl+Shift+R) — supervisor sees cards/table; KAM sees own brand; user without scope sees no-access screen; Guest redirected to login.

## 8. Re-run probes (now page check passes) + UAT per `08_PHASE_E_PLAN.md` §6

Send me both probe outputs + UAT result. **Only after that → mark Phase E production-complete** (I'll close it in the handover log) → then we decide enabling the scheduler (remove the site_config key) as its own approved step.

## Rollback (any point)

Page → `rollback_alert_page.ps1` (unpublish). Scheduler → already dormant via kill switch. APIs/fields → revert PR on GitHub → FC deploy. Records stay for audit. PM work unaffected throughout.

## Out of scope (unchanged)

Real Omisell ingestion (Phase D — still gated on `OMISELL_API_CHECKLIST.md`), real stock lock execution, sidebar nav item, retry/cancel/release UI.
