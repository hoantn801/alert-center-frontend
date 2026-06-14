# Alert Center — Phase G1.1 Local Implementation Report
## Alert Evidence & Price Basis

Date: 2026-06-08 · Status: **BACKEND IMPLEMENTED in `C:\dev\ecentric_workspace` (branch `alerts-g1-1-evidence-price-basis`, from main `ef00732`). COMMIT HELD pending a real golden-payload capture (per your instruction). Frontend = Drop 2 (pending).** Read-only to Omisell; no stock write; DS1 locked; schedulers/hooks/tasks/PM untouched.

> **R2 UPDATE (component-based price basis).** Price basis is no longer a fixed enum — it is now **per-brand component include-flags** (your latest direction). `EC Brand Alert Config` fields: `include_seller_discount`, `include_seller_voucher`, `include_platform_discount`, `include_platform_voucher`, `use_customer_paid_if_available` (defaults 1/1/0/0/0 = legacy seller-funded). `effective_check_price = RSP − [included seller_discount] − [included seller_voucher] − [included platform_discount] − [included platform_voucher]` (optionally overridden by a reliable customer-paid unit price). Per-line component AMOUNTS are stored separately for audit (`rsp_price`, `seller_discount_amount`, `seller_voucher_amount`, `platform_discount_amount`, `platform_voucher_amount`, `effective_check_price`, `price_components_used`) on both Order Item and Occurrence. The normalizer now keeps the four Omisell components separate (they were summed before). **Confirmed via the golden file that Omisell item prices/discounts are PER-UNIT** (`original − the four = discounted_price` per unit), so RSP and components are used as-is (only `customer_paid_price`, a line total, is divided by qty). Validated: **54/54 pure tests pass** (G1.1 19, G1 19, rules_pure 16); all 7 changed Python files `py_compile` clean; all 5 DocType JSONs parse. Examples §3. The enum (`price_eval_basis`, `evaluate_price`, `seller_funded_price`/`platform_included_price`/`price_basis_used`) is fully removed — no stale references remain.

> Environment note: the old OneDrive repo reverted in-progress edits (sync-down clobber). Per your decision the repo was moved to `C:\dev\ecentric_workspace` (outside OneDrive) and G1.1 backend was redone there. The bash sandbox mount of `C:\dev` reads some freshly-written files with a lag, so a few in-sandbox `py_compile` checks reported false truncation; the **host files were verified complete/correct via direct reads**, and the pure price-basis + dedupe logic was validated in an isolated `/tmp` harness (13/13). Full `bench run-tests` is the owner-side gate.

---

## 1. Files changed (all under `C:\dev\ecentric_workspace\ecentric_workspace\alerts\`)

**New DocTypes (2):**
- `doctype/ec_alert_occurrence/` (`.json` + `.py` + `__init__.py`) — per-order-line evidence; immutable; UNIQUE `dedupe_key`; SM-only DocPerm.
- `doctype/ec_brand_alert_config/` (`.json` + `.py` + `__init__.py`) — `brand` (unique) + `price_eval_basis`; SM-only.

**DocType field additions (3):**
- `ec_alert` (Case): `+sec_evidence` section, `occurrence_count`, `first_seen_at`, `last_seen_at`, `worst_gap_percent`, `effective_check_price`, `price_basis_used`.
- `ec_marketplace_order_item`: `seller_funded_price`, `platform_included_price`, `effective_check_price`, `price_basis_used` (and `unit_check_price` relabelled legacy alias).
- `ec_alert_rule`: `severe_drop_percent`, `high_alert_percent`.

**Services / API (edited):**
- `services/pricing.py` — `+PRICE_BASES`, `price_candidates()`, `evaluate_price(line, basis)` (legacy `compute_unit_check_price` untouched).
- `services/dedupe_keys.py` — `+occurrence_key()`.
- `services/rule_overlay.py` — `find_rules` reads new rule fields; `overlay_params` prefers `severe_drop_percent`/`high_alert_percent` over legacy `threshold_percent`.
- `services/alert_engine.py` — price branch uses `evaluate_price(basis)`, writes audit fields to the order line, and routes to the new Case+Occurrence path (`_brand_price_basis`, `_record_price_violation`, `_find_or_create_case`, `_bump_case`).
- `api_alerts.py` — `+bulk_set_status(names, new_status, note)`, `+alert_occurrences(alert, ...)`, rollup fields added to `LIST_FIELDS`.
- `api_brands.py` — `+get_brand_alert_config(brand)`, `+set_brand_alert_config(brand, price_eval_basis)`.
- `tests/test_phase_g1_1.py` — new test module.

