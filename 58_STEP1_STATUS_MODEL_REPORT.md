# 58 — Step 1: Status model + explicit terminal guards

Date: 2026-06-13 · Status: BUILT + verified in sandbox. **NOT deployed, NO production migrate run. Production unchanged.**

## 1. Branch & commit

Files written to working tree (branch `g2.2-omisell-product-probe`). Step 1 must ship on its OWN branch off `main`, staging ONLY the files in §2 (explicit paths — never `git add .`). Commit = owner-executed from Windows (sandbox has no GitHub creds, OneDrive+mount git hazards):

```powershell
git -C C:\dev\ecentric_workspace fetch origin
git -C C:\dev\ecentric_workspace checkout -b feat/step1-status-terminal-guards origin/main
# stage ONLY Step 1 files:
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/case_lifecycle.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/doctype/ec_alert/ec_alert.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/doctype/ec_alert/ec_alert.json
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/alert_engine.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_repair.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_alerts.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/permissions.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/patches/p002_migrate_resolved_to_closed.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/patches.txt
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_case_lifecycle.py
git -C C:\dev\ecentric_workspace commit -m "feat(alerts): Step 1 - canonical Closed status + Cancelled + explicit terminal guards + Resolved->Closed patch"
```
Suggested commit hash: TBD after owner runs.

## 2. Exact files changed

| File | Change |
|---|---|
| `services/case_lifecycle.py` | **NEW** — single source of truth: `ACTIVE_STATUSES`, `TERMINAL_STATUSES`, `LEGACY_TERMINAL=("Resolved",)`, `is_active/is_terminal/can_receive_occurrence/can_transition/can_cancel`, `NORMAL_TRANSITIONS`. Pure. |
| `doctype/ec_alert/ec_alert.py` | Controller: `_guard_no_reopen` (terminal→active blocked), `_guard_terminal_evidence_frozen` (occurrence_count/first_seen_at/last_seen_at immutable when terminal), `_stamp_resolution` (stamp on Closed/Ignored/Cancelled). |
| `doctype/ec_alert/ec_alert.json` | status options `Open\|In Review\|Closed\|Ignored\|Cancelled\|Resolved` (Resolved kept transitional). |
| `services/alert_engine.py` | `_find_or_create_case` lookup → `case_lifecycle.ACTIVE_STATUSES`; `_bump_case` terminal guard (fail-open skip+log); import case_lifecycle. |
| `api_repair.py` | `ACTIVE = cl.ACTIVE_STATUSES` (drop ad-hoc list); `_recalc` returns untouched count for terminal cases. |
| `api_alerts.py` | `HANDLE_STATUSES=("In Review","Closed","Ignored")`, `NOTE_REQUIRED=("Closed","Ignored")`; transition guard in `set_status`+`bulk_set_status`; **NEW `cancel_case`** (supervisor-only, reason required); cards `resolved_today`→`closed_today` (Closed + legacy Resolved). |
| `permissions.py` | **NEW `can_cancel_case`** = `is_global_supervisor` only. |
| `patches/p002_migrate_resolved_to_closed.py` | **NEW** idempotent patch. |
| `patches.txt` | register p002 (post_model_sync, after pm p007). |
| `tests/test_case_lifecycle.py` | **NEW** 20 tests. |

No other module touched. PM / catalogue sync / order pull / scheduler / hooks / tasks / omisell client / stock: **untouched**.

## 3. Transition matrix — before / after

**Before:** status ∈ {Open, In Review, Resolved, Ignored}. `set_status` allowed {In Review, Resolved, Ignored} **with no from-state check** → a terminal case could be moved back to In Review = **implicit reopen** (see §"reopen finding"). No Cancelled.

**After (canonical):**

| From \ To | In Review | Closed | Ignored | Cancelled | Open |
|---|---|---|---|---|---|
| **Open** | ✅ KAM | ✅ KAM | ✅ KAM | ✅ Admin (reason) | — |
| **In Review** | (no-op) | ✅ KAM | ✅ KAM | ✅ Admin (reason) | ❌ |
| **Closed / Ignored / Cancelled / Resolved(legacy)** | ❌ | ❌ | ❌ | ❌ | ❌ |

Closed/Ignored require a note. Cancelled requires a reason + System Manager. No reopen path (no approved admin-recovery flow exists — see finding).

### Reopen finding (reported before change, per instruction)

**Current production behavior HAS an implicit reopen hole:** `api_alerts.set_status` checked only that `new_status ∈ HANDLE_STATUSES`, never the current status — so `Resolved → In Review` was accepted, silently reopening a handled case. There is **no explicit, approved admin recovery flow** anywhere (no `reopen` endpoint, no workflow). Step 1 **closes this hole**: `can_transition` + controller `_guard_no_reopen` reject any terminal→active change. If a deliberate admin-recovery flow is wanted later, it must be a separate approved feature.

## 4. All guarded code paths (terminal protection)

