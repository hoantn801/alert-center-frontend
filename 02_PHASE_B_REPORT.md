# Alert Center — Phase B Implementation Report

Date: 2026-06-06 (~23:55 +07) · Status: **IMPLEMENTED LOCALLY on branch `alerts-phase-b` — NOT pushed, NOT deployed.** Frappe Cloud deploy waits for separate confirmation (D4 gate).

Branch state: `alerts-phase-b` = `origin/main (993bf1a)` + 2 commits:
- **`5e4d6c1`** — Alert Center Phase B (32 files, +1870, all additive)
- **`e13aaaa`** — PM v2 G3 re-commit (yours — see §9 incident note)

---

## 1. Files added / changed (commit 5e4d6c1)

Changed (3, all additive — verified clean diffs, no CRLF churn committed):
- `ecentric_workspace/modules.txt` — +`Alerts` module line.
- `ecentric_workspace/hooks.py` — fixtures filter += `"Brand Approver-kam_owner"` (+3 lines). No scheduler added.
- `ecentric_workspace/fixtures/custom_field.json` — + kam_owner record (now 3 records).

Added (29): `alerts/__init__.py`, `alerts/permissions.py` (144 lines), `alerts/doctype/__init__.py`, `alerts/tests/{__init__,test_phase_b}.py` (229 lines), and 8 DocType folders (`__init__.py` + `.json` + `.py` each).

## 2. DocTypes created (module `Alerts`, custom=0, track_changes=1, 143 fields total)

| DocType | Naming | Fields | Unique constraints |
|---|---|---|---|
| EC Marketplace Shop | `field:shop_code` | 8 | shop_code, omisell_shop_id |
| EC Brand Integration Settings | `EC-BIS-{####}` | 17 | (brand, integration_type) via validate() |
| EC Price Policy | `EC-PP-{#####}` | 18 | — |
| EC Marketplace Order Log | `EC-MOL-{######}` | 16 | order_key (= source\|external_order_id, auto-set) |
| EC Marketplace Order Item (child) | — | 13 | — |
| EC Alert | `EC-AL-{######}` | 32 | dedupe_key |
| EC Alert Action | `EC-AA-{######}` | 25 | dedupe_key |
| EC Automation Pause | `EC-AP-{#####}` | 14 | — |

Spec compliance highlights: rule_code has all 8 values incl. `missing_brand_mapping` / `missing_integration_credential` / `stock_lock_api_failed`; action_type has **no Off Listing**; `dry_run_stock_lock` default 1; `severe_drop_percent` default 70; `stock_lock_duration_minutes` default 120; EC Alert Action statuses include Skipped + Dry Run; `is_brand_fallback` flag makes policy lookup priority 6 an explicit opt-in; api_key/api_secret/token are Password fieldtype. Controllers: minimal validate/before_insert only (BIS uniqueness, policy date/target sanity, order_key auto-set, resolved_at/by auto-set, pause window sanity). Business logic = Phase C.

## 3. Custom Field fixture

`Brand Approver-kam_owner` — Link User, label "KAM Owner", insert_after `manager_email`, in_list_view + in_standard_filter, not reqd (D1). Synced automatically on migrate. The 7 existing brand records still need values filled (you, in Desk — or I seed with confirmation).

## 4. Permission implementation (D2 — no new roles)

- Every non-child DocType ships DocPerm = **System Manager only** (in DocType JSON, version-controlled; zero changes to existing DocTypes/roles; nothing touched in Role Permission Manager).
- `alerts/permissions.py`: `get_allowed_brands(user)` → `"*"` for System Manager/Administrator, else `{brand: role}` from **active** Brand Approver records (`kam_owner`→kam, `manager_email`→manager, `leader_email`→leader, strongest wins). Gates: `require_alert_center_access`, `require_brand_access`, `filter_brands`. Capabilities: handle alert = kam/manager/leader; create pause = kam/manager; cancel pause = manager/leader; credentials + action execution = System Manager only. Fail-safe: lookup error → empty scope, logged, never widened.

## 5. Migration requirement

One standard migrate (no patches): creates 8 tables + syncs fixture. `patches.txt` untouched. Idempotent — re-running migrate is safe.

## 6. Local test results