No `hooks.py`/`tasks.py`/scheduler/PM change. No Frappe-native DocType touched. No new role/DocPerm.

---

## 2. Schema / migration impact

**Migrate REQUIRED.** Creates `EC Alert Occurrence` + `EC Brand Alert Config` tables and adds the new columns to `EC Alert`, `EC Marketplace Order Item`, `EC Alert Rule`. All additive — no column drops, no data backfill. Existing rows keep their values (e.g. an old Policy's `severe_drop_percent`/`high_alert_percent` stay as the deprecated fallback). `EC Brand Alert Config` is empty after migrate ⇒ every brand defaults to `seller_funded` ⇒ **zero behavior change until a brand opts in**. Per approved decision, after deploy: create `EC Brand Alert Config` for **FES-VN** and **LOF-VN** with `price_eval_basis = seller_plus_platform`.

---

## 3. Pricing basis logic (`pricing.evaluate_price`)

Per-unit candidates from the raw line: `seller_funded = list − seller_discount`; `platform_included = list − seller_discount − platform_discount`; `customer_paid = customer_paid_price / qty` (when present); `payload_unit` (Omisell `discounted_price`, last-resort). The brand's `price_eval_basis` picks one with a deterministic fallback chain, and `price_basis_used` records any fallback. `strictest` = lowest available candidate. Quantities >1 are divided per unit. Validated 13/13 in `/tmp`, incl. the **P02056 case**: list 300k, seller −40k, platform −14k → `seller_plus_platform` = **246,000** (< 250k min → violation) while `seller_funded` = 260,000 (would miss it). This is the root-cause fix.

---

## 4. Case / Occurrence dedupe logic (`alert_engine`)

Per violating order line: compute `occurrence_key = omisell|{order}|{line}|occ|{rule}`. If an `EC Alert Occurrence` with that key exists → **no-op** (re-pull never duplicates; a resolved Case is never reopened). Else: find the open Case (`EC Alert` where brand+seller_sku+rule_code and status ∈ {Open, In Review}); if none, create one (Case key `case|{brand}|{sku}|{rule}|{first_order}|{first_line}`, UNIQUE). Insert the Occurrence linked to the Case, then bump the Case rollup (`occurrence_count += 1`, `last_seen_at`, `worst_gap_percent`, `effective_check_price`, `price_basis_used`; `first_seen_at` on create). A different violating order line → new Occurrence + count increments, so KAM sees **how many orders were below min**. Lock actions only fire on a newly-created occurrence. Validated: occurrence key is per-order-line, stable on re-pull, distinct across orders/lines, and distinct from the legacy `price_alert_key`.

---

## 5. API endpoint contracts (all scoped; writes are status-only)

- `api_alerts.bulk_set_status(names, new_status∈{In Review,Resolved,Ignored}, note?)` → `{ok[], denied[], failed[]}`; per-row `can_handle_alert`; note required for Resolved/Ignored; one bad row never aborts the batch.
- `api_alerts.alert_occurrences(alert, start=0, page_len=50)` → `{rows[OCC_FIELDS], total}`; brand-scoped to the Case's brand.
- `api_alerts.list_alerts` now also returns `occurrence_count`, `effective_check_price`, `price_basis_used`, `first/last_seen_at`, `worst_gap_percent`.
- `api_brands.get_brand_alert_config(brand)` → `{price_eval_basis, configured, options}` (brand-scoped read).
- `api_brands.set_brand_alert_config(brand, price_eval_basis)` → upsert; `can_manage_policy` (manager-level).

No Omisell calls added anywhere.

---

## 6. UI changes — Drop 2 (NOT yet built)

Frontend (`ALERT_CENTER/frontend/build_alert_pages.py`, still in OneDrive) is deferred to **Drop 2**: `/alerts` Case list gets a checkbox column + select-all + bulk bar (Resolve/Ignore/In Review selected, optional Pause SKU) + an `occurrence_count` column; the Case drawer gets the Occurrences evidence table (order no./time/status, sku/name, list/seller/platform, effective_check_price, min/baseline at check, price_basis_used, rule result); `/alerts/policies` hides `high_alert_percent`/`severe_drop_percent`; `/alerts/rules` adds the two threshold inputs. Backend endpoints for all of this are live in Drop 1. Recommend moving `ALERT_CENTER/` out of OneDrive too (same hazard) before building Drop 2, or building it via the proven `/tmp` rebuild path.

---

## 7. Test results

- **Pure logic: 13/13 PASS** (`/tmp` harness): price-basis matrix (seller_funded / seller_plus_platform / customer_paid + fallback / strictest / per-unit / unresolved / legacy 2-tuple) and occurrence-key dedupe (per-order-line, stable, distinct).
- `services/rule_overlay.py` and `api_brands.py` `py_compile` clean in-sandbox.
- `tests/test_phase_g1_1.py` written (price basis + occurrence key + rule-owns-thresholds + GOLDEN identity) — run via `bench run-tests --module ecentric_workspace.alerts.tests.test_phase_g1_1` on the site (engine Case/Occurrence DB behavior is bench-only).
- Host files verified complete via direct reads (pricing 118 ln, alert_engine 320 ln, dedupe 68 ln, ec_alert.json well-formed).

---

## 8. No-write confirmation

No Omisell write (engine never calls the client; ingestion writes Frappe only). No stock/buffer/inventory write; DS1 stays locked (Occurrence/Case carry dry-run lock recommendation only; lock matrix unchanged). `hooks.py`/`tasks.py`/schedulers = 0 diff. No PM files. No new role/DocPerm. GOLDEN identity preserved: with no `EC Brand Alert Config` row and no Active Rule, behavior is unchanged (default basis = legacy seller-funded; `rule_overlay` returns params unchanged).

---

## 9. Deploy / rollback

**Drop 1 (backend, this report) — owner commits from Windows** (the host repo `C:\dev\ecentric_workspace` has the correct files; do NOT rely on the sandbox bash mount for git):
```
cd C:\dev\ecentric_workspace
git checkout alerts-g1-1-evidence-price-basis      # already created
git add ecentric_workspace/alerts/doctype/ec_alert_occurrence ^
        ecentric_workspace/alerts/doctype/ec_brand_alert_config ^
        ecentric_workspace/alerts/doctype/ec_alert/ec_alert.json ^
        ecentric_workspace/alerts/doctype/ec_marketplace_order_item/ec_marketplace_order_item.json ^
        ecentric_workspace/alerts/doctype/ec_alert_rule/ec_alert_rule.json ^
        ecentric_workspace/alerts/services/pricing.py ^
        ecentric_workspace/alerts/services/dedupe_keys.py ^
        ecentric_workspace/alerts/services/rule_overlay.py ^
        ecentric_workspace/alerts/services/alert_engine.py ^
        ecentric_workspace/alerts/api_alerts.py ^
        ecentric_workspace/alerts/api_brands.py ^
        ecentric_workspace/alerts/tests/test_phase_g1_1.py
git status            # confirm ONLY these files (ignore CRLF-only drift on others; don't add them)
git commit -m "Alert Center G1.1: Case/Occurrence evidence model + configurable price basis + Policy/Rule threshold cleanup"
git push -u origin alerts-g1-1-evidence-price-basis
```
→ PR → merge → **FC deploy WITH migrate**. Post-deploy: create `EC Brand Alert Config` for FES-VN + LOF-VN = `seller_plus_platform`; run `bench run-tests --module ...test_phase_g1_1`.

**Rollback:** revert PR → FC deploy. New DocTypes/fields are additive (leave in place, harmless); engine reverts to per-line `EC Alert` + seller-funded basis; no data unwind. Instant softening without revert: delete the `EC Brand Alert Config` rows ⇒ all brands fall back to seller_funded.

---

## 10. P02056 verification plan (post-deploy, FES-VN `seller_plus_platform`)

1. Set FES-VN `EC Brand Alert Config.price_eval_basis = seller_plus_platform`.
2. Re-pull (or wait for) a P02056 order whose customer-checkout price ≈ 246k (list − seller − platform). Expected: a **Case** (EC Alert, rule `below_min`) appears/updates with `occurrence_count ≥ 1`, `effective_check_price ≈ 246000`, `price_basis_used = seller_plus_platform`; one **Occurrence** row created.
3. **Re-pull the same order** → no duplicate Occurrence (same `order|line|rule` key); Case count unchanged.
4. **A different P02056 order line** below min → a new Occurrence; Case `occurrence_count` increments → answers "how many orders below min".
5. Drawer (Drop 2) shows every order's evidence + which price + whether platform voucher was included.
6. Regression: a brand with no `EC Brand Alert Config` still evaluates seller-funded (GOLDEN identity); FES-VN/LOF-VN schedulers + G1 Integration Health unaffected.
