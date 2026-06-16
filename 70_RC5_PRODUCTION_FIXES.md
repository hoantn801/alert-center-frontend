# RC5 — Production logic fixes (Price Policy validation, Price Setup lifecycle, legacy Shop, Rules override)

Date: 2026-06-16. Scope: the five RC5 items only (one minimal backend compatibility
fix + frontend UX corrections). **Not committed, not merged, not deployed.** Two
repos touched: backend `ecentric_workspace`, frontend `ALERT_CENTER`
(`frontend/build_alert_pages.py`, single builder). Generated `frontend/*.html` are
git-ignored build artifacts. DS1 stays closed; no real stock lock is introduced.

---

## 1. Backend root cause and fix (Price Policy legacy threshold validation)

**Symptom.** Saving / activating a Price Setup policy failed with
`High-alert % (high_alert_percent) must be > 0 and <= 100`, even though the RC4 form
no longer submits that field.

**Root cause (inspected, not guessed).** The category is **validation** — not API
payload handling, not worker lookup. The chain:

- `alerts/services/policy_validation.py :: validate_policy_values` is the single
  validator used by every write path (the EC Price Policy controller `validate()`,
  `api_policies.save_policy`, `api_policies.set_policy_status`, and the CSV import).
- `_present(v)` treats `0` as *present* (it only rejects `None` / empty string), so a
  legacy/default stored `high_alert_percent = 0` hit the range check `0 < raw <= 100`
  → `0 < 0` is false → the throw. `api_policies.save_policy` loads the existing doc
  and only overwrites the fields present in the incoming payload (`for k in EDITABLE:
  if k in data`), so an omitted `high_alert_percent` keeps its stored `0` and the
  controller re-validates it on `doc.save()`.
- The old `require_complete=True` (Active) branch ALSO *required* both percents, so a
  policy carrying only price facts could never be activated from the new form.

**Authoritative threshold source confirmed.** `alerts/services/rule_overlay.py` +
`alerts/services/rules.py` show the **Rules overlay is authoritative**: an Active EC
Alert Rule overrides the policy thresholds, and the engine has safe fallbacks when
the policy has none (`severe_pct or DEFAULT_SEVERE_DROP_PERCENT`; `high_pct` is
optional and only fires when `> 0`). A `0` does nothing in evaluation. So the policy
does **not** need these fields populated.

**Smallest safe fix (validation relaxation + normalization).** In
`validate_policy_values` the two percent fields are now treated as **legacy
fallbacks, never required** (not even on Active), a `0`/blank value is treated as
**unset and ignored**, and a **positive** value is still range-checked (so `150`/`-5`
are still rejected). `min_price` remains required on Active. No silent 30/70 default
is introduced; no schema change; no permission change; legacy stored values are
neither cleared nor overwritten (the form simply never sends them).

Files: `ecentric_workspace/alerts/services/policy_validation.py` (validator + module
docstring). The controller, `save_policy`, `set_policy_status`, and the CSV path all
inherit the fix because they share this one validator.

## 2. Frontend — Price Setup lifecycle moved to the table (no drawer buttons)

`frontend/build_alert_pages.py` (PAGE2):

- The drawer's Activate/Pause/Set-Draft buttons + the More menu (`pl-life`,
  `pl-more`, `pl-st-draft`) are removed. The drawer now contains only the fields +
  **Save / Cancel** (`pl-save` / `pl-cancel`).
- A per-row **Status switch** (`statusToggle` → `<input class="pl-tog">` styled as
  `al-switch`) sits in the table **immediately after Brand** (header order Brand →
  Status → Platform). ON == Active.
- The switch reflects **backend truth only**: on flip it snaps back to the current
  status and disables itself (`cb.checked=(cur==="Active");cb.disabled=true`), calls
  `api_policies.set_policy_status` (turning ON → `Active`, OFF → `Paused`), and only a
  **successful reload** renders the new state. A conflict / validation failure keeps
  the prior status and shows the **exact business error** via the toast
  (`A.toast(e.message)`). It never shows ON unless the transition succeeded.
- Activate needs activate rights, Pause needs manage rights; otherwise the switch is
  disabled. A new saved policy is Draft (switch OFF).

