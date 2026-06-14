# 62 — Step 2 two-flow ToDo: implementation (pre-commit review)

Date: 2026-06-13 · Status: BUILT + sandbox-verified. **NOT committed/deployed. Zero migration.** Q-S2-B approved (Brand Approver reference). Supersedes single-flow doc 60.

## 1. Exact PM assignment call pattern reused

From `pm/api/tasks.py:15,340` (the only proven assignment in the app — PM uses **only** `add`):
```python
from frappe.desk.form.assign_to import add as _assign_add
_assign_add({"doctype": "Task", "name": doc.name, "assign_to": [assignee]})   # in try/except + log_error
```
`case_todo.py` reuses this exact contract (same `add(args_dict)` shape), adding the standard documented `description` key (Frappe stores it on the ToDo):
```python
def _assign_add(args):
    from frappe.desk.form.assign_to import add as _add
    _add(args)
# incident:  _assign_add({"doctype":"EC Alert","name":case,"assign_to":[owner],"description":...})
# setup:     _assign_add({"doctype":"Brand Approver","name":brand,"assign_to":[owner],"description":...})
```
No `ignore_permissions`, no `notify` (matches PM → no email spam; engine runs as Administrator).

**Close:** PM never closes assignments, so there is no proven `remove`/`close_all_assignments` pattern to copy. Per your gate we do **NOT** use `close_all_assignments` (signature unproven). We use the stable public `assign_to.remove(doctype, name, user)` — query active ToDo rows, call `remove` once per allocated user; never force `ToDo.status` (keeps `_assign` consistent):
```python
def _assign_remove(doctype, name, user):
    from frappe.desk.form.assign_to import remove as _remove
    _remove(doctype, name, user)
```
The setup-ToDo count update is the ONLY direct ToDo write — `frappe.db.set_value("ToDo", name, "description", desc, update_modified=False)` — which touches neither status nor `_assign`.

## 2. Exact dedupe queries

```python
# Incident open ToDos for a case:
frappe.get_all("ToDo", filters={"reference_type":"EC Alert",
    "reference_name":case, "status":"Open"}, fields=["name","allocated_to","description"])

# Setup open ToDo(s) for a brand (marker-scoped, optionally owner-scoped):
frappe.get_all("ToDo", filters={"reference_type":"Brand Approver",
    "reference_name":brand, "status":"Open",
    "description":["like","[price_setup_missing]%"]}, fields=[...])

# Remaining distinct missing-policy SKUs for the brand (Flow B count source):
frappe.db.sql("""SELECT COUNT(DISTINCT seller_sku) AS n FROM `tabEC Alert`
    WHERE brand=%s AND rule_code='missing_policy' AND status IN %s
      AND seller_sku IS NOT NULL AND seller_sku != ''""",
    (brand, tuple(case_lifecycle.ACTIVE_STATUSES)))
```
Identity: incident = (EC Alert, case, Open); setup = (Brand Approver, brand, Open, marker `[price_setup_missing]`). Reuse/dedupe driven entirely by these.

## 3. Rule classification

| Set | rules | flow |
|---|---|---|
| `INCIDENT_RULES` | below_min, above_high, severe_price_drop, possible_missing_zero, missing_brand_mapping | A — per-case EC Alert ToDo |
| `SETUP_RULES` | missing_policy | B — aggregated Brand Approver ToDo |
| (none) | missing_integration_credential, ingestion_api_failed, stock_lock_api_failed | no KAM ToDo (System Manager) |

`sync_todo(case)` dispatches by `case.rule_code`. missing_policy never makes a per-case ToDo (test asserts).

## 4. Behavior verified

Flow A: active incident → 1 ToDo; occurrences → no dup; terminal → close; new case after terminal → new ToDo; owner change → reassign; no owner → diagnostic.
Flow B: N active missing_policy SKUs → ONE brand setup ToDo with "N SKU" in description; more cases reuse+update same ToDo (no dup); count→0 → close; recurrence → NEW ToDo (closed one never reopened, query is `status=Open` only); brands separate; owner change → reassign; no owner → diagnostic.
Recursion guard (`frappe.flags._ec_alert_todo_syncing`) + fail-open (try/except → log_error with case/brand/owner/status/rule) retained across both flows.

## 5. Test results (sandbox)

**`test_case_todo` 20/20 PASS** — incident 1–5 + missing_policy-not-incident + non-KAM-rule + setup 6–10 + setup reassign + setup no-owner + recursion guard + guard reset + fail-open + wiring (classification constants, reuses PM add + remove, no close_all_assignments call/import, controller dispatch). Regression: `test_case_lifecycle` 30/30, `test_case_grouping` 15/15.

