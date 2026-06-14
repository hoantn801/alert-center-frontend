# Alert Center — Phase G1.1 Pre-Code Proposal
## Alert Evidence & Price Basis

Date: 2026-06-08 · Status: **PRE-CODE — awaiting approval. No code written.** Runs before G2. Read-only to Omisell; no stock write; DS1 locked; schedulers + G1 Integration Health untouched.

---

## 0. Root-cause clarification (read from code first)

Two separate things were conflated in the P02056 report; the fix differs for each.

**A. Dedupe is NOT too broad for price rules.** `alert_engine` already keys price-rule alerts per order line: `price_alert_key = "omisell|{external_order_id}|{external_line_id}|price|{rule_code}"` (`services/dedupe_keys.py`). So a *genuinely new order* already creates a *new* `EC Alert`; only `missing_policy`/`missing_brand_mapping` use the daily SKU-level key. The "one snapshot per SKU" feeling comes from those master-data alerts, not from `below_min`.

**B. The 246K miss is almost certainly the PRICE BASIS.** `services/pricing.compute_unit_check_price` resolves the check price in this order: (1) `customer_paid_price/qty`, (2) payload `unit_check_price`, (3) `list_price − seller_discount` (platform discount deliberately NOT subtracted). The Omisell normalizer sets `customer_paid_price = None` and `unit_check_price = discounted_price` (the **seller-funded** discounted unit price; `platform_discount = discount_platform + voucher_platform` is carried but never subtracted). So if a customer checked out at ~246K because of a **platform voucher**, the engine still evaluated the **seller-funded** price (~≥250K) → no `below_min` → no alert. That is correct to the *current* rule ("platform-funded subsidy is not a seller pricing decision") but **wrong for the business need** ("a customer could buy below min"). G1.1 makes the basis explicit + configurable.

So G1.1 = (1) make per-order-line violations first-class **evidence** (Case + Occurrence) and visibly countable, (2) make the **price basis** configurable + fully audited, (3) bulk handling, (4) evidence drawer, (5) Policy/Rule field-ownership cleanup.

---

## 1. Alert granularity — Case + Occurrence (recommended)

