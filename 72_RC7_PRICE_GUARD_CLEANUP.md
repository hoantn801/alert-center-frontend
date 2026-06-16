# RC7 — Price Setup fallback badge + safe deletion (A), Rules action hierarchy (B), Gift/Freebie exemption design (C)

Date: 2026-06-16. **A and B implemented; C is a design report only (no schema change
this round).** Repos: frontend `ALERT_CENTER` (`frontend/build_alert_pages.py`),
backend `ecentric_workspace`. **Not committed, not merged, not migrated, not deployed.**
Generated `frontend/*.html` are git-ignored artifacts.

---

## A. Price Setup: misleading fallback badge removed + safe deletion defined

### A1. Fallback badge (frontend)
Inspected: the policy row rendered two legacy scope indicators — `polScope(r)` beside
Brand ("Brand fallback" / "Shop Policy" / "Platform Policy" / "SKU-specific") and the
conflict badge beside the SKU whose `overridden` branch showed "fallback"/"override"
(the old Shop+Platform override hierarchy). Since Shop is no longer part of the
canonical identity, both are misleading.

- Removed `polScope(r)` from the row's Brand cell (the function stays defined; it is
  simply no longer rendered in the table).
- Removed the `overridden` → "fallback"/"override" branch from `loadConflicts`. The
  genuine **"duplicate"** conflict warning beside the SKU is kept.
- Legacy lookup metadata (shop, is_brand_fallback) remains stored; it is not shown
  beside the SKU in the normal table.

### A2. Safe deletion — does a safe delete API exist today? **No (before RC7).**
Inspected `api_policies.py` (endpoints: list/save/set_policy_status/missing/caps/
conflicts/canonical_duplicates/csv*), the controller, and references. Findings:
- **No** `delete_policy` / `archive_policy` endpoint existed.
- `set_policy_status` already reaches **Paused / Inactive / Expired** (so
  deactivate/archive is the existing ordinary-user path).
- The controller had **no `on_trash`** guard.
- EC Alert / EC Alert Occurrence reference a policy only **functionally by scope**
  (brand + platform + seller_sku/item) — there is no Link field; `policy_setup.
  terminalize_for_policy` closes covered missing-policy alerts but stores no FK.

**Implemented the safe-delete contract** (backend; never frontend-only):
- Pure decision `policy_validation.delete_decision(status, is_admin, open_deps)`:
  Draft → delete if no open dependents; Active → `active_no_delete`; Paused/Inactive/
  Expired → `admin_only` for non-admins, else allowed if no dependents.
- API `api_policies.delete_policy(name)` enforces it: `_require_manage` scope, admin =
  `perms.is_global_supervisor` (System Manager / global supervisor), dependents =
  `_policy_open_dependents` = count of NON-terminal (Open/In Review) EC Alerts matching
  the policy scope. Audit history + alert rows are never touched.
- Controller `on_trash` defense-in-depth: an Active policy or one with open dependents
  can never be deleted, even via Desk.
- Frontend: a low-emphasis `Xoá vĩnh viễn` (Delete) button in the drawer footer, shown
  only when the contract could allow it (existing record, not Active, Draft→manager or
  retired→supervisor). It calls the real `delete_policy`, confirms first, and the
  backend re-enforces everything (no frontend-only deletion). Deactivate/pause stays on
  the table status switch (RC5/RC6).

## B. Rules page: one primary action per row

Inspected the RC5-4 inline editor. The override-editing row previously showed **two**
full buttons (Save + "Bỏ tùy chỉnh"). Redesign:
- Main behaviour row: rule name + All-platforms value/input + **one primary Save** +
  small status chip (unchanged — already one primary).
- Inherited platform row: `Platform` + `Kế thừa X%` (read-only) + a small `Thêm tùy
  chỉnh` button only — no input, no Save.
