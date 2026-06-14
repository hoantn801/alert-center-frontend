# Alert Center - Deploy & Rollback Runbook

Operational runbook for the Alert Center MVP. Two independently deployable
halves: the **backend app** (`ecentric_workspace`, the Python module
`ecentric_workspace.alerts`) and the **frontend Web Pages** (this repo's builder
output). Backend changes need a bench/Frappe-Cloud deploy; frontend changes need
only the builder + deploy script.

Site: `team.ecentric.vn`. Substitute `<site>` and the bench path as appropriate.

---

## A. Backend deploy (app repo `ecentric_workspace`)

```bash
# 1. verify you are on the intended branch/commit
cd ~/frappe-bench/apps/ecentric_workspace
git status                      # clean tree
git log --oneline -3            # confirm the commit you intend to ship
git checkout main && git pull   # or the release branch

# 2. migrate (runs patches.txt entries; idempotent)
cd ~/frappe-bench
bench --site <site> migrate

# 3. clear cache + restart workers/web
bench --site <site> clear-cache
bench --site <site> clear-website-cache
bench restart                   # (Frappe Cloud: push to the connected branch; FC migrates+restarts)
```

**Patch verification** (the operational/setup retirement patches must be applied
once, and never re-create data):

```bash
bench --site <site> console
>>> import frappe
>>> frappe.db.get_all("Patch Log", filters={"patch": ("like", "%alerts.patches.p00%")}, pluck="patch")
# expect p004_retire_missing_policy_alerts and p005_backfill_order_log_brand_from_shop present
```

**Backend success signals**

- `bench migrate` ends `Updating Dashboard ... Done` with no traceback.
- `Patch Log` contains p004 + p005.
- A read smoke (below) returns all `[OK]`.

---

## B. Frontend deploy (this repo)

```powershell
cd C:\dev\ALERT_CENTER

# 1. compile + build all 5 pages from the canonical snapshot
python -m py_compile frontend\build_alert_pages.py
python frontend\build_alert_pages.py `
  deploy\backups\home_20260608_154510\main_section_html.bak.html `
  frontend
```

Expected build output: `[OK] built ... alert_center.html` ... through
`alert_health.html`, then the self-assert lines
(`[OK] M2c policy-drawer asserts pass`, `... dashboard asserts pass`,
`... module-shell asserts pass`). Any `AssertionError` = STOP, do not deploy.

**Validation markers** (the deploy script re-checks these and refuses a bad
page): each page contains its `ec-alert-*` marker, is 100% ASCII, and has
balanced `<style>`/`<script>`.

```powershell
# 2. deploy (backs up the existing Web Page under deploy\backups\ first)
.\deploy\deploy_alert_pages.ps1                  # or  -Only alert-policies

# 3. refresh site cache
bench --site team.ecentric.vn clear-website-cache
```

**Frontend success signals**

- Deploy prints `[OK] <file>: <N> chars, ASCII, marker ok` then an update/create
  line per route, and a backup path under `deploy\backups\<route>_<timestamp>\`.
- All five routes load (next section).

---

## C. Post-deploy checks

```powershell
# routes + read-only API invariants (operational/setup separation, scope, secrets)
.\deploy\verify_alert_center_postdeploy.ps1          # expect every line [OK], final PASSED
# 24h brand health
.\deploy\monitor_brands.ps1 -Brands FES-VN,LOF-VN    # FES-VN/LOF-VN OK, breaker=0, sync fresh
```

Manual spot checks (browser, logged in):

- `/alerts` default list shows operational price alerts only (NO
  `missing_brand_mapping`); the **Setup Issues** KPI card is separate; clicking a
  KPI card filters the list; advanced filters + filter chips work.
- `/alerts/policies` coverage chips + Price Setup load; create a Draft, activate,
  edit, deactivate using a clearly-disposable SKU; conflict validation fires.
- `/alerts/rules`, `/alerts/locks`, `/alerts/integration-health` load; FES-VN /
  LOF-VN healthy; no secret fields in any payload.

**Permission spot checks** (authoritative matrix = bench tests
`test_permissions_scope`, `test_e2e_permission_matrix`):

- A brand-scoped KAM sees only their brand(s); an explicit out-of-scope `brand`
  request is rejected/empty.
- An Administrator / System Manager / active `Management - EC` employee sees all
  brands; the Management-EC user does NOT get credential/execute/cancel-case
  capabilities.
- An unassigned user gets a permission error / empty scope.

**Operational/setup separation signal**: `kpis` returns both operational
(`open/critical/warning`) and `setup_issues`; `by_dimension(rule_code)` default
has no `missing_brand_mapping`; `by_dimension(brand)` default has no `(none)`;
`setup_only=1` and explicit `rule_code=missing_brand_mapping` still return rows.

---

## D. Rollback

### Frontend (fast)

```powershell
# Option 1 - take pages offline (content preserved):
.\deploy\rollback_alert_pages.ps1                # or  -Only alert-policies

# Option 2 - restore previous CONTENT: re-deploy the prior build. Either
#   (a) git checkout the previous frontend\build_alert_pages.py, rebuild, deploy; or
#   (b) restore main_section from the backup captured at the last deploy:
#       deploy\backups\<route>_<timestamp>\web_page.json
bench --site team.ecentric.vn clear-website-cache
```

### Backend (git revert, never a destructive migrate-down)

```bash
cd ~/frappe-bench/apps/ecentric_workspace
git revert <bad_commit>     # or: git checkout <previous_good_commit>
cd ~/frappe-bench
bench --site <site> migrate
bench --site <site> clear-cache && bench restart
```

### Caveats (read before rolling back)

- **No hard delete of audit history.** Alerts, locks, policies, occurrences, and
  Version/timeline rows are never deleted on rollback. The retirement patch
  (p004) *closed* historical `missing_policy` alerts; reverting code does not and
  should not re-open or delete them.
- **Patches are forward-only.** p004/p005 have no down-migration; a code revert
  leaves their data effects in place (historically closed alerts stay closed,
  backfilled `Order Log.brand` stays set). This is intended.
- **Frontend rollback is content-only** - it changes Web Page `main_section`,
  never any alert/lock/policy data.
- Re-run `verify_alert_center_postdeploy.ps1` after any rollback; it must return
  all `[OK]`.

---

## Quick reference

| Action | Command |
| --- | --- |
| Build pages | `python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend` |
| Deploy all | `.\deploy\deploy_alert_pages.ps1` |
| Deploy one | `.\deploy\deploy_alert_pages.ps1 -Only alert-policies` |
| Smoke | `.\deploy\verify_alert_center_postdeploy.ps1` |
| Monitor | `.\deploy\monitor_brands.ps1` |
| Frontend rollback | `.\deploy\rollback_alert_pages.ps1` |
| Backend migrate | `bench --site <site> migrate` |
