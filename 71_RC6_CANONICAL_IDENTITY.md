# RC6 — Canonical Price Policy identity + in-place status toggle

Date: 2026-06-16. Two bounded Price Setup micro-fixes only. **Not committed, not
merged, not deployed.** Repos: backend `ecentric_workspace`, frontend
`ALERT_CENTER` (`frontend/build_alert_pages.py`). No schema, no permission change.
Generated `frontend/*.html` are git-ignored artifacts.

---

## 1. Enforce one canonical policy per Brand + Platform + Seller SKU

### Root cause

The Active-conflict guard keyed on `scope_key(platform, **shop**, seller_sku, item,
fallback)` (`alerts/services/policy_scope.py`) — i.e. **Shop was part of the scope
identity**. Since Shop was removed from the standard model (RC5), two rows like
`FES-VN / TikTok / P02056 / shop=""` and `FES-VN / TikTok / P02056 /
shop=FES-VN-TIKTOK` had *different* scope keys, so both could be Active. The old
guard also only fired for `status == "Active"` and required overlapping validity
windows, so Draft/Paused duplicates and shop-variant duplicates slipped through.

### Fix (inspected first; smallest safe change)

Inspected: `policy_scope` (scope key + `find_active_conflict`), the controller
`EC Price Policy.validate()` + `_guard_exact_scope_conflict`, `api_policies.save_policy`
/ `set_policy_status` (both end in `doc.save()` → `validate()`), the engine
`policy_lookup.find_policy` (Active-only, seller_sku matched by the DB's
case-insensitive collation), and the existing `policy_conflicts` badge endpoint.

New **canonical identity** in `policy_scope.py`:

- `canonical_key(brand, platform, seller_sku, item)` = `(brand, platform or "All",
  normalized target)` where target = `strip().upper()` of `seller_sku` (falling back
  to the legacy ERP `item` for old rows). **Shop is ignored.** Empty target = the
  brand/platform **fallback** identity, which is *distinct* from any SKU.
- `LIVE_STATUSES = ("Draft","Active","Paused")` = "non-cancelled". There is no literal
  `Cancelled` status on EC Price Policy (statuses are Draft/Active/Paused/Expired/
  Inactive); per the lifecycle contract **Expired + Inactive are the retired
  ("cancelled") equivalents** and do **not** participate in the conflict (they free
  the identity). This is documented in the module + the test.
- `find_canonical_conflict(...)` returns `{name, status, shop}` of an existing LIVE
  policy sharing the canonical identity, excluding self. Normalizes platform in
  Python so legacy NULL platforms still compare.

Enforcement: a new controller guard `EC Price Policy._guard_canonical_identity()` runs
inside `validate()` (so it fires on **create/update Save AND on the Draft/Paused →
Active transition**, since both call `doc.save()`). On conflict it `frappe.throw`s a
business-friendly **"Duplicate Price Policy"** error naming the existing policy + its
status (and noting if the existing row is shop-specific) and telling the user to edit
that policy instead of creating another. It never deletes or merges any row.

Behaviour:
- same brand/platform/SKU, **different shop** → conflict (rejected).
- same brand/platform/SKU, one shop empty → conflict (rejected).
- same brand/platform, **different SKU** → allowed.
- brand/platform **empty-SKU fallback vs SKU-specific** → allowed (distinct).
- editing the **same** policy → no self-conflict (excluded by name).
- Cancelled equivalents (Expired/Inactive) → excluded; do not block a new policy.

Frontend: on a conflict the existing RC5/RC6-2 toggle path catches the throw, keeps
the switch OFF, and shows the exact backend error (the error names the existing
policy). The create/edit drawer surfaces the same error via its toast. No silent
auto-merge happens (the old auto-terminalize step only runs *after* a successful
save, so a canonical conflict is rejected before it).

### Read-only duplicate diagnostic

- `policy_scope.canonical_duplicate_groups(brands=None)` — groups LIVE policies by
  canonical key and returns every key with 2+ members (name/status/shop/...), for
  manual cleanup. Pure read; never mutates.
- API: `api_policies.canonical_duplicates(brand=None)` (whitelisted, brand-scoped) —
  returns `{groups, group_count, total_rows}`.

## 2. In-place status toggle (no full table reload)