**Two-tier model** (the user's "better model"), additive:

- **`EC Alert` = the Case** (the actionable unit KAM works): one per `brand + seller_sku + rule_code` while open. Holds a rollup: `occurrence_count`, `first_seen_at`, `last_seen_at`, `worst_gap_percent`, plus the existing min/baseline snapshot. Case dedupe stays coarse so the worklist isn't 500 rows.
- **`EC Alert Occurrence` = NEW DocType, per violating order line** (the evidence; append-only, immutable): one row per `external_order_id + external_line_id + rule_code`. Links to its Case (`Link EC Alert`). This is where "how many orders below min" is counted and every order line is visible.

Behavior in `alert_engine.check_order_log`:
1. line violates a rule → compute the occurrence `dedupe_key = "omisell|{order}|{line}|occ|{rule}"`.
2. **Occurrence**: insert if key absent (re-pull of the same line = no-op; a different order = new occurrence). Immutable.
3. **Case**: upsert the `EC Alert` for `brand+sku+rule` (open) — create if none open, else bump `occurrence_count`, `last_seen_at`, `worst_gap_percent`. Case is NOT recreated per order (keeps the worklist sane) but its count grows so KAM sees scale.

Why this satisfies the requirement: KAM sees **N orders below min** (Case.occurrence_count) and can drill into every line (Occurrences); re-pull never duplicates; a new order line always adds visible evidence.

> **Alternative (short-term, smaller):** keep only `EC Alert` and make EVERY violating order line its own `EC Alert` (drop the SKU rollup). Since `price_alert_key` is already per-line, this is mostly a *display* change (don't collapse in the list) + a SKU "group by" view. It's less work but makes the worklist noisy and has no native count. **Recommendation: do the two-tier Case+Occurrence** — it's the durable model for compliance evidence and scales for G2/G3. (Spam is acceptable per your note, but occurrences-as-evidence + case-as-worklist gives the count *without* burying the worklist.)

New DocType `EC Alert Occurrence` (custom=0, System-Manager-only DocPerm, service-layer access like the others). Fields in §3. Requires **migrate**.

---

## 2. Bulk handling (on the /alerts Cases list)

- Checkbox column + "select all on page"; a sticky bulk bar appears when ≥1 selected.
- Actions: **Resolve selected**, **Ignore selected**, **In Review selected** (note optional/required matching the single-row rules), and optional **Pause SKU from selected** (creates one `EC Automation Pause` per distinct brand+SKU via the existing `api_pauses` path — dry-run, DS1 untouched).
- New endpoint `api_alerts.bulk_set_status(names, new_status, note=None)` — `require_alert_center_access`, per-row `require_brand_access`/`can_handle_alert`, atomic-ish loop with per-row result; reuses the existing single `set_status` logic. Bulk pause reuses `api_pauses.create_pause`. No new permission.

---

## 3. Price basis configuration + audit fields

**Config (brand-level).** Add `price_eval_basis` (Select) — recommended home: a new tiny **`EC Brand Alert Config`** (one per brand: `brand`, `price_eval_basis`, room for future tuning) so EC Brand Integration Settings stays integration/credentials only (clean module boundary). *Lighter alternative:* a single `price_eval_basis` field on `EC Brand Integration Settings` (SM-only, no new DocType). **Recommendation:** new `EC Brand Alert Config` (manager-editable via service layer; falls back to a system default when absent → preserves today's behavior).

`price_eval_basis` options + meaning (all computed per unit):
- **`seller_funded`** (DEFAULT = today's behavior): `list_price − seller_discount`.
- **`seller_plus_platform`**: `list_price − seller_discount − platform_discount`.
- **`customer_paid`**: `customer_paid_price/qty` when reliably present, else deterministic fallback (records the fallback).
- **`strictest`**: `min(` of all available candidates `)` — lowest price, most likely to breach min (strictest compliance).

`pricing.compute_unit_check_price(line, basis)` is refactored to compute **all candidates** and return the chosen one + a basis tag + the candidate set. Stored on **both** the Order Item and the Occurrence/Case (audit, never recomputed retroactively — snapshot rule from §30 holds):

| Field | On |
|---|---|
| `price_basis_used` (Data) | Order Item + Occurrence + Alert |
| `effective_check_price` (Currency) | Order Item + Occurrence + Alert (= the price actually compared to min) |
| `seller_funded_price` (Currency) | Order Item + Occurrence |
| `platform_included_price` (Currency) | Order Item + Occurrence |
| `customer_paid_price` (Currency) | already on Order Item; copied to Occurrence |
| `list_price`, `seller_discount`, `platform_discount` (Currency) | already on Order Item; copied to Occurrence for immutable audit |

(Existing `unit_check_price` stays as the legacy field = `effective_check_price` for back-compat.) Changing the basis affects only **future** evaluations; existing occurrences keep their recorded basis.

---

## 4. Alert drawer evidence

Case drawer gains an **Occurrences table** (newest first, paginated/capped) with exactly the requested columns: Omisell order number · order time · current order status · seller_sku / product_name · list_price · seller_discount · platform_discount · effective_check_price · min_price_at_check · baseline_price_at_check · price_basis_used · rule result. Plus the Case rollup header (count, first/last seen, worst gap). New read endpoint `api_alerts.alert_occurrences(alert, start, page_len)` (brand-scoped). Same `.al-*` styling.

---

## 5. Price Policy vs Rule cleanup

Field ownership made unambiguous:

- **EC Price Policy = price master data only:** `min_price`, `reference_price` (benchmark), `target_price` (listed/RSP), `enable_stock_safety_lock`, `stock_lock_duration_minutes`, validity, status. **Hide/deprecate `high_alert_percent` + `severe_drop_percent` in the Policy UI.**
- **EC Alert Rule = severity/action thresholds:** owns `severe_drop_percent`, `high_alert_percent` (add these two as explicit rule fields alongside the existing `threshold_percent`), `severity_override`, `recommend_stock_lock`.
- **Engine resolution (no behavior break):** `rule_overlay` prefers an Active Rule → else the **deprecated** Policy percentages (kept as hidden fallback) → else **system defaults** (constants). So hiding them from the Policy UI changes nothing until Rules are authored. Migration: optionally seed a default brand Rule from existing Policy percentages (separate, reversible step). Full column removal deferred to a later phase once Rules are populated.

This removes the "two places set thresholds" confusion while keeping the GOLDEN identity (no Active rule ⇒ unchanged results).

---

## 6. DocTypes & schema (summary)

- **NEW** `EC Alert Occurrence` (per-line evidence; immutable; SM-only DocPerm).
- **NEW** `EC Brand Alert Config` (brand, price_eval_basis; manager via service layer) — or 1 field on BIS (alternative).
- **EC Alert** +rollup fields (`occurrence_count`, `first_seen_at`, `last_seen_at`, `worst_gap_percent`, `price_basis_used`, `effective_check_price`).
- **EC Marketplace Order Item** +audit fields (`seller_funded_price`, `platform_included_price`, `price_basis_used`, `effective_check_price`).
- **EC Price Policy** — no new fields; `high_alert_percent`/`severe_drop_percent` hidden (Property Setter / UI), retained as deprecated fallback.
- **EC Alert Rule** +`severe_drop_percent`, `high_alert_percent`.

All custom=0, additive; **migrate required** (new DocType + Custom Fields). No DocPerm/role widening; access stays service-layer. No Frappe-native DocType touched.

---

## 7. API endpoints (all read/scoped unless noted)

- `api_alerts.bulk_set_status(names, new_status, note=None)` — write to EC Alert status only (existing capability), per-row brand-scoped.
- `api_alerts.alert_occurrences(alert, start=0, page_len=50)` — read evidence rows for a Case.
- `api_brands`/`api_policies` extended trivially to read/write `price_eval_basis` on the config (manager-gated); SM for BIS-field variant.
- Engine internal: `pricing.compute_unit_check_price(line, basis)` (pure, +basis), `alert_engine` Case+Occurrence write path. No Omisell calls added.

---

## 8. UI structure

`/alerts` list: checkbox column + bulk bar (§2); rows now = Cases with an `occurrence_count` column ("N orders"). Case drawer: rollup header + Occurrences evidence table (§4). `/alerts/policies`: hide the two threshold fields, add a help note pointing to Rules. `/alerts/rules`: add severe-drop% / high-alert% inputs. Optional: surface `price_eval_basis` per brand on `/alerts/integration-health` (read-only display) or a small config control. Same `.al-*` components; ASCII-only builder pages.

---

## 9. Permission model

Unchanged service-layer: `require_alert_center_access` + per-brand `can_handle_alert` (bulk status), `can_manage_policy` (price basis config = manager-level), occurrences read = `require_brand_access`. No new role, no DocPerm widening. Occurrence/Config DocTypes ship SM-only DocPerm like the rest.

---

## 10. Constraints / no-write confirmation

No Omisell write (engine never calls the client; ingestion writes Frappe only). No stock/buffer/inventory write; DS1 stays locked (Occurrence/Case carry dry-run lock recommendation only). Schedulers (FES-VN/LOF-VN) and `tasks.py`/`hooks.py` untouched. G1 Integration Health unaffected (new fields are additive; `api_brands` unchanged except optional price_basis display). No PM files.

---

## 11. Deploy / rollback

Two drops. **Drop 1 (backend + migrate):** new DocType(s) + Custom Fields + engine/pricing/dedupe changes + new endpoints; PR (files-changed gate); FC deploy **WITH migrate** (creates `EC Alert Occurrence`, adds fields). **Drop 2 (frontend):** rebuild + `deploy_alert_pages.ps1` (alerts list bulk + drawer evidence; policies hide thresholds; rules add %). Rollback: revert PR → FC deploy; new DocType/fields are additive (left in place, harmless) — engine reverts to per-line `EC Alert` behavior; no data unwind. Price basis defaults to `seller_funded` (today's behavior) if config absent, so deploy is non-disruptive.

---

## 12. Verification (P02056)

With brand `price_eval_basis` set so the customer-checkout price is evaluated (e.g. `customer_paid` or `strictest`):
1. Order at ~246K, policy min 250K → a `below_min` **Occurrence** is created and a **Case** appears/updates with `occurrence_count≥1`, `effective_check_price≈246000`, `price_basis_used` recorded.
2. **Re-pull the same order** → no duplicate occurrence (same `order|line|rule` key); Case count unchanged.
3. **A different order line** for P02056 below min → a new Occurrence; Case `occurrence_count` increments → KAM sees how many orders were below min.
4. Drawer shows the full per-order evidence (list/seller/platform/effective/min/baseline/basis/rule).
5. Regression: with default `seller_funded` basis, GOLDEN identity holds (no behavior change for brands that don't opt into a stricter basis); FES-VN/LOF-VN schedulers + G1 health unaffected.

Unit tests: pricing basis matrix (seller_funded/seller_plus_platform/customer_paid/strictest + fallbacks), occurrence dedupe (re-pull vs new order), Case rollup increment, bulk_set_status scoping, rule-owns-thresholds overlay identity.

---

## Open questions for approval

1. **Model:** confirm two-tier **Case + Occurrence** (recommended) vs short-term per-line-only `EC Alert`.
2. **Price basis home:** new `EC Brand Alert Config` DocType (recommended) vs single field on `EC Brand Integration Settings`.
3. **Default basis:** keep `seller_funded` as global default (safe, no behavior change) and let each brand opt into `customer_paid`/`strictest`? Recommended yes. For FES-VN specifically — set which basis now?
4. **Customer-paid reliability:** Omisell currently sends no `customer_paid_price` (it's None; `discounted_price` = seller-funded). To evaluate true customer-checkout price we likely need `seller_plus_platform` (we DO have platform_discount) as the practical "customer paid" proxy until a confirmed customer-paid field exists. OK to treat `seller_plus_platform` as the customer-checkout basis for now?
5. **Threshold migration:** seed default Rules from existing Policy percentages, or just hide Policy fields and rely on system defaults until Rules are authored?
