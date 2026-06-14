# 60 — Step 2: Frappe ToDo lifecycle for Alert Case

Date: 2026-06-13 · Status: BUILT + sandbox-verified. **NOT deployed. Zero migration. Production unchanged.**

## Files (3; zero migration)

| File | Change |
|---|---|
| `services/case_todo.py` | **NEW** — `sync_todo`, `ensure_one_open_todo`, `close_open_todos`, `_add/_remove/_close_all/_open_todos`, `_description`. Reuses `case_lifecycle` (status) + reads `case.owner_user` (resolved once by `brand_resolver.resolve_owner` at case creation — no re-resolve). |
| `doctype/ec_alert/ec_alert.py` | `after_insert` → `sync_todo`; `on_update` → `sync_todo` **only when status or owner_user changed** (skips occurrence_count/evidence updates). |
| `tests/test_case_todo.py` | **NEW** — 19 tests (10 binding + reassign/recursion/fail-open/guard-reset + wiring). |

No `todo_name` field → **no migration**. No PM / order pull / scheduler / catalogue / Omisell / stock touched.

## Recursion handling

The assignment API mutates `_assign` on the EC Alert (and may add a comment), which can re-enter `on_update`. Two layers stop a loop:

1. **Thread flag (hard stop):** `sync_todo` sets `frappe.flags._ec_alert_todo_syncing = True` on entry, returns immediately if already set, and resets it in `finally`. Any nested EC Alert save triggered by `assign_to` finds the flag set → no-op.
2. **Controller pre-check (cheap filter):** `on_update` calls `sync_todo` only when `before.status != self.status` or `before.owner_user != self.owner_user`. An `_assign`-only change (no status/owner delta) never reaches `sync_todo` in the first place. (In Frappe v15 `_assign` is updated via `frappe.db.set_value`, which does not run controller hooks — but the flag covers any edge path that does `doc.save`.)

Net: ToDo work runs exactly once per real case insert / status-change / owner-change; never recursively, never on occurrence bumps.

## Fail-open logging

`sync_todo` wraps the whole branch in `try/except` → on any error `frappe.log_error(traceback, "alerts.case_todo.sync_todo case=<name> brand=<brand> owner=<owner> status=<status>")`. **A ToDo backend error never propagates → Alert Case insert/update always succeeds** (verified by `test_fail_open_logs_and_does_not_raise`). Additional diagnostics:
- No owner: `frappe.logger("alerts").warning({"todo_skipped_no_owner": case, "brand":…, "rule_code":…})` — case still created/visible to Admin/Manager, just unassigned (D-S2-2).
- Per-user close failure inside `_close_all` is caught + logged, loop continues.

## Exact Frappe assignment API calls used (v15)

```python
# CREATE / assign (ensure_one_open_todo -> _add):
from frappe.desk.form.assign_to import add as _assign_add
_assign_add({"doctype": "EC Alert", "name": case.name,
             "assign_to": [owner], "description": _description(case),
             "notify": 0}, ignore_permissions=True)
# -> ToDo(allocated_to=owner, reference_type="EC Alert",
#         reference_name=case.name, status="Open") + sets _assign on the case.

# REASSIGN old owner / single close (_remove):
from frappe.desk.form.assign_to import remove as _assign_remove
_assign_remove("EC Alert", case.name, user, ignore_permissions=True)

# TERMINAL close-all (_close_all), with per-user fallback:
from frappe.desk.form.assign_to import close_all_assignments
close_all_assignments("EC Alert", case.name, ignore_permissions=True)
# fallback if signature differs: iterate _open_todos + _assign_remove each.
```

Closing uses the standard path → ToDo becomes **Cancelled** (Frappe's "assignment ended"), distinct from the business status `Closed`. **No bypass, no delete — records kept for audit** (D-S2-3).

**Bench verification note:** exact signatures of `remove` / `close_all_assignments` (positional vs `ignore_permissions=` kwarg) should be confirmed on the v15 bench at deploy; `_close_all` already hedges via try/except + per-user `remove` fallback, so a signature mismatch degrades gracefully rather than failing.

## Lifecycle → behavior (verified)

`Open` insert → 1 ToDo for owner. `Open→In Review` → same ToDo (idempotent). occurrence bump (`_bump_case` save) → no sync (no status/owner change). `Closed`/`Ignored`/`Cancelled` → ToDo closed. New violation after terminal → new case → new ToDo (old never reopened). Owner change while active → close old + add new (reassign); unchanged → no-op. No owner → no ToDo + diagnostic.

## Tests

Sandbox: **`test_case_todo` 19/19 PASS** (case→1 ToDo, occurrences→no extra, Open→In Review keeps, Closed/Ignored/Cancelled close, new-after-terminal→new, ensure idempotent, no-owner diagnostic, reassign, no-reassign-when-unchanged, recursion guard, fail-open, guard reset, controller-hooks-on-change-only, reuses lifecycle/owner helpers, no PM/order/Omisell, no todo_name, fail-open+guard present). Regression: `test_case_lifecycle` 30/30, `test_case_grouping` 15/15. (assign_to round-trip is bench-only; logic proven via in-memory fakes — owner runs `bench run-tests --module ...test_case_todo` on host.)

## Deploy & rollback

Branch off `main` (code-only, **no migrate**):
```powershell
git -C C:\dev\ecentric_workspace checkout -b feat/step2-todo-lifecycle origin/main
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/services/case_todo.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/doctype/ec_alert/ec_alert.py
git -C C:\dev\ecentric_workspace add ecentric_workspace/alerts/tests/test_case_todo.py
git -C C:\dev\ecentric_workspace commit -m "feat(alerts): Step 2 - Frappe ToDo lifecycle per Alert Case (fail-open, recursion-guarded, reassign, zero migration)"
git -C C:\dev\ecentric_workspace push -u origin feat/step2-todo-lifecycle
```
Depends on Step 1 (`case_lifecycle`, terminal statuses, ec_alert controller) — merge Step 1 first.
Rollback = revert the merge (no data/schema change; existing ToDos remain, simply no longer auto-managed). Safe, no migration.

## Production unchanged

No deploy, no migrate, no PUT/POST to the site, no scheduler/hooks/tasks/order-pull/catalogue change. Local files pending owner branch+commit+PR+deploy.