- Override (edit) row: input + **one primary Save**; **"Bỏ tùy chỉnh" demoted to a
  small destructive ✕ icon** (`ru-icon ru-danger`, tooltip/aria "Bỏ tùy chỉnh").
- The states are mutually exclusive — Add (inherited) vs Save+small-✕ (override) — so
  Add + Save + Remove never appear together. Backend truth + canonical reload after
  save/remove and the RC6 override-identity fix are preserved.

## Files changed (A + B)

Frontend: `frontend/build_alert_pages.py` (PAGE2 row badge + drawer Delete button +
`deletePolicy`/`refreshDeleteBtn` + labels + `.al-danger` CSS; PAGE3 override icon +
`.ru-icon` CSS; RC7 in-builder asserts).

Backend:
- `ecentric_workspace/alerts/services/policy_validation.py` — `delete_decision()`.
- `ecentric_workspace/alerts/api_policies.py` — `delete_policy()` +
  `_policy_open_dependents()` + `ALERT_OPEN_STATUSES`.
- `ecentric_workspace/alerts/doctype/ec_price_policy/ec_price_policy.py` — `on_trash`.
- `ecentric_workspace/alerts/tests/test_policy_validation.py` — `TestDeleteDecision`.

## Validation (A + B)

- Backend `test_policy_validation` — **Ran 22 tests, OK** (incl. the 5 new delete-
  contract tests: Active never deletable, Draft no-deps allowed, Draft+deps blocked,
  retired admin-only, retired+deps blocked). `py_compile` OK for policy_validation,
  api_policies, ec_price_policy, policy_scope.
- Frontend: full 5-page build, **all 8 assert suites pass** (M2d now asserts the row
  fallback badge is gone + the safe-delete wiring; M3 asserts the override remove is a
  small icon). `node --check` 5/5 JS_OK; duplicate-id 5/5 NONE; RC7 grep proofs all
  True; repo pages regenerated. No unrelated page changes.

---

## C. Gift/Freebie Price Guard exemption — architecture report (NO schema change yet)

### Can an existing doctype carry this cleanly? **No — a small dedicated doctype is the smallest safe model.**
Reviewed all `alerts/doctype/*`. The closest candidates and why they don't fit:
- `EC Automation Pause` — has brand/platform/shop/seller_sku + window + reason, but its
  semantics are committed to "Stock Safety Lock automation pause"; reusing it for price
  exemption is an overload.
- `EC Marketplace SKU Catalog` — order-derived, read-only discovery; adding an exemption
  flag overloads an audit table.
- `EC Price Policy` / `EC Alert Rule` — these ARE the price config; encoding "skip this
  SKU" as a policy/rule is semantically confusing and not auditable as an exemption.

None carries an explicit, auditable per-(brand, platform, seller_sku) exemption.

### Proposed model: new doctype `EC Price Guard Exemption`
Fields:
- `brand` (Link Brand Approver, reqd, filter)
- `platform` (Select All/Shopee/Lazada/TikTok, default All, filter)
- `seller_sku` (Data, reqd, filter) — normalized strip()+upper() to match the canonical
  identity convention
- `reason` (Select or Small Text, reqd; includes **Gift / Freebie**, plus e.g. Sample /
  Test Stock / Other)
- `effective_from` (Date, optional), `effective_to` (Date, optional)
- `status` (Select Active/Inactive/Expired, default Active, list view + filter)
- `exempted_by` (Link User, read-only, set on insert) + track_changes for audit
- autoname `format:EC-EXEMPT-{######}`

Semantics are explicit (the doctype name + fields) and auditable (reason + window +
exempted_by + change tracking).

### Evaluation insertion points (must run BEFORE rule selection AND before coverage)
- **Alert engine:** `services/alert_engine.py` — immediately before the single
  `policy_lookup.find_policy(...)` call per order line: if
  `is_exempt(brand, platform, seller_sku)` → set the line result to a canonical
  `"Skipped — Gift/Freebie"` and `continue` (skips below-min, above-high, severe-drop,
  missing-zero, and missing-policy for that line). Unrelated mapping / integration-health
  checks are NOT skipped.