## 3. Legacy Shop handling (removed from the normal flow, value preserved)

`frontend/build_alert_pages.py` (PAGE2):

- The editable Shop input is removed. Normal scope is **Brand / Platform / Seller
  SKU**. `e-shop` is kept as a **hidden** input only (drives the live scope preview)
  and `shop` is **removed from the submitted `FIELDS`**, so `save_policy` never sends
  it → the backend preserves the stored value untouched (no silent clear).
- When editing a policy that already has a shop, it is shown **read-only** as legacy
  metadata (`#e-shop-legacy` / `#e-shop-legacy-val`). No existing shop-specific data
  is altered; a real change to those records would require an explicit migration
  decision (not done here).

## 4. Rules override — root cause and fix (state machine + backend dedup)

**Symptoms.** (A) saving a Shopee override reported success but the row still showed
*inherited*; (B) after “Bỏ tùy chỉnh”, re-adding the override could not be saved.

**Root cause (inspected).** `api_rules.save_rule` had **no identity lookup**: with no
`name` it always created a NEW `EC Alert Rule`, and the doctype autonames
`EC-AR-{#####}` with **no uniqueness** on `(brand, rule_code, platform, shop,
seller_sku, item)`. So:
- (B) “Bỏ tùy chỉnh” pauses the override; re-adding created a **duplicate** row
  (Paused + a new Draft) of the same scope, and the paused one was left paused.
- (A) with two rows of the same scope, the renderer and the resolver could pick
  different rows → the override appeared inherited. The frontend also did not exclude
  Paused overrides from resolution.

**Backend fix (smallest safe).** `api_rules.save_rule` now **finds-or-updates by
scope identity** (`_find_rule_by_identity`: brand + rule_code + platform + normalized
shop/seller_sku/item) when no `name` is given, so a create can never duplicate an
existing (incl. Paused) row. If the matched row was **Paused**, editing it **resumes
it to Draft** (re-approval; KAMs draft, Lead/SM activate) so it is no longer ignored
by the resolver. No schema/permission change. File:
`ecentric_workspace/alerts/api_rules.py`.

**Frontend fix — explicit per-platform state machine** (`frontend/build_alert_pages.py`,
PAGE3):
- **Inherited** state: read-only `Kế thừa X%`, the only action is **Thêm tùy chỉnh**,
  there is **no Save button** and no editable input.
- **Override (editing/active)** state: editable threshold input labelled **Tùy
  chỉnh**, actions **Lưu** + **Bỏ tùy chỉnh**.
- **After Save** (`savePf`): waits for backend success, clears the client editing
  flag, **reloads canonical rule data** (`reloadRules`) and the row renders as an
  override with the saved value.
- **After “Bỏ tùy chỉnh”** (`rmPf`): pauses the override (or cancels an unsaved edit),
  reloads, and the row renders **inherited**; **Thêm tùy chỉnh** works again and the
  next Save resumes/updates the paused record via the backend find-or-update.
- The frontend resolver now **excludes Paused** (`if(r.status==="Paused")return;`),
  and the renderer prefers the **non-paused** row when legacy duplicates exist, so the
  renderer and resolver never disagree. Backend remains the evaluation source of
  truth; the frontend resolver is preview/test only.

## 5. Rules full-width layout

Each behaviour now uses a **full-width grid** (`.ru-beh-head` = name | All-platforms
cell) and each platform override row is a full-width grid (`.ru-ovrow` = Platform |
value/input | actions, with `.ru-mid` / `.ru-acts`). The empty right gutter is gone;
the expanded platform customization spans the available width. Still no drawer;
compact and aligned.

## 6. Files changed

Backend (`ecentric_workspace`):
- `ecentric_workspace/alerts/services/policy_validation.py` — validator relaxation +
  docstring.
- `ecentric_workspace/alerts/api_rules.py` — `save_rule` find-or-update by identity +
  resume-paused; new `_find_rule_by_identity` / `_norm` helpers.
- `ecentric_workspace/alerts/tests/test_policy_validation.py` — updated to the RC5
  contract + new legacy-threshold regression class.
- `ecentric_workspace/alerts/tests/test_rule_identity.py` — **new** dedup regression
  (self-stubs frappe; runs frappe-free).