Files (3, zero migration): `services/case_todo.py` (rewritten two-flow), `doctype/ec_alert/ec_alert.py` (controller unchanged from Step 2 shape — `after_insert`/`on_update` → `sync_todo`), `tests/test_case_todo.py` (rewritten 20 tests).

## 7. Gate resolutions (2026-06-13)

### Gate 1 — exact emitted rule-code inventory (grep-verified, not remembered)

Canonical source of truth = `EC Alert.rule_code` Select enum (9 codes). Emission sites:

| rule_code | emitted by | classification |
|---|---|---|
| `below_min` | `services/rules.py` `_hit` | INCIDENT |
| `above_high` | rules.py `_hit` | INCIDENT |
| `severe_price_drop` | rules.py `_hit` | INCIDENT |
| `possible_missing_zero` | rules.py `_hit` | INCIDENT |
| `missing_brand_mapping` | `alert_engine.py:55` `_create_alert` | INCIDENT |
| `missing_policy` | `alert_engine.py:99` `_create_alert` | **SETUP** |
| `missing_integration_credential` | `api_omisell.py:157`, `action_queue.py:171` | SYSTEM (no ToDo) |
| `ingestion_api_failed` | `api_omisell.py:206` | SYSTEM (no ToDo) |
| `stock_lock_api_failed` | EC Alert enum (stock-lock exec path) | SYSTEM (no ToDo) |

The shorthand `severe_drop` / `missing_zero` are **NOT** real codes — the engine emits `severe_price_drop` / `possible_missing_zero` (rules.py:44,51). No invented strings.

`case_todo.py` now defines `INCIDENT_RULES`, `SETUP_RULES`, `SYSTEM_RULES`; `sync_todo` dispatch:
- SETUP → Flow B; INCIDENT → Flow A; SYSTEM → `pass` (intentional no ToDo);
- **else (unknown/future code) → no ToDo + `logger.warning({"todo_unknown_rule_code", "case", "brand"})`** (fail-safe).

Tests: `test_union_covers_every_real_code` (union of the 3 sets == the 9 canonical codes — a new enum code that's unclassified fails this), `test_sets_disjoint`, behavior test per incident/setup/system code, `test_unknown_code_no_todo_and_diagnostic`.

### Gate 2 — missing-policy completion dependency (recorded, enforced)

Setup count = distinct `seller_sku` among **ACTIVE missing_policy CASES** — NOT policy-row existence. Creating a policy alone does not reduce it until the matching case is terminalized. Documented in `_remaining_missing_skus` docstring + **recorded as a Step 6 dependency in `57_…PLAN.md`**: after a successful policy save, Step 6 MUST auto-close matching active missing_policy cases + re-trigger the brand setup recompute. Do NOT claim auto-close on policy creation until Step 6 ships it. Tests: `test_terminalizing_final_case_closes_setup_todo`, `test_remaining_cases_keep_it_open`, `test_recurrence_new_todo_not_reopen`.

### Final classification table

INCIDENT = {below_min, above_high, severe_price_drop, possible_missing_zero, missing_brand_mapping} · SETUP = {missing_policy} · SYSTEM(no ToDo) = {missing_integration_credential, ingestion_api_failed, stock_lock_api_failed} · unknown → no ToDo + diagnostic.

### Three-file diff (net, vs pre-Step-2)

- `services/case_todo.py` (**NEW**, ~160 lines): two-flow ToDo service — INCIDENT/SETUP/SYSTEM sets + unknown fallback, `_ensure_incident_todo`/`_close_incident_todo` (ref EC Alert), `_sync_brand_setup`/`_remaining_missing_skus`/`_setup_description`/`_open_setup_todos` (ref Brand Approver, marker `[price_setup_missing]`), `_assign_add`/`_assign_remove` (PM contract, no close_all), recursion guard + fail-open `sync_todo`.
- `doctype/ec_alert/ec_alert.py` (**+11 lines**): `after_insert` → `sync_todo`; `on_update` → `sync_todo` only when `status` or `owner_user` changed. (Step-1 validate/guards unchanged.)
- `tests/test_case_todo.py` (**NEW**, ~355 lines): 29 tests — incident 1–5 + setup 6–10 + rule-classification inventory/behavior/unknown + setup-completion-dependency + recursion/guard-reset/fail-open + wiring.

### Test results
`test_case_todo` **29/29 PASS**; regression `test_case_lifecycle` 30/30, `test_case_grouping` 15/15.

## 6. Not committed

Awaiting your review of §1–§3 before commit. No deploy/migrate/Step 3. The assign_to round-trip + the COUNT SQL are bench-only (logic proven via in-memory fakes + stubbed count); owner runs `bench run-tests --module ...test_case_todo` on host before merge. Branch (after approval): `feat/step2-todo-two-flow` off main (merge Step 1 first).