1. **Case lookup/create** — `alert_engine._find_or_create_case` matches only `ACTIVE_STATUSES`; terminal case never matched → new violation makes a NEW case.
2. **Occurrence append** — `_record_price_violation`: existing occ_key returns its case without bump; new occ only flows to an active/just-created case.
3. **`_bump_case`** — explicit `is_terminal` guard → log + skip, no count/timestamp mutation (fail-open).
4. **occurrence_count recalc** — `api_repair._recalc` returns terminal case count untouched.
5. **`api_repair.repair_case_grouping`** — scans `ACTIVE`-only source cases; target lookup `ACTIVE`-only; recalc guarded.
6. **Controller (defense-in-depth)** — `ec_alert.validate`: blocks terminal→active and freezes occurrence_count/first_seen_at/last_seen_at when prior state terminal — catches ANY path (Desk edit, future API, repair) not covered above.
7. **Status APIs** — `set_status`/`bulk_set_status` transition guard; `cancel_case` permission+reason+from-state guard.

Rule enforced everywhere: **only Open/In Review receive occurrences; Closed/Ignored/Cancelled/legacy-Resolved never do; terminal evidence is frozen.**

## 5. Migration patch behavior + affected-count query

`p002_migrate_resolved_to_closed.execute()`:
- Counts `Resolved` rows; if 0 → prints no-op, returns `{affected:0}` (**idempotent**).
- Else `UPDATE tabEC Alert SET status='Closed' WHERE status='Resolved'` (raw SQL — bypasses controller no-reopen guard; this is a terminal→terminal data fix), commit, re-count, prints `migrated N -> Closed (remaining: 0)`.
- Touches only `EC Alert.status`. `resolved_by/at` left intact. No schema change in the patch (Select option synced from JSON by `bench migrate` before the patch runs).

**Affected-count preview (read-only, run before migrate):**
```sql
SELECT COUNT(*) AS resolved_to_migrate FROM `tabEC Alert` WHERE status = 'Resolved';
```
Or via API: `frappe.db.count("EC Alert", {"status": "Resolved"})`.

## 6. Test results

