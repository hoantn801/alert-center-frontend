# G1.1 Gate — Real Omisell Golden Capture (FES-VN / P02056)

Date: 2026-06-08 · Status: **Backend G1.1 (component-based) implemented in `C:\dev\ecentric_workspace`, COMMIT HELD. This capture is the gate before commit/deploy.** Read-only to Omisell; no stock write; DS1 locked.

The current `tests/golden/omisell_order_detail.json` is a **sanitized placeholder** shaped from the docs. We must confirm the mapping against ONE real order before finalizing fields and committing.

---

## Step 1 — Capture (owner runs on Windows; read-only to Omisell)

Find a real **Omisell order number** that contains SKU **P02056** with seller/platform voucher components (Omisell dashboard, or the `reference`/order number on a P02056 alert in `/alerts`). `pull_one_order` needs the order number, not the SKU.

```powershell
cd "C:\Users\admin\NextCommerce\Data - Documents\General\ERP Website\ALERT_CENTER\deploy"
.\capture_golden_order.ps1 -OrderNumber "<omisell_order_number>"
```
The script: calls `pull_one_order(brand=FES-VN, omisell_order_number=..., capture_golden=1)` (GET + idempotent Frappe ingest; returns the **sanitized** payload), saves `golden_capture_<order>.json`, and auto-prints, per line item: **every field name+value**, the arithmetic check, and a per-unit hint. Share the saved JSON back.

> Note: `pull_one_order` ingests the order into Frappe (idempotent) and, under the *current* (pre-G1.1, seller-funded) engine, may raise an alert — that's expected and harmless. No Omisell write, no stock write.

---

## Step 2 — Confirm the 7 mapping questions (from the dump)

1. **Field names** for: product-level seller discount, seller/shop voucher, platform discount, platform voucher. (Expected `discount_seller`, `voucher_seller`, `discount_platform`, `voucher_platform`.)
2. **`discounted_price == original_price − (the four)`?** The script prints `arithmetic OK` or `MISMATCH`. A mismatch ⇒ an extra discount layer exists.
3. **Extra layers?** Scan the per-line field dump for anything like `coin`, `point`, `shipping`, `subsidy`, `campaign`, `payment_discount`, `discount_*`, `voucher_*` beyond the four. If present, we add candidate fields/flags for them.
4. **Per-unit vs line-total?** The script prints `discounted_price × qty` vs order `transaction_amount`. If `Σ(discounted_price × qty) == transaction_amount`, the item prices/discounts are **per-unit** (our current assumption). If not, they're line totals and we divide by qty.
5. **Reliable final customer-paid item price?** Is `discounted_price` truly the customer-checkout price (so `use_customer_paid_if_available` could map to it)?

---

## Step 3 — Only after the golden confirms

1. **Finalize component fields** — if extra layers exist, add `*_amount` audit fields + `include_*` flags for them (and candidates in `pricing.evaluate_components`); if per-unit assumption is wrong, switch to line-total division. Re-run pure tests.
2. **Commit G1.1 backend** from Windows on `alerts-g1-1-evidence-price-basis` (the 12-file add list is in report §9; new files: 2 DocTypes + test_phase_g1_1) → PR → merge.
3. **FC deploy WITH migrate** (creates EC Alert Occurrence + EC Brand Alert Config; adds the granular audit columns).
4. **Create EC Brand Alert Config** for **FES-VN** and **LOF-VN** with the relevant components enabled (customer-checkout = all four `include_*` ON):
   `api_brands.set_brand_alert_config(brand, flags={include_seller_discount:1, include_seller_voucher:1, include_platform_discount:1, include_platform_voucher:1})` (or tick them in Desk).
5. **Verify P02056 below-min occurrence** — re-pull the P02056 order; expect a `below_min` **Case** with `occurrence_count ≥ 1`, a new **Occurrence** with the price breakdown (RSP − components = effective ≈ the customer-checkout price < 250k), `price_components_used` listing the included layers; re-pull = no dup; another P02056 order line = +1 occurrence.

---

## Why hold

Committing before the real capture risks (a) wrong field names, (b) missing an extra discount layer (so effective_check_price is too high and violations are missed — the exact P02056 bug), (c) wrong per-unit/line-total handling. The capture is cheap (one read-only call) and removes all three risks. Holding per your instruction.