- **Coverage / missing-policy:** `services/policy_coverage.py` `missing_rows()` WHERE
  clause — add `AND NOT <exempt EXISTS>` so an active-exempt SKU is removed from the
  missing/coverage count.

### Files that would change (for the C implementation round, NOT done now)
1. NEW `alerts/doctype/ec_price_guard_exemption/ec_price_guard_exemption.json` (+ `.py`)
2. NEW `alerts/services/exemption_guard.py` — `is_exempt(brand, platform, seller_sku,
   on_date=None)` + a small cached SQL `EXISTS` predicate (active + date-window)
3. MODIFY `alerts/services/alert_engine.py` — exemption check before `find_policy`
4. MODIFY `alerts/services/policy_coverage.py` — exclude exempt SKUs from missing count
5. NEW `alerts/api_exemptions.py` — whitelisted, brand-scoped CRUD (list/create/update/
   deactivate)
6. Tests: pure `is_exempt` window/status logic + an evaluation-skip test returning the
   canonical `Skipped — Gift/Freebie` result
7. Frontend (optional, later): a small Exemptions admin view; not required for the engine

**Recommendation:** approve the dedicated `EC Price Guard Exemption` doctype + the two
evaluation insertion points above; that is the smallest explicit, auditable model and
keeps exemption logic out of the policy/rule/pause doctypes. Awaiting approval before any
schema/migration.

(Approved + implemented — see "RC7 FINAL" below.)

---

## RC7 FINAL — A hardened, B revalidated, C (Gift Exemption V1) implemented

### A (hardened) — permanent-delete eligibility
"No open alerts" is NOT treated as proof a policy is unused. The pure contract is now
3-valued on historical dependency: `delete_decision(status, is_admin,
historical_dependency)` → `historical_dependency` ∈ {True, False, None}; **None (cannot
determine reliably) fails closed**. Active → never; Draft → only if reliably no
historical dependency; Paused/Inactive/Expired → System-Manager-only with reliably no
historical dependency.

**Schema reality (reported):** there is NO direct EC Alert → EC Price Policy relation.
So we never positively enumerate historical alerts; we assert "reliably none" only when
the policy was provably **never operationally used** (the engine matches Active policies
only). "Ever Active" is read reliably from the change history — **EC Price Policy has
`track_changes: 1`** (`_policy_ever_active` via the Version log; unreadable/untracked →
None → fail closed). Recommended future hardening: add a `matched_policy` Link on
EC Alert / EC Alert Occurrence to enable a positive historical-dependency check.

Frontend never infers eligibility from status: `refreshDeleteBtn` calls
`api_policies.policy_delete_capability` → `{can_delete, delete_reason}` and only shows
Delete when `can_delete`. Desk `on_trash` and the API use the SAME guard.

### B — revalidated only (no change). One primary Save per override row; "Bỏ tùy chỉnh"
is the small destructive icon. M3 asserts still green.

### C — Gift Exemption V1 (implemented)
Dedicated gift/freebie Seller SKUs only (canonical `brand + platform + seller_sku`);
mixed-use SKUs are explicitly out of scope (need a line-level gift signal). New doctype
`EC Price Guard Exemption` (brand, platform, seller_sku, reason incl. **Gift / Freebie**,
effective_from/to, status Active/Inactive, notes, exempted_by, `track_changes:1`) with
uniqueness/overlap validation (no two Active exemptions for the same scope with
overlapping windows). ONE shared resolver `services/exemption_guard.py`
(`match_exemption`/`is_exempt` + `exempt_exists_sql`) reused at all three insertion
points:
- `alert_engine.py` — checked BEFORE `policy_lookup.find_policy`; a match sets the line
  to canonical `Skipped — Gift/Freebie` and `continue`s, skipping below-min/above-high/
  severe-drop/possible-missing-zero AND missing-policy. Brand/SKU mapping +
  integration-health checks run upstream and are untouched.