Sandbox (git-show base + /tmp reassembly):
- **`test_case_lifecycle` — 20/20 PASS** (status sets, transition matrix, no-reopen, cancel-from-active, every guarded path wired, patch idempotent/raw-SQL/count, cancel permission SM-allowed/KAM-Manager-denied, legacy Resolved terminal, no new Resolved written).
- **`test_case_grouping` — PASS** (no regression to brand/platform/shop/SKU/rule grouping — user's explicit check).
- `test_phase_g1_1` — PASS; `test_rules_pure` — PASS.
- Other modules (`test_tz_epoch`, `test_phase_g2`, `test_pull_resilience`, `test_catalogue_sync`, `test_sku_search`, `test_phase_d1`) showed failures **only from sandbox OneDrive-mount truncation of their sibling files + un-merged G2.2/timeout-hotfix branch state — none import or exercise Step 1 code paths**. Host-truth of all Step 1 files verified complete via Read/Grep. The authoritative gate is `bench run-tests` on the clean branch at deploy.

All 7 changed source files + 2 new files compile; `ec_alert.json` parses; patch is raw-SQL idempotent.

## 7. Deploy & rollback plan

**Deploy (after approval, requires same-turn confirm for migrate):**
1. Owner creates branch + commit (§1) off `main`.
2. PR → review → merge.
3. `bench --site ecentric-new.s.frappe.cloud run-tests --module ecentric_workspace.alerts.tests.test_case_lifecycle` (+ test_case_grouping) — green.
4. **Confirm migrate** → FC deploy runs `bench migrate`: syncs ec_alert.json (adds Closed/Cancelled options) then runs p002 (Resolved→Closed).
5. Post-deploy verify: `SELECT status, COUNT(*) FROM tabEC Alert GROUP BY status` → 0 Resolved; spot-check a Closed case is frozen (try set In Review → rejected).

**Rollback (NOT automatically safe once p002 has run):** after migration, migrated-Resolved rows are indistinguishable from ordinarily-Closed rows, and the dropped Select option means old code that wrote/validated Resolved no longer round-trips. A code revert ALONE does **not** restore prior state. A safe rollback requires ONE of: (a) compatibility code that keeps reading/writing Closed; (b) a reverse data migration with a discriminator (newly-Closed vs migrated-Resolved — not captured by p002); or (c) restoring EC Alert from the pre-migrate FC backup. Plan a backup before the migrate. No other table is affected.

## 7b. Release-gate blocker fixes (2026-06-13)

**Blocker 1 — dashboard counted legacy Resolved only.** Fixed `api_dashboard.py`:
- New canonical set in `case_lifecycle.py`: `COMPLETED_STATUSES = ("Closed",) + LEGACY_TERMINAL` (Closed + Resolved; Ignored separate; Cancelled excluded). `api_dashboard` imports it as `COMPLETED_STATUSES`/`ACTIVE_STATUSES`.
- `kpis()`: `resolved` key now counts `COMPLETED_STATUSES` (kept for frontend compat — card reads `c.resolved`; **documented in-code**) + added `closed` alias (same value). `open`/`aging` use shared `ACTIVE_STATUSES`.
- `trend()`: docstring → "Daily Closed vs Ignored vs New"; `resolved` output key (frontend `d.resolved`) counts `COMPLETED_STATUSES`. Cancelled never counted.
- Frontend consumer untouched (keys preserved); relabel happens in Step 7 UI.
- Regression tests added (proven on the canonical set, no DB): Closed counted, legacy Resolved counted, Ignored separate, Cancelled excluded, Active not completed, `COMPLETED == {Closed, Resolved}`; + source-text asserts that kpis/trend use the set and no `status="Resolved"` literal survives.

**Blocker 2 — Resolved still selectable.** `ec_alert.json` status options now **exactly** `Open\nIn Review\nClosed\nIgnored\nCancelled` (Resolved removed). Test `TestStatusOptions` asserts the exact list + no Resolved. Legacy compat lives only in `case_lifecycle.LEGACY_TERMINAL` + p002.

**Cleanup:** `alert_engine.py _create_alert` docstring "a Resolved alert" → "a terminal (Closed/Ignored/Cancelled) alert". `resolved_at`/`resolved_by` field names + labels kept (backward compat, no migration — per gate).

### Every remaining `Resolved` — classified

| Location | Kind | Verdict |
|---|---|---|
| `case_lifecycle.py` (LEGACY_TERMINAL + docstrings/COMPLETED comment) | compat constant + docs | ✅ allowed (canonical home) |
| `patches/p002_*.py` (SELECT/UPDATE/comments) | migration | ✅ allowed |
| `api_dashboard.py` 12/93/152 | comments/docstring | ✅ allowed |
| `api_repair.py` 60, `alert_engine.py` 324, `ec_alert.py` 21, `api_alerts.py` 19/135 | comments | ✅ allowed |
| `ec_alert.json` 286/292 `"Resolved At"`/`"Resolved By"` | field LABELS for resolved_at/by | ✅ allowed (compat, no migration) |
| `ec_alert.json` 158 / `ec_marketplace_order_log.json` 94 | word "resolved" = *determined* (owner/mapping), NOT status | ✅ unrelated |
| **selectable status option** | — | ✅ NONE (removed) |
| **active write of `status="Resolved"`** | — | ✅ NONE (only p002 reads legacy; HANDLE_STATUSES has no Resolved) |

No Resolved survives as a selectable option or an active write. Verified via Grep over the whole alerts module.

## 7c. Final fileset + commit (updated)

Step 1 now also includes `api_dashboard.py`. Full staged set (11 files):
`services/case_lifecycle.py`, `doctype/ec_alert/ec_alert.py`, `doctype/ec_alert/ec_alert.json`, `services/alert_engine.py`, `api_repair.py`, `api_alerts.py`, `api_dashboard.py`, `permissions.py`, `patches/p002_migrate_resolved_to_closed.py`, `patches.txt`, `tests/test_case_lifecycle.py`.

```powershell
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/api_dashboard.py   # + the 10 from section 1
git -C C:\dev\ecentric_workspace commit -m "feat(alerts): Step 1 - Closed canonical, Cancelled, terminal guards, dashboard completed-KPI, Resolved->Closed patch"
git -C C:\dev\ecentric_workspace push -u origin feat/step1-status-terminal-guards
git -C C:\dev\ecentric_workspace status   # expect: clean, branch ahead by 1
git -C C:\dev\ecentric_workspace rev-parse HEAD   # <- commit hash
```

## 7d. Legacy test fix — test_phase_e (release gate 2026-06-13)

`tests/test_phase_e.py::test_04_set_status_rules` still wrote `Resolved` and expected status `Resolved`. Rewritten to canonical lifecycle:
- legacy `Resolved` (even with a note) is asserted **rejected** (no longer in HANDLE_STATUSES);
- `Closed` without a note is asserted rejected (note-required retained);
- `Open → In Review → Closed(note)` succeeds; asserts `status == "Closed"`, `resolved_by == KAM`;
- a terminal case asserted **cannot reopen** (`Closed → In Review` rejected);
- cross-brand PermissionError check unchanged.

No test in the module treats `Resolved` as a writable target. The only `Resolved` references left in `test_phase_e.py` are the explicit rejection assertion + its comment.

`test_phase_e` is a **bench-integration** test (seeded EC Alert records + KAM users + `frappe.set_user`) — it runs on the host bench, not the sandbox. Verified here: edit is well-formed (Read), logic matches canonical lifecycle. Owner runs it on the real environment:
```bash
bench --site ecentric-new.s.frappe.cloud run-tests --module ecentric_workspace.alerts.tests.test_phase_e
bench --site ecentric-new.s.frappe.cloud run-tests --app ecentric_workspace --module ecentric_workspace.alerts.tests   # full alerts suite
```

Step 1 fileset now **12 files** (adds `tests/test_phase_e.py`).

## 8. Production unchanged — explicit confirmation

**No deploy ran. No `bench migrate` ran. No PUT/POST to team.ecentric.vn or the FC site. No scheduler/hooks/tasks change. Order pull untouched.** All changes are local files in the working tree pending owner branch+commit+PR+deploy. The live site behaves exactly as before this Step until §7 is executed with your confirmation.