### Root cause

`togglePolicyStatus` called the full `load()` after every successful transition,
rebuilding the whole table (losing scroll position, re-running the query, flicker).

### Fix (`frontend/build_alert_pages.py`, PAGE2)

`togglePolicyStatus` now updates **only the clicked row**:
- a per-name guard (`S.toggling[name]`) blocks rapid double-clicks / duplicate
  transitions; the switch is disabled while pending.
- the switch is snapped back to the current truth until the backend confirms (never
  shows the new state optimistically).
- on **success**: update the in-memory `S.rows[i].status`, the switch `checked` +
  `data-status` + `title`, the visible `.al-switch-tx` label (`statusLabel`), and
  recompute the switch's enabled state from caps — **no `load()`**, so scroll +
  filters are preserved. KPI/coverage counts refresh in the background
  (`loadMissing()` / `loadCoverageSummary()` — neither rebuilds the policy table).
- on **failure**: restore the switch + label to the old status, re-enable, and toast
  the exact backend error (a conflict therefore keeps the switch OFF with the precise
  message).

The change-event handler is wired once (no duplicate handlers); the guard prevents
duplicate in-flight transitions.

## 3. Files changed

Backend (`ecentric_workspace`):
- `ecentric_workspace/alerts/services/policy_scope.py` — `canonical_key`,
  `LIVE_STATUSES`, `find_canonical_conflict`, `canonical_duplicate_groups`.
- `ecentric_workspace/alerts/doctype/ec_price_policy/ec_price_policy.py` —
  `_guard_canonical_identity()` called from `validate()`.
- `ecentric_workspace/alerts/api_policies.py` — `canonical_duplicates` diagnostic
  endpoint.
- `ecentric_workspace/alerts/tests/test_canonical_identity.py` — **new** regression.

Frontend (`ALERT_CENTER`):
- `frontend/build_alert_pages.py` — PAGE2 `togglePolicyStatus` (in-place) + RC6-2
  in-builder asserts.
- `frontend/alert_*.html` — regenerated git-ignored artifacts.

## 4. Tests & validation

Backend (frappe-free, ran in sandbox): `test_canonical_identity` — **Ran 12 tests,
OK**. Covers canonical key (shop ignored / SKU normalized / empty-SKU fallback /
legacy item target), conflict (different shop, empty shop, different SKU allowed,
fallback-vs-SKU allowed, self-edit allowed, retired/Expired+Inactive excluded,
Draft/Paused live), and the duplicate diagnostic (groups only true canonical dups;
empty when none). `py_compile` OK for `policy_scope.py`, `api_policies.py`,
`ec_price_policy.py`. (Full activation-conflict path runs under `bench run-tests` on
the owner's site; the logic is exercised here at the `policy_scope` level the
controller delegates to.)

Frontend (built from a faithful reconstruction; the Windows build is authoritative):
`py_compile` OK; 5-page build OK; **all assert suites pass** (M2c, M2/M2b, M2d incl.
**RC6-2: toggle does not call `load()`, has the `S.toggling` guard, updates the
in-memory row + visible label in place, refreshes counts in the background**, M3, M4,
G1, module-shell, nav). `node --check` 5/5 JS_OK; duplicate-DOM-id audit 5/5 NONE.
All prior RC4/RC5 behaviour remains intact (every prior assert still green); repo
pages regenerated.

## 5. Existing production duplicates — manual cleanup required

**Yes.** The guard prevents **new** canonical duplicates and the renderer/resolver
are resilient, but it does **not** retroactively change existing rows (no silent
delete/merge, per the brief). Any pre-existing live duplicates (e.g. the FES-VN /
TikTok / P02056 shop-empty + shop-specific pair) remain until manually reconciled.

Recommended cleanup:
1. Run the diagnostic: `api_policies.canonical_duplicates` (optionally per brand) to
   list every canonical key with 2+ live members (names, statuses, shop).
2. For each group, keep ONE policy (the intended one) and retire the others by setting
   their status to **Inactive** (or **Expired**) — which removes them from the
   canonical conflict per the lifecycle contract — or delete the obsolete shop-specific
   rows if confirmed redundant. This is an explicit operator decision; nothing is
   auto-changed.