- `policy_coverage.py missing_rows()` — exempt SKUs excluded from the missing-policy
  count (date = today, so only during the window).
- `baseline.py _history_prices()` — gift-window order lines excluded from the 30-day
  median (DATE(order_datetime) inside the window) so gift prices never contaminate the
  baseline after the exemption ends.
Time-window: matches only when status Active and the date is within effective_from/to;
after expiry the SKU returns to normal coverage + Price Guard. API `api_exemptions.py`
(brand-scoped list/save/set_status; NO hard delete in V1). UI: a compact "Gift
Exemptions" panel in Price Setup (separate from the policy table) — list, create/edit
modal, in-place status toggle.

### Files changed (RC7 full)
Backend (`ecentric_workspace`):
- `alerts/services/policy_validation.py` — 3-valued `delete_decision`.
- `alerts/api_policies.py` — `_policy_ever_active`, `_policy_historical_dependency`,
  `policy_delete_capability`, `delete_policy`, `_raise_delete_reason`.
- `alerts/doctype/ec_price_policy/ec_price_policy.py` — `on_trash` (same guard).
- `alerts/services/exemption_guard.py` — **NEW** shared resolver.
- `alerts/doctype/ec_price_guard_exemption/{__init__.py, .json, .py}` — **NEW** doctype.
- `alerts/api_exemptions.py` — **NEW** API.
- `alerts/services/alert_engine.py`, `services/baseline.py`, `services/policy_coverage.py`
  — exemption insertion points (reuse the shared resolver).
- `alerts/tests/test_policy_validation.py` (delete contract), `tests/test_exemptions.py`
  (**NEW**).

Frontend (`ALERT_CENTER`): `frontend/build_alert_pages.py` — PAGE2 row fallback-badge
removal, safe-delete button via capability, Gift Exemptions panel + modal + JS + labels
+ asserts; PAGE3 override icon. (`frontend/alert_*.html` regenerated, git-ignored.)

### Migration / schema impact
ONE schema change: the new `EC Price Guard Exemption` doctype → requires
`bench --site <site> migrate` to create `tabEC Price Guard Exemption`. No change to
existing tables/fields; no data migration. (EC Price Policy `track_changes` was already
enabled — no change.)

### Test results
- Backend: **58/58 unit tests pass** per-module (`test_policy_validation` 24 incl. the
  3-valued delete contract + fail-closed; `test_canonical_identity` 19; `test_exemptions`
  15 incl. window/inactive/platform/SKU/overlap + engine-before-lookup, coverage- and
  baseline-exclusion wiring via the single shared resolver). `py_compile` OK for all 9
  changed modules; the exemption doctype JSON parses.
- Frontend: full 5-page build, **all 8 assert suites pass** (incl. RC7-A capability
  wiring + RC7-C exemptions UI). `node --check` 5/5 JS_OK; duplicate-id 5/5 NONE; repo
  pages regenerated.

### Deployment order (when approved)
1. **Backend first**: deploy `ecentric_workspace`, then `bench --site <site> migrate`
   (creates the exemption table) + `bench build` / restart so `api_exemptions`,
   `api_policies.delete_policy` / `policy_delete_capability`, and the engine/coverage/
   baseline changes are live.
2. **Then frontend**: rebuild + publish the 5 Web Pages (the Gift Exemptions UI and the
   Delete button call the backend added in step 1).
Rolling out the frontend before the backend would make the new API calls 404.

### Blockers
None blocking. Two documented limitations (by design, not defects): (1) no Alert→Policy
FK, so permanent delete fails closed for any ever-Active policy until a `matched_policy`
link is added; (2) Gift Exemption V1 covers dedicated gift SKUs only — mixed-use SKUs
need a future line-level gift signal.

**Not committed, not merged, not migrated, not deployed — pending approval.**