No bench/Frappe site exists in this sandbox, so:
- **Executed here:** `py_compile` on all 13 Python files [OK]; JSON schema validation on all 8 DocTypes (field_order consistency, track_changes, module, Link targets, perms, autoname, rule_code completeness) [OK]; **mock-frappe harness: 24/24 permission-matrix assertions passed** (incl. kam>manager rank, cross-brand denial, fail-safe on DB error); blob-level verification that committed content is intact (re-parsed JSON/py from `git show 5e4d6c1:...`) [OK].
- **Pending on a real site:** `alerts/tests/test_phase_b.py` (10 cases: schema, unique dedupe, kam_owner field, link integrity, BIS uniqueness + dry-run default, policy validation, permission matrix, Desk lockdown, order_key dedupe). Run with `bench --site <dev-site> run-tests --module ecentric_workspace.alerts.tests.test_phase_b` on your local bench, or on FC staging/Bench console after deploy. This is the honest limitation: schema has not been through a real `migrate` yet.

## 7. Risks / limitations

- **Not migrate-tested** until run on a real site (§6) — recommend local bench or FC staging first if available; otherwise the production deploy IS the first migrate (mitigated: additive only, no data migration, instant rollback by revert).
- Naming series `format:EC-XX-{####}` assumed supported by site's Frappe version (standard since v13) — verified at migrate.
- Fixture now owns `Brand Approver-kam_owner`; future manual edits to that Custom Field get overwritten on migrate.
- OneDrive working-copy quirks (see §9) — repo operations from the sandbox side are fragile; recommend final push happens from your Windows git.

## 8. Frappe Cloud deploy steps (NOT executed — awaiting your confirmation)

1. (You or me w/ confirmation) push `alerts-phase-b` to GitHub → review → merge to `main`. Recommend pushing from **your Windows machine** (`git push origin alerts-phase-b`) given OneDrive lock flakiness in the sandbox.
2. Frappe Cloud dashboard → site `team.ecentric.vn` → **Update/Deploy** (pulls main, builds, runs migrate).
3. Watch deploy log: fixture sync + 8 DocType creations, no errors.
4. Post-deploy verification (read-only): Desk → check `kam_owner` on Brand Approver, 8 DocTypes exist under module Alerts, non-SM user sees none of them; optionally run test module on FC bench console; fresh `snapshot_live_state.ps1` → confirm custom_doctypes_list goes 31→39.
5. Fill `kam_owner` for the 7 brands. Then approve Phase C.

## 9. Rollback plan

All additive. Rollback = revert the merge commit on `main` → FC re-deploy. DocTypes already created on site can stay harmlessly (invisible to non-SM; no jobs, no UI) — physical removal only with explicit approval. `kam_owner` field likewise. No destructive step exists; nothing to release/disable yet (no scheduler, no page, no API).

## 10. ⚠️ Incident note — concurrent commit collision (2026-06-06 23:41)

While Phase B files were staged in the sandbox, a commit was made from your Windows machine ("PM v2 G3: checklist UI…"). Because the working copy was checked out on `alerts-phase-b` (I switched it for Phase B), your G3 commit landed **on the alerts branch and swept the 32 staged Phase B files into it** (mixed commit `4ab1cd3`, 34 files). The OneDrive-synced `.git` also produced stale lock files and one corrupted index along the way.

Resolution performed (nothing pushed at any point, no content lost): rebuilt index, untangled into two clean commits — `5e4d6c1` (Phase B, my authorship) + `e13aaaa` (PM v2 G3, your authorship, **byte-identical** to your original work: `git diff 4ab1cd3 e13aaaa` = empty). `4ab1cd3` and one bogus intermediate are now dangling (recoverable, ignorable).

Follow-ups for you:
1. **Your working copy is still on `alerts-phase-b`** — if you keep committing PM work tonight, it lands there. Either fine (it merges to main with Phase B) or `git checkout main` first — your call.
2. Housekeeping (Windows side, where unlink works): delete `.git/*.stale*` files and `.git/index.corrupt.*`.
3. Your G3 commit is currently only on `alerts-phase-b`; if PM G3 must reach main before Alert Center merges, cherry-pick `e13aaaa` to main.
4. Suggestion going forward: tell me when you're about to commit on this repo (or I'll work via patch files instead of the shared checkout) — git + OneDrive + two concurrent writers is the root risk here.