3. After cleanup, editing/activating the remaining policy will pass the guard.

## 6. Proposed commit commands (owner runs on Windows; do NOT merge/deploy)

Backend:
```powershell
cd C:\dev\ecentric_workspace
python -m py_compile ecentric_workspace\alerts\services\policy_scope.py ecentric_workspace\alerts\doctype\ec_price_policy\ec_price_policy.py ecentric_workspace\alerts\api_policies.py
# bench --site <dev-site> run-tests --module ecentric_workspace.alerts.tests.test_canonical_identity
git add ecentric_workspace\alerts\services\policy_scope.py ecentric_workspace\alerts\doctype\ec_price_policy\ec_price_policy.py ecentric_workspace\alerts\api_policies.py ecentric_workspace\alerts\tests\test_canonical_identity.py
git commit -m "Alerts RC6: enforce canonical Price Policy identity (brand+platform+seller_sku, Shop ignored) on save+activation + read-only duplicate diagnostic, with tests"
```

Frontend:
```powershell
cd C:\dev\ALERT_CENTER
python -m py_compile frontend\build_alert_pages.py
git add frontend\build_alert_pages.py 71_RC6_CANONICAL_IDENTITY.md
git status   # confirm NO generated frontend\*.html staged
git commit -m "Alert UI RC6: in-place Price Setup status toggle (no full table reload)"
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
```

**Not committed, not merged, not deployed.**

---

## 7. RC6 corrections (2026-06-16) — edge cases

Three corrections after review; all backend (no frontend source change this round).

1. **ERP Item removed from the canonical key.** `canonical_key` is now exactly
   `(brand, platform, normalized seller_sku)` — signature `(brand, platform,
   seller_sku)`, no `item` parameter. The legacy `item` no longer participates, so two
   empty-SKU rows are the SAME brand/platform fallback identity even if their stored
   Item differs (they now correctly conflict). `find_canonical_conflict` and
   `canonical_duplicate_groups` no longer read/compare `item`.

2. **Retiring duplicates stays possible.** The status gate is centralized in
   `policy_scope.canonical_guard_conflict(status, ...)` (the controller delegates to
   it): uniqueness is enforced ONLY when the target status is LIVE (Draft/Active/
   Paused). Saving a row to a retired status (Inactive/Expired/any non-live) is
   allowed, so an operator can retire one of two existing duplicates. Self-edit
   exclusion (by name) is preserved.

3. **Diagnostic permission scope hardened.** `canonical_duplicate_groups` now returns
   `[]` for an empty brand list (never a full-table scan), so the brand-scoped
   `api_policies.canonical_duplicates` (which passes the caller's accessible brands,
   or a single brand gated by `require_brand_access`) can never leak cross-brand
   duplicate data to a user without access.

### Files changed (corrections)
- `ecentric_workspace/alerts/services/policy_scope.py` — `canonical_key` (no item),
  `find_canonical_conflict` (no item), new `canonical_guard_conflict` (status gate),
  `canonical_duplicate_groups` (no item + empty-brands guard).
- `ecentric_workspace/alerts/doctype/ec_price_policy/ec_price_policy.py` — guard now
  calls `canonical_guard_conflict`; error text drops the item fallback.
- `ecentric_workspace/alerts/tests/test_canonical_identity.py` — rewritten: no-item
  identity (empty-SKU+different-Item conflicts), retire-gate (Inactive/Expired
  allowed, live duplicate still blocked, surviving-row edit allowed, self-edit
  excluded), empty-brand-scope returns [] without querying.

`api_policies.py` was NOT changed in the corrections (its existing brand-scoping plus
the helper's empty-brands guard cover point 3). No frontend change in the corrections.

### Re-validation (corrections)
- `test_canonical_identity` — **Ran 19 tests, OK**.
- `test_policy_validation` — **Ran 17 tests, OK**.
- `py_compile` OK: `policy_scope.py`, `ec_price_policy.py`, `api_policies.py`.
- Frontend full 5-page build — all 8 assert suites pass (incl. M2d toggle in-place);
  `node --check` 5/5 JS_OK; duplicate-id 5/5 NONE; toggle proof (no `load()`, guard,
  in-memory row + label update) True; repo pages regenerated.

**Still not committed, not merged, not deployed.**