Frontend (`ALERT_CENTER`):
- `frontend/build_alert_pages.py` — PAGE2 (lifecycle switch + Shop removal) and PAGE3
  (override state machine + full-width layout) + in-builder asserts.
- `frontend/alert_*.html` (5) — regenerated git-ignored artifacts.

No permission, scheduler, or doctype-schema change in either repo.

## 7. Tests and validation

Backend (frappe-free, ran in the sandbox):
- `test_policy_validation` — **Ran 17 tests, OK**. Covers: create without thresholds
  (Draft + Active), edit legacy `high_alert_percent=0`, edit legacy
  `severe_drop_percent=0`, activate a valid policy (only `min_price`), existing valid
  legacy values still accepted, positive out-of-range still rejected.
- `test_rule_identity` — **Ran 7 tests, OK**. Covers the identity match (platform
  override vs shop/SKU exception, paused match, brand-default `All`, none-when-empty),
  so no duplicate rule is created.
- `py_compile` OK for `policy_validation.py` and `api_rules.py`.

Frontend (built from a faithful reconstruction because the sandbox mount truncates
the ~190 KB builder; the Windows build is authoritative):
- `py_compile` OK; full 5-page build OK.
- **All assert suites pass**: M2c, M2/M2b, **M2d (lifecycle switch in table after
  Brand + switch-reflects-truth + no drawer lifecycle + Shop hidden/not-submitted +
  legacy display)**, **M3 (RC5-4 state machine: `data-add-pf`/`addPf`, inherited has
  no save, resolver excludes Paused, dedup prefers non-paused, reload-after-save; +
  RC5-5 full-width grid)**, M4, G1, module-shell, nav/terminology.
- `node --check` 5/5 JS_OK; duplicate-DOM-id audit 5/5 NONE.
- Grep proofs on the generated pages: `pl-tog`=1, `togglePolicyStatus`=1,
  `id="pl-life"`=0, editable shop input=0, hidden shop=1, `data-add-pf`=1, `addPf`=1,
  resolver-excludes-paused=1, `.ru-ovrow{display:grid`=1, `.ru-beh-head{display:grid`=1.
- All prior RC4 behaviour (ECharts, Alert drawer, inline Rules write, Omisell label,
  etc.) remains intact (all RC4 asserts still green).

## 8. Proposed commit commands (owner runs on Windows; do NOT merge or deploy)

Backend repo:

```powershell
cd C:\dev\ecentric_workspace
python -m py_compile ecentric_workspace\alerts\services\policy_validation.py ecentric_workspace\alerts\api_rules.py
# optional: bench --site <dev-site> run-tests --module ecentric_workspace.alerts.tests.test_policy_validation
#           bench --site <dev-site> run-tests --module ecentric_workspace.alerts.tests.test_rule_identity
git add ecentric_workspace\alerts\services\policy_validation.py ecentric_workspace\alerts\api_rules.py ecentric_workspace\alerts\tests\test_policy_validation.py ecentric_workspace\alerts\tests\test_rule_identity.py
git commit -m "Alerts RC5: Price Policy legacy-threshold validation relaxation + rule save-by-identity dedup (resume paused), with regression tests"
```

Frontend repo:

```powershell
cd C:\dev\ALERT_CENTER
python -m py_compile frontend\build_alert_pages.py
git add frontend\build_alert_pages.py 70_RC5_PRODUCTION_FIXES.md
git status   # confirm NO generated frontend\*.html staged
git commit -m "Alert UI RC5: Price Setup status switch in table + Shop removed from normal flow (legacy preserved); Rules override state machine + full-width layout"
# rebuild git-ignored pages locally:
python frontend\build_alert_pages.py deploy\backups\home_20260608_154510\main_section_html.bak.html frontend
```

**Not committed, not merged, not deployed.**

## 9. Follow-ups / notes

- Existing duplicate `EC Alert Rule` rows from before this fix (if any) are not
  cleaned up here — the backend now prevents NEW duplicates, and the renderer is
  resilient to old ones, but a one-time cleanup of pre-existing duplicates is a
  separate data-migration decision.
- Pre-existing shop-specific policies keep their shop; converting/migrating them is a
  separate explicit decision (not done in RC5).
